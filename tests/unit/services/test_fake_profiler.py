import pytest

from tablesleuth.models import FileRef, SnapshotInfo
from tablesleuth.services.profiling.fake_backend import FakeProfiler


def test_fake_profiler_profiles() -> None:
    snapshot = SnapshotInfo(
        snapshot_id=1,
        parent_id=None,
        timestamp_ms=0,
        operation="append",
        summary={},
        data_files=[],
        delete_files=[],
    )
    backend = FakeProfiler()
    view = backend.register_snapshot_view(snapshot)
    profile = backend.profile_single_column(view, "col")
    assert profile.column == "col"
    assert profile.row_count == 100


def test_fake_profiler_performance_not_implemented() -> None:
    """Test that performance profiling raises NotImplementedError by default."""
    snapshot = SnapshotInfo(
        snapshot_id=1,
        parent_id=None,
        timestamp_ms=0,
        operation="append",
        summary={},
        data_files=[],
        delete_files=[],
    )
    backend = FakeProfiler()

    with pytest.raises(NotImplementedError, match="does not support performance profiling"):
        backend.profile_query_performance(snapshot, "SELECT COUNT(*)")
