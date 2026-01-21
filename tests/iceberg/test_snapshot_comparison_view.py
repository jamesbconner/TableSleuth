"""Tests for snapshot comparison and performance test views."""

from __future__ import annotations

from datetime import datetime

import pytest
from textual.widgets import Button, Input, Select, Static

from tablesleuth.models.iceberg import (
    IcebergSnapshotInfo,
    PerformanceComparison,
    QueryPerformanceMetrics,
    SnapshotComparison,
)
from tablesleuth.tui.views.snapshot_comparison_view import (
    PerformanceTestView,
    SnapshotComparisonView,
)


@pytest.fixture
def mock_snapshot_a() -> IcebergSnapshotInfo:
    """Create mock snapshot A."""
    return IcebergSnapshotInfo(
        snapshot_id=1,
        parent_snapshot_id=None,
        timestamp_ms=int(datetime(2024, 1, 1, 12, 0).timestamp() * 1000),
        operation="append",
        summary={},
        manifest_list="s3://bucket/manifest1.avro",
        schema_id=0,
        total_records=1000,
        total_data_files=10,
        total_delete_files=2,
        total_size_bytes=1000000,
        position_deletes=20,
        equality_deletes=0,
    )


@pytest.fixture
def mock_snapshot_b() -> IcebergSnapshotInfo:
    """Create mock snapshot B."""
    return IcebergSnapshotInfo(
        snapshot_id=2,
        parent_snapshot_id=1,
        timestamp_ms=int(datetime(2024, 1, 2, 12, 0).timestamp() * 1000),
        operation="delete",
        summary={},
        manifest_list="s3://bucket/manifest2.avro",
        schema_id=0,
        total_records=900,
        total_data_files=12,
        total_delete_files=5,
        total_size_bytes=950000,
        position_deletes=50,
        equality_deletes=0,
    )


@pytest.fixture
def mock_comparison(
    mock_snapshot_a: IcebergSnapshotInfo,
    mock_snapshot_b: IcebergSnapshotInfo,
) -> SnapshotComparison:
    """Create mock snapshot comparison."""
    return SnapshotComparison(
        snapshot_a=mock_snapshot_a,
        snapshot_b=mock_snapshot_b,
        data_files_added=2,
        data_files_removed=0,
        delete_files_added=3,
        delete_files_removed=0,
        records_added=100,
        records_deleted=200,
        records_delta=-100,  # Net change
        size_added_bytes=1024 * 1024,  # 1 MB
        size_removed_bytes=512 * 1024,  # 512 KB
        size_delta_bytes=512 * 1024,  # Net change
        delete_ratio_change=3.0,  # Change in delete ratio
        read_amplification_change=0.1,  # Change in read amplification
    )


@pytest.fixture
def mock_performance_comparison() -> PerformanceComparison:
    """Create mock performance comparison."""
    return PerformanceComparison(
        table_a_name="snapshot_1",
        table_b_name="snapshot_2",
        query="SELECT COUNT(*) FROM {table}",
        metrics_a=QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=1000,
            memory_peak_mb=50.0,
        ),
        metrics_b=QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=12,
            bytes_scanned=1200000,
            rows_scanned=900,
            rows_returned=900,
            memory_peak_mb=60.0,
        ),
    )


class TestSnapshotComparisonView:
    """Tests for SnapshotComparisonView widget."""

    async def test_initialization_without_comparison(self) -> None:
        """Test SnapshotComparisonView initializes without comparison."""
        view = SnapshotComparisonView()
        assert view._comparison is None

    async def test_initialization_with_comparison(
        self, mock_comparison: SnapshotComparison
    ) -> None:
        """Test SnapshotComparisonView initializes with comparison."""
        view = SnapshotComparisonView(comparison=mock_comparison)
        assert view._comparison == mock_comparison

    async def test_show_placeholder(self) -> None:
        """Test show_placeholder displays placeholder message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotComparisonView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotComparisonView)
            view.show_placeholder()
            await pilot.pause()

            content = view.query_one("#comparison-content", Static)
            # Access the rendered content
            rendered = str(content.render())
            assert "Select exactly 2 snapshots" in rendered

    async def test_update_comparison(self, mock_comparison: SnapshotComparison) -> None:
        """Test update_comparison displays comparison data."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotComparisonView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotComparisonView)
            view.update_comparison(mock_comparison)
            await pilot.pause()

            content = view.query_one("#comparison-content", Static)
            content_text = str(content.render())

            # Check that key information is displayed
            assert "Comparing Snapshots" in content_text
            assert str(mock_comparison.snapshot_a.snapshot_id) in content_text
            assert str(mock_comparison.snapshot_b.snapshot_id) in content_text
            assert "File Changes" in content_text
            assert "Record Changes" in content_text

    async def test_clear(self, mock_comparison: SnapshotComparison) -> None:
        """Test clear resets the view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotComparisonView(comparison=mock_comparison, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotComparisonView)
            view.clear()
            await pilot.pause()

            assert view._comparison is None
            content = view.query_one("#comparison-content", Static)
            rendered = str(content.render())
            assert "Select exactly 2 snapshots" in rendered

    async def test_format_size_positive(self) -> None:
        """Test _format_size with positive sizes."""
        assert SnapshotComparisonView._format_size(512) == "512.0 B"
        assert SnapshotComparisonView._format_size(1024) == "1.0 KB"
        assert SnapshotComparisonView._format_size(1024 * 1024) == "1.0 MB"
        assert SnapshotComparisonView._format_size(1024 * 1024 * 1024) == "1.0 GB"

    async def test_format_size_negative(self) -> None:
        """Test _format_size with negative sizes."""
        assert SnapshotComparisonView._format_size(-512) == "-512.0 B"
        assert SnapshotComparisonView._format_size(-1024) == "-1.0 KB"
        assert SnapshotComparisonView._format_size(-1024 * 1024) == "-1.0 MB"

    async def test_format_size_zero(self) -> None:
        """Test _format_size with zero."""
        assert SnapshotComparisonView._format_size(0) == "0.0 B"

    async def test_comparison_displays_mor_metrics(
        self, mock_comparison: SnapshotComparison
    ) -> None:
        """Test that MOR metrics are displayed in comparison."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotComparisonView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotComparisonView)
            view.update_comparison(mock_comparison)
            await pilot.pause()

            content = view.query_one("#comparison-content", Static)
            content_text = str(content.render())

            assert "Merge-on-Read Metrics" in content_text
            assert "Delete Ratio" in content_text
            assert "Read Amplification" in content_text

    async def test_comparison_displays_compaction_recommendation(
        self, mock_comparison: SnapshotComparison
    ) -> None:
        """Test that compaction recommendation is displayed."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield SnapshotComparisonView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", SnapshotComparisonView)
            view.update_comparison(mock_comparison)
            await pilot.pause()

            content = view.query_one("#comparison-content", Static)
            content_text = str(content.render())

            # Should contain compaction recommendation
            assert mock_comparison.compaction_recommendation in content_text


class TestPerformanceTestView:
    """Tests for PerformanceTestView widget."""

    async def test_initialization(self) -> None:
        """Test PerformanceTestView initializes correctly."""
        view = PerformanceTestView()
        assert view._table_a_name is None
        assert view._table_b_name is None
        assert view._test_result is None

    async def test_show_placeholder(self) -> None:
        """Test show_placeholder displays placeholder message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            await pilot.pause()

            results = view.query_one("#results-content", Static)
            rendered = str(results.render())
            assert "Configure and run a performance test" in rendered

    async def test_set_table_names(self) -> None:
        """Test set_table_names updates table names."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            view.set_table_names("table_a", "table_b")
            await pilot.pause()

            assert view._table_a_name == "table_a"
            assert view._table_b_name == "table_b"

            info = view.query_one("#table-names-info", Static)
            info_text = str(info.render())
            assert "table_a" in info_text
            assert "table_b" in info_text

    async def test_update_results(self, mock_performance_comparison: PerformanceComparison) -> None:
        """Test update_results displays performance comparison."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            view.update_results(mock_performance_comparison)
            await pilot.pause()

            results = view.query_one("#results-content", Static)
            results_text = str(results.render())

            # Check that key information is displayed
            assert "Query" in results_text
            assert mock_performance_comparison.query in results_text
            assert "Execution Time" in results_text
            assert "Files Scanned" in results_text
            assert "Scan Efficiency" in results_text
            assert "Analysis" in results_text

    async def test_clear(self, mock_performance_comparison: PerformanceComparison) -> None:
        """Test clear resets the view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            view.set_table_names("table_a", "table_b")
            view.update_results(mock_performance_comparison)
            await pilot.pause()

            view.clear()
            await pilot.pause()

            assert view._test_result is None
            assert view._table_a_name is None
            assert view._table_b_name is None

            results = view.query_one("#results-content", Static)
            rendered = str(results.render())
            assert "Configure and run a performance test" in rendered

    async def test_query_template_select_options(self) -> None:
        """Test that query template select has correct options."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            select = view.query_one("#query-template-select", Select)

            # Check that select has options
            assert len(select._options) > 0

            # Check for expected query types
            option_values = [opt[1] for opt in select._options]
            assert "full_scan" in option_values
            assert "sample_rows" in option_values
            assert "table_stats" in option_values

    async def test_performance_comparison_displays_delta_colors(
        self, mock_performance_comparison: PerformanceComparison
    ) -> None:
        """Test that performance deltas are displayed with appropriate colors."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            view.update_results(mock_performance_comparison)
            await pilot.pause()

            results = view.query_one("#results-content", Static)
            results_text = str(results.render())

            # Should contain delta information
            assert "Delta:" in results_text

    async def test_input_placeholder(self) -> None:
        """Test that query input has correct placeholder."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            query_input = view.query_one("#query-input", Input)

            assert "{table}" in query_input.placeholder

    async def test_run_test_button_exists(self) -> None:
        """Test that run test button exists."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield PerformanceTestView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", PerformanceTestView)
            button = view.query_one("#run-test-button", Button)

            assert button.label == "Run Performance Test"
            assert button.variant == "primary"
