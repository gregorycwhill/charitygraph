import pytest
from uuid import UUID

from charitygraph.contracts.ids import deterministic_id, new_opaque_id, validate_typed_id


def test_opaque_subject_id_has_no_semantic_content():
    value = new_opaque_id("subject:", uuid_value=UUID("12345678-1234-4234-8234-123456789abc"))
    assert value == "subject:12345678123442348234123456789abc"
    assert "name" not in value and "example" not in value
    assert validate_typed_id(value, "subject:") == value


def test_deterministic_ids_are_stable_and_material_changes_matter():
    assert deterministic_id("srcrec:", {"b": 2, "a": 1}) == deterministic_id("srcrec:", {"a": 1, "b": 2})
    assert deterministic_id("srcrec:", {"a": 1}) != deterministic_id("srcrec:", {"a": 2})


@pytest.mark.parametrize("value", ["Subject:" + "1" * 32, "subject:ABC", "subject:not-a-filename", "unknown:" + "1" * 32])
def test_invalid_typed_ids_fail(value):
    with pytest.raises(ValueError):
        validate_typed_id(value)


def test_expected_prefix_is_enforced():
    with pytest.raises(ValueError):
        validate_typed_id("subject:" + "1" * 32, "decision:")
