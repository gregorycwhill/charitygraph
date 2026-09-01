from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from charitygraph.contracts import (
    ConductComplianceWireEvidenceRef,
    ConductComplianceWireOutput,
    ConductComplianceWireProposition,
    ConductWireOtherNamedParty,
    ConductWireSourcePublisher,
    ConductWireTargetSubject,
    ConductWireUnknownOwner,
    ConductComplianceSemanticProposition,
    conduct_project_observation,
    conduct_review_flags,
    conduct_wire_to_domain,
)
from charitygraph.section16_preflight import wire_schema, wire_schema_sha
from charitygraph.section16_recovery import recover_historical_wire
from charitygraph.strict_schema import validate_strict_schema


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
SUBJECT = "subject:" + "a" * 32
LOCATOR = "[S001:L0001]"


def ref(role="supporting", evidence_key="E000001"):
    return ConductComplianceWireEvidenceRef(evidence_key=evidence_key, role=role)


def proposition(**updates):
    value = {
        "proposition_class": "enforcement_action",
        "procedural_status": "no_longer_in_force",
        "scope_id": SUBJECT,
        "owner": {"kind": "source_publisher"},
        "statement": "The regulator published an enforcement action.",
        "temporal": {"effective_from": "2020-09-21", "effective_to": "2020-10-01"},
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
        ConductWireOtherNamedParty.model_validate({"kind": "other_named_party"})
    assert proposition(owner={"kind": "other_named_party", "label": "Another party"})
    for owner in ({"kind": "source_publisher", "label": "bad"}, {"kind": "target_subject", "label": "bad"}, {"kind": "unknown", "label": "bad"}):
        with pytest.raises(ValidationError):
            proposition(owner=owner)


def test_nonempty_proposition_requires_supporting_evidence():
    with pytest.raises(ValidationError):
        proposition(evidence=(ref("context"),))
    assert ConductComplianceWireOutput.model_validate({"propositions": []}).propositions == ()
    with pytest.raises(ValidationError):
        ConductComplianceWireProposition.model_validate({
            "proposition_class": "finding", "procedural_status": "completed", "scope_id": SUBJECT,
            "owner": {"kind": "source_publisher"}, "statement": "x",
            "evidence": [{"locator": "[S001:L0001]", "role": "supporting"}],
        })


def test_temporal_strings_convert_and_invalid_syntax_fails_closed():
    domain = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(),)), observed_at=NOW)
    assert domain.propositions[0].observation_time.effective_from.isoformat() == "2020-09-21"
    with pytest.raises(ValueError, match="invalid effective_from"):
        conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(temporal={"effective_from": "not-a-date"}),)), observed_at=NOW)
    with pytest.raises(ValueError, match="Builder observation timestamp"):
        conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(),)))
    temporal_schema = wire_schema()["$defs"]["ConductComplianceWireTemporal"]
    assert "observed_at" not in temporal_schema["properties"]


def test_scope_and_evidence_are_exact_task_bindings():
    wire = ConductComplianceWireOutput(propositions=(proposition(),))
    assert conduct_wire_to_domain(wire, allowed_scope_ids={SUBJECT}, evidence_key_map={"E000001": LOCATOR}, observed_at=NOW).propositions
    with pytest.raises(ValueError, match="scope_id"):
        conduct_wire_to_domain(wire, allowed_scope_ids={"subject:" + "b" * 32}, evidence_key_map={"E000001": LOCATOR}, observed_at=NOW)
    with pytest.raises(ValueError, match="evidence key"):
        conduct_wire_to_domain(wire, allowed_scope_ids={SUBJECT}, evidence_key_map={"E000002": "[S001:L0002]"}, observed_at=NOW)
    with pytest.raises(ValueError, match="evidence key map"):
        conduct_wire_to_domain(wire, allowed_scope_ids={SUBJECT}, evidence_key_map={"E000001": LOCATOR, "E000002": LOCATOR}, observed_at=NOW)


def test_projection_preserves_owner_status_and_existing_observation_shape():
    domain = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(owner={"kind": "target_subject"}),)), observed_at=NOW)
    observation = conduct_project_observation(
        domain.propositions[0], record_id="observation:" + "b" * 32, subject_id=SUBJECT,
        source_record_ids=("srcrec:" + "c" * 32,), created_at=NOW,
        producer={"kind": "code", "producer_id": "section16-fixture"},
    )
    assert observation.predicate == "conduct_compliance.enforcement_action"
    assert observation.value["procedural_status"] == "no_longer_in_force"
    assert observation.value["proposition_owner_kind"] == "target_subject"


def test_review_flags_are_structural_not_phrase_heuristics():
    allegation = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(proposition_class="allegation", procedural_status="pending"),)), observed_at=NOW).propositions[0]
    assert "allegation_without_formal_finding" in conduct_review_flags(allegation)
    varied = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(procedural_status="varied"),)), observed_at=NOW).propositions[0]
    assert "status_varied" in conduct_review_flags(varied)
    unknown_owner = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(proposition(owner={"kind": "unknown"}),)), observed_at=NOW).propositions[0]
    assert "proposition_owner_ambiguous" in conduct_review_flags(unknown_owner)


def test_strict_provider_schema_is_valid_and_bounded():
    schema = wire_schema()
    validate_strict_schema(schema)
    assert wire_schema_sha() and "schema" not in ConductComplianceWireOutput(propositions=()).model_dump(mode="json")
    assert "CanonicalValue" not in str(schema)
    assert "additionalProperties" in str(schema)
    assert not any(isinstance(v, dict) and isinstance(v.get("additionalProperties"), dict) for v in schema.get("$defs", {}).values())
    evidence_schema = schema["$defs"]["ConductComplianceWireEvidenceRef"]
    assert evidence_schema["required"] == ["evidence_key", "role"]
    assert "locator" not in evidence_schema["properties"]


def test_provider_owner_shapes_round_trip_to_domain_without_flat_label_leakage():
    owners = [
        {"kind": "source_publisher"}, {"kind": "target_subject"},
        {"kind": "unknown"}, {"kind": "other_named_party", "label": "Commission"},
    ]
    for owner in owners:
        item = proposition(owner=owner)
        domain = conduct_wire_to_domain(ConductComplianceWireOutput(propositions=(item,)), observed_at=NOW)
        assert domain.propositions[0].proposition_owner_kind == owner["kind"]
        assert domain.propositions[0].proposition_owner_label == owner.get("label")


def test_provider_schema_uses_tagged_owner_and_rejects_legacy_flat_fields():
    schema = wire_schema()["$defs"]["ConductComplianceWireProposition"]
    assert "owner" in schema["required"]
    assert "proposition_owner_kind" not in schema["properties"]
    assert "proposition_owner_label" not in schema["properties"]


def test_historical_owner_recovery_removes_only_redundant_inapplicable_label():
    raw_item = proposition().model_dump(mode="json")
    raw_item.pop("owner")
    raw_item.update({"proposition_owner_kind": "source_publisher", "proposition_owner_label": "redundant"})
    raw = {"propositions": [raw_item]}
    wire, diagnostics = recover_historical_wire(raw)
    assert wire.propositions[0].owner.kind == "source_publisher"
    assert diagnostics["removed_owner_labels"][0]["redundant_label"] == "redundant"
    assert wire.propositions[0].statement == "The regulator published an enforcement action."


def test_historical_recovery_removes_null_observed_at_and_injects_builder_time():
    raw_item = proposition().model_dump(mode="json")
    raw_item.pop("owner")
    raw_item.update({"proposition_owner_kind": "source_publisher", "proposition_owner_label": "redundant"})
    raw_item["temporal"]["observed_at"] = None
    from charitygraph.section16_recovery import recover_historical_domain
    output, diagnostics = recover_historical_domain({"propositions": [raw_item]}, observed_at=NOW)
    assert output.propositions[0].observation_time.observed_at == NOW
    assert diagnostics["removed_owner_labels"][0]["removed_temporal_observed_at"] is True
