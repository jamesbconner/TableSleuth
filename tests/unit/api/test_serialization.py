"""Tests for API serialization utilities."""

from dataclasses import dataclass

import pytest

from tablesleuth.api.serialization import JS_MAX_SAFE_INT, to_dict


@dataclass
class SimpleDataclass:
    """Simple dataclass for testing."""

    name: str
    value: int


@dataclass
class NestedDataclass:
    """Nested dataclass for testing."""

    simple: SimpleDataclass
    items: list[int]
    metadata: dict[str, str]


@dataclass
class DataclassWithProperty:
    """Dataclass with computed property."""

    base_value: int

    @property
    def computed_value(self) -> int:
        """Computed property."""
        return self.base_value * 2


@dataclass
class DataclassWithSkippableField:
    """Dataclass with field that should be skipped."""

    name: str
    native_object: object  # Non-serializable field


def test_to_dict_simple_dataclass() -> None:
    """Test basic dataclass serialization."""
    obj = SimpleDataclass(name="test", value=42)
    result = to_dict(obj)

    assert result == {"name": "test", "value": 42}
    assert isinstance(result, dict)


def test_to_dict_nested_dataclass() -> None:
    """Test nested dataclass serialization."""
    obj = NestedDataclass(
        simple=SimpleDataclass(name="nested", value=100),
        items=[1, 2, 3],
        metadata={"key": "value"},
    )
    result = to_dict(obj)

    assert result == {
        "simple": {"name": "nested", "value": 100},
        "items": [1, 2, 3],
        "metadata": {"key": "value"},
    }


def test_to_dict_list() -> None:
    """Test list serialization."""
    objs = [
        SimpleDataclass(name="first", value=1),
        SimpleDataclass(name="second", value=2),
    ]
    result = to_dict(objs)

    assert result == [
        {"name": "first", "value": 1},
        {"name": "second", "value": 2},
    ]


def test_to_dict_dict() -> None:
    """Test dict serialization."""
    obj = {
        "a": SimpleDataclass(name="test", value=1),
        "b": [1, 2, 3],
    }
    result = to_dict(obj)

    assert result == {
        "a": {"name": "test", "value": 1},
        "b": [1, 2, 3],
    }


def test_to_dict_primitives() -> None:
    """Test that primitives pass through unchanged."""
    assert to_dict("string") == "string"
    assert to_dict(42) == 42
    assert to_dict(3.14) == 3.14
    assert to_dict(True) is True
    assert to_dict(None) is None


def test_to_dict_skip_fields() -> None:
    """Test skipping specific fields."""
    obj = DataclassWithSkippableField(name="test", native_object=object())
    result = to_dict(obj, skip_fields={"native_object"})

    assert result == {"name": "test"}
    assert "native_object" not in result


def test_to_dict_include_properties() -> None:
    """Test including @property values."""
    obj = DataclassWithProperty(base_value=10)

    # Without include_properties
    result_without = to_dict(obj, include_properties=False)
    assert result_without == {"base_value": 10}
    assert "computed_value" not in result_without

    # With include_properties
    result_with = to_dict(obj, include_properties=True)
    assert result_with == {"base_value": 10, "computed_value": 20}


def test_to_dict_safe_int_threshold() -> None:
    """Test converting large integers to strings."""
    obj = SimpleDataclass(name="test", value=JS_MAX_SAFE_INT + 1)

    # Without threshold
    result_without = to_dict(obj)
    assert result_without["value"] == JS_MAX_SAFE_INT + 1
    assert isinstance(result_without["value"], int)

    # With threshold
    result_with = to_dict(obj, safe_int_threshold=JS_MAX_SAFE_INT)
    assert result_with["value"] == str(JS_MAX_SAFE_INT + 1)
    assert isinstance(result_with["value"], str)


def test_to_dict_safe_int_threshold_negative() -> None:
    """Test converting large negative integers to strings."""
    obj = SimpleDataclass(name="test", value=-(JS_MAX_SAFE_INT + 1))

    result = to_dict(obj, safe_int_threshold=JS_MAX_SAFE_INT)
    assert result["value"] == str(-(JS_MAX_SAFE_INT + 1))
    assert isinstance(result["value"], str)


def test_to_dict_safe_int_threshold_within_range() -> None:
    """Test that integers within threshold remain as integers."""
    obj = SimpleDataclass(name="test", value=JS_MAX_SAFE_INT)

    result = to_dict(obj, safe_int_threshold=JS_MAX_SAFE_INT)
    assert result["value"] == JS_MAX_SAFE_INT
    assert isinstance(result["value"], int)


def test_to_dict_safe_int_threshold_boolean() -> None:
    """Test that booleans are not converted to strings."""
    # Booleans are instances of int in Python, but should not be converted
    @dataclass
    class BoolDataclass:
        flag: bool

    obj = BoolDataclass(flag=True)
    result = to_dict(obj, safe_int_threshold=0)  # Very low threshold

    assert result["flag"] is True
    assert isinstance(result["flag"], bool)


def test_to_dict_combined_options() -> None:
    """Test using multiple options together."""

    @dataclass
    class ComplexDataclass:
        name: str
        large_id: int
        native_obj: object

        @property
        def computed(self) -> str:
            return f"{self.name}_computed"

    obj = ComplexDataclass(
        name="test",
        large_id=JS_MAX_SAFE_INT + 100,
        native_obj=object(),
    )

    result = to_dict(
        obj,
        skip_fields={"native_obj"},
        include_properties=True,
        safe_int_threshold=JS_MAX_SAFE_INT,
    )

    assert result == {
        "name": "test",
        "large_id": str(JS_MAX_SAFE_INT + 100),
        "computed": "test_computed",
    }
    assert "native_obj" not in result


def test_to_dict_nested_with_options() -> None:
    """Test that options propagate through nested structures."""

    @dataclass
    class Inner:
        value: int

    @dataclass
    class Outer:
        inner: Inner
        items: list[Inner]

    obj = Outer(
        inner=Inner(value=JS_MAX_SAFE_INT + 1),
        items=[Inner(value=JS_MAX_SAFE_INT + 2), Inner(value=100)],
    )

    result = to_dict(obj, safe_int_threshold=JS_MAX_SAFE_INT)

    assert result["inner"]["value"] == str(JS_MAX_SAFE_INT + 1)
    assert result["items"][0]["value"] == str(JS_MAX_SAFE_INT + 2)
    assert result["items"][1]["value"] == 100  # Within threshold


def test_js_max_safe_int_constant() -> None:
    """Test that JS_MAX_SAFE_INT constant is correct."""
    assert JS_MAX_SAFE_INT == 9007199254740991
    assert JS_MAX_SAFE_INT == (1 << 53) - 1
