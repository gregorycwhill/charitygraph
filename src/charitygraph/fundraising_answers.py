"""Deterministic, evidence-preserving answers to bounded fundraising questions.

This is deliberately a presentation contract over ``FundraisingQueryInput``.
It never converts an empty result into a negative claim, and it refuses a
request to attribute an organisation-level money fact to an activity.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .fundraising_money_linkage import FundraisingMoneyScopeLink
from .fundraising_query import FundraisingQueryInput, _EXPENDITURE_KINDS
from .models import CoverageObservation, EvidenceRef


FUNDRAISING_ANSWER_CONTRACT_VERSION = "fundraising-answer.v1"

QuestionKind = Literal[
    "current_f2f", "evidenced_methods", "external_provider", "disclosed_costs",
    "disclosed_income_or_proceeds", "amounts_linked_to_activity", "unknowns",
    "compatible_cost_change",
]
AnswerStatus = Literal["supported", "not_current", "unknown", "refused"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FundraisingQuestion(_Strict):
    kind: QuestionKind
    # Required only when asking whether money is linked to a named activity.
    activity_scope_kind: Literal["practice", "campaign", "appeal", "provider_relationship"] | None = None
    activity_scope_id: str | None = None


class FundraisingAnswer(_Strict):
    contract_version: str = FUNDRAISING_ANSWER_CONTRACT_VERSION
    question: FundraisingQuestion
    causebase_id: str
    status: AnswerStatus
    statement: str
    observation_ids: tuple[str, ...] = ()
    money_observation_ids: tuple[str, ...] = ()
    source_wording: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    coverage: tuple[CoverageObservation, ...] = ()
    refusal_reason: str | None = None


def _coverage(item: FundraisingQueryInput, *capabilities: str) -> tuple[CoverageObservation, ...]:
    wanted = set(capabilities)
    return tuple(entry for entry in item.card.coverage if entry.capability in wanted)


def _evidence(item: FundraisingQueryInput, ids: set[str]) -> tuple[EvidenceRef, ...]:
    return tuple(entry for entry in item.card.evidence if entry.evidence_id in ids)


def _answer(
    item: FundraisingQueryInput, question: FundraisingQuestion, *, status: AnswerStatus,
    statement: str, observation_ids: tuple[str, ...] = (), money: tuple[FundraisingMoneyScopeLink, ...] = (),
    wording: tuple[str, ...] = (), evidence_ids: set[str] | None = None,
    coverage: tuple[CoverageObservation, ...] = (), refusal_reason: str | None = None,
) -> FundraisingAnswer:
    ids = evidence_ids if evidence_ids is not None else {
        evidence_id for link in money for evidence_id in (*link.measurement.evidence_ids, *link.linkage_evidence_ids)
    }
    return FundraisingAnswer(
        question=question, causebase_id=item.card.causebase_id, status=status, statement=statement,
        observation_ids=observation_ids, money_observation_ids=tuple(link.measurement.observation_id for link in money),
        source_wording=wording, evidence=_evidence(item, ids), coverage=coverage, refusal_reason=refusal_reason,
    )


def answer_fundraising_question(item: FundraisingQueryInput, question: FundraisingQuestion) -> FundraisingAnswer:
    """Answer one question for one already subject-bound, validated input."""
    card = item.card
    if question.kind == "current_f2f":
        f2f = tuple(p for p in card.fundraising_practice_observed if "fundraising.face_to_face" in p.canonical_facets)
        current = tuple(p for p in f2f if p.lifecycle == "current")
        if current:
            ids = {eid for p in current for eid in p.evidence_ids}
            return _answer(item, question, status="supported", statement="Current face-to-face practice is supported only as of the cited evidence.", observation_ids=tuple(p.observation_id for p in current), wording=tuple(p.source_native_phrase for p in current), evidence_ids=ids, coverage=_coverage(item, "fundraising_practices"))
        ended = tuple(p for p in f2f if p.lifecycle == "ended")
        if ended:
            ids = {eid for p in ended for eid in p.evidence_ids}
            return _answer(item, question, status="not_current", statement="Cited evidence says the face-to-face practice ended; this is not an organisation-wide continuity claim.", observation_ids=tuple(p.observation_id for p in ended), wording=tuple(p.source_native_phrase for p in ended), evidence_ids=ids, coverage=_coverage(item, "fundraising_practices"))
        return _answer(item, question, status="unknown", statement="Current face-to-face use is not established by the bounded evidence.", coverage=_coverage(item, "fundraising_practices"))

    if question.kind == "evidenced_methods":
        practices = tuple(card.fundraising_practice_observed)
        ids = {eid for p in practices for eid in p.evidence_ids}
        return _answer(item, question, status="supported" if practices else "unknown", statement="Only source-evidenced standing practices are listed; campaigns and funding sources are separate." if practices else "No standing fundraising practice is established by the bounded evidence.", observation_ids=tuple(p.observation_id for p in practices), wording=tuple(p.source_native_phrase for p in practices), evidence_ids=ids, coverage=_coverage(item, "fundraising_practices"))

    if question.kind == "external_provider":
        providers = tuple(card.fundraising_provider_relationships)
        ids = {eid for p in providers for eid in p.evidence_ids}
        return _answer(item, question, status="supported" if providers else "unknown", statement="The listed provider relationships are source-evidenced; no provider is inferred from a method or campaign." if providers else "An external fundraising agency or platform is not established by the bounded evidence.", observation_ids=tuple(p.relationship_id for p in providers), wording=tuple(p.relationship.relationship_type for p in providers), evidence_ids=ids, coverage=_coverage(item, "fundraising_provider_relationships"))

    if question.kind in {"disclosed_costs", "disclosed_income_or_proceeds"}:
        costs = question.kind == "disclosed_costs"
        money = tuple(link for link in item.money_links if (link.measurement.measure_kind in _EXPENDITURE_KINDS) == costs)
        return _answer(item, question, status="supported" if money else "unknown", statement=("Disclosed fundraising costs retain their source scope, period and measurement semantics." if costs else "Disclosed fundraising income/proceeds retain their source scope, period and measurement semantics.") if money else "No compatible disclosed money fact is available in this bounded input.", money=money, wording=tuple(link.measurement.source_wording for link in money), coverage=_coverage(item, "fundraising_money", "fundraising_expenditure"))

    if question.kind == "amounts_linked_to_activity":
        if not question.activity_scope_kind or not question.activity_scope_id:
            return _answer(item, question, status="refused", statement="An activity identifier and scope are required before a money-link question can be answered.", refusal_reason="activity_scope_required")
        money = tuple(link for link in item.money_links if link.linkage_status == "explicit" and link.attributed_scope_kind == question.activity_scope_kind and link.attributed_scope_id == question.activity_scope_id)
        return _answer(item, question, status="supported" if money else "unknown", statement="Only explicitly linked amounts are returned; organisation-level amounts are not allocated." if money else "No explicitly linked amount is available for this activity.", money=money, wording=tuple(link.linkage_source_wording or link.measurement.source_wording for link in money), coverage=_coverage(item, "fundraising_money", "fundraising_expenditure"))

    if question.kind == "unknowns":
        coverage = _coverage(item, "fundraising_practices", "fundraising_campaigns", "fundraising_provider_relationships", "fundraising_money", "fundraising_expenditure")
        unknown = tuple(entry for entry in coverage if entry.status != "observed")
        return _answer(item, question, status="supported", statement="Coverage states describe what remains unknown, unavailable, scoped, or unprocessed; they are not negative findings.", coverage=unknown)

    return _answer(item, question, status="refused", statement="A cost-change answer requires separately compatible, period-identified measurements; this single-input answer does not derive one.", refusal_reason="comparison_input_and_compatibility_required", coverage=_coverage(item, "fundraising_money", "fundraising_expenditure"))
