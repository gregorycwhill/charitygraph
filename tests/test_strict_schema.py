import pytest

from charitygraph.contracts.direct_service import DirectServiceSemanticOutput
from charitygraph.strict_schema import strictify_schema, validate_strict_schema


def test_invalid_empty_enum_is_rejected_before_authorization():
    with pytest.raises(ValueError, match="empty enum"):
        validate_strict_schema({"type": "string", "enum": []})


def test_object_required_and_additional_properties_are_checked():
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_strict_schema({"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]})
    with pytest.raises(ValueError, match="required"):
        validate_strict_schema({"type": "object", "properties": {"x": {}}, "required": [] , "additionalProperties": False})


def test_direct_service_schema_strictification_passes_and_removes_defaults_empty_enums():
    schema = strictify_schema(DirectServiceSemanticOutput.model_json_schema())
    validate_strict_schema(schema)
    assert "default" not in str(schema)
    assert all(value != [] for value in schema.get("$defs", {}).values() if isinstance(value, dict) for value in [value.get("enum")])
