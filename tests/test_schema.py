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
