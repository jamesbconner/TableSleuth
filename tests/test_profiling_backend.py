"""Tests for profiling backend interface and implementations."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tablesleuth.models import FileRef, SnapshotInfo
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.services.profiling.backend_base import ProfilingBackend


# Create a simple fake profiler for testing
class FakeProfiler(ProfilingBackend):
    """Fake profiling backend for testing."""

    def __init__(self) -> None:
        self.registered_views: dict[str, list[str]] = {}
        self.profile_calls: list[tuple[str, str]] = []

    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Register snapshot view."""
        view_name = f"snap_{snapshot.snapshot_id}"
        self.registered_views[view_name] = [f.path for f in snapshot.data_files]
        return view_name

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Register file paths for profiling."""
        if not file_paths:
            raise ValueError("file_paths cannot be empty")

        if view_name is None:
            view_name = f"test_view_{len(self.registered_views)}"

        self.registered_views[view_name] = file_paths
        return view_name

    def profile_single_column(
        self, view_name: str, column: str, filters: str | None = None
    ) -> ColumnProfile:
        """Profile a single column."""
        self.profile_calls.append((view_name, column))

        return ColumnProfile(
            column=column,
            row_count=100,
            non_null_count=95,
            null_count=5,
            distinct_count=50,
            min_value=1,
            max_value=100,
        )

    def profile_columns(
        self, view_name: str, columns: Sequence[str], filters: str | None = None
    ) -> dict[str, ColumnProfile]:
        """Profile multiple columns."""
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}


class TestProfilingBackend:
    """Tests for ProfilingBackend interface."""

    @pytest.fixture
    def fake_profiler(self) -> FakeProfiler:
        """Create a FakeProfiler instance."""
        return FakeProfiler()

    @pytest.fixture
    def sample_snapshot(self) -> SnapshotInfo:
        """Create a sample SnapshotInfo."""
        return SnapshotInfo(
            snapshot_id=1,
            parent_id=None,
            timestamp_ms=1234567890,
            operation="append",
            summary={},
            data_files=[
                FileRef(
                    path="/path/to/file1.parquet",
                    file_size_bytes=1024,
                    record_count=100,
                    source="iceberg",
                )
            ],
            delete_files=[],
        )

    def test_fake_profiler_initialization(self, fake_profiler: FakeProfiler) -> None:
        """Test that FakeProfiler can be initialized."""
        assert fake_profiler is not None

    def test_register_snapshot_view(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test register_snapshot_view interface."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)

        assert view_name is not None
        assert isinstance(view_name, str)
        assert len(view_name) > 0

    def test_register_file_view(self, fake_profiler: FakeProfiler) -> None:
        """Test register_file_view interface."""
        file_paths = ["/path/to/file1.parquet", "/path/to/file2.parquet"]

        view_name = fake_profiler.register_file_view(file_paths)

        assert view_name is not None
        assert isinstance(view_name, str)
        assert len(view_name) > 0

    def test_register_file_view_with_custom_name(
        self,
        fake_profiler: FakeProfiler,
    ) -> None:
        """Test register_file_view with custom view name."""
        file_paths = ["/path/to/file.parquet"]
        custom_name = "my_custom_view"

        view_name = fake_profiler.register_file_view(file_paths, custom_name)

        assert view_name == custom_name

    def test_register_file_view_empty_list(self, fake_profiler: FakeProfiler) -> None:
        """Test that empty file list raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            fake_profiler.register_file_view([])

    def test_profile_single_column(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profile_single_column interface."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)

        profile = fake_profiler.profile_single_column(view_name, "test_column")

        assert profile is not None
        assert isinstance(profile, ColumnProfile)
        assert profile.column == "test_column"
        assert profile.row_count >= 0
        assert profile.non_null_count >= 0
        assert profile.null_count >= 0

    def test_profile_single_column_with_filters(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profile_single_column with filters."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)

        profile = fake_profiler.profile_single_column(
            view_name, "test_column", filters="value > 10"
        )

        assert profile is not None
        assert profile.column == "test_column"

    def test_profile_columns(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profile_columns interface."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)
        columns = ["col1", "col2", "col3"]

        profiles = fake_profiler.profile_columns(view_name, columns)

        assert profiles is not None
        assert isinstance(profiles, dict)
        assert len(profiles) == 3

        for col in columns:
            assert col in profiles
            assert isinstance(profiles[col], ColumnProfile)
            assert profiles[col].column == col

    def test_profile_columns_with_filters(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profile_columns with filters."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)
        columns = ["col1", "col2"]

        profiles = fake_profiler.profile_columns(view_name, columns, filters="value > 10")

        assert len(profiles) == 2

    def test_profile_query_performance_not_implemented(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test that performance profiling raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="does not support"):
            fake_profiler.profile_query_performance(sample_snapshot, "SELECT COUNT(*)")

    def test_column_profile_structure(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test that ColumnProfile has correct structure."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)
        profile = fake_profiler.profile_single_column(view_name, "test_column")

        # Verify all required fields
        assert hasattr(profile, "column")
        assert hasattr(profile, "row_count")
        assert hasattr(profile, "non_null_count")
        assert hasattr(profile, "null_count")
        assert hasattr(profile, "distinct_count")
        assert hasattr(profile, "min_value")
        assert hasattr(profile, "max_value")

    def test_profile_consistency(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test that profile counts are consistent."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)
        profile = fake_profiler.profile_single_column(view_name, "test_column")

        # row_count should equal non_null_count + null_count
        assert profile.row_count == profile.non_null_count + profile.null_count

    def test_multiple_views(self, fake_profiler: FakeProfiler) -> None:
        """Test registering multiple views."""
        view1 = fake_profiler.register_file_view(["/path/to/file1.parquet"])
        view2 = fake_profiler.register_file_view(["/path/to/file2.parquet"])

        # Views should have different names
        assert view1 != view2

    def test_profile_multiple_columns_separately(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profiling multiple columns separately."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)

        profile1 = fake_profiler.profile_single_column(view_name, "col1")
        profile2 = fake_profiler.profile_single_column(view_name, "col2")

        assert profile1.column == "col1"
        assert profile2.column == "col2"

    def test_register_file_view_single_file(
        self,
        fake_profiler: FakeProfiler,
    ) -> None:
        """Test registering a single file."""
        view_name = fake_profiler.register_file_view(["/path/to/file.parquet"])

        assert view_name is not None

    def test_register_file_view_multiple_files(
        self,
        fake_profiler: FakeProfiler,
    ) -> None:
        """Test registering multiple files."""
        files = [
            "/path/to/file1.parquet",
            "/path/to/file2.parquet",
            "/path/to/file3.parquet",
        ]

        view_name = fake_profiler.register_file_view(files)

        assert view_name is not None

    def test_profiling_backend_is_protocol(self) -> None:
        """Test that ProfilingBackend is a Protocol."""
        # This test verifies the interface exists
        assert ProfilingBackend is not None

    def test_fake_profiler_implements_protocol(
        self,
        fake_profiler: FakeProfiler,
    ) -> None:
        """Test that FakeProfiler implements ProfilingBackend protocol."""
        # Verify all required methods exist
        assert hasattr(fake_profiler, "register_snapshot_view")
        assert hasattr(fake_profiler, "register_file_view")
        assert hasattr(fake_profiler, "profile_single_column")
        assert hasattr(fake_profiler, "profile_columns")
        assert hasattr(fake_profiler, "profile_query_performance")

    def test_profile_with_none_filters(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test profiling with None filters."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)

        profile = fake_profiler.profile_single_column(view_name, "test_column", filters=None)

        assert profile is not None

    def test_column_profile_optional_fields(
        self,
        fake_profiler: FakeProfiler,
        sample_snapshot: SnapshotInfo,
    ) -> None:
        """Test that optional fields can be None."""
        view_name = fake_profiler.register_snapshot_view(sample_snapshot)
        profile = fake_profiler.profile_single_column(view_name, "test_column")

        # These fields can be None
        # Just verify no exceptions are raised
        _ = profile.distinct_count
        _ = profile.min_value
        _ = profile.max_value
