"""Tests for FileSystem service."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pyarrow.fs as pafs
import pytest

from tablesleuth.services.filesystem import FileSystem
from tablesleuth.utils.path_utils import is_s3_path


class TestFileSystem:
    """Tests for FileSystem class."""

    def test_initialization_with_default_region(self) -> None:
        """Test FileSystem initializes with default region."""
        with patch.dict(os.environ, {}, clear=True):
            fs = FileSystem()
            assert fs.region == "us-east-2"

    def test_initialization_with_aws_region_env(self) -> None:
        """Test FileSystem uses AWS_REGION environment variable."""
        with patch.dict(os.environ, {"AWS_REGION": "us-west-1"}):
            fs = FileSystem()
            assert fs.region == "us-west-1"

    def test_initialization_with_aws_default_region_env(self) -> None:
        """Test FileSystem uses AWS_DEFAULT_REGION environment variable."""
        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "eu-west-1"}, clear=True):
            fs = FileSystem()
            assert fs.region == "eu-west-1"

    def test_initialization_with_explicit_region(self) -> None:
        """Test FileSystem uses explicitly provided region."""
        fs = FileSystem(region="ap-southeast-1")
        assert fs.region == "ap-southeast-1"

    def test_is_s3_path_with_s3_url(self) -> None:
        """Test is_s3_path utility returns True for S3 URLs."""
        assert is_s3_path("s3://bucket/key") is True
        assert is_s3_path("s3://my-bucket/path/to/file.parquet") is True
        assert is_s3_path("s3a://bucket/key") is True
        assert is_s3_path("s3n://bucket/key") is True

    def test_is_s3_path_with_local_path(self) -> None:
        """Test is_s3_path utility returns False for local paths."""
        assert is_s3_path("/local/path/file.parquet") is False
        assert is_s3_path("relative/path/file.parquet") is False
        assert is_s3_path("file.parquet") is False

    def test_normalize_s3_path(self) -> None:
        """Test normalize_s3_path removes S3 scheme prefixes."""
        fs = FileSystem()
        assert fs.normalize_s3_path("s3://bucket/key") == "bucket/key"
        assert (
            fs.normalize_s3_path("s3://my-bucket/path/to/file.parquet")
            == "my-bucket/path/to/file.parquet"
        )
        # Test s3a:// and s3n:// schemes
        assert fs.normalize_s3_path("s3a://bucket/key") == "bucket/key"
        assert fs.normalize_s3_path("s3n://bucket/key") == "bucket/key"

    def test_normalize_s3_path_with_local_path(self) -> None:
        """Test normalize_s3_path returns local path unchanged."""
        fs = FileSystem()
        local_path = "/local/path/file.parquet"
        assert fs.normalize_s3_path(local_path) == local_path

    def test_exists_local_file_exists(self, tmp_path: Path) -> None:
        """Test exists returns True for existing local file."""
        fs = FileSystem()
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        assert fs.exists(str(test_file)) is True

    def test_exists_local_file_not_exists(self, tmp_path: Path) -> None:
        """Test exists returns False for non-existing local file."""
        fs = FileSystem()
        test_file = tmp_path / "nonexistent.txt"

        assert fs.exists(str(test_file)) is False

    def test_exists_s3_file_exists(self) -> None:
        """Test exists returns True for existing S3 file."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_class:
            mock_s3_fs = Mock()
            mock_file_info = Mock()
            mock_file_info.type = pafs.FileType.File
            mock_s3_fs.get_file_info = Mock(return_value=mock_file_info)
            mock_s3_class.return_value = mock_s3_fs

            fs = FileSystem()
            assert fs.exists("s3://bucket/key") is True
            mock_s3_fs.get_file_info.assert_called_once_with("bucket/key")

    def test_exists_s3_file_not_exists(self) -> None:
        """Test exists returns False for non-existing S3 file."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_class:
            mock_s3_fs = Mock()
            mock_file_info = Mock()
            mock_file_info.type = pafs.FileType.NotFound
            mock_s3_fs.get_file_info = Mock(return_value=mock_file_info)
            mock_s3_class.return_value = mock_s3_fs

            fs = FileSystem()
            assert fs.exists("s3://bucket/nonexistent") is False

    def test_exists_s3_error_handling(self) -> None:
        """Test exists handles S3 errors gracefully."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_class:
            mock_s3_fs = Mock()
            mock_s3_fs.get_file_info = Mock(side_effect=Exception("S3 error"))
            mock_s3_class.return_value = mock_s3_fs

            fs = FileSystem()
            assert fs.exists("s3://bucket/key") is False

    def test_get_size_local_file(self, tmp_path: Path) -> None:
        """Test get_size returns correct size for local file."""
        fs = FileSystem()
        test_file = tmp_path / "test.txt"
        content = "test content with some data"
        test_file.write_text(content)

        size = fs.get_size(str(test_file))
        assert size == len(content.encode())

    def test_get_size_s3_file(self) -> None:
        """Test get_size returns correct size for S3 file."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_class:
            mock_s3_fs = Mock()
            mock_file_info = Mock()
            mock_file_info.size = 12345
            mock_s3_fs.get_file_info = Mock(return_value=mock_file_info)
            mock_s3_class.return_value = mock_s3_fs

            fs = FileSystem()
            size = fs.get_size("s3://bucket/key")
            assert size == 12345
            mock_s3_fs.get_file_info.assert_called_once_with("bucket/key")

    def test_open_file_local_read(self, tmp_path: Path) -> None:
        """Test open_file opens local file for reading."""
        fs = FileSystem()
        test_file = tmp_path / "test.txt"
        content = "test content"
        test_file.write_text(content)

        with fs.open_file(str(test_file), "rb") as f:
            data = f.read()
            assert data.decode() == content

    def test_open_file_s3_read(self) -> None:
        """Test open_file opens S3 file for reading."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_class:
            mock_s3_fs = Mock()
            mock_file = Mock()
            mock_file.read = Mock(return_value=b"s3 content")
            mock_s3_fs.open_input_file = Mock(return_value=mock_file)
            mock_s3_class.return_value = mock_s3_fs

            fs = FileSystem()
            file_obj = fs.open_file("s3://bucket/key")
            assert file_obj == mock_file
            mock_s3_fs.open_input_file.assert_called_once_with("bucket/key")

    def test_get_filesystem_local(self) -> None:
        """Test get_filesystem returns LocalFileSystem for local paths."""
        fs = FileSystem()
        filesystem = fs.get_filesystem("/local/path/file.parquet")

        assert isinstance(filesystem, pafs.LocalFileSystem)

    def test_get_filesystem_s3(self) -> None:
        """Test get_filesystem returns S3FileSystem for S3 paths."""
        fs = FileSystem()
        filesystem = fs.get_filesystem("s3://bucket/key")

        assert isinstance(filesystem, pafs.S3FileSystem)

    def test_region_property(self) -> None:
        """Test region property returns configured region."""
        fs = FileSystem(region="us-west-2")
        assert fs.region == "us-west-2"

    def test_s3_filesystem_initialization_with_region(self) -> None:
        """Test S3 filesystem is initialized with correct region."""
        with patch("pyarrow.fs.S3FileSystem") as mock_s3_fs:
            fs = FileSystem(region="eu-central-1")
            mock_s3_fs.assert_called_once_with(region="eu-central-1")

    def test_open_file_local_write_mode(self, tmp_path: Path) -> None:
        """Test open_file can open local file in write mode."""
        fs = FileSystem()
        test_file = tmp_path / "test_write.txt"

        with fs.open_file(str(test_file), "wb") as f:
            f.write(b"written content")

        assert test_file.read_text() == "written content"

    def test_exists_handles_path_object(self, tmp_path: Path) -> None:
        """Test exists handles Path objects correctly."""
        fs = FileSystem()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Should work with Path object converted to string
        assert fs.exists(str(test_file)) is True
