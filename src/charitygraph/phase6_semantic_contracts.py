"""Review-only semantic contracts for bounded Phase 6 confirmation work.

These typed task contracts are deliberately isolated from production task
registration, persistence, projections, and Direct Service V1.2. They encode
mechanical distinctions between the three Phase 6 slices without attempting
natural-language classification in Python.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal, Union

from pydantic import Field, StrictStr, TypeAdapter, ValidationInfo, field_validator, model_validator

from .contracts.common import StrictModel, require_nonblank


ScopeKind = Literal["organisation", "program", "service", "study_population", "site"]
ReviewedEvidenceSourceStatus = Literal[
    "reviewed", "source_silent", "not_processed", "source_unavailable", "not_acquired", "processing_failed", "unknown",
]
ReviewedEvidenceCoverageState = Literal[
    "evidence_present", "not_found_in_reviewed_sources", "source_silent", "not_processed",
    "source_unavailable", "not_acquired", "processing_failed", "unknown", "not_applicable",
]
ReviewedEvidenceCoverageFamily = Literal["outcomes", "commitments"]
ReviewedEvidenceCoverageField = Literal[
    "observed_outcome_measure", "evaluation_assessment", "evaluator_identity", "method",
    "comparator_counterfactual", "limitations", "implementation_evidence",
    "independent_implementation_verification", "implementation_outcome",
    "affirmative_non_implementation_evidence",
]
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

# V5 corrects a V4 category error without changing V4's historical parser.
# A source role identifies the carrier of a record; a first-party epistemic
# class identifies the organisation as the claimant. Regulator material can
# faithfully carry an organisation's own submitted report, so it is a valid
# carrier for an organisation-reported assertion but never makes that assertion
# independently observed.
V5_ORGANISATION_REPORTED_CARRIER_ROLES = FIRST_PARTY_ROLES | REGULATOR_ROLES
_V5_VALIDATION = ContextVar("phase6_v5_validation", default=False)


@contextmanager
def phase6_v5_validation_context():
    """Apply V5 carrier/claimant semantics while validating V5 models only."""
    token = _V5_VALIDATION.set(True)
    try:
        yield
    finally:
        _V5_VALIDATION.reset(token)


def _organisation_reported_roles() -> set[str]:
    return V5_ORGANISATION_REPORTED_CARRIER_ROLES if _V5_VALIDATION.get() else FIRST_PARTY_ROLES


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


class ReviewedEvidenceSource(StrictModel):
    """One source's processing/review status within a named evidence universe."""

    source_record_id: StrictStr
    status: ReviewedEvidenceSourceStatus

    @field_validator("source_record_id")
    @classmethod
    def _source_record_id(cls, value: str) -> str:
        return require_nonblank(value, "source_record_id")


class ReviewedEvidenceUniverse(StrictModel):
    """A finite, explicitly scoped set of source records for coverage statements."""

    universe_id: StrictStr
    subject_id: StrictStr
    scope: Phase6Scope
    sources: tuple[ReviewedEvidenceSource, ...] = Field(min_length=1)

    @field_validator("universe_id", "subject_id")
    @classmethod
    def _universe_identity(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _unique_sources(self):
        source_ids = [source.source_record_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("reviewed evidence universe source IDs must be unique")
        return self


class ReviewedEvidenceCoverageEvidence(StrictModel):
    """Evidence locator bound to one source record in the reviewed universe."""

    source_record_id: StrictStr
    locator_id: StrictStr

    @field_validator("source_record_id", "locator_id")
    @classmethod
    def _evidence_identity(cls, value: str) -> str:
        return require_nonblank(value)


class ReviewedEvidenceCoverageItem(StrictModel):
    """Coverage for one named field, bounded to a particular reviewed universe."""

    universe_id: StrictStr
    field: ReviewedEvidenceCoverageField
    state: ReviewedEvidenceCoverageState
    evidence: tuple[ReviewedEvidenceCoverageEvidence, ...] = ()
    reviewed_source_record_ids: tuple[StrictStr, ...] = ()
    applicable_source_record_ids: tuple[StrictStr, ...] = ()
    rationale: StrictStr | None = None

    @field_validator("universe_id", "reviewed_source_record_ids", "applicable_source_record_ids")
    @classmethod
    def _nonblank_ids(cls, value):
        if isinstance(value, str):
            return require_nonblank(value)
        return tuple(require_nonblank(item) for item in value)

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _coverage_evidence_shape(self):
        if len({item.locator_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("coverage evidence locator IDs must be unique")
        if len(set(self.reviewed_source_record_ids)) != len(self.reviewed_source_record_ids):
            raise ValueError("reviewed source record IDs must be unique")
        if len(set(self.applicable_source_record_ids)) != len(self.applicable_source_record_ids):
            raise ValueError("applicable source record IDs must be unique")
        if self.state == "evidence_present" and not self.evidence:
            raise ValueError("evidence_present coverage requires evidence locators")
        if self.state == "not_found_in_reviewed_sources":
            if not self.reviewed_source_record_ids:
                raise ValueError("not_found_in_reviewed_sources requires reviewed source IDs")
            if self.evidence:
                raise ValueError("not_found_in_reviewed_sources cannot carry positive evidence locators")
        if self.state == "not_applicable" and self.rationale is None:
            raise ValueError("not_applicable coverage requires a scope-specific rationale")
        if self.state not in {"evidence_present", "not_found_in_reviewed_sources"} and self.evidence:
            raise ValueError("non-present coverage states cannot carry positive evidence locators")
        return self


_OUTCOMES_COVERAGE_FIELDS = {
    "observed_outcome_measure", "evaluation_assessment", "evaluator_identity", "method",
    "comparator_counterfactual", "limitations",
}
_COMMITMENTS_COVERAGE_FIELDS = {
    "implementation_evidence", "independent_implementation_verification", "implementation_outcome",
    "affirmative_non_implementation_evidence",
}


class ReviewedEvidenceCoverage(StrictModel):
    """Shared Outcomes/Commitments coverage, never a claim about sources outside its universe."""

    family: ReviewedEvidenceCoverageFamily
    universe: ReviewedEvidenceUniverse
    items: tuple[ReviewedEvidenceCoverageItem, ...]

    @model_validator(mode="after")
    def _scope_items_to_universe(self):
        expected = _OUTCOMES_COVERAGE_FIELDS if self.family == "outcomes" else _COMMITMENTS_COVERAGE_FIELDS
        fields = [item.field for item in self.items]
        if set(fields) != expected or len(fields) != len(expected):
            raise ValueError(f"{self.family} coverage must state each required field exactly once")
        source_status = {source.source_record_id: source.status for source in self.universe.sources}
        for item in self.items:
            if item.universe_id != self.universe.universe_id:
                raise ValueError("coverage item must reference its containing reviewed evidence universe")
            for evidence in item.evidence:
                if evidence.source_record_id not in source_status or source_status[evidence.source_record_id] != "reviewed":
                    raise ValueError("coverage evidence must bind to a reviewed source in this universe")
            if any(source_id not in source_status or source_status[source_id] != "reviewed" for source_id in item.reviewed_source_record_ids):
                raise ValueError("not-found coverage is limited to reviewed sources in this universe")
            if item.state == "not_found_in_reviewed_sources" and item.applicable_source_record_ids:
                if not set(item.applicable_source_record_ids).issubset(item.reviewed_source_record_ids):
                    raise ValueError("not-found applicability cannot exceed the reviewed source set")
            if item.state in {"source_silent", "not_processed", "source_unavailable", "not_acquired", "processing_failed", "unknown"}:
                expected_status = item.state
                if not item.applicable_source_record_ids:
                    raise ValueError(f"{item.state} coverage requires source IDs in the defined evidence universe")
                if any(source_status.get(source_id) != expected_status for source_id in item.applicable_source_record_ids):
                    raise ValueError(f"{item.state} coverage requires only matching source statuses in the universe")
        return self


class _EvidenceBound(StrictModel):
    scope: Phase6Scope
    evidence: tuple[Phase6EvidenceRef, ...] = Field(min_length=1)
    epistemic_class: EpistemicClass

    @model_validator(mode="after")
    def _unique_locators(self):
        if len({item.locator_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence locator IDs must be unique")
        if self.epistemic_class in {"first_party_claim", "first_party_measure_reported"}:
            _require_any_role(self.evidence, _organisation_reported_roles(), "first-party epistemic class conflicts with source role")
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
            _require_any_role(self.evidence, _organisation_reported_roles(), "first-party outcome measure must be labelled as a first-party report")
        return self


class OutcomeObservedReportedV6(OutcomeObservedReported):
    """V6 requires the reported observation basis to be named explicitly."""

    observation_basis: Literal[
        "quantitative_measurement", "qualitative_assessment",
        "monitoring_or_observation_result", "evaluation_result",
    ]
    observation_details: StrictStr

    @field_validator("observation_details")
    @classmethod
    def _observation_is_described(cls, value: str) -> str:
        return require_nonblank(value, "observation_details")


class ContributionClaimReported(_EvidenceBound):
    proposition_type: Literal["contribution_claim_reported"]
    epistemic_class: Literal["first_party_claim", "independent_finding_reported"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    activity: StrictStr
    claimed_relation: Literal["contributed_to", "supported", "associated_with"]

    @model_validator(mode="after")
    def _roles(self):
        roles = INDEPENDENT_ROLES if self.epistemic_class == "independent_finding_reported" else _organisation_reported_roles()
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


OutcomeClaimV6 = Annotated[
    Union[ActivityReported, OutputReported, ReachReported, OutcomeObservedReportedV6,
          ContributionClaimReported, CausalAttributionClaimReported, CausalEvidenceSupported],
    Field(discriminator="proposition_type"),
]


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


class CommitmentTextContent(StrictModel):
    """Substantive commitment wording retained from its cited source."""

    representation_type: Literal["source_text"]
    text: StrictStr

    @field_validator("text")
    @classmethod
    def _text_nonblank(cls, value: str) -> str:
        return require_nonblank(value, "commitment_content.text")


class CommitmentStructuredContent(StrictModel):
    """Typed equivalent that states both the committed action/state and WHAT it concerns."""

    representation_type: Literal["structured_equivalent"]
    committed_action_or_state: StrictStr
    object_or_result: StrictStr

    @field_validator("committed_action_or_state", "object_or_result")
    @classmethod
    def _structured_content_nonblank(cls, value: str) -> str:
        return require_nonblank(value, "commitment_content")


CommitmentContent = Annotated[
    Union[CommitmentTextContent, CommitmentStructuredContent],
    Field(discriminator="representation_type"),
]


class CommitmentStatedV5(_EvidenceBound):
    """Strengthened V5.1 commitment assertion with a mandatory substantive WHAT."""

    proposition_type: Literal["commitment_stated"]
    epistemic_class: Literal["first_party_claim", "source_native_record"]
    commitment_kind: CommitmentKind
    instrument: StrictStr
    commitment_content: CommitmentContent
    stated_period: StrictStr | None = None

    @field_validator("stated_period")
    @classmethod
    def _period_nonblank_if_present(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value, "stated_period")


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
        _require_any_role(self.evidence, _organisation_reported_roles(), "self-reported implementation requires organisation-reported evidence")
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


class ImplementationOutcomeReportedV5(_EvidenceBound):
    """V5 separates a measured implementation outcome from reach/activity."""

    proposition_type: Literal["implementation_outcome_reported"]
    epistemic_class: Literal["first_party_measure_reported", "independent_finding_reported"]
    outcome_domain: OutcomeDomain
    population: StrictStr
    indicator: StrictStr
    measured_result: Decimal | StrictStr
    unit: StrictStr
    measurement_period: StrictStr
    evidence_strength: Literal["organisation_reported_measure", "independent_evaluation_finding"]

    @model_validator(mode="after")
    def _measured_outcome_basis(self):
        for field_name in ("population", "indicator", "unit", "measurement_period"):
            require_nonblank(getattr(self, field_name), field_name)
        if self.epistemic_class == "independent_finding_reported":
            if self.evidence_strength != "independent_evaluation_finding":
                raise ValueError("independent implementation outcome requires independent evidence strength")
            _require_any_role(self.evidence, INDEPENDENT_ROLES, "independent implementation outcome requires independent evidence")
        else:
            if self.evidence_strength != "organisation_reported_measure":
                raise ValueError("organisation-reported implementation outcome requires organisation-reported evidence strength")
            _require_any_role(self.evidence, _organisation_reported_roles(), "organisation-reported implementation outcome requires an organisation-report carrier")
        return self


CommitmentClaim = Annotated[
    Union[CommitmentStated, PolicyOrStandardAdopted, ImplementationActivitySelfReported,
          ImplementationActivityIndependentlyObserved, ImplementationEvidenceExternal,
          ImplementationOutcomeReported],
    Field(discriminator="proposition_type"),
]

CommitmentClaimV5 = Annotated[
    Union[CommitmentStatedV5, PolicyOrStandardAdopted, ImplementationActivitySelfReported,
          ImplementationActivityIndependentlyObserved, ImplementationEvidenceExternal,
          ImplementationOutcomeReportedV5],
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


class Phase6SemanticOutputV2(StrictModel):
    """Historical v2 response DTO retained to reproduce the stopped-run failure."""

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


_SLICE_CLAIM_ADAPTERS = {
    "outcomes": TypeAdapter(list[OutcomeClaim]),
    "commitments": TypeAdapter(list[CommitmentClaim]),
    "capacity": TypeAdapter(list[CapacityClaim]),
}

_V5_SLICE_CLAIM_ADAPTERS = {
    "outcomes": TypeAdapter(list[OutcomeClaim]),
    "commitments": TypeAdapter(list[CommitmentClaimV5]),
    # Capacity is intentionally outside the V5 correction scope. Keeping its
    # existing adapter prevents V5 from silently broadening that experiment.
    "capacity": TypeAdapter(list[CapacityClaim]),
}

_V6_SLICE_CLAIM_ADAPTERS = {
    "outcomes": TypeAdapter(list[OutcomeClaimV6]),
    "commitments": TypeAdapter(list[CommitmentClaimV5]),
    "capacity": TypeAdapter(list[CapacityClaim]),
}


class Phase6SemanticOutput(StrictModel):
    """V3 slice-routed output; keeps cross-field semantic validation local."""

    contract_version: Literal["phase6-corrected-contracts-v3"] = "phase6-corrected-contracts-v3"
    slice_id: Literal["outcomes", "commitments", "capacity"]
    subject_id: StrictStr
    propositions: tuple[OutcomeClaim | CommitmentClaim | CapacityClaim, ...] = ()

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return require_nonblank(value, "subject_id")

    @field_validator("propositions", mode="before")
    @classmethod
    def _parse_for_selected_slice(cls, value: Any, info: ValidationInfo) -> Any:
        slice_id = info.data.get("slice_id")
        adapter = _SLICE_CLAIM_ADAPTERS.get(slice_id)
        if adapter is None or not isinstance(value, (list, tuple)):
            return value
        # Dispatch before the broad Python union is tried. This preserves the
        # selected slice's tagged-union diagnostics and prevents irrelevant
        # union_tag_invalid errors from other capabilities.
        return tuple(adapter.validate_python(value))

    @model_validator(mode="after")
    def _version_and_slice_types(self):
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


class _Phase6SemanticOutputV5Base(StrictModel):
    """V5 slice routing with the corrected carrier/claimant interpretation."""

    slice_id: Literal["outcomes", "commitments", "capacity"]
    subject_id: StrictStr
    propositions: tuple[OutcomeClaim | CommitmentClaimV5 | CapacityClaim, ...] = ()

    @model_validator(mode="wrap")
    @classmethod
    def _use_v5_carrier_rules(cls, value: Any, handler: Any) -> Any:
        """Keep the V5 carrier interpretation active through union revalidation."""
        with phase6_v5_validation_context():
            return handler(value)

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return require_nonblank(value, "subject_id")

    @field_validator("propositions", mode="before")
    @classmethod
    def _parse_for_selected_slice(cls, value: Any, info: ValidationInfo) -> Any:
        slice_id = info.data.get("slice_id")
        adapter = _V5_SLICE_CLAIM_ADAPTERS.get(slice_id)
        if adapter is None or not isinstance(value, (list, tuple)):
            return value
        with phase6_v5_validation_context():
            return tuple(adapter.validate_python(value))

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


class Phase6SemanticOutputV5(_Phase6SemanticOutputV5Base):
    """Provider-facing V5.1 contract; earlier V4/V5 bytes remain immutable evidence."""

    contract_version: Literal["phase6-corrected-contracts-v5.1"] = "phase6-corrected-contracts-v5.1"


class Phase6SemanticOutputV5Replay(_Phase6SemanticOutputV5Base):
    """Read-only V4-response parser under V5 rules; it never rewrites V4 bytes."""

    contract_version: Literal["phase6-corrected-contracts-v3"]


class Phase6SemanticOutputV5HistoricalReplay(StrictModel):
    """Read-only parser for already-retained V5 bytes under their original shape."""

    contract_version: Literal["phase6-corrected-contracts-v5"]
    slice_id: Literal["outcomes", "commitments", "capacity"]
    subject_id: StrictStr
    propositions: tuple[OutcomeClaim | CommitmentClaim | CapacityClaim, ...] = ()

    @model_validator(mode="wrap")
    @classmethod
    def _use_v5_carrier_rules(cls, value: Any, handler: Any) -> Any:
        with phase6_v5_validation_context():
            return handler(value)

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return require_nonblank(value, "subject_id")

    @field_validator("propositions", mode="before")
    @classmethod
    def _parse_historical_v5_for_selected_slice(cls, value: Any, info: ValidationInfo) -> Any:
        slice_id = info.data.get("slice_id")
        adapter = _SLICE_CLAIM_ADAPTERS.get(slice_id)
        if adapter is None or not isinstance(value, (list, tuple)):
            return value
        with phase6_v5_validation_context():
            return tuple(adapter.validate_python(value))

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


class _Phase6SemanticOutputV6Base(_Phase6SemanticOutputV5Base):
    """V6 keeps the V5 carrier rules and tightens only observed Outcomes."""

    propositions: tuple[OutcomeClaimV6 | CommitmentClaimV5 | CapacityClaim, ...] = ()

    @field_validator("propositions", mode="before")
    @classmethod
    def _parse_for_selected_slice(cls, value: Any, info: ValidationInfo) -> Any:
        slice_id = info.data.get("slice_id")
        adapter = _V6_SLICE_CLAIM_ADAPTERS.get(slice_id)
        if adapter is None or not isinstance(value, (list, tuple)):
            return value
        with phase6_v5_validation_context():
            return tuple(adapter.validate_python(value))


class Phase6SemanticOutputV6(_Phase6SemanticOutputV6Base):
    """Provider-facing Outcomes V6 contract; unrelated V5 slices are unchanged."""

    contract_version: Literal["phase6-corrected-contracts-v6"] = "phase6-corrected-contracts-v6"


class Phase6SemanticOutputV6Replay(_Phase6SemanticOutputV6Base):
    """Read-only parser for unchanged V4 response bytes under V6 semantics."""

    contract_version: Literal["phase6-corrected-contracts-v3"]


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
    "Phase6Scope", "Phase6EvidenceRef", "Phase6SemanticOutput", "Phase6SemanticOutputV5", "Phase6SemanticOutputV5Replay", "Phase6SemanticOutputV5HistoricalReplay", "Phase6SemanticOutputV6", "Phase6SemanticOutputV6Replay", "OutcomeClaim", "OutcomeClaimV6", "CommitmentClaim", "CommitmentClaimV5", "CommitmentContent", "CommitmentTextContent", "CommitmentStructuredContent", "CommitmentStatedV5",
    "CapacityClaim", "validate_scope_bindings", "validate_current_availability_freshness",
    "ActivityReported", "OutputReported", "ReachReported", "OutcomeObservedReported", "OutcomeObservedReportedV6",
    "ContributionClaimReported", "CausalAttributionClaimReported", "CausalEvidenceSupported",
    "CommitmentStated", "PolicyOrStandardAdopted", "ImplementationActivitySelfReported",
    "ImplementationActivityIndependentlyObserved", "ImplementationEvidenceExternal", "ImplementationOutcomeReported", "ImplementationOutcomeReportedV5",
    "ServiceExists", "IntendedBeneficiaryGroup", "FormalEligibilityRule", "AccessInformation",
    "AccessPathway", "HistoricalActivityVolume", "ResourceOrWorkforceMeasure", "ServiceScaleMeasure",
    "CapacityLimitOrMeasure", "AvailabilityReportedAsOf", "CurrentAvailability", "AvailabilityUnknown",
]
