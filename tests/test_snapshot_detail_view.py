"""Tests for snapshot detail view widgets."""

from __future__ import annotations

from datetime import datetime

import pytest
from textual.widgets import DataTable, Static

from tablesleuth.models.iceberg import (
    IcebergSnapshotDetails,
    IcebergSnapshotInfo,
    PartitionSpecInfo,
    SchemaField,
    SchemaInfo,
)
from tablesleuth.tui.views.snapshot_detail_view import (
    SnapshotDeletesView,
    SnapshotFilesView,
    SnapshotOverviewView,
    SnapshotPropertiesView,
    SnapshotSchemaView,
)


@pytest.fixture
def mock_snapshot() -> IcebergSnapshotInfo:
    """Create a mock snapshot."""
    return IcebergSnapshotInfo(
        snapshot_id=12345,
        parent_snapshot_id=12344,
        timestamp_ms=int(datetime(2024, 1, 15, 10, 30).timestamp() * 1000),
        operation="append",
        summary={"added-records": "1000", "added-files": "10"},
        manifest_list="s3://bucket/manifests/snap-12345.avro",
        schema_id=1,
        total_records=5000,
        total_data_files=50,
        total_delete_files=5,
        total_size_bytes=1024 * 1024 * 100,  # 100 MB
        position_deletes=100,
        equality_deletes=0,
    )


@pytest.fixture
def mock_snapshot_no_deletes() -> IcebergSnapshotInfo:
    """Create a mock snapshot without deletes."""
    return IcebergSnapshotInfo(
        snapshot_id=12346,
        parent_snapshot_id=12345,
        timestamp_ms=int(datetime(2024, 1, 16, 10, 30).timestamp() * 1000),
        operation="append",
        summary={"added-records": "500"},
        manifest_list="s3://bucket/manifests/snap-12346.avro",
        schema_id=1,
        total_records=5500,
        total_data_files=55,
        total_delete_files=0,
        total_size_bytes=1024 * 1024 * 110,  # 110 MB
        position_deletes=0,
        equality_deletes=0,
    )


@pytest.fixture
def mock_schema() -> SchemaInfo:
    """Create a mock schema."""
    return SchemaInfo(
        schema_id=1,
        fields=[
            SchemaField(
                field_id=1,
                name="id",
                field_type="long",
                required=True,
                doc="Primary key",
            ),
            SchemaField(
                field_id=2,
                name="name",
                field_type="string",
                required=False,
                doc="User name",
            ),
            SchemaField(
                field_id=3,
                name="created_at",
                field_type="timestamp",
                required=True,
                doc=None,
            ),
        ],
    )


@pytest.fixture
def mock_snapshot_details(
    mock_snapshot: IcebergSnapshotInfo, mock_schema: SchemaInfo
) -> IcebergSnapshotDetails:
    """Create mock snapshot details."""
    return IcebergSnapshotDetails(
        snapshot_info=mock_snapshot,
        data_files=[
            {
                "file_path": "s3://bucket/data/file1.parquet",
                "file_size_bytes": 1024 * 1024,  # 1 MB
                "record_count": 1000,
            },
            {
                "file_path": "s3://bucket/data/file2.parquet",
                "file_size_bytes": 2 * 1024 * 1024,  # 2 MB
                "record_count": 2000,
            },
        ],
        delete_files=[
            {
                "file_path": "s3://bucket/deletes/delete1.parquet",
                "file_size_bytes": 512 * 1024,  # 512 KB
                "record_count": 100,
            }
        ],
        schema=mock_schema,
        partition_spec=PartitionSpecInfo(spec_id=0, fields=[]),
        sort_order=None,
    )


@pytest.fixture
def mock_snapshot_details_no_deletes(
    mock_snapshot_no_deletes: IcebergSnapshotInfo, mock_schema: SchemaInfo
) -> IcebergSnapshotDetails:
    """Create mock snapshot details without delete files."""
    return IcebergSnapshotDetails(
        snapshot_info=mock_snapshot_no_deletes,
        data_files=[
            {
                "file_path": "s3://bucket/data/file3.parquet",
                "file_size_bytes": 1024 * 1024,
                "record_count": 500,
            }
        ],
        delete_files=[],
        schema=mock_schema,
        partition_spec=PartitionSpecInfo(spec_id=0, fields=[]),
        sort_order=None,
    )


class TestSnapshotOverviewView:
    """Tests for SnapshotOverviewView widget."""

    async def test_initialization_without_snapshot(self) -> None:
        """Test SnapshotOverviewView initializes without snapshot."""
        view = SnapshotOverviewView()
        assert view._snapshot is None

    async def test_initialization_with_snapshot(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test SnapshotOverviewView initializes with snapshot."""
        view = SnapshotOverviewView(snapshot=mock_snapshot)
        assert view._snapshot == mock_snapshot

    async def test_update_snapshot(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test updating snapshot displays correct information."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotOverviewView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotOverviewView)
            view.update_snapshot(mock_snapshot)
            await pilot.pause()

            content = view.query_one("#overview-content", Static)
            rendered = str(content.render())

            # Check key information is displayed
            assert "12345" in rendered  # Snapshot ID
            assert "12344" in rendered  # Parent ID
            assert "append" in rendered  # Operation
            assert "5000" in rendered or "5,000" in rendered  # Total records

    async def test_update_snapshot_with_deletes(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test snapshot with deletes shows MOR metrics."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotOverviewView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotOverviewView)
            view.update_snapshot(mock_snapshot)
            await pilot.pause()

            content = view.query_one("#overview-content", Static)
            rendered = str(content.render())

            # Should show MOR metrics
            assert "Merge-on-Read Metrics" in rendered
            assert "Delete Ratio" in rendered
            assert "Read Amplification" in rendered

    async def test_update_snapshot_without_deletes(
        self, mock_snapshot_no_deletes: IcebergSnapshotInfo
    ) -> None:
        """Test snapshot without deletes doesn't show MOR metrics."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotOverviewView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotOverviewView)
            view.update_snapshot(mock_snapshot_no_deletes)
            await pilot.pause()

            content = view.query_one("#overview-content", Static)
            rendered = str(content.render())

            # Should not show MOR metrics
            assert "Merge-on-Read Metrics" not in rendered

    async def test_clear(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test clearing the overview view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotOverviewView(snapshot=mock_snapshot, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotOverviewView)
            view.clear()
            await pilot.pause()

            assert view._snapshot is None
            content = view.query_one("#overview-content", Static)
            rendered = str(content.render())
            assert "Select a snapshot" in rendered

    async def test_format_size(self) -> None:
        """Test size formatting."""
        assert SnapshotOverviewView._format_size(512) == "512.0 B"
        assert SnapshotOverviewView._format_size(1024) == "1.0 KB"
        assert SnapshotOverviewView._format_size(1024 * 1024) == "1.0 MB"
        assert SnapshotOverviewView._format_size(1024 * 1024 * 1024) == "1.0 GB"


class TestSnapshotFilesView:
    """Tests for SnapshotFilesView widget."""

    async def test_initialization_without_details(self) -> None:
        """Test SnapshotFilesView initializes without details."""
        view = SnapshotFilesView()
        assert view._details is None

    async def test_initialization_with_details(
        self, mock_snapshot_details: IcebergSnapshotDetails
    ) -> None:
        """Test SnapshotFilesView initializes with details."""
        view = SnapshotFilesView(details=mock_snapshot_details)
        assert view._details == mock_snapshot_details

    async def test_update_details(self, mock_snapshot_details: IcebergSnapshotDetails) -> None:
        """Test updating details displays files."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotFilesView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotFilesView)
            view.update_details(mock_snapshot_details)
            await pilot.pause()

            table = view.query_one("#files-table", DataTable)
            # Should have 2 data files + 1 delete file = 3 rows
            assert table.row_count == 3

    async def test_update_details_shows_data_and_delete_files(
        self, mock_snapshot_details: IcebergSnapshotDetails
    ) -> None:
        """Test that both data and delete files are shown."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotFilesView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotFilesView)
            view.update_details(mock_snapshot_details)
            await pilot.pause()

            table = view.query_one("#files-table", DataTable)
            # Verify we have the expected number of files
            assert table.row_count == 3  # 2 data + 1 delete

    async def test_clear(self, mock_snapshot_details: IcebergSnapshotDetails) -> None:
        """Test clearing the files view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotFilesView(details=mock_snapshot_details, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotFilesView)
            view.clear()
            await pilot.pause()

            assert view._details is None
            table = view.query_one("#files-table", DataTable)
            assert table.row_count == 0

    async def test_format_size(self) -> None:
        """Test size formatting."""
        assert SnapshotFilesView._format_size(1024) == "1.0 KB"
        assert SnapshotFilesView._format_size(1024 * 1024) == "1.0 MB"


class TestSnapshotSchemaView:
    """Tests for SnapshotSchemaView widget."""

    async def test_initialization_without_schema(self) -> None:
        """Test SnapshotSchemaView initializes without schema."""
        view = SnapshotSchemaView()
        assert view._schema is None

    async def test_initialization_with_schema(self, mock_schema: SchemaInfo) -> None:
        """Test SnapshotSchemaView initializes with schema."""
        view = SnapshotSchemaView(schema=mock_schema)
        assert view._schema == mock_schema

    async def test_update_schema(self, mock_schema: SchemaInfo) -> None:
        """Test updating schema displays fields."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotSchemaView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotSchemaView)
            view.update_schema(mock_schema)
            await pilot.pause()

            table = view.query_one("#schema-table", DataTable)
            # Should have 3 fields
            assert table.row_count == 3

    async def test_update_schema_shows_required_fields(self, mock_schema: SchemaInfo) -> None:
        """Test that required fields are marked."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotSchemaView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotSchemaView)
            view.update_schema(mock_schema)
            await pilot.pause()

            table = view.query_one("#schema-table", DataTable)
            assert table.row_count == 3

    async def test_clear(self, mock_schema: SchemaInfo) -> None:
        """Test clearing the schema view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotSchemaView(schema=mock_schema, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotSchemaView)
            view.clear()
            await pilot.pause()

            assert view._schema is None
            table = view.query_one("#schema-table", DataTable)
            assert table.row_count == 0


class TestSnapshotDeletesView:
    """Tests for SnapshotDeletesView widget."""

    async def test_initialization_without_details(self) -> None:
        """Test SnapshotDeletesView initializes without details."""
        view = SnapshotDeletesView()
        assert view._details is None

    async def test_initialization_with_details(
        self, mock_snapshot_details: IcebergSnapshotDetails
    ) -> None:
        """Test SnapshotDeletesView initializes with details."""
        view = SnapshotDeletesView(details=mock_snapshot_details)
        assert view._details == mock_snapshot_details

    async def test_update_details_with_deletes(
        self, mock_snapshot_details: IcebergSnapshotDetails
    ) -> None:
        """Test updating details with delete files."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotDeletesView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotDeletesView)
            view.update_details(mock_snapshot_details)
            await pilot.pause()

            content = view.query_one("#deletes-content", Static)
            rendered = str(content.render())

            # Should show delete file summary
            assert "Delete Files Summary" in rendered
            assert "Total Delete Files" in rendered
            assert "Merge-on-Read Impact" in rendered

    async def test_update_details_without_deletes(
        self, mock_snapshot_details_no_deletes: IcebergSnapshotDetails
    ) -> None:
        """Test updating details without delete files."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotDeletesView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotDeletesView)
            view.update_details(mock_snapshot_details_no_deletes)
            await pilot.pause()

            content = view.query_one("#deletes-content", Static)
            rendered = str(content.render())

            # Should show "no delete files" message
            assert "No delete files" in rendered

    async def test_clear(self, mock_snapshot_details: IcebergSnapshotDetails) -> None:
        """Test clearing the deletes view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotDeletesView(details=mock_snapshot_details, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotDeletesView)
            view.clear()
            await pilot.pause()

            assert view._details is None
            content = view.query_one("#deletes-content", Static)
            rendered = str(content.render())
            assert "Select a snapshot" in rendered

    async def test_format_size(self) -> None:
        """Test size formatting."""
        assert SnapshotDeletesView._format_size(512 * 1024) == "512.0 KB"


class TestSnapshotPropertiesView:
    """Tests for SnapshotPropertiesView widget."""

    async def test_initialization_without_snapshot(self) -> None:
        """Test SnapshotPropertiesView initializes without snapshot."""
        view = SnapshotPropertiesView()
        assert view._snapshot is None

    async def test_initialization_with_snapshot(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test SnapshotPropertiesView initializes with snapshot."""
        view = SnapshotPropertiesView(snapshot=mock_snapshot)
        assert view._snapshot == mock_snapshot

    async def test_update_snapshot(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test updating snapshot displays properties."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotPropertiesView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotPropertiesView)
            view.update_snapshot(mock_snapshot)
            await pilot.pause()

            table = view.query_one("#properties-table", DataTable)
            # Should have properties from summary
            assert table.row_count == len(mock_snapshot.summary)

    async def test_clear(self, mock_snapshot: IcebergSnapshotInfo) -> None:
        """Test clearing the properties view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotPropertiesView(snapshot=mock_snapshot, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotPropertiesView)
            view.clear()
            await pilot.pause()

            assert view._snapshot is None
            table = view.query_one("#properties-table", DataTable)
            assert table.row_count == 0
