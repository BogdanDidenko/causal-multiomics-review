from __future__ import annotations

from typing import Any


class SchemaError(ValueError):
    pass


def validate_object(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate the JSON Schema subset used by the screening contracts."""
    if not isinstance(value, dict):
        raise SchemaError("Response must be a JSON object")

    properties = schema.get("properties", {})
    missing = sorted(set(schema.get("required", [])) - set(value))
    if missing:
        raise SchemaError(f"Missing required fields: {', '.join(missing)}")

    if schema.get("additionalProperties") is False:
        extra = sorted(set(value) - set(properties))
        if extra:
            raise SchemaError(f"Unexpected fields: {', '.join(extra)}")

    for field, field_schema in properties.items():
        if field not in value:
            continue
        item = value[field]
        if "enum" in field_schema and item not in field_schema["enum"]:
            raise SchemaError(f"{field} has invalid value {item!r}")
        expected_type = field_schema.get("type")
        if expected_type == "string" and not isinstance(item, str):
            raise SchemaError(f"{field} must be a string")
        if expected_type == "array":
            if not isinstance(item, list):
                raise SchemaError(f"{field} must be an array")
            item_schema = field_schema.get("items", {})
            for child in item:
                if item_schema.get("type") == "string" and not isinstance(child, str):
                    raise SchemaError(f"{field} items must be strings")
                if "enum" in item_schema and child not in item_schema["enum"]:
                    raise SchemaError(f"{field} has invalid item {child!r}")
            if field_schema.get("uniqueItems") and len(item) != len(set(item)):
                raise SchemaError(f"{field} items must be unique")
    return value
