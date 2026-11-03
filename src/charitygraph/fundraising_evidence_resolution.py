"""Fail-closed deduplication and conflict presentation for fundraising evidence.

This module does not replace source records or select a truth merely because
two records look alike.  It groups byte-for-byte repeated extractions, retains
every contributing evidence ID, and exposes corroboration and disagreement as
separate reviewable outcomes.  A preferred claim is emitted only for the
narrow case where reviewed, confirmed claims concern the same subject, fact,
scope and *exact* valid-time window and the source-role contract supplies an
unambiguous precedence.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fundraising_evidence_roles import EvidenceScope, EvidenceRole, FundraisingEvidence


FUNDRAISING_EVIDENCE_RESOLUTION_VERSION = "fundraising-evidence-resolution.v1"
ClaimKind = Literal["practice", "money"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FundraisingResolutionClaim(_Strict):
    """One typed interpretation of one retained source extraction.

    ``claim_value`` stays source-governed (for example ``current`` or a
    normalised money value plus its declared measurement key); this resolver
    never parses prose or equates unlike money measures.
    """

    claim_id: str = Field(min_length=1)
    subject_causebase_id: str = Field(min_length=1)
    claim_kind: ClaimKind
    semantic_key: tuple[str, ...] = Field(min_length=1)
    claim_value: str = Field(min_length=1)
    evidence: FundraisingEvidence

    @model_validator(mode="after")
    def evidence_is_reviewable(self):
        if self.evidence.subject_binding != "confirmed":
            raise ValueError("resolution claims require confirmed subject binding")
        if self.evidence.coverage != "observed":
            raise ValueError("resolution claims require observed evidence")
        return self


class EvidenceDuplicateGroup(_Strict):
    canonical_claim_id: str
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_id: str
    locator: str
    source_wording: str


class FundraisingEvidenceConflict(_Strict):
    semantic_key: tuple[str, ...]
    subject_causebase_id: str
    claim_ids: tuple[str, ...]
    values: tuple[str, ...]
    scope: EvidenceScope
    valid_from: date | None = None
    valid_to: date | None = None
    preferred_claim_id: str | None = None
    resolution: Literal["inspectable_conflict", "source_role_precedence"]


class FundraisingEvidenceResolution(_Strict):
    contract_version: str = FUNDRAISING_EVIDENCE_RESOLUTION_VERSION
    duplicate_groups: tuple[EvidenceDuplicateGroup, ...] = ()
    corroborated_claim_ids: tuple[tuple[str, ...], ...] = ()
    temporal_successor_claim_ids: tuple[tuple[str, ...], ...] = ()
    scope_distinct_claim_ids: tuple[tuple[str, ...], ...] = ()
    conflicts: tuple[FundraisingEvidenceConflict, ...] = ()


# This is deliberately a partial order.  Equal-rank roles do not break ties,
# and unlisted roles (including membership/registration) never win a conflict.
_ROLE_PRECEDENCE: dict[EvidenceRole, int] = {
    "first_party_practice_page": 30,
    "first_party_campaign_page": 30,
    "annual_report_statement": 20,
    "agency_provider_case_evidence": 10,
    "platform_campaign_page": 10,
}


def _scope_key(scope: EvidenceScope) -> tuple[object, ...]:
    return scope.kind, scope.identifier, scope.geography, scope.description


def _time_key(evidence: FundraisingEvidence) -> tuple[date | None, date | None]:
    return evidence.valid_from, evidence.valid_to


def _duplicate_key(claim: FundraisingResolutionClaim) -> tuple[object, ...]:
    evidence = claim.evidence
    return (
        claim.subject_causebase_id, claim.claim_kind, claim.semantic_key,
        claim.claim_value, evidence.source_id, evidence.locator,
        evidence.source_wording, _scope_key(evidence.scope), _time_key(evidence),
    )


def _fact_key(claim: FundraisingResolutionClaim) -> tuple[object, ...]:
    return claim.subject_causebase_id, claim.claim_kind, claim.semantic_key


def _preferred(claims: tuple[FundraisingResolutionClaim, ...]) -> str | None:
    """Use role precedence only for reviewed, identical-time, identical-scope claims."""
    if len({claim.evidence.review_status for claim in claims}) != 1 or claims[0].evidence.review_status != "reviewed":
        return None
    if len({_scope_key(claim.evidence.scope) for claim in claims}) != 1:
        return None
    if len({_time_key(claim.evidence) for claim in claims}) != 1:
        return None
    ranks = [( _ROLE_PRECEDENCE.get(claim.evidence.source_role, 0), claim.claim_id) for claim in claims]
    highest = max(rank for rank, _ in ranks)
    winners = [claim_id for rank, claim_id in ranks if rank == highest]
    return winners[0] if highest and len(winners) == 1 else None


def resolve_fundraising_evidence(
    claims: tuple[FundraisingResolutionClaim, ...],
) -> FundraisingEvidenceResolution:
    """Classify repeated, corroborating and conflicting claims without data loss."""
    ids = [claim.claim_id for claim in claims]
    if len(ids) != len(set(ids)):
        raise ValueError("resolution claim IDs must be unique")

    duplicate_groups = []
    canonical = []
    by_duplicate: dict[tuple[object, ...], list[FundraisingResolutionClaim]] = {}
    for claim in claims:
        by_duplicate.setdefault(_duplicate_key(claim), []).append(claim)
    for group in by_duplicate.values():
        canonical.append(group[0])
        if len(group) > 1:
            first = group[0].evidence
            duplicate_groups.append(EvidenceDuplicateGroup(
                canonical_claim_id=group[0].claim_id,
                claim_ids=tuple(item.claim_id for item in group),
                evidence_ids=tuple(item.evidence.evidence_id for item in group),
                source_id=first.source_id, locator=first.locator, source_wording=first.source_wording,
            ))

    corroborated, successors, scope_distinct, conflicts = [], [], [], []
    by_fact: dict[tuple[object, ...], list[FundraisingResolutionClaim]] = {}
    for claim in canonical:
        by_fact.setdefault(_fact_key(claim), []).append(claim)
    for group in by_fact.values():
        if len(group) < 2:
            continue
        ids = tuple(item.claim_id for item in group)
        values = {item.claim_value for item in group}
        scopes = {_scope_key(item.evidence.scope) for item in group}
        times = {_time_key(item.evidence) for item in group}
        sources = {item.evidence.source_id for item in group}
        if len(scopes) > 1:
            scope_distinct.append(ids)
        elif len(times) > 1:
            successors.append(ids)
        elif len(values) == 1 and len(sources) > 1:
            corroborated.append(ids)
        elif len(values) > 1:
            preferred = _preferred(tuple(group))
            evidence = group[0].evidence
            conflicts.append(FundraisingEvidenceConflict(
                semantic_key=group[0].semantic_key, subject_causebase_id=group[0].subject_causebase_id,
                claim_ids=ids, values=tuple(sorted(values)), scope=evidence.scope,
                valid_from=evidence.valid_from, valid_to=evidence.valid_to,
                preferred_claim_id=preferred,
                resolution="source_role_precedence" if preferred else "inspectable_conflict",
            ))
    return FundraisingEvidenceResolution(
        duplicate_groups=tuple(duplicate_groups), corroborated_claim_ids=tuple(corroborated),
        temporal_successor_claim_ids=tuple(successors), scope_distinct_claim_ids=tuple(scope_distinct),
        conflicts=tuple(conflicts),
    )
