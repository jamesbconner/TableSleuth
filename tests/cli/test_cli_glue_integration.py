"""Integration tests for CLI Glue Hive table support."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from tablesleuth.cli.parquet import parquet


class TestGlueHiveIntegration:
    """Integration tests for Glue Hive table discovery via CLI."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("boto3.client")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_glue_hive_table_success(
        self, mock_adapter, mock_boto3_client, mock_app, runner, tmp_path
    ):
        """Test successful Glue Hive table discovery."""
        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock Iceberg adapter to fail (catalog not found)
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance
        mock_adapter_instance.open_table.side_effect = Exception("No such catalog: testdb")

        # Mock Glue response
        mock_glue_client = Mock()
        mock_boto3_client.return_value = mock_glue_client
        mock_glue_client.get_table.return_value = {
            "Table": {
                "Parameters": {},  # No table_type = Hive table
                "StorageDescriptor": {"Location": str(tmp_path)},
            }
        }

        # Mock TUI app
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        # Execute
        result = runner.invoke(
            parquet, ["--catalog", "testdb", "--region", "us-east-2", "testdb.testtable"]
        )

        # Verify
        assert result.exit_code == 0
        assert "Loading table" in result.output
        assert "trying Glue database" in result.output
        assert "Found 1 Parquet files in Glue Hive table" in result.output
        mock_app.assert_called_once()

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("boto3.client")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_glue_iceberg_table_detection(self, mock_adapter, mock_boto3_client, mock_app, runner):
        """Test that Iceberg tables in Glue are detected and provide helpful error."""
        # Mock Iceberg adapter to fail (catalog not found)
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance
        mock_adapter_instance.open_table.side_effect = Exception("No such catalog: testdb")

        # Mock Glue response with Iceberg table
        mock_glue_client = Mock()
        mock_boto3_client.return_value = mock_glue_client
        mock_glue_client.get_table.return_value = {
            "Table": {
                "Parameters": {"table_type": "ICEBERG"},
                "StorageDescriptor": {"Location": "s3://bucket/path"},
            }
        }

        # Execute
        result = runner.invoke(
            parquet, ["--catalog", "testdb", "--region", "us-east-2", "testdb.iceberg_table"]
        )

        # Verify
        assert result.exit_code == 1
        assert "Iceberg table" in result.output
        assert ".pyiceberg.yaml" in result.output

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("boto3.client")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_glue_table_not_found(self, mock_adapter, mock_boto3_client, mock_app, runner):
        """Test error handling when Glue table not found."""
        from botocore.exceptions import ClientError

        # Mock Iceberg adapter to fail
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance
        mock_adapter_instance.open_table.side_effect = Exception("No such catalog: testdb")

        # Mock Glue client error
        mock_glue_client = Mock()
        mock_boto3_client.return_value = mock_glue_client
        mock_glue_client.get_table.side_effect = ClientError(
            {"Error": {"Code": "EntityNotFoundException", "Message": "Table not found"}},
            "GetTable",
        )

        # Execute
        result = runner.invoke(
            parquet, ["--catalog", "testdb", "--region", "us-east-2", "testdb.nonexistent"]
        )

        # Verify
        assert result.exit_code == 1
        assert "Error: Could not load table" in result.output
        assert "Tried:" in result.output
        assert "Suggestions:" in result.output
        assert "--region flag" in result.output

    @patch("tablesleuth.cli.parquet.TableSleuthApp")
    @patch("tablesleuth.cli.parquet.IcebergAdapter")
    def test_region_flag_usage(self, mock_adapter, mock_app, runner, tmp_path, monkeypatch):
        """Test that --region flag is properly used."""
        # Set different env var to ensure flag takes precedence
        monkeypatch.setenv("AWS_REGION", "us-west-1")

        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock Iceberg adapter to fail
        mock_adapter_instance = Mock()
        mock_adapter.return_value = mock_adapter_instance
        mock_adapter_instance.open_table.side_effect = Exception("No such catalog: testdb")

        # Mock boto3 at the module level to capture region
        with patch("boto3.client") as mock_boto3_client:
            mock_glue_client = Mock()
            mock_boto3_client.return_value = mock_glue_client
            mock_glue_client.get_table.return_value = {
                "Table": {
                    "Parameters": {},
                    "StorageDescriptor": {"Location": str(tmp_path)},
                }
            }

            # Mock TUI app
            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance

            # Execute with --region flag
            result = runner.invoke(
                parquet,
                ["--catalog", "testdb", "--region", "eu-west-1", "testdb.testtable"],
            )

            # Verify region flag was used (not env var)
            assert result.exit_code == 0
            mock_boto3_client.assert_called_with("glue", region_name="eu-west-1")
