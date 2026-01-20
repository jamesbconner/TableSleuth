"""Tests for path utility functions."""

from __future__ import annotations

import pytest

from tablesleuth.utils.path_utils import (
    get_storage_type,
    is_azure_path,
    is_cloud_path,
    is_gcs_path,
    is_hdfs_path,
    is_local_path,
    is_s3_path,
    normalize_s3_scheme,
    should_check_local_exists,
    strip_scheme,
    validate_local_path_exists,
)


class TestS3PathDetection:
    """Tests for S3 path detection."""

    def test_is_s3_path_with_s3_scheme(self):
        """Test detection of s3:// paths."""
        assert is_s3_path("s3://bucket/path/file.parquet")
        assert is_s3_path("s3://bucket/file.parquet")
        assert is_s3_path("S3://BUCKET/FILE.PARQUET")  # Case insensitive

    def test_is_s3_path_with_s3a_scheme(self):
        """Test detection of s3a:// paths."""
        assert is_s3_path("s3a://bucket/path/file.parquet")
        assert is_s3_path("S3A://BUCKET/FILE.PARQUET")

    def test_is_s3_path_with_s3n_scheme(self):
        """Test detection of s3n:// paths."""
        assert is_s3_path("s3n://bucket/path/file.parquet")
        assert is_s3_path("S3N://BUCKET/FILE.PARQUET")

    def test_is_s3_path_with_local_path(self):
        """Test that local paths are not detected as S3."""
        assert not is_s3_path("/local/path/file.parquet")
        assert not is_s3_path("C:\\Windows\\path\\file.parquet")
        assert not is_s3_path("./relative/path/file.parquet")

    def test_is_s3_path_with_other_cloud_schemes(self):
        """Test that other cloud schemes are not detected as S3."""
        assert not is_s3_path("gs://bucket/file.parquet")
        assert not is_s3_path("abfs://container/file.parquet")
        assert not is_s3_path("hdfs://namenode/file.parquet")


class TestCloudPathDetection:
    """Tests for general cloud path detection."""

    def test_is_cloud_path_with_s3(self):
        """Test cloud detection for S3 paths."""
        assert is_cloud_path("s3://bucket/file.parquet")
        assert is_cloud_path("s3a://bucket/file.parquet")
        assert is_cloud_path("s3n://bucket/file.parquet")

    def test_is_cloud_path_with_gcs(self):
        """Test cloud detection for GCS paths."""
        assert is_cloud_path("gs://bucket/file.parquet")
        assert is_cloud_path("gcs://bucket/file.parquet")

    def test_is_cloud_path_with_azure(self):
        """Test cloud detection for Azure paths."""
        assert is_cloud_path("abfs://container/file.parquet")
        assert is_cloud_path("abfss://container/file.parquet")
        assert is_cloud_path("wasb://container/file.parquet")
        assert is_cloud_path("wasbs://container/file.parquet")

    def test_is_cloud_path_with_hdfs(self):
        """Test cloud detection for HDFS paths."""
        assert is_cloud_path("hdfs://namenode/file.parquet")
        assert is_cloud_path("viewfs://namenode/file.parquet")

    def test_is_cloud_path_with_local(self):
        """Test that local paths are not detected as cloud."""
        assert not is_cloud_path("/local/path/file.parquet")
        assert not is_cloud_path("C:\\Windows\\path\\file.parquet")
        assert not is_cloud_path("./relative/path/file.parquet")


class TestGCSPathDetection:
    """Tests for GCS path detection."""

    def test_is_gcs_path_with_gs_scheme(self):
        """Test detection of gs:// paths."""
        assert is_gcs_path("gs://bucket/file.parquet")
        assert is_gcs_path("GS://BUCKET/FILE.PARQUET")

    def test_is_gcs_path_with_gcs_scheme(self):
        """Test detection of gcs:// paths."""
        assert is_gcs_path("gcs://bucket/file.parquet")
        assert is_gcs_path("GCS://BUCKET/FILE.PARQUET")

    def test_is_gcs_path_with_non_gcs(self):
        """Test that non-GCS paths are not detected."""
        assert not is_gcs_path("s3://bucket/file.parquet")
        assert not is_gcs_path("/local/path/file.parquet")


class TestAzurePathDetection:
    """Tests for Azure path detection."""

    def test_is_azure_path_with_abfs(self):
        """Test detection of abfs:// and abfss:// paths."""
        assert is_azure_path("abfs://container/file.parquet")
        assert is_azure_path("abfss://container/file.parquet")

    def test_is_azure_path_with_wasb(self):
        """Test detection of wasb:// and wasbs:// paths."""
        assert is_azure_path("wasb://container/file.parquet")
        assert is_azure_path("wasbs://container/file.parquet")

    def test_is_azure_path_with_non_azure(self):
        """Test that non-Azure paths are not detected."""
        assert not is_azure_path("s3://bucket/file.parquet")
        assert not is_azure_path("/local/path/file.parquet")


class TestHDFSPathDetection:
    """Tests for HDFS path detection."""

    def test_is_hdfs_path_with_hdfs_scheme(self):
        """Test detection of hdfs:// paths."""
        assert is_hdfs_path("hdfs://namenode/file.parquet")
        assert is_hdfs_path("HDFS://NAMENODE/FILE.PARQUET")

    def test_is_hdfs_path_with_viewfs_scheme(self):
        """Test detection of viewfs:// paths."""
        assert is_hdfs_path("viewfs://namenode/file.parquet")
        assert is_hdfs_path("VIEWFS://NAMENODE/FILE.PARQUET")

    def test_is_hdfs_path_with_non_hdfs(self):
        """Test that non-HDFS paths are not detected."""
        assert not is_hdfs_path("s3://bucket/file.parquet")
        assert not is_hdfs_path("/local/path/file.parquet")


class TestStorageTypeDetection:
    """Tests for storage type detection."""

    def test_get_storage_type_s3(self):
        """Test storage type detection for S3."""
        assert get_storage_type("s3://bucket/file.parquet") == "s3"
        assert get_storage_type("s3a://bucket/file.parquet") == "s3"
        assert get_storage_type("s3n://bucket/file.parquet") == "s3"

    def test_get_storage_type_gcs(self):
        """Test storage type detection for GCS."""
        assert get_storage_type("gs://bucket/file.parquet") == "gcs"
        assert get_storage_type("gcs://bucket/file.parquet") == "gcs"

    def test_get_storage_type_azure(self):
        """Test storage type detection for Azure."""
        assert get_storage_type("abfs://container/file.parquet") == "azure"
        assert get_storage_type("abfss://container/file.parquet") == "azure"
        assert get_storage_type("wasb://container/file.parquet") == "azure"
        assert get_storage_type("wasbs://container/file.parquet") == "azure"

    def test_get_storage_type_hdfs(self):
        """Test storage type detection for HDFS."""
        assert get_storage_type("hdfs://namenode/file.parquet") == "hdfs"
        assert get_storage_type("viewfs://namenode/file.parquet") == "hdfs"

    def test_get_storage_type_local(self):
        """Test storage type detection for local paths."""
        assert get_storage_type("/local/path/file.parquet") == "local"
        assert get_storage_type("C:\\Windows\\path\\file.parquet") == "local"
        assert get_storage_type("./relative/path/file.parquet") == "local"


class TestLocalPathDetection:
    """Tests for local path detection."""

    def test_is_local_path_with_absolute_unix(self):
        """Test detection of absolute Unix paths."""
        assert is_local_path("/local/path/file.parquet")
        assert is_local_path("/usr/bin/python")

    def test_is_local_path_with_absolute_windows(self):
        """Test detection of absolute Windows paths."""
        assert is_local_path("C:\\Windows\\path\\file.parquet")
        assert is_local_path("D:\\data\\file.parquet")

    def test_is_local_path_with_relative(self):
        """Test detection of relative paths."""
        assert is_local_path("./relative/path/file.parquet")
        assert is_local_path("../parent/file.parquet")
        assert is_local_path("file.parquet")

    def test_is_local_path_with_cloud(self):
        """Test that cloud paths are not detected as local."""
        assert not is_local_path("s3://bucket/file.parquet")
        assert not is_local_path("gs://bucket/file.parquet")
        assert not is_local_path("abfs://container/file.parquet")


class TestShouldCheckLocalExists:
    """Tests for should_check_local_exists helper."""

    def test_should_check_local_exists_for_local_paths(self):
        """Test that local paths should be checked."""
        assert should_check_local_exists("/local/path/file.parquet")
        assert should_check_local_exists("./relative/file.parquet")

    def test_should_check_local_exists_for_cloud_paths(self):
        """Test that cloud paths should not be checked locally."""
        assert not should_check_local_exists("s3://bucket/file.parquet")
        assert not should_check_local_exists("s3a://bucket/file.parquet")
        assert not should_check_local_exists("gs://bucket/file.parquet")
        assert not should_check_local_exists("abfs://container/file.parquet")


class TestValidateLocalPathExists:
    """Tests for validate_local_path_exists."""

    def test_validate_local_path_exists_with_existing_file(self, tmp_path):
        """Test validation of existing local file."""
        test_file = tmp_path / "test.parquet"
        test_file.write_text("test")

        assert validate_local_path_exists(str(test_file))

    def test_validate_local_path_exists_with_nonexistent_file(self):
        """Test validation of nonexistent local file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            validate_local_path_exists("/nonexistent/path/file.parquet")

        assert "Path not found" in str(exc_info.value)

    def test_validate_local_path_exists_with_cloud_path(self):
        """Test that cloud paths are not validated (assumed valid)."""
        # Cloud paths should not raise errors - they're validated by cloud libraries
        assert validate_local_path_exists("s3://bucket/file.parquet")
        assert validate_local_path_exists("s3a://bucket/file.parquet")
        assert validate_local_path_exists("gs://bucket/file.parquet")


class TestNormalizeS3Scheme:
    """Tests for S3 scheme normalization."""

    def test_normalize_s3_scheme_with_s3a(self):
        """Test normalization of s3a:// to s3://."""
        assert normalize_s3_scheme("s3a://bucket/file.parquet") == "s3://bucket/file.parquet"

    def test_normalize_s3_scheme_with_s3n(self):
        """Test normalization of s3n:// to s3://."""
        assert normalize_s3_scheme("s3n://bucket/file.parquet") == "s3://bucket/file.parquet"

    def test_normalize_s3_scheme_with_s3(self):
        """Test that s3:// is unchanged."""
        assert normalize_s3_scheme("s3://bucket/file.parquet") == "s3://bucket/file.parquet"

    def test_normalize_s3_scheme_with_non_s3(self):
        """Test that non-S3 paths are unchanged."""
        assert normalize_s3_scheme("gs://bucket/file.parquet") == "gs://bucket/file.parquet"
        assert normalize_s3_scheme("/local/path/file.parquet") == "/local/path/file.parquet"

    def test_normalize_s3_scheme_case_insensitive(self):
        """Test that S3 scheme normalization is case-insensitive."""
        # Uppercase schemes
        assert normalize_s3_scheme("S3://bucket/file.parquet") == "s3://bucket/file.parquet"
        assert normalize_s3_scheme("S3A://bucket/file.parquet") == "s3://bucket/file.parquet"
        assert normalize_s3_scheme("S3N://bucket/file.parquet") == "s3://bucket/file.parquet"

        # Mixed case schemes
        assert normalize_s3_scheme("S3a://bucket/file.parquet") == "s3://bucket/file.parquet"
        assert normalize_s3_scheme("s3A://bucket/file.parquet") == "s3://bucket/file.parquet"
        assert normalize_s3_scheme("S3n://bucket/file.parquet") == "s3://bucket/file.parquet"
        assert normalize_s3_scheme("s3N://bucket/file.parquet") == "s3://bucket/file.parquet"


class TestStripScheme:
    """Tests for scheme stripping."""

    def test_strip_scheme_with_s3(self):
        """Test stripping s3:// scheme."""
        assert strip_scheme("s3://bucket/path/file.parquet") == "bucket/path/file.parquet"

    def test_strip_scheme_with_s3a(self):
        """Test stripping s3a:// scheme."""
        assert strip_scheme("s3a://bucket/path/file.parquet") == "bucket/path/file.parquet"

    def test_strip_scheme_with_s3n(self):
        """Test stripping s3n:// scheme."""
        assert strip_scheme("s3n://bucket/path/file.parquet") == "bucket/path/file.parquet"

    def test_strip_scheme_with_gs(self):
        """Test stripping gs:// scheme."""
        assert strip_scheme("gs://bucket/path/file.parquet") == "bucket/path/file.parquet"

    def test_strip_scheme_with_gcs(self):
        """Test stripping gcs:// scheme."""
        assert strip_scheme("gcs://bucket/path/file.parquet") == "bucket/path/file.parquet"

    def test_strip_scheme_with_azure(self):
        """Test stripping Azure schemes."""
        assert strip_scheme("abfs://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("abfss://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("wasb://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("wasbs://container/file.parquet") == "container/file.parquet"

    def test_strip_scheme_with_hdfs(self):
        """Test stripping HDFS schemes."""
        assert strip_scheme("hdfs://namenode/path/file.parquet") == "namenode/path/file.parquet"
        assert strip_scheme("viewfs://namenode/path/file.parquet") == "namenode/path/file.parquet"

    def test_strip_scheme_with_local_path(self):
        """Test that local paths are unchanged."""
        assert strip_scheme("/local/path/file.parquet") == "/local/path/file.parquet"
        assert strip_scheme("./relative/file.parquet") == "./relative/file.parquet"

    def test_strip_scheme_case_insensitive(self):
        """Test that scheme stripping is case-insensitive."""
        # Uppercase schemes
        assert strip_scheme("S3://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("S3A://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("S3N://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("GS://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("GCS://bucket/file.parquet") == "bucket/file.parquet"

        # Mixed case schemes
        assert strip_scheme("S3a://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("s3A://bucket/file.parquet") == "bucket/file.parquet"
        assert strip_scheme("Gs://bucket/file.parquet") == "bucket/file.parquet"

        # Azure schemes
        assert strip_scheme("ABFS://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("ABFSS://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("WASB://container/file.parquet") == "container/file.parquet"
        assert strip_scheme("WASBS://container/file.parquet") == "container/file.parquet"

        # HDFS schemes
        assert strip_scheme("HDFS://namenode/file.parquet") == "namenode/file.parquet"
        assert strip_scheme("VIEWFS://namenode/file.parquet") == "namenode/file.parquet"
