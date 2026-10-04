"""A non-causal joint coverage view of fundraising practices and money.

This is a cohort/accounting projection, rather than an attribution engine.
In particular, a money fact found beside an observed practice remains
``method_known_finance_aggregate`` unless its own governed scope link is
explicitly below organisation level.
"""
from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .fundraising_money_linkage import FundraisingMoneyScopeLink
from .models import CauseBaseCard, CoverageObservation


JOINT_COVERAGE_CONTRACT_VERSION = "fundraising-joint-coverage.v1"


class JointCoverageState(StrEnum):
    BOTH_KNOWN = "both_known"
    METHOD_KNOWN_FINANCE_AGGREGATE = "method_known_finance_aggregate"
    FINANCE_KNOWN_METHOD_UNKNOWN = "finance_known_method_unknown"
    LOWER_GRAIN_ATTRIBUTED = "lower_grain_attributed"
    NEITHER = "neither"


class FundraisingJointCoverage(BaseModel):
    """One organisation's answerability state, with explicit non-attribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: str = JOINT_COVERAGE_CONTRACT_VERSION
    causebase_id: str
    state: JointCoverageState
    method_observation_ids: tuple[str, ...] = ()
    finance_observation_ids: tuple[str, ...] = ()
    attributed_finance_observation_ids: tuple[str, ...] = ()
    method_coverage_statuses: tuple[str, ...] = ()
    finance_coverage_statuses: tuple[str, ...] = ()
    coexistence_is_attribution: bool = False
    note: str


class FundraisingJointCoverageSummary(BaseModel):
    """Cohort denominators, including cards without a usable answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: str = JOINT_COVERAGE_CONTRACT_VERSION
    denominator: int
    counts: dict[JointCoverageState, int]


_METHOD_CAPABILITIES = frozenset({
    "fundraising_practices", "fundraising_campaigns", "fundraising_provider_relationships",
})
_FINANCE_CAPABILITIES = frozenset({"fundraising_money", "fundraising_expenditure"})
_AGGREGATE_KINDS = frozenset({"total_fundraising_cost", "total_fundraising_income"})


def _coverage_statuses(coverage: tuple[CoverageObservation, ...], capabilities: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted({item.status for item in coverage if item.capability in capabilities}))


def classify_fundraising_joint_coverage(
    card: CauseBaseCard, money_links: tuple[FundraisingMoneyScopeLink, ...] = (),
) -> FundraisingJointCoverage:
    """Classify one card without treating absence as a negative finding."""
    for link in money_links:
        entity = link.reporting_entity_causebase_id or link.measurement.reporting_subject_causebase_id
        if entity != card.causebase_id:
            raise ValueError("fundraising money link reporting entity does not match card subject")
    methods = tuple(item.observation_id for item in card.fundraising_practice_observed)
    method_coverage = _coverage_statuses(tuple(card.coverage), _METHOD_CAPABILITIES)
    finance_coverage = _coverage_statuses(tuple(card.coverage), _FINANCE_CAPABILITIES)
    finance = tuple(link.measurement.observation_id for link in money_links)
    attributed = tuple(
        link.measurement.observation_id for link in money_links
        if link.linkage_status == "explicit" and link.attributed_scope_kind != "organisation"
    )

    if attributed:
        state = JointCoverageState.LOWER_GRAIN_ATTRIBUTED
        note = "At least one money fact has an explicit non-organisation scope link; other facts remain separate."
    elif methods and finance:
        aggregate = any(
            link.linkage_status == "unknown" or link.measurement.measure_kind in _AGGREGATE_KINDS
            for link in money_links
        )
        state = JointCoverageState.METHOD_KNOWN_FINANCE_AGGREGATE if aggregate else JointCoverageState.BOTH_KNOWN
        note = (
            "Methods and aggregate money facts coexist but are not attributable to a method, campaign, or provider."
            if aggregate else "Methods and finance facts are both observed, without a lower-grain attribution."
        )
    elif finance:
        state = JointCoverageState.FINANCE_KNOWN_METHOD_UNKNOWN
        note = "Finance is observed; no fundraising-practice observation is asserted. Coverage states describe the limit."
    else:
        state = JointCoverageState.NEITHER
        note = "Neither a fundraising-practice observation nor a compatible money fact is available; this is not a negative claim."
    return FundraisingJointCoverage(
        causebase_id=card.causebase_id, state=state, method_observation_ids=methods,
        finance_observation_ids=finance, attributed_finance_observation_ids=attributed,
        method_coverage_statuses=method_coverage, finance_coverage_statuses=finance_coverage,
        note=note,
    )


def summarise_fundraising_joint_coverage(
    observations: tuple[FundraisingJointCoverage, ...],
) -> FundraisingJointCoverageSummary:
    counts = Counter(item.state for item in observations)
    return FundraisingJointCoverageSummary(
        denominator=len(observations),
        counts={state: counts[state] for state in JointCoverageState},
    )
