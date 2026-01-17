"""Tests for IcebergAdapter helper methods."""

import pytest

from tablesleuth.services.formats.iceberg import IcebergAdapter


class TestIcebergAdapterHelpers:
    """Tests for IcebergAdapter utility methods."""

    @pytest.fixture
    def adapter(self):
        """Create IcebergAdapter instance."""
        return IcebergAdapter()

    def test_parse_s3_tables_arn_valid(self, adapter):
        """Test parsing valid S3 Tables ARN."""
        arn = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog, table_id = result
        assert catalog == "s3tables"
        assert table_id == "db.table"

    def test_parse_s3_tables_arn_with_namespace(self, adapter):
        """Test parsing ARN with multi-level namespace."""
        arn = (
            "arn:aws:s3tables:us-west-2:987654321098:bucket/data-bucket/table/prod.analytics.events"
        )
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog, table_id = result
        assert catalog == "s3tables"
        assert table_id == "prod.analytics.events"

    def test_parse_s3_tables_arn_with_uuid(self, adapter):
        """Test parsing ARN with UUID table identifier."""
        arn = "arn:aws:s3tables:eu-west-1:111222333444:bucket/test-bucket/table/550e8400-e29b-41d4-a716-446655440000"
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog, table_id = result
        assert catalog == "s3tables"
        assert table_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_parse_s3_tables_arn_invalid_format(self, adapter):
        """Test parsing invalid ARN format."""
        invalid_arns = [
            "arn:aws:s3:us-east-1:123456:bucket/my-bucket",  # Wrong service
            "arn:aws:s3tables:us-east-1",  # Incomplete
            "not-an-arn",  # Not an ARN
            "",  # Empty string
            "arn:aws:s3tables:us-east-1:123456:invalid",  # Wrong resource format
        ]

        for arn in invalid_arns:
            result = adapter._parse_s3_tables_arn(arn)
            assert result is None, f"Expected None for invalid ARN: {arn}"

    def test_parse_s3_tables_arn_different_regions(self, adapter):
        """Test parsing ARNs from different regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        for region in regions:
            arn = f"arn:aws:s3tables:{region}:123456789012:bucket/test/table/db.table"
            result = adapter._parse_s3_tables_arn(arn)

            assert result is not None
            catalog, table_id = result
            assert catalog == "s3tables"
            assert table_id == "db.table"

    def test_file_uri_to_path_s3_uri(self, adapter):
        """Test S3 URI is preserved unchanged."""
        s3_uri = "s3://my-bucket/path/to/file.parquet"
        result = adapter._file_uri_to_path(s3_uri)
        assert result == s3_uri

    def test_file_uri_to_path_s3a_uri(self, adapter):
        """Test S3A URI is preserved unchanged."""
        s3a_uri = "s3a://my-bucket/path/to/file.parquet"
        result = adapter._file_uri_to_path(s3a_uri)
        assert result == s3a_uri

    def test_file_uri_to_path_unix_file_uri(self, adapter):
        """Test Unix file:// URI conversion."""
        file_uri = "file:///home/user/data/file.parquet"
        result = adapter._file_uri_to_path(file_uri)
        assert result == "/home/user/data/file.parquet"

    def test_file_uri_to_path_windows_file_uri(self, adapter):
        """Test Windows file:// URI conversion."""
        file_uri = "file:///C:/Users/user/data/file.parquet"
        result = adapter._file_uri_to_path(file_uri)
        assert result == "C:/Users/user/data/file.parquet"

    def test_file_uri_to_path_percent_encoded(self, adapter):
        """Test file:// URI with percent-encoded characters."""
        file_uri = "file:///path/with%20spaces/file%2Bname.parquet"
        result = adapter._file_uri_to_path(file_uri)
        assert result == "/path/with spaces/file+name.parquet"

    def test_file_uri_to_path_non_uri(self, adapter):
        """Test regular path without file:// prefix."""
        regular_path = "/home/user/data/file.parquet"
        result = adapter._file_uri_to_path(regular_path)
        assert result == regular_path

    def test_file_uri_to_path_relative_path(self, adapter):
        """Test relative path is preserved."""
        relative_path = "data/file.parquet"
        result = adapter._file_uri_to_path(relative_path)
        assert result == relative_path

    def test_file_uri_to_path_empty_string(self, adapter):
        """Test empty string handling."""
        result = adapter._file_uri_to_path("")
        assert result == ""

    def test_init_with_default_catalog(self):
        """Test initialization with default catalog."""
        adapter = IcebergAdapter(default_catalog="my_catalog")
        assert adapter._default_catalog == "my_catalog"

    def test_init_without_default_catalog(self):
        """Test initialization without default catalog."""
        adapter = IcebergAdapter()
        assert adapter._default_catalog is None


class TestIcebergAdapterARNPattern:
    """Tests for S3 Tables ARN regex pattern."""

    def test_arn_pattern_matches_valid_arn(self):
        """Test ARN pattern matches valid ARN."""
        from tablesleuth.services.formats.iceberg import IcebergAdapter

        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket/table/db.table"
        match = IcebergAdapter.S3_TABLES_ARN_PATTERN.match(arn)

        assert match is not None
        assert match.group("region") == "us-east-1"
        assert match.group("account") == "123456789012"
        assert match.group("bucket") == "my-bucket"
        assert match.group("table") == "db.table"

    def test_arn_pattern_extracts_components(self):
        """Test ARN pattern extracts all components correctly."""
        from tablesleuth.services.formats.iceberg import IcebergAdapter

        arn = "arn:aws:s3tables:eu-west-2:999888777666:bucket/data-lake/table/analytics.events"
        match = IcebergAdapter.S3_TABLES_ARN_PATTERN.match(arn)

        assert match is not None
        assert match.group("region") == "eu-west-2"
        assert match.group("account") == "999888777666"
        assert match.group("bucket") == "data-lake"
        assert match.group("table") == "analytics.events"

    def test_arn_pattern_rejects_invalid_arn(self):
        """Test ARN pattern rejects invalid ARN."""
        from tablesleuth.services.formats.iceberg import IcebergAdapter

        invalid_arns = [
            "arn:aws:s3:us-east-1:123456:bucket/my-bucket",
            "not-an-arn",
            "arn:aws:s3tables:us-east-1",
            "",
        ]

        for arn in invalid_arns:
            match = IcebergAdapter.S3_TABLES_ARN_PATTERN.match(arn)
            assert match is None, f"Pattern should not match: {arn}"
