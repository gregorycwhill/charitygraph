"""Bounded, evidence-preserving queries over governed fundraising facts.

This is a local projection helper, not a search index or an attribution
engine.  A result is positive only when its supplied observation or money
link says so; missing observations and coverage states never become false.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fundraising_joint_coverage import (
    FundraisingJointCoverage,
    JointCoverageState,
    classify_fundraising_joint_coverage,
)
from .fundraising_money_linkage import FundraisingMoneyScopeLink
from .models import CauseBaseCard, CoverageObservation, EvidenceRef, FundraisingPracticeObservation


FUNDRAISING_QUERY_CONTRACT_VERSION = "fundraising-query.v1"

_PRACTICE_CAPABILITY = "fundraising_practices"
_FINANCE_CAPABILITIES = frozenset({"fundraising_money", "fundraising_expenditure"})
_EXPENDITURE_KINDS = frozenset({
    "total_expenses", "direct_fundraising_cost", "agency_fee", "commission",
    "media_spend", "staff_cost", "event_prize_cost", "administration_allocation",
    "total_fundraising_cost",
})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FundraisingQueryInput(_Strict):
    """All local facts available for one bounded subject at query time."""

    card: CauseBaseCard
    money_links: tuple[FundraisingMoneyScopeLink, ...] = ()

    @model_validator(mode="after")
    def validate_money_subject_and_evidence(self):
        known = {item.evidence_id for item in self.card.evidence}
        observations = (*self.card.fundraising_practice_observed, *self.card.fundraising_campaign_observed,
                        *self.card.fundraising_provider_relationships)
        requested_observation_evidence = {
            evidence_id for observation in observations for evidence_id in observation.evidence_ids
        }
        requested_coverage_evidence = {
            evidence_id for coverage in self.card.coverage
            if coverage.capability in {_PRACTICE_CAPABILITY, *_FINANCE_CAPABILITIES}
            for evidence_id in coverage.evidence_ids
        }
        if missing := (requested_observation_evidence | requested_coverage_evidence) - known:
            raise ValueError(f"fundraising query input references evidence absent from card: {sorted(missing)}")
        for link in self.money_links:
            entity = link.reporting_entity_causebase_id or link.measurement.reporting_subject_causebase_id
            if entity != self.card.causebase_id:
                raise ValueError("fundraising money link reporting entity does not match card subject")
            requested = set(link.measurement.evidence_ids) | set(link.linkage_evidence_ids)
            if missing := requested - known:
                raise ValueError(f"fundraising money link references evidence absent from card: {sorted(missing)}")
        return self


class FundraisingQueryMatch(_Strict):
    causebase_id: str
    practice_observation_ids: tuple[str, ...] = ()
    money_observation_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...]
    coverage: tuple[CoverageObservation, ...]
    joint_coverage: FundraisingJointCoverage
    note: str


class FundraisingQueryResult(_Strict):
    """A bounded result set with its denominator and non-causal provenance."""

    contract_version: str = FUNDRAISING_QUERY_CONTRACT_VERSION
    query: str
    denominator: int = Field(ge=0)
    matches: tuple[FundraisingQueryMatch, ...]


def _catalog(inputs: tuple[FundraisingQueryInput, ...]) -> tuple[FundraisingQueryInput, ...]:
    ids = [item.card.causebase_id for item in inputs]
    if len(ids) != len(set(ids)):
        raise ValueError("bounded fundraising query input contains duplicate causebase_id")
    return inputs


def _fresh_evidence_ids(card: CauseBaseCard, evidence_ids: set[str], on_or_after: date | None) -> set[str]:
    return {
        item.evidence_id for item in card.evidence
        if item.evidence_id in evidence_ids and (on_or_after is None or item.observed_at >= on_or_after)
    }


def _match(
    item: FundraisingQueryInput,
    *,
    practices: tuple[FundraisingPracticeObservation, ...] = (),
    money: tuple[FundraisingMoneyScopeLink, ...] = (),
    note: str,
) -> FundraisingQueryMatch:
    evidence_ids = {
        evidence_id for practice in practices for evidence_id in practice.evidence_ids
    } | {
        evidence_id for link in money
        for evidence_id in (*link.measurement.evidence_ids, *link.linkage_evidence_ids)
    }
    capabilities = {_PRACTICE_CAPABILITY} if practices else set()
    if money:
        capabilities |= _FINANCE_CAPABILITIES
    return FundraisingQueryMatch(
        causebase_id=item.card.causebase_id,
        practice_observation_ids=tuple(practice.observation_id for practice in practices),
        money_observation_ids=tuple(link.measurement.observation_id for link in money),
        evidence=tuple(evidence for evidence in item.card.evidence if evidence.evidence_id in evidence_ids),
        coverage=tuple(coverage for coverage in item.card.coverage if coverage.capability in capabilities),
        joint_coverage=classify_fundraising_joint_coverage(item.card, item.money_links),
        note=note,
    )


def charities_with_current_practice(
    inputs: tuple[FundraisingQueryInput, ...], facet: str, *, evidence_observed_on_or_after: date | None = None,
) -> FundraisingQueryResult:
    """Return only directly evidenced current standing practices with ``facet``."""
    matches = []
    for item in _catalog(inputs):
        practices = tuple(
            practice for practice in item.card.fundraising_practice_observed
            if practice.lifecycle == "current" and facet in practice.canonical_facets
            and _fresh_evidence_ids(item.card, set(practice.evidence_ids), evidence_observed_on_or_after)
        )
        if practices:
            matches.append(_match(item, practices=practices, note="Current practice is bounded by the cited evidence date."))
    return FundraisingQueryResult(query=f"current_practice:{facet}", denominator=len(inputs), matches=tuple(matches))


def charities_with_current_practices(
    inputs: tuple[FundraisingQueryInput, ...], facets: tuple[str, ...], *, evidence_observed_on_or_after: date | None = None,
) -> FundraisingQueryResult:
    """Conjunctive query: every requested facet needs its own current evidence."""
    if not facets or len(facets) != len(set(facets)):
        raise ValueError("facets must be a non-empty tuple of unique canonical facet IDs")
    matches = []
    for item in _catalog(inputs):
        selected = tuple(
            practice for practice in item.card.fundraising_practice_observed
            if practice.lifecycle == "current"
            and _fresh_evidence_ids(item.card, set(practice.evidence_ids), evidence_observed_on_or_after)
            and any(facet in practice.canonical_facets for facet in facets)
        )
        if all(any(facet in practice.canonical_facets for practice in selected) for facet in facets):
            matches.append(_match(item, practices=selected, note="Each requested practice facet has current, cited evidence; no provider is implied."))
    return FundraisingQueryResult(query="current_practices:" + ",".join(facets), denominator=len(inputs), matches=tuple(matches))


def charities_with_disclosed_fundraising_expenditure(inputs: tuple[FundraisingQueryInput, ...]) -> FundraisingQueryResult:
    """Return source-disclosed expenditure facts, retaining their reporting scope."""
    matches = []
    for item in _catalog(inputs):
        money = tuple(link for link in item.money_links if link.measurement.measure_kind in _EXPENDITURE_KINDS)
        if money:
            matches.append(_match(item, money=money, note="Expenditure is source-disclosed and remains at its explicit scope."))
    return FundraisingQueryResult(query="disclosed_fundraising_expenditure", denominator=len(inputs), matches=tuple(matches))


def charities_with_campaign_level_proceeds(inputs: tuple[FundraisingQueryInput, ...]) -> FundraisingQueryResult:
    """Return explicitly campaign/appeal-linked gross-proceeds facts only."""
    matches = []
    for item in _catalog(inputs):
        money = tuple(
            link for link in item.money_links
            if link.linkage_status == "explicit"
            and link.attributed_scope_kind in {"campaign", "appeal"}
            and link.measurement.measure_kind == "gross_proceeds"
        )
        if money:
            matches.append(_match(item, money=money, note="Gross proceeds are explicitly linked to the stated campaign or appeal."))
    return FundraisingQueryResult(query="campaign_level_gross_proceeds", denominator=len(inputs), matches=tuple(matches))


def charities_with_method_known_finance_unattributed(inputs: tuple[FundraisingQueryInput, ...]) -> FundraisingQueryResult:
    """Return coexistence cases explicitly labelled non-attributed, never causal."""
    matches = []
    for item in _catalog(inputs):
        joint = classify_fundraising_joint_coverage(item.card, item.money_links)
        if joint.state is JointCoverageState.METHOD_KNOWN_FINANCE_AGGREGATE:
            matches.append(_match(item, practices=tuple(item.card.fundraising_practice_observed), money=item.money_links,
                                  note="Practice and aggregate finance coexist; this result makes no method-level attribution."))
    return FundraisingQueryResult(query="method_known_finance_unattributed", denominator=len(inputs), matches=tuple(matches))
