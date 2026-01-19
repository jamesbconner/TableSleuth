"""Tests for Glue Hive table discovery functionality."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tablesleuth.services.file_discovery import FileDiscoveryService, resolve_aws_region


class TestRegionResolution:
    """Tests for AWS region resolution logic."""

    def test_region_override_takes_precedence(self, monkeypatch):
        """Test that --region flag takes highest precedence."""
        monkeypatch.setenv("AWS_REGION", "us-west-1")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

        result = resolve_aws_region("us-east-1")
        assert result == "us-east-1"

    def test_aws_region_env_var(self, monkeypatch):
        """Test that AWS_REGION env var is used when no override."""
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.setenv("AWS_REGION", "us-west-1")

        result = resolve_aws_region(None)
        assert result == "us-west-1"

    def test_aws_default_region_env_var(self, monkeypatch):
        """Test that AWS_DEFAULT_REGION is used as fallback."""
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

        result = resolve_aws_region(None)
        assert result == "us-west-2"

    def test_default_region(self, monkeypatch):
        """Test that default region is used when no other sources."""
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

        result = resolve_aws_region(None)
        assert result == "us-east-2"


class TestGlueHiveDiscovery:
    """Tests for Glue Hive table discovery."""

    @patch("boto3.client")
    def test_discover_from_glue_database_success(self, mock_boto3_client, tmp_path):
        """Test successful discovery from Glue Hive table."""
        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock Glue response
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.return_value = {
            "Table": {
                "Parameters": {},  # No table_type = Hive table
                "StorageDescriptor": {"Location": str(tmp_path)},
            }
        }

        # Test discovery
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_glue_database("testdb", "testdb.testtable")

        assert len(files) == 1
        assert files[0].path == str(test_file)
        mock_client.get_table.assert_called_once_with(DatabaseName="testdb", Name="testtable")

    @patch("boto3.client")
    def test_discover_from_glue_database_table_only(self, mock_boto3_client, tmp_path):
        """Test discovery with table name only (no database prefix)."""
        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock Glue response
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.return_value = {
            "Table": {
                "Parameters": {},
                "StorageDescriptor": {"Location": str(tmp_path)},
            }
        }

        # Test discovery with table name only
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_glue_database("mydb", "mytable")

        assert len(files) == 1
        mock_client.get_table.assert_called_once_with(DatabaseName="mydb", Name="mytable")

    @patch("boto3.client")
    def test_discover_from_glue_database_iceberg_table_error(self, mock_boto3_client):
        """Test that Iceberg tables in Glue raise helpful error."""
        # Mock Glue response with Iceberg table
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.return_value = {
            "Table": {
                "Parameters": {"table_type": "ICEBERG"},
                "StorageDescriptor": {"Location": "s3://bucket/path"},
            }
        }

        service = FileDiscoveryService(region="us-east-2")

        with pytest.raises(ValueError) as exc_info:
            service.discover_from_glue_database("testdb", "testdb.iceberg_table")

        error_msg = str(exc_info.value)
        assert "Iceberg table" in error_msg
        assert ".pyiceberg.yaml" in error_msg
        assert "type: glue" in error_msg

    @patch("boto3.client")
    def test_discover_from_glue_database_table_not_found(self, mock_boto3_client):
        """Test error handling when table not found in Glue."""
        from botocore.exceptions import ClientError

        # Mock Glue client error
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.side_effect = ClientError(
            {"Error": {"Code": "EntityNotFoundException", "Message": "Table not found"}},
            "GetTable",
        )

        service = FileDiscoveryService(region="us-east-2")

        with pytest.raises(ValueError) as exc_info:
            service.discover_from_glue_database("testdb", "testdb.nonexistent")

        error_msg = str(exc_info.value)
        assert "Table not found" in error_msg
        assert "us-east-2" in error_msg
        assert "aws glue get-table" in error_msg

    @patch("boto3.client")
    def test_discover_from_glue_database_no_location(self, mock_boto3_client):
        """Test error when table has no S3 location."""
        # Mock Glue response without Location
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.return_value = {"Table": {"Parameters": {}, "StorageDescriptor": {}}}

        service = FileDiscoveryService(region="us-east-2")

        with pytest.raises(ValueError) as exc_info:
            service.discover_from_glue_database("testdb", "testdb.testtable")

        error_msg = str(exc_info.value)
        assert "no S3 location" in error_msg

    @patch("boto3.client")
    def test_discover_from_glue_database_uses_resolved_region(self, mock_boto3_client, tmp_path):
        """Test that resolved region is used for Glue client."""
        # Create test Parquet file
        test_file = tmp_path / "test.parquet"
        test_file.write_bytes(b"PAR1" + b"\x00" * 100 + b"PAR1")

        # Mock Glue response
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.get_table.return_value = {
            "Table": {
                "Parameters": {},
                "StorageDescriptor": {"Location": str(tmp_path)},
            }
        }

        # Test with custom region
        service = FileDiscoveryService(region="eu-west-1")
        service.discover_from_glue_database("testdb", "testdb.testtable")

        # Verify boto3 client was created with correct region
        mock_boto3_client.assert_called_once_with("glue", region_name="eu-west-1")


class TestFileDiscoveryServiceInit:
    """Tests for FileDiscoveryService initialization with region."""

    def test_init_with_region_override(self):
        """Test initialization with region override."""
        service = FileDiscoveryService(region="us-west-1")
        assert service._resolved_region == "us-west-1"

    def test_init_without_region(self, monkeypatch):
        """Test initialization without region uses resolution logic."""
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

        service = FileDiscoveryService()
        assert service._resolved_region == "us-east-2"

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization respects environment variables."""
        monkeypatch.setenv("AWS_REGION", "ap-south-1")

        service = FileDiscoveryService()
        assert service._resolved_region == "ap-south-1"


class TestS3PathDiscovery:
    """Tests for S3 path discovery."""

    @patch("pyarrow.parquet.ParquetFile")
    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    def test_discover_from_s3_single_file(self, mock_filetype, mock_s3fs_class, mock_pf_class):
        """Test discovering a single Parquet file from S3."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock file info for single file
        mock_file_info = MagicMock()
        mock_file_info.type = "File"
        mock_file_info.size = 1024
        mock_s3fs.get_file_info.return_value = mock_file_info

        # Mock ParquetFile to return row count
        mock_pf = MagicMock()
        mock_pf.metadata.num_rows = 500
        mock_pf_class.return_value = mock_pf

        # Test discovery
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_path("s3://bucket/path/file.parquet")

        assert len(files) == 1
        assert files[0].path == "s3://bucket/path/file.parquet"
        assert files[0].file_size_bytes == 1024
        assert files[0].record_count == 500
        assert files[0].source == "s3"

    @patch("pyarrow.parquet.ParquetFile")
    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    @patch("pyarrow.fs.FileSelector")
    def test_discover_from_s3_directory(
        self, mock_selector, mock_filetype, mock_s3fs_class, mock_pf_class
    ):
        """Test discovering Parquet files from S3 directory."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock directory file info
        mock_dir_info = MagicMock()
        mock_dir_info.type = "Directory"

        # Mock file infos for files in directory
        mock_file1 = MagicMock()
        mock_file1.type = "File"
        mock_file1.path = "bucket/path/file1.parquet"
        mock_file1.size = 1024

        mock_file2 = MagicMock()
        mock_file2.type = "File"
        mock_file2.path = "bucket/path/file2.parquet"
        mock_file2.size = 2048

        # Setup mock to return directory info first, then file list
        mock_s3fs.get_file_info.side_effect = [mock_dir_info, [mock_file1, mock_file2]]

        # Mock ParquetFile to return row counts
        mock_pf1 = MagicMock()
        mock_pf1.metadata.num_rows = 100
        mock_pf2 = MagicMock()
        mock_pf2.metadata.num_rows = 200
        mock_pf_class.side_effect = [mock_pf1, mock_pf2]

        # Test discovery
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_path("s3://bucket/path/")

        assert len(files) == 2
        assert files[0].path == "s3://bucket/path/file1.parquet"
        assert files[0].record_count == 100
        assert files[1].path == "s3://bucket/path/file2.parquet"
        assert files[1].record_count == 200

    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    def test_discover_from_s3_not_found(self, mock_filetype, mock_s3fs_class):
        """Test error when S3 path not found."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock not found
        mock_file_info = MagicMock()
        mock_file_info.type = "NotFound"
        mock_s3fs.get_file_info.return_value = mock_file_info

        service = FileDiscoveryService(region="us-east-2")

        with pytest.raises(FileNotFoundError) as exc_info:
            service.discover_from_path("s3://bucket/nonexistent/")

        assert "S3 path not found" in str(exc_info.value)

    @patch("pyarrow.parquet.ParquetFile")
    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    def test_discover_from_s3a_single_file(self, mock_filetype, mock_s3fs_class, mock_pf_class):
        """Test discovering a single Parquet file from S3 using s3a:// scheme."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock file info for single file
        mock_file_info = MagicMock()
        mock_file_info.type = "File"
        mock_file_info.size = 2048
        mock_s3fs.get_file_info.return_value = mock_file_info

        # Mock ParquetFile to return row count
        mock_pf = MagicMock()
        mock_pf.metadata.num_rows = 750
        mock_pf_class.return_value = mock_pf

        # Test discovery with s3a:// scheme
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_path("s3a://bucket/path/file.parquet")

        assert len(files) == 1
        assert files[0].path == "s3a://bucket/path/file.parquet"
        assert files[0].file_size_bytes == 2048
        assert files[0].record_count == 750
        assert files[0].source == "s3"

    @patch("pyarrow.parquet.ParquetFile")
    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    @patch("pyarrow.fs.FileSelector")
    def test_discover_from_s3a_directory(
        self, mock_selector, mock_filetype, mock_s3fs_class, mock_pf_class
    ):
        """Test discovering Parquet files from S3 directory using s3a:// scheme."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock directory file info
        mock_dir_info = MagicMock()
        mock_dir_info.type = "Directory"

        # Mock file infos for files in directory
        mock_file1 = MagicMock()
        mock_file1.type = "File"
        mock_file1.path = "bucket/data/file1.parquet"
        mock_file1.size = 512

        mock_file2 = MagicMock()
        mock_file2.type = "File"
        mock_file2.path = "bucket/data/file2.parquet"
        mock_file2.size = 1024

        # Setup mock to return directory info first, then file list
        mock_s3fs.get_file_info.side_effect = [mock_dir_info, [mock_file1, mock_file2]]

        # Mock ParquetFile to return row counts
        mock_pf1 = MagicMock()
        mock_pf1.metadata.num_rows = 50
        mock_pf2 = MagicMock()
        mock_pf2.metadata.num_rows = 100
        mock_pf_class.side_effect = [mock_pf1, mock_pf2]

        # Test discovery with s3a:// scheme
        service = FileDiscoveryService(region="us-east-2")
        files = service.discover_from_path("s3a://bucket/data/")

        assert len(files) == 2
        # Verify paths preserve s3a:// scheme
        assert files[0].path == "s3a://bucket/data/file1.parquet"
        assert files[0].record_count == 50
        assert files[1].path == "s3a://bucket/data/file2.parquet"
        assert files[1].record_count == 100

    @patch("pyarrow.fs.S3FileSystem")
    @patch("pyarrow.fs.FileType")
    def test_discover_from_s3_non_parquet_file_error(self, mock_filetype, mock_s3fs_class):
        """Test that non-parquet S3 files raise ValueError instead of returning empty list."""
        # Mock S3 filesystem
        mock_s3fs = MagicMock()
        mock_s3fs_class.return_value = mock_s3fs

        # Mock FileType enum
        mock_filetype.File = "File"
        mock_filetype.Directory = "Directory"
        mock_filetype.NotFound = "NotFound"

        # Mock file info for non-parquet file
        mock_file_info = MagicMock()
        mock_file_info.type = "File"
        mock_file_info.size = 1024
        mock_s3fs.get_file_info.return_value = mock_file_info

        service = FileDiscoveryService(region="us-east-2")

        # Test with .csv file
        with pytest.raises(ValueError) as exc_info:
            service.discover_from_path("s3://bucket/path/data.csv")

        error_msg = str(exc_info.value)
        assert "File is not a Parquet file" in error_msg
        assert ".parquet or .pq extension" in error_msg

        # Test with .json file
        with pytest.raises(ValueError) as exc_info:
            service.discover_from_path("s3://bucket/path/data.json")

        error_msg = str(exc_info.value)
        assert "File is not a Parquet file" in error_msg
