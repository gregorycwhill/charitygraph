"""Deterministic North Star v0.2 section-13 finance projections.

This module accepts one evidence-bound financial proposition at a time.  It is
not an extractor, financial ledger, audit-management system, or a section-14
funding adapter.  In particular, accounting recognition and cash-flow stages
remain separately typed even where a source discusses the same money.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput
from .models import MoneyObservation, ReconciliationStatus


Section13Predicate = Literal[
    "statement_row_observed", "accounting_policy_observed", "accounting_basis_observed",
    "restriction_or_reserve_observed", "assurance_observed", "resource_flow_stage_observed",
    "comparative_transformation_observed", "reconciliation_outcome_observed",
    "derived_financial_calculation",
]
ClaimBasis = Literal["source_fact", "source_interpretation", "deterministic_calculation"]
ReportingScope = Literal["subject", "organisation_group", "consolidated_group", "unknown"]
ScopeKind = Literal["organisation", "reporting_group", "operating_division", "program", "service", "other"]
AttributionMethod = Literal["direct_subject_report", "group_scope_report", "explicit_allocation", "division_reported", "unknown"]
StatementType = Literal["profit_and_loss", "financial_position", "cash_flow", "changes_in_equity", "note", "other"]
FinancialStage = Literal["award", "commitment", "payment", "receipt", "revenue_recognition", "expenditure_or_use", "refund_or_return"]
AssuranceKind = Literal["audited_financial_report", "independent_auditor_opinion", "unaudited_source_presented"]
ComparativeTransformation = Literal["ordinary_prior_period", "presentation_reclassified", "currency_translated_comparative"]

_MISSINGNESS = {
    "not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
    "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
    "not_processed": ("NOT_PROCESSED", "no_domain_result"), "not_reviewed": ("NOT_REVIEWED", "not_reviewed"),
    "processing_failed": ("PROCESSING_FAILED", "processing_failed"), "not_attempted": ("NOT_ATTEMPTED", "not_attempted"),
    "not_applicable": ("NOT_APPLICABLE", "not_applicable"), "withheld": ("WITHHELD", "withheld"),
    "stale": ("STALE", "unknown_history"), "unknown": ("UNKNOWN", "unknown_history"),
}


class Section13FinanceInput(StrictModel):
    """One source-bound §13 proposition, with no implicit cross-section effect."""
    predicate: Section13Predicate
    subject_id: str
    scope_id: str
    scope_kind: ScopeKind
    reporting_scope: ReportingScope
    attribution_method: AttributionMethod
    financial_record_id: str
    coverage_state: CoverageState = "unknown"
    claim_basis: ClaimBasis
    source_role: Literal["supporting", "corroborating", "context"]
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    observation_time: ObservationTime | None = None
    statement_type: StatementType | None = None
    statement_identity: str | None = None
    source_row_label: str | None = None
    money: MoneyObservation | None = None
    comparative_money: MoneyObservation | None = None
    detail: str | None = None
    stage: FinancialStage | None = None
    assurance_kind: AssuranceKind | None = None
    comparative_transformation: ComparativeTransformation | None = None
    reconciliation_status: ReconciliationStatus | None = None
    related_observation_ids: tuple[str, ...] = ()
    calculation_method: str | None = None
    numerator_observation_id: str | None = None
    denominator_observation_id: str | None = None
    value: CanonicalValue | None = None

    @field_validator("subject_id", "scope_id", "financial_record_id", "statement_identity", "source_row_label", "detail", "calculation_method", "numerator_observation_id", "denominator_observation_id")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids", "related_observation_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("finance projection identifiers must be nonblank and unique")
        return value

    @model_validator(mode="after")
    def _bounded_semantics(self) -> "Section13FinanceInput":
        if self.coverage_state in {"asserted_none", "observed_absent"}:
            raise ValueError("absence claims require a separately authorised evidence-bound representation")
        if self.coverage_state == "supported" and (not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids or self.observation_time is None):
            raise ValueError("supported finance propositions require time, locator, source and lineage")
        if self.scope_kind == "operating_division":
            if self.attribution_method not in {"division_reported", "explicit_allocation"}:
                raise ValueError("operating-division finance requires division_reported or explicit_allocation attribution")
        elif self.attribution_method == "division_reported":
            raise ValueError("division_reported attribution requires an operating-division scope")
        if self.predicate == "statement_row_observed":
            if self.statement_type is None or self.statement_identity is None or self.source_row_label is None or self.money is None:
                raise ValueError("statement rows require statement identity, source row and money")
            if self.claim_basis != "source_fact":
                raise ValueError("statement rows are source facts")
        elif self.comparative_money is not None:
            raise ValueError("comparative money is limited to a statement row")
        if self.predicate == "resource_flow_stage_observed":
            if self.stage is None or self.detail is None:
                raise ValueError("resource-flow stages require an explicit stage and source detail")
        elif self.stage is not None:
            raise ValueError("stage is limited to resource-flow-stage observations")
        if self.predicate == "assurance_observed":
            if self.assurance_kind is None or self.detail is None:
                raise ValueError("assurance requires an explicit source-reported assurance kind and detail")
        elif self.assurance_kind is not None:
            raise ValueError("assurance kind is limited to assurance observations")
        if self.predicate == "comparative_transformation_observed":
            if self.comparative_transformation is None or self.detail is None:
                raise ValueError("comparative transformation requires an explicit kind and source detail")
        elif self.comparative_transformation is not None:
            raise ValueError("comparative transformation is limited to its observation")
        if self.predicate == "reconciliation_outcome_observed":
            if self.reconciliation_status is None or len(self.related_observation_ids) < 2 or self.detail is None:
                raise ValueError("reconciliation requires status, two observations and source detail")
        elif self.reconciliation_status is not None or self.related_observation_ids:
            raise ValueError("reconciliation fields are limited to reconciliation observations")
        if self.predicate == "derived_financial_calculation":
            if self.claim_basis != "deterministic_calculation" or self.value is None or not all((self.calculation_method, self.numerator_observation_id, self.denominator_observation_id)):
                raise ValueError("derived calculation requires deterministic basis, result, method and operands")
        elif any(item is not None for item in (self.calculation_method, self.numerator_observation_id, self.denominator_observation_id)):
            raise ValueError("calculation provenance is limited to a derived calculation")
        if self.predicate in {"accounting_policy_observed", "accounting_basis_observed", "restriction_or_reserve_observed"} and self.detail is None:
            raise ValueError("policy, basis, restriction and reserve propositions require source detail")
        return self


def _payload(item: Section13FinanceInput) -> dict[str, CanonicalValue]:
    payload: dict[str, CanonicalValue] = {
        "north_star_projection_contract": "north-star-v0.2", "section_id": 13,
        "section13_predicate": item.predicate, "financial_record_id": item.financial_record_id,
        "reporting_scope": item.reporting_scope, "attribution_method": item.attribution_method,
        "scope_kind": item.scope_kind, "claim_basis": item.claim_basis, "coverage_state": item.coverage_state,
        "source_role": item.source_role,
    }
    for key in ("statement_type", "statement_identity", "source_row_label", "detail", "stage", "assurance_kind",
                "comparative_transformation", "reconciliation_status", "calculation_method", "numerator_observation_id",
                "denominator_observation_id", "value"):
        value = getattr(item, key)
        if value is not None:
            payload[key] = value
    if item.money is not None:
        payload["money"] = item.money.model_dump(mode="json")
    if item.comparative_money is not None:
        payload["comparative_money"] = item.comparative_money.model_dump(mode="json")
    if item.related_observation_ids:
        payload["related_observation_ids"] = list(item.related_observation_ids)
    return payload


def project_section13_finance_observation(item: Section13FinanceInput, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    """Project one bounded §13 fact; it cannot create §8 or §14 evidence."""
    if item.observation_time is None:
        raise ValueError("section-13 reprojection requires explicit observation_time; created_at is record metadata")
    outcome = "supported" if item.coverage_state == "supported" else "unknown"
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,),
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=x) for x in item.lineage_ids),
        subject_id=item.subject_id, scope_id=item.scope_id, predicate=f"north_star_v02.section13.{item.predicate}", value=_payload(item),
        outcome_state=outcome, evidence_locator_ids=item.evidence_locator_ids, source_record_ids=item.source_record_ids,
        observation_time=item.observation_time, method="north_star_v02_section13_finance_reprojection")


def section13_finance_card_evidence(item: Section13FinanceInput, observation: Observation) -> CardEvidence:
    outcome = "supported" if item.coverage_state == "supported" else "unknown"
    if (observation.subject_id != item.subject_id or observation.about_subject_ids != (item.subject_id,) or observation.scope_id != item.scope_id
        or observation.predicate != f"north_star_v02.section13.{item.predicate}" or observation.value != _payload(item)
        or observation.outcome_state != outcome or observation.evidence_locator_ids != item.evidence_locator_ids
        or observation.source_record_ids != item.source_record_ids or observation.observation_time != item.observation_time
        or observation.method != "north_star_v02_section13_finance_reprojection"):
        raise ValueError("section-13 CardEvidence requires the matching projected observation")
    if tuple(edge.target_artifact_id for edge in observation.lineage if edge.edge_type == "projected_as") != item.lineage_ids:
        raise ValueError("section-13 CardEvidence requires matching observation lineage")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(13,),
        projection_contract_id="north-star-v0.2", note=f"v0.2-only section-13 {item.predicate}; no automatic section-8 or section-14 assignment")


def section13_finance_missingness(*, subject_id: str, coverage_state: CoverageState, note: str | None = None) -> CoverageInput:
    try:
        state, basis = _MISSINGNESS[coverage_state]
    except KeyError as exc:
        raise ValueError("section-13 missingness requires a non-positive coverage state") from exc
    return CoverageInput(subject_id=subject_id, section_id=13, projection_contract_id="north-star-v0.2", state=state, basis=basis, note=note)


__all__ = ["Section13FinanceInput", "project_section13_finance_observation", "section13_finance_card_evidence", "section13_finance_missingness"]
