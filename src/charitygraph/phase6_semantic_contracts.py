"""Review-only semantic contracts for bounded Phase 6 confirmation work.

These typed task contracts are deliberately isolated from production task
registration, persistence, projections, and Direct Service V1.2. They encode
mechanical distinctions between the three Phase 6 slices without attempting
natural-language classification in Python.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import Field, StrictStr, field_validator, model_validator

from .contracts.common import StrictModel, require_nonblank


ScopeKind = Literal["organisation", "program", "service", "study_population", "site"]
SourceRole = Literal[
    "official_homepage", "annual_report", "financial_report", "first_party_policy",
    "historical_frozen_regulator_material", "regulator_record", "court_or_inquiry_record",
    "independent_evaluation", "external_authoritative", "unknown",
]
EpistemicClass = Literal[
    "source_native_record", "first_party_claim", "first_party_measure_reported",
    "independent_finding_reported", "source_claimed_causation",
]

FIRST_PARTY_ROLES = {"official_homepage", "annual_report", "financial_report", "first_party_policy"}
REGULATOR_ROLES = {"historical_frozen_regulator_material", "regulator_record", "court_or_inquiry_record"}
INDEPENDENT_ROLES = {"independent_evaluation", "external_authoritative", "court_or_inquiry_record"}


class Phase6Scope(StrictModel):
    scope_id: StrictStr
    scope_kind: ScopeKind
    scope_label: StrictStr

    @field_validator("scope_id", "scope_label")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)


class Phase6EvidenceRef(StrictModel):
    """One immutable, request-bound evidence locator and its source role/date."""

    locator_id: StrictStr
    source_role: SourceRole
    source_date: date | None = None
    retrieved_at: datetime | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    @field_validator("locator_id")
    @classmethod
    def _locator(cls, value: str) -> str:
        return require_nonblank(value, "locator_id")


class _EvidenceBound(StrictModel):
    scope: Phase6Scope
    evidence: tuple[Phase6EvidenceRef, ...] = Field(min_length=1)
    epistemic_class: EpistemicClass

    @model_validator(mode="after")
    def _unique_locators(self):
        if len({item.locator_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence locator IDs must be unique")
        if self.epistemic_class in {"first_party_claim", "first_party_measure_reported"}:
            _require_any_role(self.evidence, FIRST_PARTY_ROLES, "first-party epistemic class conflicts with source role")
        elif self.epistemic_class == "source_native_record":
            _require_any_role(self.evidence, REGULATOR_ROLES, "source-native record requires regulator/source-native evidence")
        elif self.epistemic_class == "independent_finding_reported":
            _require_any_role(self.evidence, INDEPENDENT_ROLES, "independent finding epistemic class conflicts with source role")
        elif self.epistemic_class == "source_claimed_causation":
            _require_any_role(self.evidence, FIRST_PARTY_ROLES | INDEPENDENT_ROLES, "causal claim requires an attributable source")
        return self


def _require_any_role(evidence: tuple[Phase6EvidenceRef, ...], allowed: set[str], message: str) -> None:
    if not any(item.source_role in allowed for item in evidence):
        raise ValueError(message)


OutcomeKind = Literal[
    "activity_reported", "output_reported", "reach_or_participation_reported",
    "outcome_observed_reported", "contribution_claim_reported",
    "causal_attribution_claim_reported", "causal_evidence_supported",
]
OutcomeDomain = Literal[
    "health", "education", "housing_security", "wellbeing", "ecological_condition",
    "social_condition", "safety", "other_beneficiary_or_target_state",
]


class ActivityReported(_EvidenceBound):
    proposition_type: Literal["activity_reported"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    activity_kind: Literal["service_delivery", "research", "advocacy", "management", "fundraising", "other"]
    reporting_period: StrictStr | None = None
    count: Decimal | None = None
    unit: StrictStr | None = None

    @model_validator(mode="after")
    def _roles(self):
        _require_any_role(self.evidence, FIRST_PARTY_ROLES | REGULATOR_ROLES, "activity report requires first-party or source-native evidence")
        return self


class OutputReported(_EvidenceBound):
    proposition_type: Literal["output_reported"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    output_kind: Literal["services_delivered", "grants_made", "funds_raised", "hectares_managed", "publications", "other_direct_output"]
    measure: Decimal | StrictStr
    unit: StrictStr
    reporting_period: StrictStr


class ReachReported(_EvidenceBound):
    proposition_type: Literal["reach_or_participation_reported"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    population: StrictStr
    count: Decimal
    unit: StrictStr
    reporting_period: StrictStr
    denominator: StrictStr | None = None


class OutcomeObservedReported(_EvidenceBound):
    proposition_type: Literal["outcome_observed_reported"]
    epistemic_class: Literal["first_party_measure_reported", "independent_finding_reported"]
    measured_subject_kind: Literal["beneficiary_state", "target_system_condition"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    indicator: StrictStr
    measured_result: Decimal | StrictStr
    unit: StrictStr
    measurement_period: StrictStr

    @model_validator(mode="after")
    def _outcome_requires_measurement(self):
        require_nonblank(self.population, "population")
        require_nonblank(self.indicator, "indicator")
        require_nonblank(self.unit, "unit")
        require_nonblank(self.measurement_period, "measurement_period")
        if self.epistemic_class == "independent_finding_reported":
            _require_any_role(self.evidence, INDEPENDENT_ROLES, "independent outcome finding requires independent evidence")
        else:
            _require_any_role(self.evidence, FIRST_PARTY_ROLES, "first-party outcome measure must be labelled as a first-party report")
        return self


class ContributionClaimReported(_EvidenceBound):
    proposition_type: Literal["contribution_claim_reported"]
    epistemic_class: Literal["first_party_claim", "independent_finding_reported"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    activity: StrictStr
    claimed_relation: Literal["contributed_to", "supported", "associated_with"]

    @model_validator(mode="after")
    def _roles(self):
        roles = INDEPENDENT_ROLES if self.epistemic_class == "independent_finding_reported" else FIRST_PARTY_ROLES
        _require_any_role(self.evidence, roles, "contribution claim epistemic class conflicts with source role")
        return self


class CausalAttributionClaimReported(_EvidenceBound):
    proposition_type: Literal["causal_attribution_claim_reported"]
    epistemic_class: Literal["source_claimed_causation"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    intervention: StrictStr
    attributed_result: StrictStr

    @model_validator(mode="after")
    def _source_claim_only(self):
        _require_any_role(self.evidence, FIRST_PARTY_ROLES | INDEPENDENT_ROLES, "reported causal claim requires an attributable source")
        return self


class CausalEvidenceSupported(_EvidenceBound):
    proposition_type: Literal["causal_evidence_supported"]
    epistemic_class: Literal["independent_finding_reported"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    intervention: StrictStr
    comparator: StrictStr
    measured_result: StrictStr
    study_design: Literal["randomized_comparison", "quasi_experimental", "natural_experiment", "other_explicit_counterfactual"]
    study_period: StrictStr
    limitations: tuple[StrictStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _causal_basis(self):
        _require_any_role(self.evidence, {"independent_evaluation", "external_authoritative"}, "supported causal evidence requires independent evaluation evidence")
        for field_name in ("population", "intervention", "comparator", "measured_result", "study_period"):
            require_nonblank(getattr(self, field_name), field_name)
        return self


OutcomeClaim = Annotated[
    Union[ActivityReported, OutputReported, ReachReported, OutcomeObservedReported,
          ContributionClaimReported, CausalAttributionClaimReported, CausalEvidenceSupported],
    Field(discriminator="proposition_type"),
]


CommitmentKind = Literal["commitment", "pledge", "goal", "target", "formal_obligation"]


class CommitmentStated(_EvidenceBound):
    proposition_type: Literal["commitment_stated"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    commitment_kind: CommitmentKind
    instrument: StrictStr
    stated_period: StrictStr | None = None


class PolicyOrStandardAdopted(_EvidenceBound):
    proposition_type: Literal["policy_or_standard_adopted"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    instrument: StrictStr
    adoption_status: Literal["adopted", "not_adopted", "unclear"]


class ImplementationActivitySelfReported(_EvidenceBound):
    proposition_type: Literal["implementation_activity_self_reported"]
    epistemic_class: Literal["first_party_claim"]
    activity: StrictStr
    activity_status: Literal["planned", "in_progress", "reported_completed"]
    reporting_period: StrictStr | None = None

    @model_validator(mode="after")
    def _first_party_only(self):
        _require_any_role(self.evidence, FIRST_PARTY_ROLES, "self-reported implementation requires first-party evidence")
        return self


class ImplementationActivityIndependentlyObserved(_EvidenceBound):
    proposition_type: Literal["implementation_activity_independently_observed"]
    epistemic_class: Literal["independent_finding_reported"]
    activity: StrictStr
    observation_period: StrictStr
    evaluator_or_authority: StrictStr

    @model_validator(mode="after")
    def _independent_only(self):
        _require_any_role(self.evidence, INDEPENDENT_ROLES, "independently observed implementation requires independent evidence")
        return self


class ImplementationEvidenceExternal(_EvidenceBound):
    proposition_type: Literal["implementation_evidence_regulatory_or_external"]
    epistemic_class: Literal["independent_finding_reported", "source_native_record"]
    finding_kind: Literal["regulatory_finding", "court_finding", "external_audit", "independent_assessment"]
    finding: StrictStr
    finding_period: StrictStr | None = None

    @model_validator(mode="after")
    def _external_only(self):
        _require_any_role(self.evidence, REGULATOR_ROLES | INDEPENDENT_ROLES, "external implementation evidence requires regulator, court, or independent evidence")
        return self


class ImplementationOutcomeReported(_EvidenceBound):
    proposition_type: Literal["implementation_outcome_reported"]
    epistemic_class: Literal["first_party_measure_reported", "independent_finding_reported"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    result: StrictStr
    reporting_period: StrictStr


CommitmentClaim = Annotated[
    Union[CommitmentStated, PolicyOrStandardAdopted, ImplementationActivitySelfReported,
          ImplementationActivityIndependentlyObserved, ImplementationEvidenceExternal,
          ImplementationOutcomeReported],
    Field(discriminator="proposition_type"),
]


class ServiceExists(_EvidenceBound):
    proposition_type: Literal["service_exists"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    service_name: StrictStr
    service_scope: Literal["organisation", "program", "service"]


class IntendedBeneficiaryGroup(_EvidenceBound):
    proposition_type: Literal["intended_beneficiary_group"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    population: StrictStr


class FormalEligibilityRule(_EvidenceBound):
    proposition_type: Literal["formal_eligibility_rule"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    rule_basis: Literal["explicit_published_criteria", "mandated_criterion"]
    rule_issuer: StrictStr
    rule: StrictStr
    assessment_required: bool


class AccessInformation(_EvidenceBound):
    proposition_type: Literal["access_information"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    information_kind: Literal["address", "contact", "directions", "service_hours", "information_page", "online_flag"]
    information: StrictStr


class AccessPathway(_EvidenceBound):
    proposition_type: Literal["access_pathway"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    entry_actions: tuple[Literal["apply", "request_referral", "call_intake", "book_appointment", "complete_assessment", "attend_drop_in", "submit_online_request"], ...] = Field(min_length=1)
    entry_conditions: tuple[StrictStr, ...] = ()


class HistoricalActivityVolume(_EvidenceBound):
    proposition_type: Literal["historical_activity_volume"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    measure: Decimal
    unit: StrictStr
    period: StrictStr


class ResourceOrWorkforceMeasure(_EvidenceBound):
    proposition_type: Literal["resource_or_workforce_measure"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    resource_kind: Literal["expenditure", "staff_fte", "volunteers", "funds", "other_resource"]
    measure: Decimal
    unit: StrictStr
    period: StrictStr


class ServiceScaleMeasure(_EvidenceBound):
    proposition_type: Literal["service_scale_measure"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    scale_kind: Literal["homes", "beds", "locations", "people_served", "services_delivered", "other_scale"]
    measure: Decimal
    unit: StrictStr
    period: StrictStr


class CapacityLimitOrMeasure(_EvidenceBound):
    proposition_type: Literal["capacity_limit_or_capacity_measure"]
    epistemic_class: Literal["first_party_measure_reported", "source_native_record"]
    capacity_basis: Literal["published_limit", "maximum_throughput", "concurrent_capacity", "available_slots_as_of"]
    measure: Decimal
    unit: Literal["people", "places", "beds", "appointments", "appointments_per_period", "service_instances_per_period", "available_slots"]
    as_of: date
    measurement_period: StrictStr | None = None


Availability = Literal["available", "limited", "waitlisted", "unavailable", "unknown"]


class AvailabilityReportedAsOf(_EvidenceBound):
    proposition_type: Literal["availability_reported_as_of_date"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    status: Availability
    as_of: date


class CurrentAvailability(_EvidenceBound):
    proposition_type: Literal["current_availability"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    status: Literal["available", "limited", "waitlisted", "unavailable"]
    as_of: date
    freshness_policy_id: StrictStr

    @field_validator("freshness_policy_id")
    @classmethod
    def _policy_id(cls, value: str) -> str:
        return require_nonblank(value, "freshness_policy_id")


class AvailabilityUnknown(StrictModel):
    proposition_type: Literal["availability_unknown"]
    scope: Phase6Scope
    coverage_state: Literal["source_silent", "source_unavailable", "not_processed", "processing_failed", "stale", "unknown"]
    evidence: tuple[Phase6EvidenceRef, ...] = ()


CapacityClaim = Annotated[
    Union[ServiceExists, IntendedBeneficiaryGroup, FormalEligibilityRule, AccessInformation,
          AccessPathway, HistoricalActivityVolume, ResourceOrWorkforceMeasure, ServiceScaleMeasure,
          CapacityLimitOrMeasure, AvailabilityReportedAsOf, CurrentAvailability, AvailabilityUnknown],
    Field(discriminator="proposition_type"),
]


class Phase6SemanticOutput(StrictModel):
    """One slice-local, unreviewed candidate output; never a persisted decision."""

    slice_id: Literal["outcomes", "commitments", "capacity"]
    subject_id: StrictStr
    propositions: tuple[OutcomeClaim | CommitmentClaim | CapacityClaim, ...] = ()

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return require_nonblank(value, "subject_id")

    @model_validator(mode="after")
    def _slice_types(self):
        expected = {
            "outcomes": OutcomeKind.__args__,
            "commitments": (
                "commitment_stated", "policy_or_standard_adopted", "implementation_activity_self_reported",
                "implementation_activity_independently_observed", "implementation_evidence_regulatory_or_external",
                "implementation_outcome_reported",
            ),
            "capacity": (
                "service_exists", "intended_beneficiary_group", "formal_eligibility_rule", "access_information",
                "access_pathway", "historical_activity_volume", "resource_or_workforce_measure", "service_scale_measure",
                "capacity_limit_or_capacity_measure", "availability_reported_as_of_date", "current_availability", "availability_unknown",
            ),
        }[self.slice_id]
        if any(item.proposition_type not in expected for item in self.propositions):
            raise ValueError("proposition type does not belong to the selected Phase 6 slice")
        return self


def validate_scope_bindings(output: Phase6SemanticOutput, allowed_scope_ids: set[str]) -> None:
    """Require all proposition scopes to be explicitly present in the task packet."""

    if not allowed_scope_ids:
        raise ValueError("Phase 6 task must provide at least one allowed scope ID")
    for item in output.propositions:
        if item.scope.scope_id not in allowed_scope_ids:
            raise ValueError(f"unknown proposition scope_id: {item.scope.scope_id}")


def validate_current_availability_freshness(
    item: CurrentAvailability,
    *,
    assessed_at: datetime,
    max_age: timedelta,
) -> None:
    """Fail closed unless dated evidence meets an explicitly approved freshness window."""

    if max_age <= timedelta(0):
        raise ValueError("freshness window must be positive")
    assessment = assessed_at if assessed_at.tzinfo is not None else assessed_at.replace(tzinfo=timezone.utc)
    evidence_times = []
    for evidence in item.evidence:
        if evidence.retrieved_at is not None:
            when = evidence.retrieved_at if evidence.retrieved_at.tzinfo is not None else evidence.retrieved_at.replace(tzinfo=timezone.utc)
            evidence_times.append(when)
        elif evidence.source_date is not None:
            evidence_times.append(datetime.combine(evidence.source_date, datetime.min.time(), tzinfo=timezone.utc))
    if not evidence_times:
        raise ValueError("current availability requires dated evidence")
    if item.as_of > assessment.date():
        raise ValueError("current availability as_of is dated after the assessment time")
    if any(when > assessment for when in evidence_times):
        raise ValueError("availability evidence is dated after the assessment time")
    if assessment.date() - item.as_of > max_age:
        raise ValueError("current availability as_of exceeds the approved freshness window")
    if assessment - max(evidence_times) > max_age:
        raise ValueError("source evidence exceeds the approved freshness window")


__all__ = [
    "Phase6Scope", "Phase6EvidenceRef", "Phase6SemanticOutput", "OutcomeClaim", "CommitmentClaim",
    "CapacityClaim", "validate_scope_bindings", "validate_current_availability_freshness",
    "ActivityReported", "OutputReported", "ReachReported", "OutcomeObservedReported",
    "ContributionClaimReported", "CausalAttributionClaimReported", "CausalEvidenceSupported",
    "CommitmentStated", "PolicyOrStandardAdopted", "ImplementationActivitySelfReported",
    "ImplementationActivityIndependentlyObserved", "ImplementationEvidenceExternal", "ImplementationOutcomeReported",
    "ServiceExists", "IntendedBeneficiaryGroup", "FormalEligibilityRule", "AccessInformation",
    "AccessPathway", "HistoricalActivityVolume", "ResourceOrWorkforceMeasure", "ServiceScaleMeasure",
    "CapacityLimitOrMeasure", "AvailabilityReportedAsOf", "CurrentAvailability", "AvailabilityUnknown",
]
