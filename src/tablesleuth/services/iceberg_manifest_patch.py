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
        from urllib.parse import urlparse

        import boto3  # already a project dependency via pyiceberg

        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        s3 = boto3.client("s3")
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        return bytes(body)

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
        logger.warning(
            "Patched delete manifest: lowercased %d file_format field(s)",
            sum(
                1
                for r in records
                if isinstance(r.get("data_file"), dict)
                and r["data_file"].get("file_format") == "parquet"
            ),
        )
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
        orig = record.get("manifest_path", "")  # type: ignore[union-attr]
        if orig in path_map:
            record = dict(record)  # type: ignore[arg-type]
            record["manifest_path"] = path_map[orig]
        records.append(record)  # type: ignore[arg-type]

    out = io.BytesIO()
    fastavro.writer(out, fastavro.parse_schema(schema), records)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Public context manager
# ---------------------------------------------------------------------------


@contextmanager
def patched_iceberg_metadata(
    native_table: Any,  # pyiceberg.table.Table
    snapshot_id: int,
) -> Generator[str, None, None]:  # noqa: UP043
    """Yield a ``file://`` URI for a locally-patched copy of Iceberg snapshot metadata.

    Two problems are corrected:

    1. **DuckDB delete-file format bug** — DuckDB's ``iceberg_scan()`` rejects delete
       manifests whose ``file_format`` is ``'PARQUET'`` (uppercase).  Affected avro
       files are re-encoded with the value lowercased.

    2. **Stale current-snapshot-id** — DuckDB applies delete files based on the
       table's ``current-snapshot-id`` rather than the ``version =>`` argument.
       When comparing an older snapshot against a newer one that introduced deletes,
       the older snapshot would incorrectly inherit those deletes.  The patched
       metadata sets ``current-snapshot-id`` to the target snapshot so DuckDB only
       sees the delete files that belong to that particular snapshot.

    A temporary local ``metadata.json`` is always written (even when no avro
    re-encoding is needed) to carry the corrected ``current-snapshot-id``.

    Args:
        native_table: PyIceberg ``Table`` instance (from ``IcebergTableInfo.native_table``).
        snapshot_id:  Snapshot ID to patch.

    Yields:
        A ``file://`` URI pointing to the patched local ``metadata.json``, suitable
        for passing to ``iceberg_scan(uri, version => snapshot_id)``.
    """
    metadata_location: str = native_table.metadata_location
    logger.debug(
        "patched_iceberg_metadata: metadata_location=%r snapshot_id=%s",
        metadata_location,
        snapshot_id,
    )

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
    logger.debug("patched_iceberg_metadata: manifest_list_uri=%r", manifest_list_uri)

    # Read the manifest-list avro to discover which manifests are DELETE manifests.
    try:
        ml_bytes = _read_bytes(manifest_list_uri)
    except Exception as exc:
        logger.warning("Cannot read manifest-list for patching, using original: %s", exc)
        yield metadata_location
        return

    import fastavro

    ml_reader = fastavro.reader(io.BytesIO(ml_bytes))
    ml_records: list[dict] = list(ml_reader)  # type: ignore[arg-type]

    # Identify DELETE manifests (content == 1 in the manifest-list schema).
    delete_manifest_uris = [r["manifest_path"] for r in ml_records if r.get("content", 0) == 1]

    logger.debug(
        "patched_iceberg_metadata: found %d delete manifest(s): %r",
        len(delete_manifest_uris),
        delete_manifest_uris,
    )

    # Always create a patched metadata copy even when no delete manifests need format
    # fixing.  DuckDB's iceberg_scan() applies delete files based on the table's
    # *current-snapshot-id* rather than on the version specified via ``version =>``.
    # Setting current-snapshot-id to the target snapshot in a local copy ensures
    # DuckDB only sees delete files that belong to that snapshot, preventing older
    # snapshots from inheriting delete records added by a newer current snapshot.
    with tempfile.TemporaryDirectory(prefix="tablesleuth_iceberg_patch_") as tmpdir:
        tmp = Path(tmpdir)
        path_map: dict[str, str] = {}  # original URI → local posix path

        for idx, del_uri in enumerate(delete_manifest_uris):
            try:
                raw = _read_bytes(del_uri)
            except Exception as exc:
                logger.warning("Cannot read delete manifest %r: %s", del_uri, exc)
                continue

            patched = _patch_delete_manifest(raw)
            if patched is raw:
                # No uppercase PARQUET found — no format patch needed for this manifest.
                logger.debug(
                    "patched_iceberg_metadata: delete manifest %r needed no patching", del_uri
                )
                continue

            local_name = f"delete_manifest_{idx}.avro"
            local_path = tmp / local_name
            local_path.write_bytes(patched)
            # Use posix path (no file:// prefix) so DuckDB can open it directly.
            # file:///C:/... URIs get mangled by DuckDB's internal path stripping
            # (file:// stripped → /C:/... which is invalid on Windows).
            local_posix = local_path.as_posix()
            path_map[del_uri] = local_posix
            logger.debug(
                "patched_iceberg_metadata: patched delete manifest %r → %s", del_uri, local_posix
            )

        # Rewrite the manifest-list only when some delete manifests were re-encoded.
        new_ml_posix: str | None = None
        if path_map:
            patched_ml = _rewrite_manifest_list(ml_bytes, path_map)
            ml_path = tmp / "manifest_list.avro"
            ml_path.write_bytes(patched_ml)
            new_ml_posix = ml_path.as_posix()
            logger.debug("patched_iceberg_metadata: rewrote manifest-list → %s", new_ml_posix)
        else:
            logger.debug(
                "patched_iceberg_metadata: %d delete manifest(s) found; none needed format patching",
                len(delete_manifest_uris),
            )

        # Always rewrite the metadata JSON so that:
        #   1. current-snapshot-id points to the target snapshot (not the table's
        #      current HEAD), preventing DuckDB from applying newer delete files.
        #   2. If delete manifests were re-encoded, the manifest-list path is updated.
        patched_meta = json.loads(json.dumps(metadata))  # deep copy
        patched_meta["current-snapshot-id"] = snapshot_id

        if new_ml_posix is not None:
            for snap in patched_meta.get("snapshots", []):
                if snap.get("snapshot-id") == snapshot_id:
                    snap["manifest-list"] = new_ml_posix
                    break

        meta_path = tmp / "metadata.json"
        meta_path.write_text(json.dumps(patched_meta), encoding="utf-8")
        logger.debug(
            "patched_iceberg_metadata: yielding patched metadata URI: %s", meta_path.as_uri()
        )

        yield meta_path.as_uri()
