"""Patch Iceberg snapshot metadata to work around DuckDB iceberg_scan() issues.

Three problems are corrected:

1. **Uppercase file_format** — DuckDB's ``iceberg_scan()`` rejects delete files whose
   ``file_format`` is stored as ``'PARQUET'`` (uppercase); it only accepts ``'parquet'``.
   Affected delete manifest avro files are re-encoded with the value lowercased.

2. **Stale current-snapshot-id** — DuckDB applies delete files based on the table's
   ``current-snapshot-id`` rather than the ``version =>`` argument.  The patched
   ``metadata.json`` always sets ``current-snapshot-id`` to the target snapshot.

3. **Relative paths in local tables** — When an Iceberg table lives on the local
   filesystem, manifest paths and data file paths stored in the metadata chain are
   often relative.  DuckDB resolves them from GizmoSQL's working directory, which
   differs from the server's CWD on Windows.  The patched metadata chain rewrites
   all relative paths to absolute posix paths so DuckDB can find them regardless of
   CWD.

This module creates a lightweight, temporary, locally-patched copy of the metadata chain:

    metadata.json        →  patched temp copy (JSON rewrite)
    manifest-list.avro   →  patched temp copy (avro rewrite via fastavro; redirects
                             any re-encoded manifests and resolves relative paths)
    manifests (all)      →  fastavro-rewritten temp copies when needed:
                             - data manifests: relative file_path resolved to absolute
                             - delete manifests: same + file_format lowercased

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


def _is_relative_local_path(path: str) -> bool:
    """Return True if *path* is a relative local filesystem path (not a URI, not absolute).

    S3 URIs, file:// URIs, and absolute OS paths all return False.
    """
    if not path:
        return False
    if path.startswith(("s3://", "s3a://", "gs://", "az://", "abfs://", "file://")):
        return False
    return not Path(path).is_absolute()


def _patch_manifest_record(obj: Any, fix_format: bool) -> tuple[Any, bool]:
    """Recursively patch a deserialized Avro manifest record.

    Two transformations:
    - ``file_path`` fields whose value is a relative local path are resolved to
      absolute posix paths (so DuckDB can open them from any CWD).
    - ``file_format`` fields whose value is ``'PARQUET'`` are lowercased to
      ``'parquet'`` when *fix_format* is True (delete manifests only).

    Returns:
        Tuple of (possibly-modified object, changed_flag).
    """
    if isinstance(obj, dict):
        changed = False
        new_obj: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "file_path" and isinstance(v, str) and _is_relative_local_path(v):
                new_obj[k] = Path(v).resolve().as_posix()
                changed = True
            elif k == "file_format" and fix_format and isinstance(v, str) and v == "PARQUET":
                new_obj[k] = "parquet"
                changed = True
            else:
                new_v, sub_changed = _patch_manifest_record(v, fix_format)
                new_obj[k] = new_v
                if sub_changed:
                    changed = True
        return new_obj, changed
    elif isinstance(obj, list):
        changed = False
        new_list: list[Any] = []
        for item in obj:
            new_item, sub_changed = _patch_manifest_record(item, fix_format)
            new_list.append(new_item)
            if sub_changed:
                changed = True
        return new_list, changed
    else:
        return obj, False


def _patch_manifest(content: bytes, is_delete: bool) -> bytes:
    """Patch a manifest avro file using fastavro round-tripping.

    For data manifests (``is_delete=False``): resolves relative ``file_path`` values.
    For delete manifests (``is_delete=True``): also lowercases ``file_format``.

    Falls back to binary ``b'PARQUET'`` → ``b'parquet'`` substitution for delete
    manifests if fastavro fails (handles most null-codec avro files).

    Returns the original bytes object unchanged if no patching was needed.
    Caller uses identity comparison (``patched is content``) to detect this.
    """
    import fastavro

    try:
        reader = fastavro.reader(io.BytesIO(content))
        schema = reader.writer_schema
        records: list[dict] = []
        changed = False

        for record in reader:
            new_record, was_changed = _patch_manifest_record(record, fix_format=is_delete)
            records.append(new_record)
            if was_changed:
                changed = True

        if not changed:
            return content  # Same object — identity check in caller will skip this manifest

        out = io.BytesIO()
        fastavro.writer(out, fastavro.parse_schema(schema), records)
        return out.getvalue()

    except Exception as exc:
        logger.warning("fastavro round-trip failed (%s), falling back to binary patch", exc)
        if is_delete and b"PARQUET" in content:
            return content.replace(b"PARQUET", b"parquet")
        return content


def _rewrite_manifest_list(content: bytes, path_map: dict[str, str]) -> bytes:
    """Rewrite a manifest-list avro file, updating manifest_path values.

    Two transformations are applied:
    - Paths in *path_map* are replaced with their mapped values (patched manifests).
    - Relative local paths not in path_map are resolved to absolute posix paths so
      DuckDB can open them when the manifest-list lives in a temp directory.

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
        elif _is_relative_local_path(orig):
            record = dict(record)  # type: ignore[arg-type]
            record["manifest_path"] = Path(orig).resolve().as_posix()
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

    See module docstring for the three problems corrected.

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

    # Read the metadata JSON.
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

    # Read the manifest-list avro.
    try:
        ml_bytes = _read_bytes(manifest_list_uri)
    except Exception as exc:
        logger.warning("Cannot read manifest-list for patching, using original: %s", exc)
        yield metadata_location
        return

    import fastavro

    ml_reader = fastavro.reader(io.BytesIO(ml_bytes))
    ml_records: list[dict] = list(ml_reader)  # type: ignore[arg-type]

    logger.debug("patched_iceberg_metadata: manifest-list has %d entries", len(ml_records))

    with tempfile.TemporaryDirectory(prefix="tablesleuth_iceberg_patch_") as tmpdir:
        tmp = Path(tmpdir)
        # Maps original manifest URI → local posix path for any re-encoded manifest.
        path_map: dict[str, str] = {}

        # Process ALL manifests — both data (content=0) and delete (content=1).
        # Data manifests may have relative file_path values; delete manifests may
        # additionally have uppercase file_format values.
        for idx, ml_record in enumerate(ml_records):
            manifest_uri: str = ml_record.get("manifest_path", "")
            is_delete = ml_record.get("content", 0) == 1

            try:
                raw = _read_bytes(manifest_uri)
            except Exception as exc:
                logger.warning("Cannot read manifest %r: %s", manifest_uri, exc)
                continue

            patched = _patch_manifest(raw, is_delete=is_delete)
            if patched is raw:
                logger.debug(
                    "patched_iceberg_metadata: manifest %r needed no patching", manifest_uri
                )
                continue

            local_name = f"manifest_{idx}.avro"
            local_path = tmp / local_name
            local_path.write_bytes(patched)
            # Use posix path (no file:// prefix) so DuckDB can open it directly.
            local_posix = local_path.as_posix()
            path_map[manifest_uri] = local_posix
            logger.debug(
                "patched_iceberg_metadata: patched manifest %r → %s", manifest_uri, local_posix
            )

        # Rewrite the manifest-list when: (a) some manifests were re-encoded, OR
        # (b) it contains relative manifest_path values (Windows local tables).
        needs_ml_rewrite = bool(path_map) or any(
            _is_relative_local_path(r.get("manifest_path", "")) for r in ml_records
        )

        new_ml_posix: str | None = None
        if needs_ml_rewrite:
            patched_ml = _rewrite_manifest_list(ml_bytes, path_map)
            ml_path = tmp / "manifest_list.avro"
            ml_path.write_bytes(patched_ml)
            new_ml_posix = ml_path.as_posix()
            logger.debug("patched_iceberg_metadata: rewrote manifest-list → %s", new_ml_posix)

        # Always rewrite metadata.json to:
        #   1. Set current-snapshot-id to target snapshot (prevents DuckDB from
        #      applying delete files from newer snapshots to this one).
        #   2. Point this snapshot's manifest-list to the patched copy (if any).
        #   3. Resolve relative manifest-list paths for all other snapshots.
        patched_meta = json.loads(json.dumps(metadata))  # deep copy
        patched_meta["current-snapshot-id"] = snapshot_id

        for snap in patched_meta.get("snapshots", []):
            ml = snap.get("manifest-list", "")
            if snap.get("snapshot-id") == snapshot_id and new_ml_posix is not None:
                snap["manifest-list"] = new_ml_posix
            elif _is_relative_local_path(ml):
                snap["manifest-list"] = Path(ml).resolve().as_posix()

        meta_path = tmp / "metadata.json"
        meta_path.write_text(json.dumps(patched_meta), encoding="utf-8")
        logger.debug(
            "patched_iceberg_metadata: yielding patched metadata URI: %s", meta_path.as_uri()
        )

        yield meta_path.as_uri()
