"""Serialization utilities for API responses."""

from __future__ import annotations

import dataclasses
from typing import Any

# JavaScript's Number.MAX_SAFE_INTEGER = 2^53 - 1
_JS_MAX_SAFE_INT = 9007199254740991


def to_dict(
    obj: Any,
    *,
    skip_fields: set[str] | None = None,
    include_properties: bool = False,
    safe_int_threshold: int | None = None,
) -> Any:
    """Recursively convert dataclasses and nested objects to serializable dicts.

    Args:
        obj: Object to convert (dataclass, list, dict, or primitive).
        skip_fields: Set of field names to skip when serializing dataclasses.
        include_properties: If True, include @property values from dataclasses.
        safe_int_threshold: If set, integers exceeding this value (positive or negative)
            are serialized as strings to prevent precision loss in JavaScript.
            Use _JS_MAX_SAFE_INT for JavaScript compatibility.

    Returns:
        Serializable dictionary, list, or primitive value.

    Examples:
        Basic usage:
            >>> to_dict(my_dataclass)

        Skip non-serializable fields:
            >>> to_dict(obj, skip_fields={"native_table"})

        Include computed properties:
            >>> to_dict(obj, include_properties=True)

        JavaScript-safe integers:
            >>> to_dict(obj, safe_int_threshold=_JS_MAX_SAFE_INT)
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = {}
        for field in dataclasses.fields(obj):
            if skip_fields and field.name in skip_fields:
                continue
            # Use getattr rather than dataclasses.asdict() to avoid deep-copying
            # all fields before we can skip them, which can cause pickle errors
            # on non-serializable objects.
            d[field.name] = to_dict(
                getattr(obj, field.name),
                skip_fields=skip_fields,
                include_properties=include_properties,
                safe_int_threshold=safe_int_threshold,
            )

        # Include @property values if requested
        # (dataclasses.fields() only returns declared fields, not computed properties)
        if include_properties:
            for name, val in vars(type(obj)).items():
                if isinstance(val, property) and name not in d:
                    d[name] = to_dict(
                        getattr(obj, name),
                        skip_fields=skip_fields,
                        include_properties=include_properties,
                        safe_int_threshold=safe_int_threshold,
                    )
        return d

    if isinstance(obj, list):
        return [
            to_dict(
                i,
                skip_fields=skip_fields,
                include_properties=include_properties,
                safe_int_threshold=safe_int_threshold,
            )
            for i in obj
        ]

    if isinstance(obj, dict):
        return {
            k: to_dict(
                v,
                skip_fields=skip_fields,
                include_properties=include_properties,
                safe_int_threshold=safe_int_threshold,
            )
            for k, v in obj.items()
        }

    # Serialize large integers as strings to avoid silent float64 rounding in JavaScript
    if safe_int_threshold is not None and isinstance(obj, int) and not isinstance(obj, bool):
        if obj > safe_int_threshold or obj < -safe_int_threshold:
            return str(obj)

    return obj


# Convenience constants for common use cases
JS_MAX_SAFE_INT = _JS_MAX_SAFE_INT
