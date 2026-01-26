"""Tests for CLI commands."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from tablesleuth.cli import main as cli
from tablesleuth.cli.parquet import parquet
from tablesleuth.models.file_ref import FileRef


class TestCLI:
    """Tests for CLI entry point."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test CLI help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "TableSleuth" in result.output
        assert "parquet" in result.output

    def test_cli_version(self, runner):
        """Test CLI version output."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()


class TestParquetCommand:
    """Tests for parquet command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_parquet_file(self, tmp_path):
        """Create a temporary parquet file for testing."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        # Create simple parquet file
        table = pa.table({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        file_path = tmp_path / "test.parquet"
        pq.write_table(table, file_path)
        return file_path

    def test_parquet_help(self, runner):
        """Test parquet command help."""
        result = runner.invoke(parquet, ["--help"])
        assert result.exit_code == 0
        assert "Inspect Parquet" in result.output  # Changed from "Inspect Parquet files"
        assert "--catalog" in result.output
        assert "--verbose" in result.output

    def test_parquet_nonexistent_file(self, runner):
        """Test inspecting nonexistent file."""
        result = runner.invoke(parquet, ["/nonexistent/file.parquet"])
        assert result.exit_code == 1
        assert "does not exist" in result.output

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    def test_parquet_single_file(self, mock_app, runner, temp_parquet_file):
        """Test inspecting a single parquet file."""
        # Mock the TUI app
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        result = runner.invoke(parquet, [str(temp_parquet_file)])

        # Should succeed
        assert result.exit_code == 0
        assert "Loading" in result.output or "Launching" in result.output

        # App should be created and run
        mock_app.assert_called_once()
        mock_app_instance.run.assert_called_once()

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    def test_parquet_directory(self, mock_app, runner, temp_parquet_file):
        """Test inspecting a directory."""
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Use the parent directory
        directory = temp_parquet_file.parent
        result = runner.invoke(parquet, [str(directory)])

        assert result.exit_code == 0
        mock_app.assert_called_once()

    def test_parquet_with_verbose_flag(self, runner, temp_parquet_file):
        """Test parquet with verbose logging."""
        with patch("tablesleuth.cli.parquet.TableSleuthApp") as mock_app:
            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance

            result = runner.invoke(parquet, ["--verbose", str(temp_parquet_file)])

            assert result.exit_code == 0

    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    def test_parquet_iceberg_table(self, mock_app, mock_discovery, mock_adapter, runner):
        """Test inspecting an Iceberg table."""
        # Setup mocks
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        mock_table_handle = Mock()
        mock_adapter_instance.open_table.return_value = mock_table_handle

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance

        test_files = [
            FileRef(path="s3://bucket/file1.parquet", file_size_bytes=1024),
            FileRef(path="s3://bucket/file2.parquet", file_size_bytes=2048),
        ]
        mock_discovery_instance.discover_from_table.return_value = test_files

        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Execute
        result = runner.invoke(parquet, ["--catalog", "test_catalog", "db.table"])

        # Verify
        assert result.exit_code == 0
        assert "Loading table" in result.output
        assert "Found 2 data files in Iceberg table" in result.output

        mock_adapter_instance.open_table.assert_called_once_with("db.table", "test_catalog")
        mock_discovery_instance.discover_from_table.assert_called_once_with(
            "db.table", "test_catalog"
        )

    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    def test_parquet_s3_tables_arn(self, mock_app, mock_discovery, mock_adapter, runner):
        """Test inspecting S3 Tables using ARN."""
        # Setup mocks
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        mock_table_handle = Mock()
        mock_adapter_instance.open_table.return_value = mock_table_handle

        # Mock ARN parsing
        mock_adapter_instance._parse_s3_tables_arn.return_value = (
            "s3tables_catalog",
            "db.table",
        )

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance

        test_files = [FileRef(path="s3://bucket/file.parquet", file_size_bytes=1024)]
        mock_discovery_instance.discover_from_table.return_value = test_files

        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Execute
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket/table/db.table"
        result = runner.invoke(parquet, [arn])

        # Verify
        assert result.exit_code == 0
        assert "Loading S3 Tables Iceberg table" in result.output
        assert "Found 1 data files" in result.output

    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_parquet_s3_tables_invalid_arn(self, mock_adapter, runner):
        """Test inspecting with invalid S3 Tables ARN."""
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        # Mock invalid ARN parsing
        mock_adapter_instance._parse_s3_tables_arn.return_value = None

        arn = "arn:aws:s3tables:invalid"
        result = runner.invoke(parquet, [arn])

        assert result.exit_code == 1
        assert "Invalid S3 Tables ARN" in result.output

    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("boto3.client")
    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    def test_parquet_iceberg_table_error(
        self, mock_discovery, mock_boto3_client, mock_app, mock_adapter, runner
    ):
        """Test error handling when loading Iceberg table fails."""
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        # Simulate Iceberg error
        mock_adapter_instance.open_table.side_effect = Exception("Catalog not found")

        # Mock FileDiscoveryService to also fail on Glue fallback
        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance._resolved_region = "us-east-2"
        mock_discovery_instance.discover_from_glue_database.side_effect = Exception(
            "Glue table not found"
        )

        result = runner.invoke(parquet, ["--catalog", "test", "db.table"])

        assert result.exit_code == 1
        assert "Error" in result.output
        # Should not launch TUI
        mock_app.assert_not_called()

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_parquet_s3_path(self, mock_adapter, mock_discovery, mock_app, runner):
        """Test inspecting S3 path directly."""
        # Mock adapter
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        # Mock FileDiscoveryService
        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance

        # Mock discovered files
        test_file = FileRef(
            path="s3://bucket/path/file.parquet",
            file_size_bytes=1024,
            record_count=100,
            source="s3",
        )
        mock_discovery_instance.discover_from_path.return_value = [test_file]

        # Mock TUI app
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Execute
        result = runner.invoke(parquet, ["s3://bucket/path/file.parquet"])

        # Verify
        assert result.exit_code == 0
        assert "Loading from S3" in result.output
        assert "Found 1 Parquet file" in result.output
        mock_discovery_instance.discover_from_path.assert_called_once_with(
            "s3://bucket/path/file.parquet"
        )
        mock_app.assert_called_once()

    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_parquet_table_not_found_in_configured_catalog(self, mock_adapter, runner):
        """Test that table not found in configured catalog doesn't trigger Glue fallback."""
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        # Simulate table not found error (not catalog missing)
        mock_adapter_instance.open_table.side_effect = Exception(
            "Table 'db.nonexistent' does not exist"
        )

        result = runner.invoke(parquet, ["--catalog", "ratebeer", "db.nonexistent"])

        # Should fail without trying Glue fallback
        assert result.exit_code == 1
        assert "Error" in result.output
        # Should NOT see "trying Glue database" message
        assert "trying Glue database" not in result.output
        # Should see the original error
        assert "does not exist" in result.output

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("boto3.client")
    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_parquet_catalog_missing_mixed_case(
        self, mock_adapter, mock_discovery, mock_boto3_client, mock_app, runner, tmp_path
    ):
        """Test that Glue fallback works with mixed-case catalog names."""
        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock adapter
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance

        # Simulate catalog not found with mixed-case name
        # PyIceberg might lowercase the catalog name in error messages
        mock_adapter_instance.open_table.side_effect = Exception(
            "Catalog 'ratebeer' does not exist"
        )

        # Mock FileDiscoveryService
        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance.discover_from_glue_database.return_value = [
            FileRef(
                path=str(test_file),
                file_size_bytes=1024,
                record_count=100,
                source="glue",
            )
        ]

        # Mock Glue client
        mock_glue_client = Mock()
        mock_boto3_client.return_value = mock_glue_client

        # Mock TUI app
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Execute with mixed-case catalog name
        result = runner.invoke(parquet, ["--catalog", "RateBeer", "RateBeer.reviews"])

        # Should trigger Glue fallback despite case mismatch
        assert result.exit_code == 0
        assert "trying Glue database" in result.output
        mock_discovery_instance.discover_from_glue_database.assert_called_once()


class TestParquetCommandErrorHandling:
    """Tests for parquet command error handling."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_parquet_non_parquet_file_warning(self, runner, tmp_path):
        """Test warning for non-parquet file extension."""
        # Create a file with wrong extension
        test_file = tmp_path / "data.txt"
        test_file.write_text("test")

        with patch("tablesleuth.cli.parquet.TableSleuthApp") as mock_app:
            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance

            result = runner.invoke(cli, ["parquet", str(test_file)])

            # Should show warning but still proceed
            assert "Warning" in result.output or "does not have .parquet extension" in result.output

    def test_parquet_empty_directory(self, runner, tmp_path):
        """Test inspecting empty directory."""
        result = runner.invoke(cli, ["parquet", str(tmp_path)])

        assert result.exit_code == 1
        assert "No Parquet files found" in result.output

    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    def test_parquet_discovery_error(self, mock_discovery, runner, tmp_path):
        """Test error handling when file discovery fails."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("fake parquet")

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance.discover_from_path.side_effect = Exception("Discovery failed")

        result = runner.invoke(cli, ["parquet", str(test_file)])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_parquet_verbose_logging(self, runner, tmp_path):
        """Test verbose flag enables debug logging."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("fake")

        with patch("tablesleuth.cli.parquet.TableSleuthApp") as mock_app:
            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance

            with patch("tablesleuth.cli.helpers.logging.basicConfig") as mock_logging:
                result = runner.invoke(cli, ["parquet", "--verbose", str(test_file)])

                # Verify debug logging was configured
                mock_logging.assert_called()

    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    def test_parquet_file_not_found_error(self, mock_discovery, runner, tmp_path):
        """Test FileNotFoundError handling."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("fake")

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance.discover_from_path.side_effect = FileNotFoundError("File missing")

        result = runner.invoke(cli, ["parquet", str(test_file)])

        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    def test_parquet_value_error(self, mock_discovery, runner, tmp_path):
        """Test ValueError handling."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("fake")

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance.discover_from_path.side_effect = ValueError("Invalid format")

        result = runner.invoke(cli, ["parquet", str(test_file)])

        assert result.exit_code == 1
        assert "Invalid input" in result.output

    @patch("tablesleuth.cli.parquet.FileDiscoveryService")
    def test_parquet_generic_error_with_verbose(self, mock_discovery, runner, tmp_path):
        """Test generic exception handling with verbose flag."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("fake")

        mock_discovery_instance = Mock()
        mock_discovery.return_value = mock_discovery_instance
        mock_discovery_instance.discover_from_path.side_effect = RuntimeError("Unexpected error")

        with patch("tablesleuth.cli.parquet.logger") as mock_logger:
            result = runner.invoke(cli, ["parquet", "--verbose", str(test_file)])

            assert result.exit_code == 1
            assert "Error" in result.output
            # Verify logger.exception was called for verbose mode
            mock_logger.exception.assert_called_once()

    def test_parquet_special_file_type(self, runner, tmp_path):
        """Test handling of special file types (not file or directory)."""
        # This is hard to test portably, but we can test the error path
        # by mocking Path.is_file and Path.is_dir
        test_path = tmp_path / "special"
        test_path.touch()

        with patch("pathlib.Path.is_file", return_value=False):
            with patch("pathlib.Path.is_dir", return_value=False):
                with patch("pathlib.Path.exists", return_value=True):
                    result = runner.invoke(cli, ["parquet", str(test_path)])

                    assert result.exit_code == 1
                    assert "neither a file nor directory" in result.output


class TestIcebergViewerCommand:
    """Tests for iceberg command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_iceberg_help(self, runner):
        """Test iceberg command help."""
        result = runner.invoke(cli, ["iceberg", "--help"])
        assert result.exit_code == 0
        assert "Iceberg" in result.output or "metadata" in result.output
        assert "--catalog" in result.output

    def test_iceberg_no_arguments(self, runner):
        """Test iceberg command without arguments."""
        result = runner.invoke(cli, ["iceberg"])

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Must provide either" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    def test_iceberg_metadata_file_not_found(self, mock_service, runner):
        """Test iceberg command with non-existent metadata file."""
        result = runner.invoke(cli, ["iceberg", "/nonexistent/metadata.json"])

        assert result.exit_code == 1
        assert "Metadata file not found" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    @patch("tablesleuth.cli.iceberg.GizmoDuckDbProfiler")
    def test_iceberg_with_metadata_path(self, mock_profiler, mock_service, runner, tmp_path):
        """Test iceberg command with metadata path."""
        # Create temp metadata file
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{}")

        # Mock service
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance

        mock_table_info = Mock()
        mock_table_info.table_uuid = "test-uuid"
        mock_table_info.format_version = 2
        mock_table_info.location = "s3://bucket/table"
        mock_service_instance.load_table.return_value = mock_table_info

        # Mock profiler
        mock_profiler_instance = Mock()
        mock_profiler.return_value = mock_profiler_instance

        # Mock the app to avoid actually running TUI
        with patch("tablesleuth.cli.iceberg.IcebergView"):
            with patch("textual.app.App.run"):
                result = runner.invoke(cli, ["iceberg", str(metadata_file)])

                # Should load table and show info
                assert "Table UUID: test-uuid" in result.output
                assert "Format version: 2" in result.output
                mock_service_instance.load_table.assert_called_once()

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    @patch("tablesleuth.cli.iceberg.GizmoDuckDbProfiler")
    def test_iceberg_with_catalog_and_table(self, mock_profiler, mock_service, runner):
        """Test iceberg command with catalog and table identifier."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance

        mock_table_info = Mock()
        mock_table_info.table_uuid = "catalog-uuid"
        mock_table_info.format_version = 2
        mock_table_info.location = "s3://bucket/catalog-table"
        mock_service_instance.load_table.return_value = mock_table_info

        mock_profiler_instance = Mock()
        mock_profiler.return_value = mock_profiler_instance

        with patch("tablesleuth.cli.iceberg.IcebergView"):
            with patch("textual.app.App.run"):
                result = runner.invoke(
                    cli,
                    ["iceberg", "--catalog", "test_catalog", "--table", "db.table"],
                )

                assert "Loading Iceberg table: db.table" in result.output
                assert "Table UUID: catalog-uuid" in result.output
                mock_service_instance.load_table.assert_called_once_with(
                    catalog_name="test_catalog",
                    table_identifier="db.table",
                )

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    @patch("tablesleuth.cli.iceberg.GizmoDuckDbProfiler")
    def test_iceberg_profiler_initialization_error(
        self, mock_profiler, mock_service, runner, tmp_path
    ):
        """Test iceberg command when profiler initialization fails."""
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{}")

        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance

        mock_table_info = Mock()
        mock_table_info.table_uuid = "test-uuid"
        mock_table_info.format_version = 2
        mock_table_info.location = "s3://bucket/table"
        mock_service_instance.load_table.return_value = mock_table_info

        # Profiler fails to initialize
        mock_profiler.side_effect = Exception("Connection failed")

        with patch("tablesleuth.cli.iceberg.IcebergView"):
            with patch("textual.app.App.run"):
                result = runner.invoke(cli, ["iceberg", str(metadata_file)])

                # Should show warning but continue
                assert "Warning: Could not initialize profiler" in result.output
                assert "Performance testing will be disabled" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    def test_iceberg_table_load_error(self, mock_service, runner):
        """Test iceberg command when table loading fails."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.load_table.side_effect = Exception("Table load failed")

        result = runner.invoke(
            cli,
            ["iceberg", "--catalog", "test", "--table", "db.table"],
        )

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    @patch("tablesleuth.cli.iceberg.GizmoDuckDbProfiler")
    def test_iceberg_verbose_logging(self, mock_profiler, mock_service, runner, tmp_path):
        """Test verbose flag enables debug logging."""
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{}")

        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance

        mock_table_info = Mock()
        mock_table_info.table_uuid = "test-uuid"
        mock_table_info.format_version = 2
        mock_table_info.location = "s3://bucket/table"
        mock_service_instance.load_table.return_value = mock_table_info

        mock_profiler_instance = Mock()
        mock_profiler.return_value = mock_profiler_instance

        with patch("tablesleuth.cli.iceberg.IcebergView"):
            with patch("textual.app.App.run"):
                with patch("tablesleuth.cli.helpers.logging.basicConfig") as mock_logging:
                    result = runner.invoke(cli, ["iceberg", "--verbose", str(metadata_file)])

                    # Verify debug logging was configured with DEBUG level
                    calls = [call for call in mock_logging.call_args_list]
                    assert any(call[1].get("level") == logging.DEBUG for call in calls if call[1])

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    def test_iceberg_file_not_found_error(self, mock_service, runner):
        """Test FileNotFoundError handling in iceberg command."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.load_table.side_effect = FileNotFoundError("Metadata not found")

        result = runner.invoke(
            cli,
            ["iceberg", "--catalog", "test", "--table", "db.table"],
        )

        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    def test_iceberg_value_error(self, mock_service, runner):
        """Test ValueError handling in iceberg command."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.load_table.side_effect = ValueError("Invalid table format")

        result = runner.invoke(
            cli,
            ["iceberg", "--catalog", "test", "--table", "db.table"],
        )

        assert result.exit_code == 1
        assert "Invalid input" in result.output

    @patch("tablesleuth.cli.iceberg.IcebergMetadataService")
    def test_iceberg_generic_error_with_verbose(self, mock_service, runner):
        """Test generic exception handling with verbose flag in iceberg command."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.load_table.side_effect = RuntimeError("Unexpected error")

        with patch("tablesleuth.cli.iceberg.logger") as mock_logger:
            result = runner.invoke(
                cli,
                ["iceberg", "--verbose", "--catalog", "test", "--table", "db.table"],
            )

            assert result.exit_code == 1
            assert "Error" in result.output
            # Verify logger.exception was called for verbose mode
            mock_logger.exception.assert_called_once()


class TestEntryPoint:
    """Tests for CLI entry point."""

    @patch("tablesleuth.cli.main")
    def test_entry_point(self, mock_main):
        """Test entry_point function calls main."""
        from tablesleuth.cli import entry_point

        entry_point()
        mock_main.assert_called_once()
