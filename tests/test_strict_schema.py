import pytest

from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput
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
    schema = strictify_schema(DirectServiceWireOutput.model_json_schema())
    validate_strict_schema(schema)
    assert "default" not in str(schema)
    assert all(value != [] for value in schema.get("$defs", {}).values() if isinstance(value, dict) for value in [value.get("enum")])


def test_annotation_only_union_branch_is_rejected_and_omitted():
    malformed = {"anyOf": [{"type": "string"}, {"description": "Enum annotation"}]}
    with pytest.raises(ValueError, match="lacks a type"):
        validate_strict_schema(malformed)
    projected = strictify_schema(malformed)
    assert projected == {"anyOf": [{"type": "string"}]}


def test_direct_service_schema_has_no_annotation_only_branches():
    schema = strictify_schema(DirectServiceWireOutput.model_json_schema())
    validate_strict_schema(schema)
    for definition in schema.get("$defs", {}).values():
        if isinstance(definition, dict) and isinstance(definition.get("anyOf"), list):
            assert all(not (isinstance(branch, dict) and set(branch).issubset({"description", "title"})) for branch in definition["anyOf"])


def test_schema_valued_typed_map_remains_a_local_rejection_fixture():
    with pytest.raises(ValueError, match="typed-map"):
        validate_strict_schema({"type": "object", "additionalProperties": {"type": "string"}})
