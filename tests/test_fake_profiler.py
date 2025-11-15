from table_sleuth.models import FileRef, SnapshotInfo
from table_sleuth.services.profiling.fake_backend import FakeProfiler


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
