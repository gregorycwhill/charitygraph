from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from charitygraph.contracts import (
    ConductComplianceWireEvidenceRef,
    ConductComplianceWireOutput,
    ConductComplianceWireProposition,
    ConductComplianceSemanticProposition,
    conduct_project_observation,
    conduct_review_flags,
    conduct_wire_to_domain,
)
from charitygraph.section16_preflight import wire_schema, wire_schema_sha
from charitygraph.strict_schema import validate_strict_schema


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
SUBJECT = "subject:" + "a" * 32
LOCATOR = "[S001:L0001]"


def ref(role="supporting", locator=LOCATOR):
    return ConductComplianceWireEvidenceRef(locator=locator, role=role)


def proposition(**updates):
    value = {
        "proposition_class": "enforcement_action",
        "procedural_status": "no_longer_in_force",
        "scope_id": SUBJECT,
        "proposition_owner_kind": "source_publisher",
        "statement": "The regulator published an enforcement action.",
        "temporal": {"observed_at": NOW.isoformat(), "effective_from": "2020-09-21", "effective_to": "2020-10-01"},
        "evidence": (ref(),),
    }
    value.update(updates)
    return ConductComplianceWireProposition.model_validate(value)


def test_class_and_status_are_separate_and_bounded():
    item = proposition(proposition_class="finding", procedural_status="completed")
    assert item.proposition_class == "finding"
    assert item.procedural_status == "completed"
    assert "registration_status" not in str(ConductComplianceWireOutput.model_json_schema())


def test_owner_label_rule_is_closed():
    with pytest.raises(ValidationError):
        proposition(proposition_owner_kind="other_named_party")
    with pytest.raises(ValidationError):
        proposition(proposition_owner_kind="target_subject", proposition_owner_label="LWB")
    assert proposition(proposition_owner_kind="other_named_party", proposition_owner_label="Another party")


def test_nonempty_proposition_requires_supporting_evidence():
    with pytest.raises(ValidationError):
        proposition(evidence=(ref("context"),))
    assert ConductComplianceWireOutput.model_validate({"propositions": []}).propositions == ()


def test_temporal_strings_convert_and_invalid_syntax_fails_closed():
    domain = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(),)))
    assert domain.propositions[0].observation_time.effective_from.isoformat() == "2020-09-21"
    with pytest.raises(ValueError, match="invalid effective_from"):
        conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(temporal={"observed_at": NOW.isoformat(), "effective_from": "not-a-date"}),)))


def test_scope_and_evidence_are_exact_task_bindings():
    wire = ConductComplianceWireOutput(propositions=(proposition(),))
    assert conduct_wire_to_domain(wire, allowed_scope_ids={SUBJECT}, evidence_locators={LOCATOR}).propositions
    with pytest.raises(ValueError, match="scope_id"):
        conduct_wire_to_domain(wire, allowed_scope_ids={"subject:" + "b" * 32}, evidence_locators={LOCATOR})
    with pytest.raises(ValueError, match="evidence locator"):
        conduct_wire_to_domain(wire, allowed_scope_ids={SUBJECT}, evidence_locators={"[S001:L0002]"})


def test_projection_preserves_owner_status_and_existing_observation_shape():
    domain = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(proposition_owner_kind="target_subject"),)))
    observation = conduct_project_observation(
        domain.propositions[0], record_id="observation:" + "b" * 32, subject_id=SUBJECT,
        source_record_ids=("srcrec:" + "c" * 32,), created_at=NOW,
        producer={"kind": "code", "producer_id": "section16-fixture"},
    )
    assert observation.predicate == "conduct_compliance.enforcement_action"
    assert observation.value["procedural_status"] == "no_longer_in_force"
    assert observation.value["proposition_owner_kind"] == "target_subject"


def test_review_flags_are_structural_not_phrase_heuristics():
    allegation = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(proposition_class="allegation", procedural_status="pending"),))).propositions[0]
    assert "allegation_without_formal_finding" in conduct_review_flags(allegation)
    varied = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(procedural_status="varied"),))).propositions[0]
    assert "status_varied" in conduct_review_flags(varied)
    unknown_owner = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(proposition_owner_kind="unknown"),))).propositions[0]
    assert "proposition_owner_ambiguous" in conduct_review_flags(unknown_owner)


def test_strict_provider_schema_is_valid_and_bounded():
    schema = wire_schema()
    validate_strict_schema(schema)
    assert wire_schema_sha() and "schema" not in ConductComplianceWireOutput(propositions=()).model_dump(mode="json")
    assert "CanonicalValue" not in str(schema)
    assert "additionalProperties" in str(schema)
    assert not any(isinstance(v, dict) and isinstance(v.get("additionalProperties"), dict) for v in schema.get("$defs", {}).values())
