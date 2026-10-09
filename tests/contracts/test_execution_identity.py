import pytest

from charitygraph.execution_identity import (
    ExecutionIdentityMismatch, assert_execution_identity, bind_execution_identity,
)


def make(**overrides):
    values = dict(
        prompt="fixed prompt bytes", schema={"type": "object", "properties": {}},
        packet_selection_contract="native-discovery-evidence-selection",
        packet_selection_version="2", packet_selection=[{"evidence_id": "e1", "content_hash": "a"}],
        retained_source_manifest=[{"evidence_id": "e1", "content_hash": "a"}],
        provider="openai.responses", model="gpt-5.6-luna", experiment_arm="A_general_baseline",
    )
    values.update(overrides)
    return bind_execution_identity(**values)


def test_matching_artifacts_are_deterministic_and_validate():
    first, second = make(), make()
    assert first == second
    assert first.identity_sha256 == second.identity_sha256
    assert_execution_identity(first.as_dict(), second)


@pytest.mark.parametrize("field", ["prompt_sha256", "schema_sha256", "packet_selection_sha256", "retained_source_manifest_sha256", "model", "experiment_arm"])
def test_c353_prompt_schema_mismatch_class_fails_before_call(field):
    requested = make().as_dict()
    actual = make(**({"prompt": "changed"} if field == "prompt_sha256" else {"schema": {"type": "string"}} if field == "schema_sha256" else {"packet_selection": [{"evidence_id": "e1", "content_hash": "changed"}]} if field == "packet_selection_sha256" else {"retained_source_manifest": [{"evidence_id": "e1", "content_hash": "changed"}]} if field == "retained_source_manifest_sha256" else {field: "changed"}))
    with pytest.raises(ExecutionIdentityMismatch, match="mismatch"):
        assert_execution_identity(requested, actual)


def test_unknown_or_missing_requested_identity_is_not_silently_accepted():
    requested = make().as_dict()
    requested.pop("schema_sha256")
    with pytest.raises(ExecutionIdentityMismatch):
        assert_execution_identity(requested, make())
