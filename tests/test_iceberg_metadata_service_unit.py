"""Unit tests for IcebergMetadataService (mocked, no Iceberg tables required)."""

from unittest.mock import Mock, patch

import pytest

from tablesleuth.exceptions import SnapshotNotFoundError, TableLoadError
from tablesleuth.models.iceberg import IcebergSnapshotInfo, IcebergTableInfo
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService


class TestIcebergMetadataServiceInit:
    """Tests for IcebergMetadataService initialization."""

    def test_init_creates_adapter(self):
        """Test initialization creates IcebergAdapter."""
        service = IcebergMetadataService()
        assert hasattr(service, "_adapter")
        assert service._adapter is not None


class TestInferOperation:
    """Tests for _infer_operation method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IcebergMetadataService()

    def test_infer_append_operation(self, service):
        """Test inferring APPEND operation."""
        summary = {
            "added-data-files": "5",
            "added-records": "1000",
        }
        result = service._infer_operation(summary)
        assert result == "APPEND"

    def test_infer_mor_update_operation(self, service):
        """Test inferring MOR UPDATE operation."""
        summary = {
            "added-data-files": "3",
            "added-delete-files": "2",
            "added-records": "500",
        }
        result = service._infer_operation(summary)
        assert result == "UPDATE"

    def test_infer_mor_delete_operation(self, service):
        """Test inferring MOR DELETE operation."""
        summary = {
            "added-data-files": "0",
            "added-delete-files": "5",
            "deleted-records": "100",
        }
        result = service._infer_operation(summary)
        assert result == "DELETE"

    def test_infer_replace_operation(self, service):
        """Test inferring REPLACE operation."""
        summary = {
            "added-data-files": "5",
            "deleted-data-files": "3",
            "replaced-partitions": "partition1,partition2",
        }
        result = service._infer_operation(summary)
        assert result == "REPLACE"

    def test_infer_overwrite_operation_full(self, service):
        """Test inferring full OVERWRITE operation."""
        summary = {
            "added-data-files": "10",
            "deleted-data-files": "10",
            "total-data-files": "10",  # All files are new
        }
        result = service._infer_operation(summary)
        assert result == "OVERWRITE"

    def test_infer_overwrite_operation_partial(self, service):
        """Test inferring partial OVERWRITE operation."""
        summary = {
            "added-data-files": "5",
            "deleted-data-files": "3",
            "total-data-files": "15",  # Not all files are new
        }
        result = service._infer_operation(summary)
        assert result == "REPLACE"

    def test_infer_overwrite_operation_only_deletions(self, service):
        """Test inferring OVERWRITE with only deletions."""
        summary = {
            "added-data-files": "0",
            "deleted-data-files": "5",
        }
        result = service._infer_operation(summary)
        assert result == "OVERWRITE"

    def test_infer_update_from_records(self, service):
        """Test inferring UPDATE from record changes."""
        summary = {
            "added-records": "100",
            "deleted-records": "50",
        }
        result = service._infer_operation(summary)
        assert result == "UPDATE"

    def test_infer_unknown_operation(self, service):
        """Test inferring UNKNOWN when no indicators present."""
        summary = {}
        result = service._infer_operation(summary)
        assert result == "UNKNOWN"

    def test_infer_append_with_zero_deletes(self, service):
        """Test APPEND takes precedence over empty delete files."""
        summary = {
            "added-data-files": "5",
            "added-delete-files": "0",
            "deleted-data-files": "0",
        }
        result = service._infer_operation(summary)
        assert result == "APPEND"


class TestLoadTable:
    """Tests for load_table method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IcebergMetadataService()

    def test_load_table_no_arguments_raises_error(self, service):
        """Test loading table without arguments raises ValueError."""
        with pytest.raises(ValueError, match="Must provide either metadata_path"):
            service.load_table()

    def test_load_table_metadata_path_not_found(self, service):
        """Test loading table with non-existent metadata path."""
        with pytest.raises(TableLoadError, match="Metadata file not found"):
            service.load_table(metadata_path="/nonexistent/metadata.json")

    @patch("tablesleuth.services.iceberg_metadata_service.StaticTable")
    def test_load_table_from_metadata_path(self, mock_static_table, service, tmp_path):
        """Test loading table from metadata path."""
        # Create a temporary metadata file
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{}")

        # Mock the table
        mock_table = Mock()
        mock_table.metadata.format_version = 2
        mock_table.metadata.table_uuid = "test-uuid-123"
        mock_table.metadata.location = "s3://bucket/table"
        mock_table.current_snapshot.return_value = None
        mock_table.properties = {"key": "value"}

        mock_static_table.from_metadata.return_value = mock_table

        result = service.load_table(metadata_path=str(metadata_file))

        assert isinstance(result, IcebergTableInfo)
        assert result.format_version == 2
        assert result.table_uuid == "test-uuid-123"
        assert result.location == "s3://bucket/table"
        assert result.current_snapshot_id is None
        assert result.properties == {"key": "value"}

    @patch("tablesleuth.services.iceberg_metadata_service.load_catalog")
    def test_load_table_from_catalog(self, mock_load_catalog, service):
        """Test loading table from catalog."""
        # Mock catalog and table
        mock_catalog = Mock()
        mock_table = Mock()
        mock_table.metadata.format_version = 2
        mock_table.metadata.table_uuid = "catalog-uuid-456"
        mock_table.metadata.location = "s3://bucket/catalog-table"
        mock_table.metadata_location = "/path/to/metadata.json"
        mock_snapshot = Mock()
        mock_snapshot.snapshot_id = 12345
        mock_table.current_snapshot.return_value = mock_snapshot
        mock_table.properties = {}

        mock_catalog.load_table.return_value = mock_table
        mock_load_catalog.return_value = mock_catalog

        result = service.load_table(
            catalog_name="test_catalog",
            table_identifier="db.table",
        )

        assert isinstance(result, IcebergTableInfo)
        assert result.table_uuid == "catalog-uuid-456"
        assert result.current_snapshot_id == 12345
        mock_load_catalog.assert_called_once_with("test_catalog")
        mock_catalog.load_table.assert_called_once_with("db.table")

    @patch("tablesleuth.services.iceberg_metadata_service.load_catalog")
    def test_load_table_catalog_not_found(self, mock_load_catalog, service):
        """Test loading table with invalid catalog."""
        mock_load_catalog.side_effect = Exception("Catalog not found")

        with pytest.raises(TableLoadError, match="Failed to load catalog"):
            service.load_table(
                catalog_name="invalid_catalog",
                table_identifier="db.table",
            )

    @patch("tablesleuth.services.iceberg_metadata_service.load_catalog")
    def test_load_table_table_not_found(self, mock_load_catalog, service):
        """Test loading non-existent table from catalog."""
        mock_catalog = Mock()
        mock_catalog.load_table.side_effect = Exception("Table not found")
        mock_load_catalog.return_value = mock_catalog

        with pytest.raises(TableLoadError, match="Failed to load table"):
            service.load_table(
                catalog_name="test_catalog",
                table_identifier="db.nonexistent",
            )


class TestCompareSnapshots:
    """Tests for compare_snapshots method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IcebergMetadataService()

    @pytest.fixture
    def mock_table(self):
        """Create mock IcebergTableInfo."""
        mock_table = Mock(spec=IcebergTableInfo)
        mock_table.native_table = Mock()
        return mock_table

    def test_compare_snapshots_snapshot_not_found(self, service, mock_table):
        """Test comparing snapshots when one doesn't exist."""
        # Mock list_snapshots to return empty list
        with patch.object(service, "list_snapshots", return_value=[]):
            with pytest.raises(SnapshotNotFoundError, match="Snapshot .* not found"):
                service.compare_snapshots(mock_table, 12345, 67890)

    def test_compare_snapshots_calculates_differences(self, service, mock_table):
        """Test snapshot comparison calculates correct differences."""
        # Create mock snapshots
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=12345,
            parent_snapshot_id=None,
            timestamp_ms=1700000000000,
            operation="APPEND",
            summary={},
            manifest_list="/path/manifest1",
            schema_id=0,
            total_records=1000,
            total_data_files=5,
            total_delete_files=0,
            total_size_bytes=1024000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=67890,
            parent_snapshot_id=12345,
            timestamp_ms=1700001000000,
            operation="APPEND",
            summary={},
            manifest_list="/path/manifest2",
            schema_id=0,
            total_records=1500,
            total_data_files=8,
            total_delete_files=2,
            total_size_bytes=2048000,
            position_deletes=50,
            equality_deletes=0,
        )

        with patch.object(service, "list_snapshots", return_value=[snapshot_a, snapshot_b]):
            result = service.compare_snapshots(mock_table, 12345, 67890)

        assert result.snapshot_a == snapshot_a
        assert result.snapshot_b == snapshot_b
        assert result.data_files_added == 3  # 8 - 5
        assert result.data_files_removed == 0
        assert result.delete_files_added == 2  # 2 - 0
        assert result.delete_files_removed == 0
        assert result.records_added == 500  # 1500 - 1000
        assert result.records_deleted == 0
        assert result.records_delta == 500
        assert result.size_added_bytes == 1024000  # 2048000 - 1024000
        assert result.size_removed_bytes == 0
        assert result.size_delta_bytes == 1024000

    def test_compare_snapshots_with_deletions(self, service, mock_table):
        """Test snapshot comparison with file deletions."""
        snapshot_a = IcebergSnapshotInfo(
            snapshot_id=12345,
            parent_snapshot_id=None,
            timestamp_ms=1700000000000,
            operation="APPEND",
            summary={},
            manifest_list="/path/manifest1",
            schema_id=0,
            total_records=2000,
            total_data_files=10,
            total_delete_files=0,
            total_size_bytes=3000000,
            position_deletes=0,
            equality_deletes=0,
        )

        snapshot_b = IcebergSnapshotInfo(
            snapshot_id=67890,
            parent_snapshot_id=12345,
            timestamp_ms=1700001000000,
            operation="DELETE",
            summary={},
            manifest_list="/path/manifest2",
            schema_id=0,
            total_records=1500,
            total_data_files=8,
            total_delete_files=5,
            total_size_bytes=2500000,
            position_deletes=100,
            equality_deletes=0,
        )

        with patch.object(service, "list_snapshots", return_value=[snapshot_a, snapshot_b]):
            result = service.compare_snapshots(mock_table, 12345, 67890)

        assert result.data_files_added == 0
        assert result.data_files_removed == 2  # 10 - 8
        assert result.delete_files_added == 5
        assert result.records_added == 0
        assert result.records_deleted == 500  # 2000 - 1500
        assert result.records_delta == -500
        assert result.size_added_bytes == 0
        assert result.size_removed_bytes == 500000  # 3000000 - 2500000
        assert result.size_delta_bytes == -500000


class TestGetSchemaEvolution:
    """Tests for get_schema_evolution method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IcebergMetadataService()

    def test_get_schema_evolution_single_schema(self, service):
        """Test getting schema evolution with single schema."""
        # Create mock table with one schema
        mock_table = Mock(spec=IcebergTableInfo)
        mock_py_table = Mock()

        mock_field = Mock()
        mock_field.field_id = 1
        mock_field.name = "id"
        mock_field.field_type = "long"
        mock_field.required = True
        mock_field.doc = "ID field"

        mock_schema = Mock()
        mock_schema.schema_id = 0
        mock_schema.fields = [mock_field]

        mock_py_table.metadata.schemas = [mock_schema]
        mock_table.native_table = mock_py_table

        result = service.get_schema_evolution(mock_table)

        assert len(result) == 1
        assert result[0].schema_id == 0
        assert len(result[0].fields) == 1
        assert result[0].fields[0].name == "id"
        assert result[0].fields[0].field_type == "long"

    def test_get_schema_evolution_multiple_schemas(self, service):
        """Test getting schema evolution with multiple schemas."""
        mock_table = Mock(spec=IcebergTableInfo)
        mock_py_table = Mock()

        # Schema v0
        mock_field1 = Mock()
        mock_field1.field_id = 1
        mock_field1.name = "id"
        mock_field1.field_type = "long"
        mock_field1.required = True
        mock_field1.doc = None

        mock_schema1 = Mock()
        mock_schema1.schema_id = 0
        mock_schema1.fields = [mock_field1]

        # Schema v1 (added field)
        mock_field2 = Mock()
        mock_field2.field_id = 2
        mock_field2.name = "name"
        mock_field2.field_type = "string"
        mock_field2.required = False
        mock_field2.doc = "Name field"

        mock_schema2 = Mock()
        mock_schema2.schema_id = 1
        mock_schema2.fields = [mock_field1, mock_field2]

        mock_py_table.metadata.schemas = [mock_schema1, mock_schema2]
        mock_table.native_table = mock_py_table

        result = service.get_schema_evolution(mock_table)

        assert len(result) == 2
        assert result[0].schema_id == 0
        assert len(result[0].fields) == 1
        assert result[1].schema_id == 1
        assert len(result[1].fields) == 2
        assert result[1].fields[1].name == "name"


class TestListSnapshots:
    """Tests for list_snapshots method."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IcebergMetadataService()

    def test_list_snapshots_empty(self, service):
        """Test listing snapshots when table has none."""
        mock_table = Mock(spec=IcebergTableInfo)
        mock_py_table = Mock()
        mock_py_table.snapshots.return_value = []
        mock_table.native_table = mock_py_table

        result = service.list_snapshots(mock_table)

        assert result == []

    def test_list_snapshots_sorted_by_timestamp(self, service):
        """Test snapshots are sorted by timestamp descending."""
        mock_table = Mock(spec=IcebergTableInfo)
        mock_py_table = Mock()

        # Create snapshots with different timestamps
        snap1 = Mock()
        snap1.snapshot_id = 1
        snap1.parent_snapshot_id = None
        snap1.timestamp_ms = 1700000000000
        snap1.summary = None
        snap1.manifest_list = "/path/manifest1"
        snap1.schema_id = 0
        snap1.operation = None

        snap2 = Mock()
        snap2.snapshot_id = 2
        snap2.parent_snapshot_id = 1
        snap2.timestamp_ms = 1700002000000  # Later
        snap2.summary = None
        snap2.manifest_list = "/path/manifest2"
        snap2.schema_id = 0
        snap2.operation = None

        snap3 = Mock()
        snap3.snapshot_id = 3
        snap3.parent_snapshot_id = 2
        snap3.timestamp_ms = 1700001000000  # Middle
        snap3.summary = None
        snap3.manifest_list = "/path/manifest3"
        snap3.schema_id = 0
        snap3.operation = None

        mock_py_table.snapshots.return_value = [snap1, snap2, snap3]
        mock_table.native_table = mock_py_table

        result = service.list_snapshots(mock_table)

        # Should be sorted by timestamp descending (most recent first)
        assert len(result) == 3
        assert result[0].snapshot_id == 2  # Latest
        assert result[1].snapshot_id == 3  # Middle
        assert result[2].snapshot_id == 1  # Earliest

    def test_list_snapshots_extracts_summary_metrics(self, service):
        """Test snapshot summary metrics are extracted correctly."""
        mock_table = Mock(spec=IcebergTableInfo)
        mock_py_table = Mock()

        snap = Mock()
        snap.snapshot_id = 1
        snap.parent_snapshot_id = None
        snap.timestamp_ms = 1700000000000
        snap.manifest_list = "/path/manifest"
        snap.schema_id = 0
        snap.operation = "append"

        # Mock summary with additional_properties
        mock_summary = Mock()
        mock_summary.additional_properties = {
            "total-records": "1000",
            "total-data-files": "5",
            "total-delete-files": "0",
            "total-files-size": "1024000",
            "total-position-deletes": "0",
            "total-equality-deletes": "0",
            "operation": "append",
        }
        snap.summary = mock_summary

        mock_py_table.snapshots.return_value = [snap]
        mock_table.native_table = mock_py_table

        result = service.list_snapshots(mock_table)

        assert len(result) == 1
        assert result[0].total_records == 1000
        assert result[0].total_data_files == 5
        assert result[0].total_delete_files == 0
        assert result[0].total_size_bytes == 1024000
        assert result[0].operation == "append"
