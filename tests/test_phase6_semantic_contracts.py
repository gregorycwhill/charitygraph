from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.phase6_semantic_contracts import (
    AccessInformation,
    AccessPathway,
    ActivityReported,
    AvailabilityUnknown,
    CapacityLimitOrMeasure,
    CausalAttributionClaimReported,
    CausalEvidenceSupported,
    CommitmentStated,
    CurrentAvailability,
    FormalEligibilityRule,
    ImplementationActivityIndependentlyObserved,
    ImplementationActivitySelfReported,
    IntendedBeneficiaryGroup,
    OutcomeObservedReported,
    Phase6EvidenceRef,
    Phase6Scope,
    Phase6SemanticOutput,
    ReachReported,
    ResourceOrWorkforceMeasure,
    ServiceScaleMeasure,
    validate_current_availability_freshness,
    validate_scope_bindings,
)
from charitygraph.phase5_standard_transport import body_sha256, canonical_standard_body_bytes
from charitygraph.phase6_evaluation_export import build_source_only_export


ORG = Phase6Scope(scope_id="scope:org-1", scope_kind="organisation", scope_label="Example Organisation")
FIRST_PARTY = Phase6EvidenceRef(
    locator_id="locator:1", source_role="annual_report", source_date=date(2025, 6, 30),
)
INDEPENDENT = Phase6EvidenceRef(
    locator_id="locator:2", source_role="independent_evaluation", source_date=date(2025, 6, 30),
)


def test_reach_and_measured_outcome_are_different_required_shapes():
    reach = ReachReported(
        proposition_type="reach_or_participation_reported", scope=ORG,
        epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
        population="people receiving support", count=5_000_000, unit="people", reporting_period="FY2025",
    )
    assert reach.proposition_type == "reach_or_participation_reported"
    with pytest.raises(ValidationError, match="measured_subject_kind"):
        OutcomeObservedReported(
            proposition_type="outcome_observed_reported", scope=ORG,
            epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
            outcome_domain="wellbeing", population="people receiving support", indicator="people reached",
            measured_result=5_000_000, unit="people", measurement_period="FY2025",
        )
    observed = OutcomeObservedReported(
        proposition_type="outcome_observed_reported", scope=ORG,
        epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
        measured_subject_kind="beneficiary_state", outcome_domain="education",
        population="Learning for Life students", indicator="reading age change",
        measured_result="reported improvement", unit="reading-age months", measurement_period="FY2025",
    )
    assert observed.proposition_type != reach.proposition_type


def test_first_party_report_cannot_be_typed_as_independent_observation():
    with pytest.raises(ValidationError, match="conflicts with source role"):
        ImplementationActivityIndependentlyObserved(
            proposition_type="implementation_activity_independently_observed", scope=ORG,
            epistemic_class="independent_finding_reported", evidence=(FIRST_PARTY,),
            activity="reported implementation activity", observation_period="FY2025", evaluator_or_authority="External reviewer",
        )
    self_report = ImplementationActivitySelfReported(
        proposition_type="implementation_activity_self_reported", scope=ORG,
        epistemic_class="first_party_claim", evidence=(FIRST_PARTY,),
        activity="implementation activity", activity_status="reported_completed", reporting_period="FY2025",
    )
    assert self_report.proposition_type == "implementation_activity_self_reported"
    commitment = CommitmentStated(
        proposition_type="commitment_stated", scope=ORG, epistemic_class="first_party_claim",
        evidence=(FIRST_PARTY,), commitment_kind="target", instrument="published target", stated_period="by 2030",
    )
    assert commitment.proposition_type != self_report.proposition_type


def test_source_native_and_independent_classes_require_compatible_roles():
    with pytest.raises(ValidationError, match="source-native record requires"):
        ActivityReported(
            proposition_type="activity_reported", scope=ORG, epistemic_class="source_native_record",
            evidence=(FIRST_PARTY,), activity_kind="service_delivery",
        )


def test_source_causal_claim_and_independently_supported_causality_stay_separate():
    attributed = CausalAttributionClaimReported(
        proposition_type="causal_attribution_claim_reported", scope=ORG,
        epistemic_class="source_claimed_causation", evidence=(FIRST_PARTY,),
        outcome_domain="ecological_condition", population="managed reserves",
        intervention="active management", attributed_result="ecosystem health improved",
    )
    assert attributed.proposition_type == "causal_attribution_claim_reported"
    with pytest.raises(ValidationError, match="independent finding epistemic class conflicts with source role"):
        CausalEvidenceSupported(
            proposition_type="causal_evidence_supported", scope=ORG,
            epistemic_class="independent_finding_reported", evidence=(FIRST_PARTY,),
            outcome_domain="ecological_condition", population="managed reserves", intervention="active management",
            comparator="unmanaged reserves", measured_result="change", study_design="quasi_experimental",
            study_period="2020-2025", limitations=("limited generalizability",),
        )
    supported = CausalEvidenceSupported(
        proposition_type="causal_evidence_supported", scope=ORG,
        epistemic_class="independent_finding_reported", evidence=(INDEPENDENT,),
        outcome_domain="ecological_condition", population="studied reserves", intervention="active management",
        comparator="matched comparison sites", measured_result="estimated change", study_design="quasi_experimental",
        study_period="2020-2025", limitations=("limited generalizability",),
    )
    assert supported.proposition_type != attributed.proposition_type


def test_activity_and_resource_counts_do_not_become_outcomes_or_capacity():
    activity = ActivityReported(
        proposition_type="activity_reported", scope=ORG, epistemic_class="first_party_claim",
        evidence=(FIRST_PARTY,), activity_kind="management", count=Decimal("100"), unit="hectares",
        reporting_period="FY2025",
    )
    expenditure = ResourceOrWorkforceMeasure(
        proposition_type="resource_or_workforce_measure", scope=ORG,
        epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
        resource_kind="expenditure", measure=Decimal("97000000"), unit="AUD", period="FY2025",
    )
    homes = ServiceScaleMeasure(
        proposition_type="service_scale_measure", scope=ORG,
        epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
        scale_kind="homes", measure=Decimal("7000"), unit="homes", period="FY2025",
    )
    assert activity.proposition_type == "activity_reported"
    assert expenditure.proposition_type != "capacity_limit_or_capacity_measure"
    assert homes.proposition_type != "capacity_limit_or_capacity_measure"
    with pytest.raises(ValidationError):
        CapacityLimitOrMeasure(
            proposition_type="capacity_limit_or_capacity_measure", scope=ORG,
            epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
            capacity_basis="published_limit", measure=Decimal("97000000"), unit="AUD", as_of=date(2025, 6, 30),
        )
    with pytest.raises(ValidationError):
        CapacityLimitOrMeasure(
            proposition_type="capacity_limit_or_capacity_measure", scope=ORG,
            epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
            capacity_basis="published_limit", measure=Decimal("7000"), unit="homes", as_of=date(2025, 6, 30),
        )


def test_intended_beneficiary_is_not_formal_eligibility():
    beneficiary = IntendedBeneficiaryGroup(
        proposition_type="intended_beneficiary_group", scope=ORG,
        epistemic_class="first_party_claim", evidence=(FIRST_PARTY,), population="children with cancer",
    )
    assert beneficiary.proposition_type == "intended_beneficiary_group"
    with pytest.raises(ValidationError):
        IntendedBeneficiaryGroup(
            proposition_type="intended_beneficiary_group", scope=ORG,
            epistemic_class="first_party_claim", evidence=(FIRST_PARTY,), population="children with cancer",
            eligibility_rule="diagnosis required",
        )
    formal = FormalEligibilityRule(
        proposition_type="formal_eligibility_rule", scope=ORG,
        epistemic_class="first_party_claim", evidence=(FIRST_PARTY,),
        rule_basis="explicit_published_criteria", rule_issuer="service operator",
        rule="referral and diagnosis required", assessment_required=True,
    )
    assert formal.proposition_type != beneficiary.proposition_type


def test_address_and_online_flag_are_information_not_access_pathways():
    address = AccessInformation(
        proposition_type="access_information", scope=ORG, epistemic_class="first_party_claim",
        evidence=(FIRST_PARTY,), information_kind="address", information="Example Street",
    )
    assert address.proposition_type == "access_information"
    with pytest.raises(ValidationError, match="entry_actions"):
        AccessPathway(
            proposition_type="access_pathway", scope=ORG, epistemic_class="first_party_claim",
            evidence=(FIRST_PARTY,),
        )
    pathway = AccessPathway(
        proposition_type="access_pathway", scope=ORG, epistemic_class="first_party_claim",
        evidence=(FIRST_PARTY,), entry_actions=("request_referral", "complete_assessment"),
    )
    assert pathway.entry_actions[0] == "request_referral"


def test_unknown_availability_is_valid_but_current_claim_needs_a_date_and_policy():
    unknown = AvailabilityUnknown(
        proposition_type="availability_unknown", scope=ORG, coverage_state="source_unavailable",
    )
    assert unknown.coverage_state == "source_unavailable"
    with pytest.raises(ValidationError):
        CurrentAvailability(
            proposition_type="current_availability", scope=ORG,
            epistemic_class="first_party_claim", evidence=(FIRST_PARTY,), status="available",
        )
    current = CurrentAvailability(
        proposition_type="current_availability", scope=ORG,
        epistemic_class="first_party_claim",
        evidence=(Phase6EvidenceRef(locator_id="locator:recent", source_role="official_homepage", retrieved_at=datetime(2025, 6, 30, tzinfo=timezone.utc)),),
        status="available", as_of=date(2025, 6, 30), freshness_policy_id="owner-approved:availability-v1",
    )
    validate_current_availability_freshness(
        current, assessed_at=datetime(2025, 7, 1, tzinfo=timezone.utc), max_age=timedelta(days=30),
    )
    with pytest.raises(ValueError, match="exceeds the approved freshness window"):
        validate_current_availability_freshness(
            current, assessed_at=datetime(2025, 8, 15, tzinfo=timezone.utc), max_age=timedelta(days=30),
        )


def test_scope_bindings_are_exact_and_no_label_matching_is_used():
    item = ReachReported(
        proposition_type="reach_or_participation_reported", scope=ORG,
        epistemic_class="first_party_measure_reported", evidence=(FIRST_PARTY,),
        population="people reached", count=100, unit="people", reporting_period="FY2025",
    )
    output = Phase6SemanticOutput(slice_id="outcomes", subject_id="subject:1", propositions=(item,))
    validate_scope_bindings(output, {ORG.scope_id})
    with pytest.raises(ValueError, match="unknown proposition scope_id"):
        validate_scope_bindings(output, {"scope:other"})


def _write_fake_request(root: Path, ordinal: int, source_content: str):
    payload = {
        "subject_id": "subject:1", "subject_name": "Example Organisation", "abn": "11111111111",
        "slice_id": "outcomes", "organization_scope": {"scope_id": "scope:1", "scope_kind": "organisation", "label": "Example Organisation"},
        "sources": [{
            "source_record_id": "srcrec:1", "source_family": "annual_report", "source_role": "annual_report",
            "source_locator": "private://frozen", "evidence_locator_id": "locator:1", "source_artifact_id": "srcblob:1",
            "representation_artifact_id": "artifact:1", "source_date": "2025-06-30", "retrieved_at": "2025-07-01T00:00:00Z",
            "content": source_content,
        }],
        "unavailable_sources": [],
    }
    body = {"model": "test-only", "input": [{"role": "system", "content": "internal prompt"}, {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload)}]}]}
    row = {
        "logical_request_id": f"logical:{ordinal}", "slice_id": "outcomes", "abn": "11111111111", "subject_name": "Example Organisation",
        "replicate_ordinal": ordinal, "request_body_sha256": body_sha256(canonical_standard_body_bytes(body)),
        "source_refs": [{
            "evidence_locator_id": "locator:1", "source_family": "annual_report", "source_role": "annual_report",
            "source_artifact_id": "srcblob:1", "representation_artifact_id": "artifact:1", "locator_kind": "pdf_page_quote",
            "source_date": "2025-06-30", "retrieved_at": "2025-07-01T00:00:00Z", "effective_period": "FY2025",
        }],
    }
    request_file = {"provider_request_body": body}
    (root / f"outcomes__11111111111__{ordinal}.json").write_text(json.dumps(request_file), encoding="utf-8")
    return row


def test_source_only_export_is_candidate_blind_exact_and_rejects_repeat_drift(tmp_path):
    source_root = tmp_path / "inputs"
    source_root.mkdir()
    prep = {"requests": [
        _write_fake_request(source_root, 1, "\nEXACT REPRESENTATION\n"),
        _write_fake_request(source_root, 2, "\nEXACT REPRESENTATION\n"),
    ]}
    (source_root / "preparation.json").write_text(json.dumps(prep), encoding="utf-8")
    output_root = tmp_path / "blind"
    manifest = build_source_only_export(source_root, output_root)
    assert manifest["task_count"] == 1
    assert manifest["candidate_outputs_read"] == 0
    assert manifest["candidate_propositions_included"] == 0
    task = json.loads((output_root / "tasks/outcomes__11111111111.json").read_text(encoding="utf-8"))
    assert task["sources"][0]["exact_transmitted_representation"] == "\nEXACT REPRESENTATION\n"
    assert task["allowed_scope_ids"][0]["scope_id"] == "scope:1"
    assert "candidate" not in json.dumps(task).casefold()
    with pytest.raises(FileExistsError):
        build_source_only_export(source_root, output_root)

    drift_root = tmp_path / "drift"
    drift_root.mkdir()
    prep_drift = {"requests": [
        _write_fake_request(drift_root, 1, "SOURCE ONE"),
        _write_fake_request(drift_root, 2, "SOURCE TWO"),
    ]}
    (drift_root / "preparation.json").write_text(json.dumps(prep_drift), encoding="utf-8")
    with pytest.raises(ValueError, match="source inputs differ"):
        build_source_only_export(drift_root, tmp_path / "drift-output")
