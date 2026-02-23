"""Patch Iceberg snapshot metadata to work around DuckDB's uppercase file_format bug.

DuckDB's iceberg_scan() rejects delete files whose file_format is stored as 'PARQUET'
(uppercase) in the manifest avro — it only accepts 'parquet' (lowercase).  This module
creates a lightweight, temporary, locally-patched copy of the metadata chain:

    metadata.json   →  patched temp copy (JSON rewrite, trivial)
    manifest-list.avro  →  patched temp copy (avro rewrite via fastavro, redirects
                            delete-manifest paths to temp copies)
    delete manifests    →  fastavro-rewritten temp copies (file_format lowercased,
                            handles null/Snappy/deflate codecs transparently)

Data manifests and all actual data / delete Parquet files are NOT copied or modified;
they are referenced by their original S3 / local paths.

Usage (context manager — cleans up temp files on exit)::

    with patched_iceberg_metadata(native_table, snapshot_id) as meta_uri:
        # meta_uri is a file:// URI pointing to the patched metadata.json
        profiler.register_iceberg_table_with_snapshot("snap_a", meta_uri, snapshot_id)
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_bytes(uri: str) -> bytes:
    """Read raw bytes from a local path, file:// URI, or s3:// URI."""
    if uri.startswith(("s3://", "s3a://")):
        import boto3  # already a project dependency via pyiceberg
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        s3 = boto3.client("s3")
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    # file:// URI or plain local path
    if uri.startswith("file://"):
        # Path.from_uri() handles Windows drive letters correctly:
        # file:///D:/path → D:\path  (available in Python 3.13+)
        return Path.from_uri(uri).read_bytes()

    return Path(uri).read_bytes()


def _patch_file_format_in_record(obj: Any) -> tuple[Any, bool]:
    """Recursively lowercase any file_format == 'PARQUET' field in a deserialized Avro object.

    Handles any nesting depth so it works regardless of whether the manifest uses
    the v1 or v2 Iceberg schema layout (direct record vs union-wrapped struct).

    Returns:
        Tuple of (possibly-modified object, changed_flag).
    """
    if isinstance(obj, dict):
        changed = False
        new_obj: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "file_format" and isinstance(v, str) and v == "PARQUET":
                new_obj[k] = "parquet"
                changed = True
            else:
                new_v, sub_changed = _patch_file_format_in_record(v)
                new_obj[k] = new_v
                if sub_changed:
                    changed = True
        return new_obj, changed
    elif isinstance(obj, list):
        changed = False
        new_list: list[Any] = []
        for item in obj:
            new_item, sub_changed = _patch_file_format_in_record(item)
            new_list.append(new_item)
            if sub_changed:
                changed = True
        return new_list, changed
    else:
        return obj, False


def _patch_delete_manifest(content: bytes) -> bytes:
    """Rewrite a delete manifest avro, lowercasing file_format 'PARQUET' → 'parquet'.

    Uses fastavro for proper Avro round-tripping so it works with null, Snappy,
    and deflate codecs.  Falls back to binary substitution if fastavro fails.

    Returns the original bytes object unchanged if no patching was needed.
    Caller uses identity comparison (patched is content) to detect this.
    """
    import fastavro

    try:
        reader = fastavro.reader(io.BytesIO(content))
        schema = reader.writer_schema
        records: list[dict] = []
        changed = False

        for record in reader:
            new_record, was_changed = _patch_file_format_in_record(record)
            records.append(new_record)
            if was_changed:
                changed = True

        if not changed:
            return content  # Same object — identity check in caller will skip this manifest

        out = io.BytesIO()
        fastavro.writer(out, fastavro.parse_schema(schema), records)
        patched = out.getvalue()
        logger.warning("Patched delete manifest: lowercased %d file_format field(s)", sum(
            1 for r in records
            if isinstance(r.get("data_file"), dict) and r["data_file"].get("file_format") == "parquet"
        ))
        return patched

    except Exception as exc:
        logger.warning("fastavro round-trip failed (%s), falling back to binary patch", exc)
        if b"PARQUET" not in content:
            return content
        return content.replace(b"PARQUET", b"parquet")


def _rewrite_manifest_list(content: bytes, path_map: dict[str, str]) -> bytes:
    """Rewrite a manifest-list avro file, updating manifest_path values per path_map.

    Uses fastavro for proper avro round-tripping (path strings change length so
    binary substitution is not safe here).
    """
    import fastavro

    reader = fastavro.reader(io.BytesIO(content))
    schema = reader.writer_schema
    records: list[dict] = []
    for record in reader:
        orig = record.get("manifest_path", "")
        if orig in path_map:
            record = dict(record)
            record["manifest_path"] = path_map[orig]
        records.append(record)

    out = io.BytesIO()
    fastavro.writer(out, fastavro.parse_schema(schema), records)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Public context manager
# ---------------------------------------------------------------------------

@contextmanager
def patched_iceberg_metadata(
    native_table,  # pyiceberg.table.Table
    snapshot_id: int,
) -> Generator[str, None, None]:
    """Yield a ``file://`` URI for a locally-patched copy of Iceberg snapshot metadata.

    The patched metadata chain resolves the DuckDB iceberg_scan() failure caused by
    delete-file manifests that store ``file_format = 'PARQUET'`` (uppercase).

    If the snapshot has no delete files, or if none of its delete manifests contain
    uppercase PARQUET strings, the original metadata URI is yielded unchanged (no temp
    files are created).

    Args:
        native_table: PyIceberg ``Table`` instance (from ``IcebergTableInfo.native_table``).
        snapshot_id:  Snapshot ID to patch.

    Yields:
        A ``file://`` URI (or the original URI if no patching was needed) suitable
        for passing to ``iceberg_scan(uri, version => snapshot_id)``.
    """
    metadata_location: str = native_table.metadata_location
    logger.warning("patched_iceberg_metadata: metadata_location=%r snapshot_id=%s", metadata_location, snapshot_id)

    # Read the metadata JSON (always local-accessible since IcebergMetadataService
    # already resolved it; for S3 tables PyIceberg caches/fetches it).
    try:
        meta_bytes = _read_bytes(metadata_location)
    except Exception as exc:
        logger.warning("Cannot read metadata for patching, using original: %s", exc)
        yield metadata_location
        return

    metadata: dict = json.loads(meta_bytes)

    # Locate the target snapshot entry.
    target_snap: dict | None = None
    for snap in metadata.get("snapshots", []):
        if snap.get("snapshot-id") == snapshot_id:
            target_snap = snap
            break

    if target_snap is None:
        logger.warning("Snapshot %s not found in metadata; using original", snapshot_id)
        yield metadata_location
        return

    manifest_list_uri: str = target_snap["manifest-list"]
    logger.warning("patched_iceberg_metadata: manifest_list_uri=%r", manifest_list_uri)

    # Read the manifest-list avro to discover which manifests are DELETE manifests.
    try:
        ml_bytes = _read_bytes(manifest_list_uri)
    except Exception as exc:
        logger.warning("Cannot read manifest-list for patching, using original: %s", exc)
        yield metadata_location
        return

    import fastavro

    ml_reader = fastavro.reader(io.BytesIO(ml_bytes))
    ml_records: list[dict] = list(ml_reader)

    # Identify DELETE manifests (content == 1 in the manifest-list schema).
    delete_manifest_uris = [
        r["manifest_path"]
        for r in ml_records
        if r.get("content", 0) == 1
    ]

    logger.warning("patched_iceberg_metadata: found %d delete manifest(s): %r", len(delete_manifest_uris), delete_manifest_uris)

    if not delete_manifest_uris:
        # No delete manifests — iceberg_scan() won't hit the format bug.
        logger.warning("patched_iceberg_metadata: no delete manifests, using original URI")
        yield metadata_location
        return

    with tempfile.TemporaryDirectory(prefix="tablesleuth_iceberg_patch_") as tmpdir:
        tmp = Path(tmpdir)
        path_map: dict[str, str] = {}  # original URI → local file:// URI

        for idx, del_uri in enumerate(delete_manifest_uris):
            try:
                raw = _read_bytes(del_uri)
            except Exception as exc:
                logger.warning("Cannot read delete manifest %r: %s", del_uri, exc)
                continue

            patched = _patch_delete_manifest(raw)
            if patched is raw:
                # No uppercase PARQUET found — no patch needed for this manifest.
                logger.warning("patched_iceberg_metadata: delete manifest %r needed no patching", del_uri)
                continue

            local_name = f"delete_manifest_{idx}.avro"
            local_path = tmp / local_name
            local_path.write_bytes(patched)
            # Use posix path (no file:// prefix) so DuckDB can open it directly.
            # file:///C:/... URIs get mangled by DuckDB's internal path stripping
            # (file:// stripped → /C:/... which is invalid on Windows).
            local_posix = local_path.as_posix()
            path_map[del_uri] = local_posix
            logger.warning("patched_iceberg_metadata: patched %r → %s", del_uri, local_posix)

        if not path_map:
            # All delete manifests were already lowercase — no patch needed.
            logger.warning(
                "patched_iceberg_metadata: %d delete manifest(s) found but none needed patching "
                "(all file_format fields were already lowercase) — using original URI",
                len(delete_manifest_uris),
            )
            yield metadata_location
            return

        # Rewrite the manifest-list to redirect patched delete manifests.
        patched_ml = _rewrite_manifest_list(ml_bytes, path_map)
        ml_path = tmp / "manifest_list.avro"
        ml_path.write_bytes(patched_ml)

        # Rewrite the metadata JSON to redirect this snapshot's manifest-list.
        # Use posix path (no file:// prefix) inside the JSON so DuckDB can open
        # the manifest-list without URI stripping issues on Windows.
        patched_meta = json.loads(json.dumps(metadata))  # deep copy
        for snap in patched_meta.get("snapshots", []):
            if snap.get("snapshot-id") == snapshot_id:
                snap["manifest-list"] = ml_path.as_posix()
                break

        meta_path = tmp / "metadata.json"
        meta_path.write_text(json.dumps(patched_meta), encoding="utf-8")
        logger.warning("patched_iceberg_metadata: yielding patched metadata URI: %s", meta_path.as_uri())

        yield meta_path.as_uri()
