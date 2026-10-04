"""Fail-closed identity binding for already-governed fundraising evidence.

This module does not read prose or discover subjects.  It evaluates stable
identifiers and an explicitly recorded domain/relationship authority supplied
by an upstream source adapter.  In particular, an organisation name or a web
domain alone never creates a binding.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BindingStatus = Literal["confirmed", "ambiguous", "unresolved"]
BindingBasis = Literal[
    "exact_abn_with_identity_authority",
    "explicit_subject_relationship",
    "verified_subject_controlled_domain",
    "ambiguous_multiple_exact_matches",
    "insufficient_identity_evidence",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _abn(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) != 11:
        raise ValueError("ABN must contain exactly 11 digits")
    return digits


def _domain(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host:
        raise ValueError("domain must contain a host")
    return host


class FundraisingIdentityCandidate(_Strict):
    """A durable subject identity already governed elsewhere."""

    subject_id: str = Field(min_length=1)
    abn: str | None = None
    canonical_domain: str | None = None
    names: tuple[str, ...] = ()

    _normalise_abn = field_validator("abn")(_abn)
    _normalise_domain = field_validator("canonical_domain")(_domain)


class FundraisingBindingEvidence(_Strict):
    """Stable binding facts supplied by the source-specific identity adapter."""

    evidence_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    observed_at: date
    asserted_abn: str | None = None
    asserted_domain: str | None = None
    # This is an explicit source fact, never a conclusion derived from a URL.
    domain_is_subject_controlled: bool = False
    relationship_subject_id: str | None = None
    relationship_is_explicit: bool = False
    source_native_name: str | None = None

    _normalise_abn = field_validator("asserted_abn")(_abn)
    _normalise_domain = field_validator("asserted_domain")(_domain)

    @model_validator(mode="after")
    def relationship_is_complete(self):
        if self.relationship_is_explicit != (self.relationship_subject_id is not None):
            raise ValueError("explicit relationship requires, and only permits, a subject ID")
        return self


class FundraisingBindingDecision(_Strict):
    evidence_id: str
    status: BindingStatus
    subject_id: str | None = None
    basis: BindingBasis
    candidate_subject_ids: tuple[str, ...] = ()
    reason: str

    @model_validator(mode="after")
    def complete_status(self):
        if self.status == "confirmed" and not self.subject_id:
            raise ValueError("confirmed binding requires a subject ID")
        if self.status != "confirmed" and self.subject_id is not None:
            raise ValueError("non-confirmed binding cannot select a subject")
        return self


def _unique(candidates: list[FundraisingIdentityCandidate], evidence: FundraisingBindingEvidence, basis: BindingBasis) -> FundraisingBindingDecision:
    subject_ids = tuple(sorted({candidate.subject_id for candidate in candidates}))
    if len(subject_ids) == 1:
        return FundraisingBindingDecision(
            evidence_id=evidence.evidence_id, status="confirmed", subject_id=subject_ids[0], basis=basis,
            candidate_subject_ids=subject_ids, reason="one governed subject matches the supplied identity authority",
        )
    return FundraisingBindingDecision(
        evidence_id=evidence.evidence_id, status="ambiguous", basis="ambiguous_multiple_exact_matches",
        candidate_subject_ids=subject_ids, reason="multiple governed subjects match the supplied identity authority",
    )


def resolve_fundraising_subject_binding(
    evidence: FundraisingBindingEvidence, candidates: tuple[FundraisingIdentityCandidate, ...]
) -> FundraisingBindingDecision:
    """Resolve only unique, authority-backed identifiers; otherwise preserve refusal."""
    if len({candidate.subject_id for candidate in candidates}) != len(candidates):
        raise ValueError("candidate subject IDs must be unique")
    if evidence.asserted_abn:
        matches = [candidate for candidate in candidates if candidate.abn == evidence.asserted_abn]
        if matches:
            return _unique(matches, evidence, "exact_abn_with_identity_authority")
    if evidence.relationship_is_explicit:
        matches = [candidate for candidate in candidates if candidate.subject_id == evidence.relationship_subject_id]
        if matches:
            return _unique(matches, evidence, "explicit_subject_relationship")
    if evidence.asserted_domain and evidence.domain_is_subject_controlled:
        matches = [candidate for candidate in candidates if candidate.canonical_domain == evidence.asserted_domain]
        if matches:
            return _unique(matches, evidence, "verified_subject_controlled_domain")
    return FundraisingBindingDecision(
        evidence_id=evidence.evidence_id, status="unresolved", basis="insufficient_identity_evidence",
        reason="name, unverified domain, or absent stable identifier cannot bind a fundraising observation",
    )


def binding_outcome_counts(decisions: tuple[FundraisingBindingDecision, ...]) -> dict[str, int]:
    """Report all binding outcomes so refusal is never hidden by resolved cases."""
    return dict(sorted(Counter(decision.status for decision in decisions).items()))


__all__ = [
    "FundraisingBindingDecision", "FundraisingBindingEvidence", "FundraisingIdentityCandidate",
    "binding_outcome_counts", "resolve_fundraising_subject_binding",
]
