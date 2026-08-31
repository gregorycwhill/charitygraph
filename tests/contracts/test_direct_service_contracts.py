from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from charitygraph.contracts import (
    DIRECT_SERVICE_OUTPUT_SCHEMA,
    DirectServiceEvidenceRef,
    DirectServiceProposition,
    DirectServiceSemanticOutput,
    DirectServiceRelationship,
    DirectServiceWireOutput,
    DirectServiceWireProposition,
    DirectServiceWireEvidenceRef,
    wire_to_domain,
    project_observation,
    ModelTaskType,
    validate_scope_bindings,
)
from charitygraph.strict_schema import strictify_schema, validate_strict_schema
from charitygraph.contracts.semantic import TASK_OUTPUT_SCHEMAS


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)
EVIDENCE = (DirectServiceEvidenceRef(locator="evidence:S001:L0001", role="supporting"),)


def proposition(kind="service_offer", **updates):
    value = {
        "proposition_type": kind,
        "scope_id": "scope:" + "1" * 32,
        "scope_kind": "service",
        "scope_label": "Crisis support service",
        "coverage_state": "supported",
        "value": "offered",
        "evidence": EVIDENCE,
        "observation_time": {"observed_at": NOW},
    }
    value.update(updates)
    return DirectServiceProposition.model_validate(value)


def test_contract_is_typed_and_sections_are_not_collapsed():
    participation = DirectServiceSemanticOutput(
        section="participation",
        propositions=(
            proposition("participation_opportunity", scope_kind="organisation", scope_label="Australian Red Cross"),
            proposition("participation_measure", value=16_000, unit="people"),
        ),
    )
    assert {item.proposition_type for item in participation.propositions} == {
        "participation_opportunity", "participation_measure",
    }
    with pytest.raises(ValidationError):
        DirectServiceSemanticOutput(section="participation", propositions=(proposition("service_offer"),))


def test_supported_and_absence_states_require_evidence_but_missingness_stays_distinct():
    for state in ("supported", "asserted_none", "observed_absent"):
        with pytest.raises(ValidationError):
            proposition(coverage_state=state, evidence=())
    values = [proposition("current_availability", coverage_state=state, evidence=()) for state in (
        "source_silent", "not_found", "not_attempted", "unknown",
    )]
    assert [item.coverage_state for item in values] == ["source_silent", "not_found", "not_attempted", "unknown"]
    with pytest.raises(ValidationError):
        proposition("service_offer", evidence=(DirectServiceEvidenceRef(locator="evidence:S001:L0002", role="context"),))


def test_service_existence_availability_and_capacity_are_distinct():
    offer = proposition("service_offer")
    availability = proposition("current_availability", value="unknown", coverage_state="source_silent", evidence=())
    capacity = proposition("capacity_measure", value=24, unit="places")
    assert offer.proposition_type != availability.proposition_type != capacity.proposition_type


def test_scheme_scope_and_status_do_not_become_quality_claims():
    accreditation = proposition(
        "accreditation", scope_kind="program", scope_label="First aid program",
        scheme_id="scheme:first-aid", scheme_version="2026", scheme_status="active",
        scheme_identifier="CERT-123",
    )
    membership = proposition(
        "scheme_membership", scope_kind="organisation", scope_label="Australian Red Cross",
        scheme_id="scheme:pfra", scheme_status="member",
    )
    assert accreditation.scope_kind == "program"
    assert membership.scope_kind == "organisation"
    with pytest.raises(ValidationError):
        proposition("accreditation", scheme_id="scheme:x", quality="high")


def test_relationship_roles_remain_distinct_and_evidence_bound():
    relationship = DirectServiceRelationship(
        source_scope_kind="organisation", source_scope_id="scope:" + "1" * 32, source_label="Australian Red Cross",
        target_scope_kind="service", target_scope_id="scope:" + "2" * 32, target_label="Emergency support",
        role="deliverer", direction="source_to_target", evidence=EVIDENCE,
    )
    assert relationship.role == "deliverer"
    with pytest.raises(ValidationError):
        DirectServiceRelationship(
            source_scope_kind="organisation", source_scope_id="scope:" + "1" * 32, source_label="Australian Red Cross",
            target_scope_kind="service", target_scope_id="scope:" + "2" * 32, target_label="Emergency support",
            role="operator", direction="source_to_target", evidence=(),
        )


def test_output_schema_and_task_registration_are_stable():
    assert DIRECT_SERVICE_OUTPUT_SCHEMA == TASK_OUTPUT_SCHEMAS["direct_service_semantics"]
    assert TypeAdapter(ModelTaskType).validate_python("direct_service_semantics") == "direct_service_semantics"


def test_scope_bindings_require_task_visible_ids_and_do_not_use_label_matching():
    output = DirectServiceSemanticOutput(section="participation", propositions=(proposition("participation_opportunity"),))
    validate_scope_bindings(output, {"scope:" + "1" * 32})
    with pytest.raises(ValueError, match="unknown proposition scope_id"):
        validate_scope_bindings(output, {"scope:" + "9" * 32})


def test_proposition_projects_to_existing_observation_without_collapsing_coverage():
    item = proposition("current_availability", value=None, coverage_state="source_silent", evidence=())
    projected = project_observation(
        item,
        record_id="observation:" + "a" * 32,
        subject_id="subject:" + "1" * 32,
        scope_id="scope:" + "2" * 32,
        source_record_ids=("srcrec:" + "3" * 32,),
        created_at=NOW,
        producer={"kind": "code", "producer_id": "direct-service-fixture"},
    )
    assert projected.scope_id == "scope:" + "2" * 32
    assert projected.predicate == "direct_service.current_availability"
    assert projected.value["coverage_state"] == "source_silent"


def test_provider_wire_schema_is_bounded_and_excludes_internal_value_algebra():
    schema = strictify_schema(DirectServiceWireOutput.model_json_schema())
    validate_strict_schema(schema)
    serialized = str(schema)
    assert "CanonicalValue" not in serialized
    assert "pattern" not in serialized
    assert "format" not in serialized
    assert not any(
        isinstance(node, dict) and isinstance(node.get("additionalProperties"), dict)
        for node in schema.get("$defs", {}).values()
        if isinstance(node, dict)
    )


def test_wire_output_converts_scalars_to_existing_domain_contract():
    wire = DirectServiceWireOutput(
        section="participation",
        propositions=(DirectServiceWireProposition(
            proposition_type="participation_measure", scope_id="scope:" + "1" * 32,
            scope_kind="service", scope_label="Training", coverage_state="supported",
            value=12.5, unit="people", evidence=(DirectServiceWireEvidenceRef(locator="evidence:S001:L0001", role="supporting"),),
            observation_time={"observed_at": NOW.isoformat()},
        ),),
    )
    domain = wire_to_domain(wire, allowed_scope_ids={"scope:" + "1" * 32}, evidence_locators={"evidence:S001:L0001"})
    assert domain.propositions[0].value == Decimal("12.5")
    assert type(domain.propositions[0].value) is Decimal


def test_wire_conversion_rejects_unknown_scope_and_evidence_locator():
    wire = DirectServiceWireOutput(section="participation", propositions=(DirectServiceWireProposition(
        proposition_type="participation_opportunity", scope_id="scope:" + "9" * 32,
        scope_kind="service", value="available", evidence=(DirectServiceWireEvidenceRef(locator="missing", role="supporting"),),
    ),))
    with pytest.raises(ValueError, match="evidence locator"):
        wire_to_domain(wire, allowed_scope_ids={"scope:" + "9" * 32}, evidence_locators={"evidence:S001:L0001"})
    with pytest.raises(ValueError, match="unknown proposition scope_id"):
        wire_to_domain(wire, allowed_scope_ids={"scope:" + "1" * 32}, evidence_locators={"missing"})
