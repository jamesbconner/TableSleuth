"""End-to-end tests for Table Sleuth.

These tests verify the complete data flow through all layers of the application.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.services.file_discovery import FileDiscoveryService
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.services.parquet_service import ParquetInspector
from tablesleuth.tui.app import TableSleuthApp


@pytest.fixture
def app_config() -> AppConfig:
    """Create test app configuration."""
    return AppConfig(
        catalog=CatalogConfig(default=None),
        gizmosql=GizmoConfig(),
    )


@pytest.fixture
def table_handle() -> TableHandle:
    """Create test table handle."""
    return TableHandle(native=None, format_name="parquet")


@pytest.fixture
def adapter() -> IcebergAdapter:
    """Create test adapter."""
    return IcebergAdapter(default_catalog=None)


class TestEndToEndSingleFile:
    """End-to-end tests for single file loading."""

    def test_load_single_file_complete_flow(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
        sample_parquet_file: Path,
    ) -> None:
        """Test complete flow: discover file -> inspect -> create app."""
        test_parquet_file = sample_parquet_file
        # Step 1: Discover file
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)

        assert len(files) == 1
        assert files[0].path == str(test_parquet_file)

        # Step 2: Inspect file
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)

        assert file_info.num_rows > 0
        assert file_info.num_columns > 0

        # Step 3: Create app with file
        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=files,
        )

        assert app is not None
        assert len(app._files) == 1

    def test_single_file_data_flow(
        self,
        sample_parquet_file: Path,
    ) -> None:
        """Test data flows correctly through all layers."""
        test_parquet_file = sample_parquet_file
        # Layer 1: File Discovery
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)
        file_ref = files[0]

        # Layer 2: Metadata Extraction
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(file_ref.path)

        # Verify data consistency
        assert file_info.path == file_ref.path
        assert file_info.file_size_bytes == file_ref.file_size_bytes

        # Layer 3: Schema extraction
        schema = inspector.get_schema(file_ref.path)
        # Schema shows logical columns, num_columns shows physical columns
        # For nested structures, these may differ
        assert len(schema) > 0

        # Layer 4: Row groups
        row_groups = inspector.get_row_groups(file_ref.path)
        assert len(row_groups) == file_info.num_row_groups


class TestEndToEndDirectory:
    """End-to-end tests for directory loading."""

    def test_load_directory_complete_flow(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
        multi_file_directory: Path,
    ) -> None:
        """Test complete flow: discover directory -> inspect files -> create app."""
        test_dir = multi_file_directory

        # Step 1: Discover files in directory
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_dir)

        assert len(files) > 0

        # Step 2: Inspect first file
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(files[0].path)

        assert file_info is not None

        # Step 3: Create app with files
        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=files,
        )

        assert len(app._files) == len(files)

    def test_directory_multiple_files_data_flow(
        self,
        multi_file_directory: Path,
    ) -> None:
        """Test data flow with multiple files from directory."""
        test_dir = multi_file_directory

        # Discover all files
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_dir)

        if len(files) == 0:
            pytest.skip("No Parquet files in test directory")

        # Inspect each file
        inspector = ParquetInspector()
        for file_ref in files:
            file_info = inspector.inspect_file(file_ref.path)

            # Verify each file has valid metadata
            assert file_info.num_rows >= 0
            assert file_info.num_columns > 0
            assert len(file_info.columns) == file_info.num_columns


class TestEndToEndIcebergTable:
    """End-to-end tests for Iceberg table loading."""

    def test_iceberg_table_discovery_flow(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
    ) -> None:
        """Test Iceberg table file discovery flow."""
        # Create mock adapter with data files
        mock_adapter = Mock()
        mock_files = [
            FileRef(
                path="/path/to/file1.parquet",
                file_size_bytes=1024,
                record_count=100,
                source="iceberg",
            ),
        ]
        mock_adapter.get_data_files.return_value = mock_files

        # Discover files from table
        discovery = FileDiscoveryService(iceberg_adapter=mock_adapter)
        files = discovery.discover_from_table("db.table", "catalog")

        assert len(files) == 1
        assert files[0].source == "iceberg"

        # Create app with discovered files
        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=files,
        )

        assert len(app._files) == 1


class TestEndToEndErrorHandling:
    """End-to-end tests for error handling."""

    def test_invalid_file_path(self) -> None:
        """Test error handling for invalid file path."""
        discovery = FileDiscoveryService()

        with pytest.raises(FileNotFoundError):
            discovery.discover_from_path("nonexistent.parquet")

    def test_invalid_parquet_file(self, tmp_path: Path) -> None:
        """Test error handling for invalid Parquet file."""
        # Create invalid file
        invalid_file = tmp_path / "invalid.parquet"
        invalid_file.write_text("not a parquet file")

        discovery = FileDiscoveryService()

        with pytest.raises(ValueError):
            discovery.discover_from_path(invalid_file)

    def test_inspector_error_handling(self) -> None:
        """Test inspector error handling."""
        inspector = ParquetInspector()

        # Nonexistent file
        with pytest.raises(FileNotFoundError):
            inspector.inspect_file("nonexistent.parquet")

    def test_app_handles_empty_file_list(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
    ) -> None:
        """Test app handles empty file list gracefully."""
        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=[],
        )

        assert len(app._files) == 0


class TestEndToEndDataConsistency:
    """End-to-end tests for data consistency across layers."""

    def test_file_size_consistency(
        self,
        sample_parquet_file: Path,
    ) -> None:
        """Test file size is consistent across layers."""
        test_parquet_file = sample_parquet_file
        # Get actual file size
        actual_size = test_parquet_file.stat().st_size

        # Discovery layer
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)
        assert files[0].file_size_bytes == actual_size

        # Inspector layer
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)
        assert file_info.file_size_bytes == actual_size

    def test_row_count_consistency(
        self,
        sample_parquet_file: Path,
    ) -> None:
        """Test row count is consistent across layers."""
        test_parquet_file = sample_parquet_file
        # Discovery layer
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)
        discovery_row_count = files[0].record_count

        # Inspector layer
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)
        inspector_row_count = file_info.num_rows

        # Should match
        assert discovery_row_count == inspector_row_count

    def test_column_count_consistency(
        self,
        sample_parquet_file: Path,
    ) -> None:
        """Test column count is consistent."""
        test_parquet_file = sample_parquet_file
        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)

        # Physical columns (num_columns) and column stats should match
        assert len(file_info.columns) == file_info.num_columns

        # Schema shows logical columns (may differ for nested structures)
        assert len(file_info.schema) > 0


class TestEndToEndAppIntegration:
    """End-to-end tests for app integration."""

    def test_app_with_inspector_integration(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
        sample_parquet_file: Path,
    ) -> None:
        """Test app integrates with inspector correctly."""
        test_parquet_file = sample_parquet_file
        # Discover and create app
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)

        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=files,
        )

        # Verify app has inspector
        assert app._inspector is not None

        # Verify inspector can inspect the file
        file_info = app._inspector.inspect_file(files[0].path)
        assert file_info is not None

    def test_app_caching_integration(
        self,
        app_config: AppConfig,
        table_handle: TableHandle,
        adapter: IcebergAdapter,
        sample_parquet_file: Path,
    ) -> None:
        """Test app caching works end-to-end."""
        test_parquet_file = sample_parquet_file
        discovery = FileDiscoveryService()
        files = discovery.discover_from_path(test_parquet_file)

        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=app_config,
            files=files,
        )

        # Verify caches are initialized
        assert hasattr(app, "_file_metadata_cache")
        assert hasattr(app, "_profile_cache")
        assert len(app._file_metadata_cache) == 0
        assert len(app._profile_cache) == 0
