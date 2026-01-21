"""Tests for AWS S3 Tables ARN parsing."""

import pytest

from tablesleuth.services.formats.iceberg import IcebergAdapter


class TestS3TablesARN:
    """Test S3 Tables ARN parsing and handling."""

    def test_parse_valid_s3_tables_arn(self):
        """Test parsing a valid S3 Tables ARN."""
        adapter = IcebergAdapter()

        arn = "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.lineitem"
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog_name, table_identifier = result
        assert catalog_name == "s3tables"
        assert table_identifier == "tpch.lineitem"

    def test_parse_s3_tables_arn_with_nested_namespace(self):
        """Test parsing S3 Tables ARN with multi-level namespace."""
        adapter = IcebergAdapter()

        arn = "arn:aws:s3tables:eu-west-1:123456789012:bucket/my-bucket/table/db.schema.table"
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog_name, table_identifier = result
        assert catalog_name == "s3tables"
        assert table_identifier == "db.schema.table"

    def test_parse_s3_tables_arn_different_region(self):
        """Test parsing S3 Tables ARN from different regions."""
        adapter = IcebergAdapter()

        test_cases = [
            (
                "arn:aws:s3tables:us-west-2:111111111111:bucket/west-bucket/table/db.table",
                "db.table",
            ),
            (
                "arn:aws:s3tables:ap-southeast-1:222222222222:bucket/asia-bucket/table/prod.users",
                "prod.users",
            ),
            (
                "arn:aws:s3tables:eu-central-1:333333333333:bucket/eu-bucket/table/analytics.events",
                "analytics.events",
            ),
        ]

        for arn, expected_table in test_cases:
            result = adapter._parse_s3_tables_arn(arn)
            assert result is not None
            catalog_name, table_identifier = result
            assert catalog_name == "s3tables"
            assert table_identifier == expected_table

    def test_parse_invalid_arn_returns_none(self):
        """Test that invalid ARNs return None."""
        adapter = IcebergAdapter()

        invalid_arns = [
            "not-an-arn",
            "arn:aws:s3:us-east-1:123456789012:bucket/my-bucket",  # S3 bucket, not S3 Tables
            "arn:aws:glue:us-east-1:123456789012:table/db/table",  # Glue table
            "arn:aws:s3tables:us-east-1:123456789012:invalid",  # Missing bucket/table parts
            "",
            "db.table",  # Regular table identifier
        ]

        for arn in invalid_arns:
            result = adapter._parse_s3_tables_arn(arn)
            assert result is None, f"Expected None for invalid ARN: {arn}"

    def test_parse_s3_tables_arn_with_special_characters(self):
        """Test parsing ARN with special characters in names."""
        adapter = IcebergAdapter()

        arn = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket-123/table/db_prod.table_v2"
        result = adapter._parse_s3_tables_arn(arn)

        assert result is not None
        catalog_name, table_identifier = result
        assert catalog_name == "s3tables"  # Default catalog
        assert table_identifier == "db_prod.table_v2"

    def test_parse_s3_tables_arn_with_custom_catalog(self):
        """Test parsing ARN with custom catalog name."""
        adapter = IcebergAdapter()

        arn = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"
        result = adapter._parse_s3_tables_arn(arn, catalog_name="tpch-s3tables")

        assert result is not None
        catalog_name, table_identifier = result
        assert catalog_name == "tpch-s3tables"  # Custom catalog
        assert table_identifier == "db.table"

    def test_parse_s3_tables_arn_default_vs_custom_catalog(self):
        """Test that default catalog is used when no catalog_name provided."""
        adapter = IcebergAdapter()

        arn = "arn:aws:s3tables:us-east-2:123456789012:bucket/my-bucket/table/db.table"

        # Without catalog_name - should use default "s3tables"
        result_default = adapter._parse_s3_tables_arn(arn)
        assert result_default is not None
        catalog_default, _ = result_default
        assert catalog_default == "s3tables"

        # With catalog_name - should use provided name
        result_custom = adapter._parse_s3_tables_arn(arn, catalog_name="my-custom-catalog")
        assert result_custom is not None
        catalog_custom, _ = result_custom
        assert catalog_custom == "my-custom-catalog"

    def test_arn_pattern_regex(self):
        """Test the ARN regex pattern directly."""
        adapter = IcebergAdapter()

        valid_arn = "arn:aws:s3tables:us-east-2:835323357340:bucket/tpch-sf100/table/tpch.lineitem"
        match = adapter.S3_TABLES_ARN_PATTERN.match(valid_arn)

        assert match is not None
        assert match.group("region") == "us-east-2"
        assert match.group("account") == "835323357340"
        assert match.group("bucket") == "tpch-sf100"
        assert match.group("table") == "tpch.lineitem"
