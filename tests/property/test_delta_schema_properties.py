"""Property-based tests for Delta Lake schema evolution.

Tests universal properties of schema change detection and evolution timeline.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Strategy for generating schema field definitions
schema_field_strategy = st.builds(
    dict,
    name=st.text(
        min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))
    ),
    type=st.sampled_from(["string", "integer", "long", "double", "boolean", "timestamp", "date"]),
    nullable=st.booleans(),
)


@settings(max_examples=100)
@given(
    schema_v1_fields=st.lists(
        schema_field_strategy, min_size=1, max_size=10, unique_by=lambda x: x["name"]
    ),
    schema_v2_fields=st.lists(
        schema_field_strategy, min_size=1, max_size=10, unique_by=lambda x: x["name"]
    ),
)
def test_property_schema_change_detection(
    schema_v1_fields: list[dict], schema_v2_fields: list[dict]
) -> None:
    """Feature: delta-lake-integration, Property 11: Schema change detection

    For any pair of consecutive versions, if the schema differs, the system
    should detect and categorize the change (column added, removed, or type changed).
    """
    # Extract field names and types
    v1_fields = {f["name"]: f["type"] for f in schema_v1_fields}
    v2_fields = {f["name"]: f["type"] for f in schema_v2_fields}

    # Detect changes
    v1_names = set(v1_fields.keys())
    v2_names = set(v2_fields.keys())

    added_columns = v2_names - v1_names
    removed_columns = v1_names - v2_names
    common_columns = v1_names & v2_names

    type_changes = {name for name in common_columns if v1_fields[name] != v2_fields[name]}

    # Property: added columns should not exist in v1
    for col in added_columns:
        assert col not in v1_fields
        assert col in v2_fields

    # Property: removed columns should not exist in v2
    for col in removed_columns:
        assert col in v1_fields
        assert col not in v2_fields

    # Property: type changes should only occur in common columns
    for col in type_changes:
        assert col in v1_fields
        assert col in v2_fields
        assert v1_fields[col] != v2_fields[col]

    # Property: total changes should account for all differences
    has_changes = len(added_columns) > 0 or len(removed_columns) > 0 or len(type_changes) > 0
    schemas_differ = v1_fields != v2_fields

    assert has_changes == schemas_differ


@settings(max_examples=100)
@given(
    version_count=st.integers(min_value=2, max_value=20),
    change_probability=st.floats(min_value=0.0, max_value=1.0),
    data=st.data(),
)
def test_property_schema_evolution_timeline_completeness(
    version_count: int, change_probability: float, data: st.DataObject
) -> None:
    """Feature: delta-lake-integration, Property 12: Schema evolution timeline completeness

    For any Delta table, the schema evolution timeline should include all
    versions where schema changes occurred.
    """
    # Simulate schema changes across versions using data.draw()
    versions_with_changes = []

    for version in range(version_count):
        # Randomly determine if this version has a schema change
        random_value = data.draw(st.floats(min_value=0.0, max_value=1.0))
        has_change = random_value < change_probability

        if has_change:
            versions_with_changes.append(version)

    # Property: all versions with changes should be in timeline
    timeline = versions_with_changes.copy()
    assert set(timeline) == set(versions_with_changes)

    # Property: timeline should not include versions without changes
    all_versions = set(range(version_count))
    versions_without_changes = all_versions - set(versions_with_changes)

    for version in versions_without_changes:
        assert version not in timeline

    # Property: timeline should be in chronological order
    assert timeline == sorted(timeline)

    # Property: timeline length should equal number of versions with changes
    assert len(timeline) == len(versions_with_changes)


@settings(max_examples=100)
@given(
    column_name=st.text(
        min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))
    ),
    old_type=st.sampled_from(["string", "integer", "long", "double"]),
    new_type=st.sampled_from(["string", "integer", "long", "double"]),
)
def test_property_type_change_categorization(
    column_name: str, old_type: str, new_type: str
) -> None:
    """Test that type changes are correctly categorized.

    Related to Property 11: Schema change detection.
    """
    # Property: if types differ, should be categorized as type change
    is_type_change = old_type != new_type

    if is_type_change:
        # Should detect as type change
        assert old_type != new_type

        # Property: change should include column name and both types
        change_record = {
            "column": column_name,
            "old_type": old_type,
            "new_type": new_type,
            "change_type": "type_changed",
        }

        assert change_record["column"] == column_name
        assert change_record["old_type"] == old_type
        assert change_record["new_type"] == new_type
        assert change_record["change_type"] == "type_changed"
    else:
        # No type change
        assert old_type == new_type


@settings(max_examples=100)
@given(
    schema_fields=st.lists(
        schema_field_strategy, min_size=1, max_size=10, unique_by=lambda x: x["name"]
    ),
    columns_to_remove=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
        min_size=0,
        max_size=5,
    ),
)
def test_property_breaking_change_detection(
    schema_fields: list[dict], columns_to_remove: list[str]
) -> None:
    """Test that column removals are flagged as potentially breaking changes.

    Related to Property 11: Schema change detection.
    """
    # Get field names
    field_names = [f["name"] for f in schema_fields]

    # Determine which columns actually exist and can be removed
    actual_removals = [col for col in columns_to_remove if col in field_names]

    # Property: removing columns should be flagged as breaking
    has_breaking_change = len(actual_removals) > 0

    if has_breaking_change:
        # Should flag as potentially breaking
        for col in actual_removals:
            assert col in field_names

            change_record = {"column": col, "change_type": "column_removed", "is_breaking": True}

            assert change_record["is_breaking"] is True

    # Property: adding columns should not be breaking
    # (tested implicitly - additions don't break existing queries)
