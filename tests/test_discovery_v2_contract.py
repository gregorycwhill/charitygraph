import pytest

from charitygraph.contracts import (
    DISCOVERY_OUTPUT_SCHEMA_V2, ProgramServiceDiscoveryOutput,
    ProgramServiceProposalV2, SemanticEvidence, discovery_schema_v2,
)
from charitygraph.native_discovery_executor import DISCOVERY_PROMPT, DISCOVERY_PROMPT_V2, PROMPT_TEMPLATE_VERSION_V2
from charitygraph.native_program_discovery import TASK_SCHEMA, TASK_SCHEMA_V2


def _proposal(disposition="program", status="current", key="p"):
    return ProgramServiceProposalV2(
        proposal_key=key, label="Example service", disposition=disposition,
        operational_status=status, evidence=(SemanticEvidence(evidence_id="evidence:1", role="supporting"),),
        rationale="Directly supported by supplied evidence", confidence="high",
    )


def test_v2_status_is_explicit_and_durable_field_removed():
    current = _proposal(status="current")
    historical = _proposal(status="historical", key="h")
    assert current.operational_status == "current"
    assert historical.operational_status == "historical"
    with pytest.raises(Exception):
        ProgramServiceProposalV2.model_validate({**current.model_dump(), "durable": True})


def test_v2_allows_identity_projection_statuses_and_rejects_unknown():
    for status in ("current", "closing_or_winding_down", "historical", "unknown"):
        assert _proposal(status=status).operational_status == status
    with pytest.raises(Exception):
        _proposal(status="not-a-status")


def test_v2_non_program_dispositions_remain_non_projectable_by_contract():
    for disposition in ("project", "campaign", "category_or_portfolio", "organisational_practice", "insufficient_evidence"):
        assert _proposal(disposition=disposition).disposition == disposition


def test_v2_schema_and_prompt_are_versioned_without_named_examples():
    schema = discovery_schema_v2(("evidence:1",))
    assert "operational_status" in schema["properties"]["proposals"]["items"]["properties"]
    assert DISCOVERY_OUTPUT_SCHEMA_V2.schema_id.endswith(":2.0")
    assert TASK_SCHEMA.schema_id != TASK_SCHEMA_V2.schema_id
    assert PROMPT_TEMPLATE_VERSION_V2 == "v2"
    assert "Current availability is not subject identity" in DISCOVERY_PROMPT_V2
    assert "Example service" not in DISCOVERY_PROMPT_V2
    assert "Current availability is not subject identity" not in DISCOVERY_PROMPT


def test_v1_output_remains_readable():
    output = ProgramServiceDiscoveryOutput.model_validate({"proposals": [{"proposal_key": "p", "label": "Old", "disposition": "program", "durable": True, "evidence": [{"evidence_id": "evidence:1", "role": "supporting", "note": None}], "rationale": "old result", "confidence": "high", "competing_interpretation": None}]})
    assert output.proposals[0].durable is True

def test_v2_projection_uses_identity_disposition_and_preserves_status():
    from charitygraph.runtime.catalog import SQLiteCatalog
    class FakeCatalog:
        def get_model_result(self, _):
            return {"validation_status": "valid", "output": {"proposals": [
                _proposal(status="historical", key="historic").model_dump(mode="python"),
                _proposal(disposition="campaign", key="campaign").model_dump(mode="python"),
            ]}, "subject_id": "subject:" + "1" * 32}
        def register_program_candidate(self, candidate):
            return {"candidate_kind": candidate.candidate_kind, "model_result_item_key": candidate.model_result_item_key}
    result = SQLiteCatalog.project_program_candidates(FakeCatalog(), "modelresult:" + "2" * 32, now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    assert result == [{"candidate_kind": "explicit_program", "model_result_item_key": "historic"}]
