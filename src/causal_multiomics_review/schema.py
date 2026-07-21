from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaDefinitionError


class SchemaError(ValueError):
    pass


def validate_object(value: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a screening response against its Draft 2020-12 JSON Schema."""
    if not isinstance(value, dict):
        raise SchemaError("Response must be a JSON object")
    try:
        Draft202012Validator.check_schema(schema)
    except JsonSchemaDefinitionError as error:
        raise SchemaError(f"Invalid response schema: {error.message}") from error
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        raise SchemaError(f"{location}: {error.message}")
    return value
