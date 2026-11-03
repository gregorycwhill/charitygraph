import json

import pytest

from charitygraph.contracts import (
    DISCOVERY_OUTPUT_SCHEMA_V2_CORRECTED,
    EvidenceMeaning,
    ProgramServiceDiscoveryOutputV2,
    SemanticEvidence,
    discovery_schema_v2_corrected,
)
from charitygraph.discovery_evidence_normalization import canonical_hash, normalize_discovery_output
from charitygraph.native_discovery_executor import DISCOVERY_PROMPT_V2_CORRECTED


def _proposal(evidence):
    return {
        "proposal_key": "p",
        "label": "Service",
        "disposition": "service",
        "operational_status": "current",
        "evidence": evidence,
        "rationale": "Directly supported by the supplied evidence.",
        "confidence": "high",
        "competing_interpretation": None,
    }


def test_legacy_single_meaning_remains_valid():
    output = ProgramServiceDiscoveryOutputV2.model_validate({"proposals": [_proposal([{"evidence_id": "locator:1", "role": "supporting", "note": "primary"}])]})
    assert output.proposals[0].evidence[0].additional_meanings == ()


def test_one_locator_preserves_supporting_and_competing_meanings():
    evidence = SemanticEvidence(evidence_id="locator:1", role="supporting", note="supports", additional_meanings=(EvidenceMeaning(role="competing", note="also ambiguous"),))
    assert [(item.role, item.note) for item in evidence.normalized_meanings()] == [("supporting", "supports"), ("competing", "also ambiguous")]


def test_one_locator_preserves_context_and_multiple_supporting_notes():
    evidence = SemanticEvidence(evidence_id="locator:1", role="supporting", note="first", additional_meanings=(EvidenceMeaning(role="context", note="context"), EvidenceMeaning(role="supporting", note="second")))
    assert len(evidence.normalized_meanings()) == 3


def test_duplicate_meaning_and_primary_repetition_are_invalid():
    with pytest.raises(ValueError, match="meanings must be unique"):
        SemanticEvidence(evidence_id="locator:1", role="supporting", note="same", additional_meanings=(EvidenceMeaning(role="supporting", note="same"),))
    with pytest.raises(ValueError, match="unique evidence references"):
        ProgramServiceDiscoveryOutputV2.model_validate({"proposals": [_proposal([
            {"evidence_id": "locator:1", "role": "supporting", "note": "one"},
            {"evidence_id": "locator:1", "role": "competing", "note": "two"},
        ])]})


def test_deterministic_normalization_preserves_order_and_hash():
    raw = {"proposals": [_proposal([
        {"evidence_id": "locator:1", "role": "supporting", "note": "first"},
        {"evidence_id": "locator:2", "role": "context", "note": "second"},
        {"evidence_id": "locator:1", "role": "competing", "note": "third"},
        {"evidence_id": "locator:1", "role": "supporting", "note": "first"},
    ])]}
    normalized = normalize_discovery_output(raw)
    assert [entry["evidence_id"] for entry in normalized["proposals"][0]["evidence"]] == ["locator:1", "locator:2"]
    assert normalized["proposals"][0]["evidence"][0]["additional_meanings"] == [{"role": "competing", "note": "third"}]
    assert canonical_hash(normalized) == canonical_hash(normalize_discovery_output(json.loads(json.dumps(raw))))


def test_corrected_schema_and_prompt_are_versioned():
    schema = discovery_schema_v2_corrected(("locator:1",))
    evidence = schema["properties"]["proposals"]["items"]["properties"]["evidence"]["items"]
    assert DISCOVERY_OUTPUT_SCHEMA_V2_CORRECTED.schema_id.endswith(":2.1")
    assert "additional_meanings" in evidence["properties"]
    assert "additional_meanings" not in evidence["required"]
    assert "may appear at most once" in DISCOVERY_PROMPT_V2_CORRECTED
