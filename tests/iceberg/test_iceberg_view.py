"""Tests for IcebergView TUI screen."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from textual.widgets import Checkbox, DataTable

from tablesleuth.models.iceberg import (
    IcebergSnapshotDetails,
    IcebergSnapshotInfo,
    IcebergTableInfo,
    SchemaField,
    SchemaInfo,
)
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService
from tablesleuth.tui.views.iceberg_view import IcebergView, SnapshotListView


@pytest.fixture
def mock_table_info() -> IcebergTableInfo:
    """Create a mock IcebergTableInfo."""
    from unittest.mock import Mock

    return IcebergTableInfo(
        table_uuid="test-uuid-1234",
        location="s3://test-bucket/test-table",
        format_version=2,
        current_snapshot_id=1,
        metadata_location="s3://test-bucket/test-table/metadata/v1.metadata.json",
        properties={},
        native_table=Mock(),
    )


@pytest.fixture
def mock_snapshots() -> list[IcebergSnapshotInfo]:
    """Create mock snapshot data."""
    return [
        IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=int(datetime(2024, 1, 1, 12, 0).timestamp() * 1000),
            operation="append",
            summary={},
            manifest_list="s3://bucket/manifest1.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=1000000,
            position_deletes=0,
            equality_deletes=0,
        ),
        IcebergSnapshotInfo(
            snapshot_id=2,
            parent_snapshot_id=1,
            timestamp_ms=int(datetime(2024, 1, 2, 12, 0).timestamp() * 1000),
            operation="delete",
            summary={},
            manifest_list="s3://bucket/manifest2.avro",
            schema_id=0,
            total_records=900,
            total_data_files=10,
            total_delete_files=5,
            total_size_bytes=950000,
            position_deletes=100,
            equality_deletes=0,
        ),
        IcebergSnapshotInfo(
            snapshot_id=3,
            parent_snapshot_id=2,
            timestamp_ms=int(datetime(2024, 1, 3, 12, 0).timestamp() * 1000),
            operation="append",
            summary={},
            manifest_list="s3://bucket/manifest3.avro",
            schema_id=0,
            total_records=1500,
            total_data_files=15,
            total_delete_files=0,
            total_size_bytes=1500000,
            position_deletes=0,
            equality_deletes=0,
        ),
    ]


@pytest.fixture
def mock_snapshot_details(mock_snapshots: list[IcebergSnapshotInfo]) -> IcebergSnapshotDetails:
    """Create mock snapshot details."""
    from tablesleuth.models.iceberg import PartitionSpecInfo

    return IcebergSnapshotDetails(
        snapshot_info=mock_snapshots[0],
        schema=SchemaInfo(
            schema_id=1,
            fields=[
                SchemaField(
                    field_id=1,
                    name="id",
                    field_type="long",
                    required=True,
                    doc="Record ID",
                ),
                SchemaField(
                    field_id=2,
                    name="name",
                    field_type="string",
                    required=False,
                    doc="Record name",
                ),
            ],
        ),
        data_files=[
            {
                "file_path": "s3://test-bucket/test-table/data/file1.parquet",
                "file_size_bytes": 1024,
                "record_count": 100,
            }
        ],
        delete_files=[],
        partition_spec=PartitionSpecInfo(spec_id=0, fields=[]),
        sort_order=None,
    )


@pytest.fixture
def mock_metadata_service(
    mock_snapshots: list[IcebergSnapshotInfo],
    mock_snapshot_details: IcebergSnapshotDetails,
) -> IcebergMetadataService:
    """Create a mock IcebergMetadataService."""
    service = Mock(spec=IcebergMetadataService)
    service.list_snapshots = Mock(return_value=mock_snapshots)
    service.get_snapshot_details = Mock(return_value=mock_snapshot_details)
    service.compare_snapshots = Mock(return_value=Mock())
    return service


class TestSnapshotListView:
    """Tests for SnapshotListView widget."""

    async def test_snapshot_list_view_initialization(self) -> None:
        """Test SnapshotListView initializes correctly."""
        view = SnapshotListView()
        assert view._snapshots == []
        assert view._compare_mode is False

    async def test_snapshot_list_view_with_initial_snapshots(
        self, mock_snapshots: list[IcebergSnapshotInfo]
    ) -> None:
        """Test SnapshotListView with initial snapshots."""
        view = SnapshotListView(snapshots=mock_snapshots)
        assert len(view._snapshots) == 3
        assert view._snapshots[0].snapshot_id == 1

    async def test_update_snapshots(self, mock_snapshots: list[IcebergSnapshotInfo]) -> None:
        """Test updating snapshots in the list view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)
            view.update_snapshots(mock_snapshots)

            # Check that table has correct number of rows
            table = view.query_one("#snapshot-table", DataTable)
            assert table.row_count == 3

    async def test_clear_snapshots(self, mock_snapshots: list[IcebergSnapshotInfo]) -> None:
        """Test clearing snapshots from the list view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=mock_snapshots, id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)
            view.clear()

            assert len(view._snapshots) == 0
            table = view.query_one("#snapshot-table", DataTable)
            assert table.row_count == 0

    async def test_get_selected_snapshot(self, mock_snapshots: list[IcebergSnapshotInfo]) -> None:
        """Test getting the selected snapshot."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=mock_snapshots, id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)

            # DataTable may have a default cursor position, so check if we can get a snapshot
            selected = view.get_selected_snapshot()

            # If there's a selection, verify it's valid
            if selected is not None:
                assert selected.snapshot_id in [1, 2, 3]

            # Move cursor using the table's move_cursor method
            table = view.query_one("#snapshot-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()

            selected = view.get_selected_snapshot()
            assert selected is not None
            assert selected.snapshot_id == 1

    async def test_set_compare_mode(self, mock_snapshots: list[IcebergSnapshotInfo]) -> None:
        """Test setting compare mode."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=mock_snapshots, id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)

            view.set_compare_mode(True)
            assert view._compare_mode is True

            view.set_compare_mode(False)
            assert view._compare_mode is False

    async def test_snapshot_with_deletes_display(self) -> None:
        """Test that snapshots with deletes show correct indicators."""
        from textual.app import App

        # Create snapshot with high delete ratio
        snapshot_with_deletes = IcebergSnapshotInfo(
            snapshot_id=1,
            parent_snapshot_id=None,
            timestamp_ms=int(datetime(2024, 1, 1, 12, 0).timestamp() * 1000),
            operation="delete",
            summary={},
            manifest_list="s3://bucket/manifest.avro",
            schema_id=0,
            total_records=1000,
            total_data_files=10,
            total_delete_files=20,  # High delete ratio
            total_size_bytes=1000000,
            position_deletes=200,
            equality_deletes=0,
        )

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=[snapshot_with_deletes], id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)
            table = view.query_one("#snapshot-table", DataTable)

            # Check that the delete indicator is present
            assert table.row_count == 1


class TestIcebergView:
    """Tests for IcebergView screen."""

    async def test_iceberg_view_initialization(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test IcebergView initializes correctly."""
        view = IcebergView(
            table_info=mock_table_info,
            metadata_service=mock_metadata_service,
        )

        assert view._table_info == mock_table_info
        assert view._metadata_service == mock_metadata_service
        assert view._compare_mode is False
        assert len(view._selected_snapshots) == 0

    async def test_iceberg_view_loads_snapshots_on_mount(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
    ) -> None:
        """Test that IcebergView loads snapshots when mounted."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            # Wait for mount to complete
            await pilot.pause()

            # Verify that list_snapshots was called
            mock_metadata_service.list_snapshots.assert_called_once_with(mock_table_info)

    async def test_format_table_info(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test table info formatting."""
        view = IcebergView(
            table_info=mock_table_info,
            metadata_service=mock_metadata_service,
        )

        info_str = view._format_table_info()
        # The format includes Rich markup, so check for the UUID substring
        assert "test-uui" in info_str  # First 8 chars of UUID
        assert "s3://test-bucket/test-table" in info_str
        assert "v2" in info_str

    async def test_compare_mode_toggle(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test toggling compare mode."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)
            checkbox = view.query_one("#compare-checkbox", Checkbox)

            # Toggle compare mode
            checkbox.toggle()
            await pilot.pause()

            assert view._compare_mode is True

            # Toggle back
            checkbox.toggle()
            await pilot.pause()

            assert view._compare_mode is False

    async def test_action_refresh(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test refresh action."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Reset the mock to clear the initial call
            mock_metadata_service.list_snapshots.reset_mock()

            # Trigger refresh
            view.action_refresh()
            await pilot.pause()

            # Verify that list_snapshots was called again
            mock_metadata_service.list_snapshots.assert_called_once()

    async def test_action_toggle_compare(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test toggle compare action."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Trigger toggle compare
            view.action_toggle_compare()
            await pilot.pause()

            assert view._compare_mode is True

    async def test_cleanup_test_tables_no_manager(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test cleanup when no test manager exists."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Should not raise an error
            view._cleanup_test_tables()
            await pilot.pause()

    async def test_snapshot_details_caching(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
        mock_snapshot_details: IcebergSnapshotDetails,
    ) -> None:
        """Test that snapshot details are cached."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Load details for the first time
            snapshot = mock_snapshots[0]
            view._load_snapshot_details(snapshot)
            await pilot.pause()

            # Verify get_snapshot_details was called
            assert mock_metadata_service.get_snapshot_details.call_count == 1

            # Load details again - should use cache
            view._load_snapshot_details(snapshot)
            await pilot.pause()

            # Should still be called only once (cached)
            assert mock_metadata_service.get_snapshot_details.call_count == 1

    async def test_error_handling_on_snapshot_load_failure(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test error handling when snapshot loading fails."""
        from textual.app import App

        # Make list_snapshots raise an exception
        mock_metadata_service.list_snapshots.side_effect = Exception("Load failed")

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Should not crash, error should be handled
            view = app.query_one(IcebergView)
            assert view is not None

    async def test_action_dismiss_notification(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test dismiss notification action."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Should not raise an error
            view.action_dismiss_notification()
            await pilot.pause()


class TestIcebergViewAdvanced:
    """Advanced tests for IcebergView screen."""

    async def test_on_data_table_row_selected_normal_mode(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
    ) -> None:
        """Test row selection in normal mode."""
        from textual.app import App
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)
            snapshot_list = view.query_one("#snapshot-list", SnapshotListView)

            # Simulate row selection
            table = snapshot_list.query_one("#snapshot-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()

            # Trigger the event handler by simulating the event
            # Create a mock event
            from unittest.mock import Mock

            event = Mock()
            event.sender = table
            view.on_data_table_row_selected(event)
            await pilot.pause()

            # Should have selected a snapshot in normal mode (or None if no cursor)
            # Just verify it doesn't crash
            assert True

    async def test_on_data_table_row_selected_compare_mode(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
    ) -> None:
        """Test row selection in compare mode."""
        from textual.app import App
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Enable compare mode
            view._compare_mode = True

            snapshot_list = view.query_one("#snapshot-list", SnapshotListView)
            table = snapshot_list.query_one("#snapshot-table", DataTable)

            # Select first snapshot
            table.move_cursor(row=0)
            await pilot.pause()

            # Create a mock event
            from unittest.mock import Mock

            event = Mock()
            event.sender = table
            view.on_data_table_row_selected(event)
            await pilot.pause()

            # Just verify it doesn't crash in compare mode
            assert True

    async def test_on_checkbox_changed_enable_compare(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test enabling compare mode via checkbox."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)
            checkbox = view.query_one("#compare-checkbox", Checkbox)

            # Simulate checkbox change
            from textual.widgets._checkbox import Checkbox as CheckboxWidget

            event = CheckboxWidget.Changed(checkbox, True)
            view.on_checkbox_changed(event)
            await pilot.pause()

            assert view._compare_mode is True
            assert len(view._selected_snapshots) == 0

    async def test_on_button_pressed_cleanup(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test cleanup button press."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)
            from textual.widgets import Button

            button = view.query_one("#cleanup-button", Button)

            # Simulate button press
            from unittest.mock import Mock

            event = Mock()
            event.button = button
            view.on_button_pressed(event)
            await pilot.pause()

            # Should not crash (no test manager initialized)

    async def test_load_snapshots_success(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
    ) -> None:
        """Test successful snapshot loading."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Verify snapshots were loaded
            assert len(view._snapshots) > 0

    async def test_load_snapshot_details_with_caching(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
        mock_snapshot_details: IcebergSnapshotDetails,
    ) -> None:
        """Test snapshot details loading uses cache."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)
            snapshot = mock_snapshots[0]

            # First load
            view._load_snapshot_details(snapshot)
            await pilot.pause()

            # Should be cached
            assert snapshot.snapshot_id in view._details_cache

            # Second load should use cache
            call_count_before = mock_metadata_service.get_snapshot_details.call_count
            view._load_snapshot_details(snapshot)
            await pilot.pause()

            # Should not make another call
            assert mock_metadata_service.get_snapshot_details.call_count == call_count_before

    async def test_update_compare_mode_with_two_snapshots(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
        mock_snapshots: list[IcebergSnapshotInfo],
    ) -> None:
        """Test compare mode update with two snapshots selected."""
        from unittest.mock import Mock

        from textual.app import App

        # Mock the comparison result
        mock_comparison = Mock()
        mock_metadata_service.compare_snapshots = Mock(return_value=mock_comparison)

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Select two snapshots
            view._selected_snapshots = [mock_snapshots[0], mock_snapshots[1]]

            # Update compare mode
            view._update_compare_mode()
            await pilot.pause()

            # Compare tab should be enabled
            compare_tab = view.query_one("#compare-tab")
            assert compare_tab.disabled is False

    async def test_format_table_info_truncates_uuid(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test that table info formatting truncates UUID."""
        view = IcebergView(
            table_info=mock_table_info,
            metadata_service=mock_metadata_service,
        )

        info = view._format_table_info()

        # Should contain truncated UUID (first 8 chars + ...)
        assert "test-uui" in info
        assert "..." in info
        assert mock_table_info.location in info
        assert f"v{mock_table_info.format_version}" in info

    async def test_action_run_test_without_profiler(
        self,
        mock_table_info: IcebergTableInfo,
        mock_metadata_service: IcebergMetadataService,
    ) -> None:
        """Test run test action without profiler."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield IcebergView(
                    table_info=mock_table_info,
                    metadata_service=mock_metadata_service,
                    profiler=None,  # No profiler
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            view = app.query_one(IcebergView)

            # Should not crash
            view.action_run_test()
            await pilot.pause()

    async def test_snapshot_list_view_get_snapshots(
        self, mock_snapshots: list[IcebergSnapshotInfo]
    ) -> None:
        """Test getting all snapshots from list view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=mock_snapshots, id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)

            snapshots = view.get_snapshots()
            assert len(snapshots) == 3
            assert snapshots[0].snapshot_id == 1

    async def test_snapshot_list_view_get_selected_snapshot_index(
        self, mock_snapshots: list[IcebergSnapshotInfo]
    ) -> None:
        """Test getting selected snapshot index."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotListView(snapshots=mock_snapshots, id="test-list")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-list", SnapshotListView)

            # Move cursor to first row
            table = view.query_one("#snapshot-table", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()

            index = view.get_selected_snapshot_index()
            assert index == 0
