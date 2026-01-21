"""Unit tests for schema evolution tracking in Delta Lake adapter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tablesleuth.services.formats.delta import DeltaAdapter


class TestSchemaEvolution:
    """Test suite for schema evolution tracking."""

    @pytest.fixture
    def temp_delta_table_with_schema_changes(self) -> Path:
        """Create a Delta table with schema evolution across versions.

        Version 0: Initial schema with id (integer)
        Version 1: Add name (string) column
        Version 2: Add age (integer) column
        Version 3: Change age type from integer to long
        Version 4: Remove name column
        """
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Version 0: Initial schema
        version_0 = delta_log_dir / "00000000000000000000.json"
        with open(version_0, "w") as f:
            protocol = {
                "protocol": {
                    "minReaderVersion": 1,
                    "minWriterVersion": 2,
                }
            }
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334625000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334625000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00000.snappy.parquet",
                    "size": 1024,
                    "modificationTime": 1705334625000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(protocol) + "\n")
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Version 1: Add name column
        version_1 = delta_log_dir / "00000000000000000001.json"
        with open(version_1, "w") as f:
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"name","type":"string","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334626000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334626000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00001.snappy.parquet",
                    "size": 2048,
                    "modificationTime": 1705334626000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Version 2: Add age column
        version_2 = delta_log_dir / "00000000000000000002.json"
        with open(version_2, "w") as f:
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"name","type":"string","nullable":true,"metadata":{}},{"name":"age","type":"integer","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334627000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334627000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00002.snappy.parquet",
                    "size": 3072,
                    "modificationTime": 1705334627000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Version 3: Change age type from integer to long
        version_3 = delta_log_dir / "00000000000000000003.json"
        with open(version_3, "w") as f:
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"name","type":"string","nullable":true,"metadata":{}},{"name":"age","type":"long","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334628000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334628000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00003.snappy.parquet",
                    "size": 4096,
                    "modificationTime": 1705334628000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        # Version 4: Remove name column
        version_4 = delta_log_dir / "00000000000000000004.json"
        with open(version_4, "w") as f:
            metadata = {
                "metaData": {
                    "id": "test-table-id",
                    "format": {"provider": "parquet", "options": {}},
                    "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}},{"name":"age","type":"long","nullable":true,"metadata":{}}]}',
                    "partitionColumns": [],
                    "configuration": {},
                    "createdTime": 1705334629000,
                }
            }
            commit_info = {
                "commitInfo": {
                    "timestamp": 1705334629000,
                    "operation": "WRITE",
                    "operationParameters": {"mode": "Append"},
                    "operationMetrics": {"numFiles": "1"},
                }
            }
            add_action = {
                "add": {
                    "path": "part-00004.snappy.parquet",
                    "size": 5120,
                    "modificationTime": 1705334629000,
                    "dataChange": True,
                    "partitionValues": {},
                }
            }
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(commit_info) + "\n")
            f.write(json.dumps(add_action) + "\n")

        return temp_dir

    def test_get_schema_at_version(self, temp_delta_table_with_schema_changes: Path) -> None:
        """Test getting schema at a specific version."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table_with_schema_changes))

        # Get schema at version 0
        schema_v0 = adapter.get_schema_at_version(table_handle, 0)
        assert "id" in schema_v0
        assert "name" not in schema_v0
        assert "age" not in schema_v0

        # Get schema at version 1 (name added)
        schema_v1 = adapter.get_schema_at_version(table_handle, 1)
        assert "id" in schema_v1
        assert "name" in schema_v1
        assert "age" not in schema_v1

        # Get schema at version 2 (age added)
        schema_v2 = adapter.get_schema_at_version(table_handle, 2)
        assert "id" in schema_v2
        assert "name" in schema_v2
        assert "age" in schema_v2

    def test_get_schema_at_version_out_of_range(
        self, temp_delta_table_with_schema_changes: Path
    ) -> None:
        """Test getting schema at an out-of-range version."""
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table_with_schema_changes))

        with pytest.raises(ValueError, match="Version .* is out of range"):
            adapter.get_schema_at_version(table_handle, 999)

    def test_compare_schemas_column_added(self) -> None:
        """Test detecting column additions."""
        adapter = DeltaAdapter()
        old_schema = {"id": "integer"}
        new_schema = {"id": "integer", "name": "string"}

        changes = adapter.compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0]["change_type"] == "column_added"
        assert changes[0]["column_name"] == "name"
        assert changes[0]["old_type"] is None
        assert changes[0]["new_type"] == "string"
        assert changes[0]["is_breaking"] is False

    def test_compare_schemas_column_removed(self) -> None:
        """Test detecting column removals."""
        adapter = DeltaAdapter()
        old_schema = {"id": "integer", "name": "string"}
        new_schema = {"id": "integer"}

        changes = adapter.compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0]["change_type"] == "column_removed"
        assert changes[0]["column_name"] == "name"
        assert changes[0]["old_type"] == "string"
        assert changes[0]["new_type"] is None
        assert changes[0]["is_breaking"] is True  # Removals are breaking

    def test_compare_schemas_type_changed(self) -> None:
        """Test detecting type changes."""
        adapter = DeltaAdapter()
        old_schema = {"id": "integer", "age": "integer"}
        new_schema = {"id": "integer", "age": "long"}

        changes = adapter.compare_schemas(old_schema, new_schema)

        assert len(changes) == 1
        assert changes[0]["change_type"] == "type_changed"
        assert changes[0]["column_name"] == "age"
        assert changes[0]["old_type"] == "integer"
        assert changes[0]["new_type"] == "long"
        assert changes[0]["is_breaking"] is False

    def test_compare_schemas_multiple_changes(self) -> None:
        """Test detecting multiple schema changes."""
        adapter = DeltaAdapter()
        old_schema = {"id": "integer", "name": "string", "age": "integer"}
        new_schema = {"id": "integer", "age": "long", "email": "string"}

        changes = adapter.compare_schemas(old_schema, new_schema)

        # Should detect: name removed, age type changed, email added
        assert len(changes) == 3

        # Find each change type
        removed = [c for c in changes if c["change_type"] == "column_removed"]
        type_changed = [c for c in changes if c["change_type"] == "type_changed"]
        added = [c for c in changes if c["change_type"] == "column_added"]

        assert len(removed) == 1
        assert removed[0]["column_name"] == "name"
        assert removed[0]["is_breaking"] is True

        assert len(type_changed) == 1
        assert type_changed[0]["column_name"] == "age"
        assert type_changed[0]["old_type"] == "integer"
        assert type_changed[0]["new_type"] == "long"

        assert len(added) == 1
        assert added[0]["column_name"] == "email"
        assert added[0]["new_type"] == "string"

    def test_compare_schemas_no_changes(self) -> None:
        """Test comparing identical schemas."""
        adapter = DeltaAdapter()
        schema = {"id": "integer", "name": "string"}

        changes = adapter.compare_schemas(schema, schema)

        assert len(changes) == 0

    def test_get_schema_evolution(self, temp_delta_table_with_schema_changes: Path) -> None:
        """Test building complete schema evolution timeline.

        Validates Requirements 4.1, 4.2, 4.3, 4.4, 4.5:
        - Detects schema changes between consecutive versions
        - Displays version number, column name, and data types
        - Flags column removals as breaking
        - Shows timeline of all schema modifications
        - Displays old and new types for type changes
        """
        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_delta_table_with_schema_changes))

        evolution = adapter.get_schema_evolution(table_handle)

        # Should have 4 versions with changes (v1, v2, v3, v4)
        assert len(evolution) == 4

        # Version 1: name column added
        v1_changes = evolution[0]
        assert v1_changes["version"] == 1
        assert v1_changes["timestamp_ms"] == 1705334626000
        assert len(v1_changes["changes"]) == 1
        assert v1_changes["changes"][0]["change_type"] == "column_added"
        assert v1_changes["changes"][0]["column_name"] == "name"
        assert v1_changes["changes"][0]["new_type"] == "string"

        # Version 2: age column added
        v2_changes = evolution[1]
        assert v2_changes["version"] == 2
        assert v2_changes["timestamp_ms"] == 1705334627000
        assert len(v2_changes["changes"]) == 1
        assert v2_changes["changes"][0]["change_type"] == "column_added"
        assert v2_changes["changes"][0]["column_name"] == "age"
        assert v2_changes["changes"][0]["new_type"] == "integer"

        # Version 3: age type changed from integer to long
        v3_changes = evolution[2]
        assert v3_changes["version"] == 3
        assert v3_changes["timestamp_ms"] == 1705334628000
        assert len(v3_changes["changes"]) == 1
        assert v3_changes["changes"][0]["change_type"] == "type_changed"
        assert v3_changes["changes"][0]["column_name"] == "age"
        assert v3_changes["changes"][0]["old_type"] == "integer"
        assert v3_changes["changes"][0]["new_type"] == "long"

        # Version 4: name column removed (breaking change)
        v4_changes = evolution[3]
        assert v4_changes["version"] == 4
        assert v4_changes["timestamp_ms"] == 1705334629000
        assert len(v4_changes["changes"]) == 1
        assert v4_changes["changes"][0]["change_type"] == "column_removed"
        assert v4_changes["changes"][0]["column_name"] == "name"
        assert v4_changes["changes"][0]["old_type"] == "string"
        assert v4_changes["changes"][0]["is_breaking"] is True

    def test_get_schema_evolution_no_changes(self) -> None:
        """Test schema evolution with no schema changes."""
        temp_dir = Path(tempfile.mkdtemp())
        delta_log_dir = temp_dir / "_delta_log"
        delta_log_dir.mkdir()

        # Create two versions with identical schemas
        for version in range(2):
            version_file = delta_log_dir / f"{version:020d}.json"
            with open(version_file, "w") as f:
                if version == 0:
                    protocol = {
                        "protocol": {
                            "minReaderVersion": 1,
                            "minWriterVersion": 2,
                        }
                    }
                    f.write(json.dumps(protocol) + "\n")

                metadata = {
                    "metaData": {
                        "id": "test-table-id",
                        "format": {"provider": "parquet", "options": {}},
                        "schemaString": '{"type":"struct","fields":[{"name":"id","type":"integer","nullable":true,"metadata":{}}]}',
                        "partitionColumns": [],
                        "configuration": {},
                        "createdTime": 1705334625000 + version,
                    }
                }
                commit_info = {
                    "commitInfo": {
                        "timestamp": 1705334625000 + version,
                        "operation": "WRITE",
                        "operationParameters": {"mode": "Append"},
                        "operationMetrics": {"numFiles": "1"},
                    }
                }
                add_action = {
                    "add": {
                        "path": f"part-{version:05d}.snappy.parquet",
                        "size": 1024,
                        "modificationTime": 1705334625000 + version,
                        "dataChange": True,
                        "partitionValues": {},
                    }
                }
                f.write(json.dumps(metadata) + "\n")
                f.write(json.dumps(commit_info) + "\n")
                f.write(json.dumps(add_action) + "\n")

        adapter = DeltaAdapter()
        table_handle = adapter.open_table(str(temp_dir))
        evolution = adapter.get_schema_evolution(table_handle)

        # No schema changes should be detected
        assert len(evolution) == 0

    def test_schema_change_categorization(self) -> None:
        """Test that schema changes are correctly categorized.

        Validates Requirements 4.2, 4.3, 4.5:
        - Column additions are categorized as "column_added"
        - Column removals are categorized as "column_removed" and flagged as breaking
        - Type changes are categorized as "type_changed" with old and new types
        """
        adapter = DeltaAdapter()

        # Test column addition
        old_schema = {"id": "integer"}
        new_schema = {"id": "integer", "name": "string"}
        changes = adapter.compare_schemas(old_schema, new_schema)
        assert changes[0]["change_type"] == "column_added"
        assert changes[0]["is_breaking"] is False

        # Test column removal (breaking)
        old_schema = {"id": "integer", "name": "string"}
        new_schema = {"id": "integer"}
        changes = adapter.compare_schemas(old_schema, new_schema)
        assert changes[0]["change_type"] == "column_removed"
        assert changes[0]["is_breaking"] is True

        # Test type change
        old_schema = {"id": "integer", "age": "integer"}
        new_schema = {"id": "integer", "age": "long"}
        changes = adapter.compare_schemas(old_schema, new_schema)
        assert changes[0]["change_type"] == "type_changed"
        assert changes[0]["old_type"] == "integer"
        assert changes[0]["new_type"] == "long"
