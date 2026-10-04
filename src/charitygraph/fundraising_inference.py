"""Compile governed, source-native fundraising claims into reviewable candidates.

This is intentionally *not* a natural-language detector.  A source adapter or
governed semantic task supplies each ``NativeFundraisingClaim``.  The compiler
only validates vocabulary references, applies the existing source-role gate,
coalesces genuinely duplicate assertions, and exposes contradictions without
resolving them.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fundraising_evidence_roles import (
    EvidenceScope,
    FundraisingEvidence,
    assess_fundraising_evidence,
)
from .f2f_currentness import F2FCurrentnessDecision, F2FSourceEvidence, decide_f2f_currentness
from .fundraising_vocabulary import FUNDRAISING_VOCABULARY_V1, FacetName


InferenceMethod = Literal["direct_observation", "deterministic_structural_parse", "governed_semantic_mapping"]
Assertion = Literal["present", "explicitly_absent"]
Lifecycle = Literal["current", "historical", "discontinued", "unknown"]
CandidateDisposition = Literal["candidate", "review_only", "blocked", "coverage_only", "unresolved"]
CandidateKind = Literal["practice", "campaign"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NativeFundraisingClaim(_Strict):
    """One already-extracted source-native assertion; wording is never rewritten."""

    claim_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    source_phrase: str = Field(min_length=1)
    extraction_locator: str | None = None
    inference_method: InferenceMethod
    candidate_kind: CandidateKind = "practice"
    assertion: Assertion = "present"
    lifecycle: Lifecycle = "unknown"
    canonical_term_id: str | None = None
    source_scheme_id: str | None = None
    source_term: str | None = None
    mapping_predicate: Literal["exact_match", "close_match", "broader_match", "narrower_match", "related_match", "no_match"] | None = None
    campaign_name: str | None = None

    @model_validator(mode="after")
    def mapping_is_explicit(self):
        if self.canonical_term_id is None:
            if self.mapping_predicate not in (None, "no_match"):
                raise ValueError("an unmapped claim must be no_match or have no mapping predicate")
        elif self.mapping_predicate in (None, "no_match"):
            raise ValueError("a canonical term requires a non-no_match mapping predicate")
        if self.inference_method == "direct_observation" and self.mapping_predicate not in (None, "exact_match"):
            raise ValueError("direct observations may only use exact_match")
        if self.assertion == "explicitly_absent" and self.lifecycle != "unknown":
            raise ValueError("an explicit absence cannot manufacture a lifecycle state")
        if self.candidate_kind == "campaign" and not self.campaign_name:
            raise ValueError("a campaign candidate requires its source-native campaign name")
        return self


class CandidateEvidence(_Strict):
    """An immutable provenance projection retained on every compiler output."""

    evidence_id: str
    source_id: str
    source_role: str
    locator: str
    source_wording: str
    subject_binding: str
    binding_basis: str
    observed_at: date
    valid_from: date | None = None
    valid_to: date | None = None
    scope: EvidenceScope
    production_method: str
    review_status: str
    coverage: str
    coverage_description: str | None = None


class FundraisingPracticeCandidate(_Strict):
    contract_version: Literal["fundraising-practice-inference-v1-candidate"] = "fundraising-practice-inference-v1-candidate"
    candidate_id: str
    candidate_kind: CandidateKind
    canonical_term_id: str | None = None
    facet: FacetName | None = None
    assertion: Assertion
    lifecycle: Lifecycle
    scope: EvidenceScope
    disposition: CandidateDisposition
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(min_length=1)
    source_phrases: tuple[str, ...] = Field(min_length=1)
    source_roles: tuple[str, ...]
    inference_methods: tuple[InferenceMethod, ...]
    subject_binding: str
    campaign_name: str | None = None
    contradiction_candidate_ids: tuple[str, ...] = ()
    reason: str


class FundraisingInferenceResult(_Strict):
    contract_version: Literal["fundraising-practice-inference-v1-candidate"] = "fundraising-practice-inference-v1-candidate"
    candidates: tuple[FundraisingPracticeCandidate, ...]
    unprocessed_claim_ids: tuple[str, ...] = ()


class F2FPracticeObservation(_Strict):
    """The F2F lifecycle policy result alongside an optional generic candidate.

    ``candidate`` is absent when the lifecycle policy did not observe a
    practice.  This deliberately retains PFRA membership, scoped silence and
    uncertain bindings without turning any of them into a negative or positive
    F2F assertion.
    """

    evidence_id: str
    lifecycle: F2FCurrentnessDecision
    candidate: FundraisingPracticeCandidate | None = None


class F2FInferenceResult(_Strict):
    """Review-only composition of F2F lifecycle and generic practice evidence."""

    contract_version: Literal["f2f-practice-inference-v1-candidate"] = "f2f-practice-inference-v1-candidate"
    observations: tuple[F2FPracticeObservation, ...]


_F2F_ROLE_COMPATIBILITY: dict[str, frozenset[str]] = {
    "pfra_membership": frozenset({"pfra_membership"}),
    "agency_client": frozenset({"agency_provider_case_evidence"}),
    "first_party_f2f_page": frozenset({"first_party_practice_page"}),
    "annual_report_statement": frozenset({"annual_report_statement"}),
    # A historical story can be a first-party record or a dated annual report,
    # but must still enter through one of those provenance roles.
    "historical_campaign_story": frozenset({"first_party_practice_page", "annual_report_statement"}),
    "explicit_cessation": frozenset({"first_party_practice_page"}),
    "scoped_source_inventory": frozenset({"scoped_source_inventory"}),
    "other": frozenset({"other"}),
}


_TERMS = {term.term_id: term for term in FUNDRAISING_VOCABULARY_V1.terms}
_EVIDENCE_FACET_BY_TERM_FACET = {
    "strategy_program": "practice",
    "solicitation_mechanism": "practice",
    "communication_channel": "channel",
    "setting_placement": "setting",
    "commitment_pattern": "commitment_pattern",
    "digital_distribution": "digital_distribution",
    "donor_relationship_stage": "donor_relationship_stage",
    "payment_transfer_instrument": "payment_transfer_instrument",
    "delivery_party": "delivery_party",
    "compensation": "compensation",
    "resource_sought": "resource_sought",
    "destination_restriction": "destination_restriction",
    "donor_funder_class": "donor_funder_class",
}
_METHOD_BY_PRODUCTION = {
    "direct_extract": "direct_observation",
    "deterministic_parse": "deterministic_structural_parse",
    "governed_semantic_inference": "governed_semantic_mapping",
}
_PROMOTION_PRIORITY = {"blocked": 4, "coverage_only": 3, "review_only": 2, "promotable": 1}


def _scope_key(scope: EvidenceScope) -> str:
    return json.dumps(scope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _candidate_id(key: tuple[object, ...]) -> str:
    payload = json.dumps(key, sort_keys=True, separators=(",", ":"), default=str)
    return "fpc:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _candidate_evidence(item: FundraisingEvidence) -> CandidateEvidence:
    return CandidateEvidence(**item.model_dump(exclude={"contract_version", "asserted_facets"}))


def compile_fundraising_candidates(
    evidence: tuple[FundraisingEvidence, ...], claims: tuple[NativeFundraisingClaim, ...]
) -> FundraisingInferenceResult:
    """Compile typed claims deterministically, retaining all source identities.

    Repeated claims with the same governed meaning and scope become one
    candidate with many evidence IDs.  Opposing present/explicit-absence claims
    are retained as separate candidates and linked as unresolved contradictions.
    """
    evidence_by_id = {item.evidence_id: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        raise ValueError("evidence IDs must be unique")
    if len({claim.claim_id for claim in claims}) != len(claims):
        raise ValueError("claim IDs must be unique")

    groups: dict[tuple[object, ...], list[NativeFundraisingClaim]] = defaultdict(list)
    unprocessed: list[str] = []
    for claim in claims:
        item = evidence_by_id.get(claim.evidence_id)
        if item is None:
            raise ValueError(f"claim {claim.claim_id} references unknown evidence {claim.evidence_id}")
        if _METHOD_BY_PRODUCTION[item.production_method] != claim.inference_method:
            raise ValueError("claim inference method must match its evidence production method")
        term = _TERMS.get(claim.canonical_term_id) if claim.canonical_term_id else None
        if claim.canonical_term_id and term is None:
            raise ValueError(f"unknown canonical fundraising term: {claim.canonical_term_id}")
        if claim.candidate_kind == "campaign" and "campaign" not in item.asserted_facets:
            raise ValueError(f"campaign claim {claim.claim_id} requires evidence {item.evidence_id} to assert campaign")
        required_facet = _EVIDENCE_FACET_BY_TERM_FACET.get(term.facet) if term else None
        if required_facet and required_facet not in item.asserted_facets:
            raise ValueError(
                f"claim {claim.claim_id} maps {term.term_id} but evidence {item.evidence_id} "
                f"does not assert required {required_facet} facet"
            )
        if term is None:
            unprocessed.append(claim.claim_id)
        key = (claim.candidate_kind, claim.canonical_term_id, claim.assertion, claim.lifecycle, _scope_key(item.scope), claim.campaign_name)
        groups[key].append(claim)

    candidates: list[FundraisingPracticeCandidate] = []
    for key, grouped in sorted(groups.items(), key=lambda pair: str(pair[0])):
        first = grouped[0]
        item = evidence_by_id[first.evidence_id]
        term = _TERMS.get(first.canonical_term_id) if first.canonical_term_id else None
        decisions = [assess_fundraising_evidence(evidence_by_id[claim.evidence_id]) for claim in grouped]
        decision = max(decisions, key=lambda value: _PROMOTION_PRIORITY[value.promotion])
        if term is None:
            disposition, reason = "unresolved", "source-native claim retained; no governed canonical term mapping"
        elif decision.promotion == "promotable":
            disposition, reason = "candidate", "role gate permits reviewed, bound evidence; canonicalisation remains reviewable"
        else:
            disposition, reason = decision.promotion, decision.reason
        candidate_id = _candidate_id(key)
        candidates.append(FundraisingPracticeCandidate(
            candidate_id=candidate_id, candidate_kind=first.candidate_kind, canonical_term_id=first.canonical_term_id,
            facet=term.facet if term else None, assertion=first.assertion, lifecycle=first.lifecycle,
            scope=item.scope, disposition=disposition, evidence_ids=tuple(sorted({c.evidence_id for c in grouped})),
            evidence=tuple(_candidate_evidence(evidence_by_id[evidence_id]) for evidence_id in sorted({c.evidence_id for c in grouped})),
            claim_ids=tuple(sorted(c.claim_id for c in grouped)), source_phrases=tuple(sorted({c.source_phrase for c in grouped})),
            source_roles=tuple(sorted({evidence_by_id[c.evidence_id].source_role for c in grouped})),
            inference_methods=tuple(sorted({c.inference_method for c in grouped})),
            subject_binding=item.subject_binding, campaign_name=first.campaign_name, reason=reason,
        ))

    links: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        if candidate.canonical_term_id is None:
            continue
        for other in candidates:
            if candidate.candidate_id == other.candidate_id:
                continue
            if (candidate.canonical_term_id == other.canonical_term_id and candidate.scope == other.scope
                    and candidate.assertion != other.assertion):
                links[candidate.candidate_id].add(other.candidate_id)
    resolved = tuple(candidate.model_copy(update={"contradiction_candidate_ids": tuple(sorted(links[candidate.candidate_id]))}) for candidate in candidates)
    return FundraisingInferenceResult(candidates=resolved, unprocessed_claim_ids=tuple(sorted(unprocessed)))


def compile_f2f_practice_observations(
    evidence: tuple[FundraisingEvidence, ...], lifecycle_evidence: tuple[F2FSourceEvidence, ...]
) -> F2FInferenceResult:
    """Compose F2F lifecycle decisions with the generic evidence compiler.

    The two inputs intentionally have separate responsibilities: the common
    evidence record supplies public-review provenance, binding basis, production
    method and review state; the F2F record supplies source-role-specific
    lifecycle semantics.  They must describe the same source assertion before
    the compiler can emit an F2F candidate.
    """
    common_by_id = {item.evidence_id: item for item in evidence}
    if len(common_by_id) != len(evidence):
        raise ValueError("evidence IDs must be unique")
    if len({item.evidence_id for item in lifecycle_evidence}) != len(lifecycle_evidence):
        raise ValueError("F2F lifecycle evidence IDs must be unique")

    observations: list[F2FPracticeObservation] = []
    for item in sorted(lifecycle_evidence, key=lambda value: value.evidence_id):
        common = common_by_id.get(item.evidence_id)
        if common is None:
            raise ValueError(f"F2F lifecycle evidence {item.evidence_id} has no common provenance record")
        if common.source_role not in _F2F_ROLE_COMPATIBILITY[item.source_role]:
            raise ValueError(f"{item.source_role} is incompatible with common evidence role {common.source_role}")
        if (common.subject_binding != item.subject_binding or common.source_wording != item.source_wording
                or common.observed_at != item.observed_at or common.valid_from != item.valid_from
                or common.valid_to != item.valid_to or common.scope.model_dump() != item.scope.model_dump()):
            raise ValueError("F2F lifecycle and common provenance records must agree on binding, wording, time and scope")

        decision = decide_f2f_currentness(item)
        candidate: FundraisingPracticeCandidate | None = None
        if decision.practice_observed is True:
            if "practice" not in common.asserted_facets:
                raise ValueError("an observed F2F practice requires common evidence to assert the practice facet")
            if decision.currentness in {"current", "recent", "discontinued"} and "currentness" not in common.asserted_facets:
                raise ValueError("a current, recent or discontinued F2F lifecycle requires common evidence to assert currentness")
            inference_method = _METHOD_BY_PRODUCTION[common.production_method]
            mapping_predicate = "exact_match" if inference_method == "direct_observation" else "close_match"
            claim = NativeFundraisingClaim(
                claim_id=f"f2f:{item.evidence_id}", evidence_id=item.evidence_id,
                source_phrase=item.source_wording, inference_method=inference_method,
                canonical_term_id="fundraising.face_to_face", mapping_predicate=mapping_predicate,
                lifecycle=decision.currentness,
            )
            candidate = compile_fundraising_candidates((common,), (claim,)).candidates[0]
        observations.append(F2FPracticeObservation(
            evidence_id=item.evidence_id, lifecycle=decision, candidate=candidate,
        ))
    return F2FInferenceResult(observations=tuple(observations))
