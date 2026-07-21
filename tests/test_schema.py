import pytest

from causal_multiomics_review.schema import SchemaError, validate_object

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "evidence"],
    "properties": {
        "decision": {"enum": ["yes", "no", "unclear"]},
        "evidence": {"type": "string"},
    },
}


def test_schema_accepts_valid_object() -> None:
    value = {"decision": "yes", "evidence": "reported in abstract"}
    assert validate_object(value, SCHEMA) == value


@pytest.mark.parametrize(
    "value",
    [
        {"decision": "maybe", "evidence": "x"},
        {"decision": "yes"},
        {"decision": "yes", "evidence": "x", "final_label": "include"},
    ],
)
def test_schema_rejects_invalid_objects(value: dict[str, str]) -> None:
    with pytest.raises(SchemaError):
        validate_object(value, SCHEMA)


def test_schema_validates_nested_objects() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["evidence"],
        "additionalProperties": False,
        "properties": {
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section_id"],
                    "additionalProperties": False,
                    "properties": {"section_id": {"type": "string", "minLength": 1}},
                },
            }
        },
    }
    with pytest.raises(SchemaError, match="unexpected"):
        validate_object(
            {"evidence": [{"section_id": "S1", "invented": True}]},
            schema,
        )
