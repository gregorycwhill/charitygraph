"""Deterministic, provider-free compatibility gate for downstream projections.

The gate deliberately evaluates governed metadata, not English.  A caller may
run bounded wording/review after this function, but it cannot change an
ABSTAIN or remove a required qualifier from the returned audit record.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping
from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION = "projection-compatibility.v1"

class Disposition(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_QUALIFICATION = "ALLOW_WITH_QUALIFICATION"
    ABSTAIN = "ABSTAIN"

class EvaluationGrain(StrEnum):
    PROPOSITION = "proposition"
    CLAUSE = "clause"
    SECTION_CARD = "section_card"
    WHOLE_ANSWER = "whole_answer"

class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    answer_intent: str | None = None
    claim_family: str | None = None
    authority_source_role: str | None = None
    currentness: str | None = None
    scope: str | None = None
    coverage: str | None = None
    evidence_refs: tuple[str, ...] = ()

class Qualification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    text: str

class CompatibilityAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_version: str = POLICY_VERSION
    disposition: Disposition
    grain: EvaluationGrain
    reason_codes: tuple[str, ...] = ()
    governed_inputs: PolicyInput
    required_qualifiers: tuple[Qualification, ...] = ()
    input_refs: tuple[str, ...] = ()

    def with_wording_review(self, _review: Mapping[str, Any]) -> "CompatibilityAudit":
        """Return the mechanical result unchanged; wording cannot override it."""
        return self

_DIMENSIONS = (
    "answer_intent", "claim_family", "authority_source_role",
    "currentness", "scope", "coverage",
)

def evaluate_compatibility(
    inputs: PolicyInput | Mapping[str, Any],
    *, grain: EvaluationGrain = EvaluationGrain.PROPOSITION,
) -> CompatibilityAudit:
    """Evaluate the six supported dimensions with explicit absence handling."""
    governed = inputs if isinstance(inputs, PolicyInput) else PolicyInput.model_validate(inputs)
    missing = tuple(f"MISSING_{name.upper()}" for name in _DIMENSIONS if getattr(governed, name) in (None, ""))
    reasons: list[str] = list(missing)
    qualifiers: list[Qualification] = []

    if governed.currentness in {"stale", "unknown"}:
        reasons.append("CURRENTNESS_UNSAFE")
        qualifiers.append(Qualification(code="CURRENTNESS_LIMIT", text="Currentness is not established."))
    if governed.coverage in {"not_found_in_source", "not_available_from_source", "unknown", "retrieval_failed"}:
        reasons.append("COVERAGE_LIMIT")
        qualifiers.append(Qualification(code="COVERAGE_LIMIT", text="The source does not establish complete coverage."))
    if governed.authority_source_role in {"unknown", "unverified"}:
        reasons.append("AUTHORITY_UNVERIFIED")
        qualifiers.append(Qualification(code="AUTHORITY_LIMIT", text="Source authority is not verified."))

    hard = bool(missing) or any(code in reasons for code in ("CURRENTNESS_UNSAFE", "AUTHORITY_UNVERIFIED"))
    disposition = Disposition.ABSTAIN if hard else (Disposition.ALLOW_WITH_QUALIFICATION if qualifiers else Disposition.ALLOW)
    return CompatibilityAudit(
        disposition=disposition, grain=grain, reason_codes=tuple(dict.fromkeys(reasons)),
        governed_inputs=governed, required_qualifiers=tuple(dict.fromkeys(qualifiers)),
        input_refs=governed.evidence_refs,
    )

def compose_audits(audits: tuple[CompatibilityAudit, ...], *, grain: EvaluationGrain) -> CompatibilityAudit:
    """Compose child evaluations; ABSTAIN is monotonic and cannot be softened."""
    if not audits:
        return evaluate_compatibility({}, grain=grain)
    if any(a.disposition is Disposition.ABSTAIN for a in audits):
        disposition = Disposition.ABSTAIN
    elif any(a.disposition is Disposition.ALLOW_WITH_QUALIFICATION for a in audits):
        disposition = Disposition.ALLOW_WITH_QUALIFICATION
    else:
        disposition = Disposition.ALLOW
    first = audits[0]
    return CompatibilityAudit(
        disposition=disposition, grain=grain,
        reason_codes=tuple(dict.fromkeys(code for a in audits for code in a.reason_codes)),
        governed_inputs=first.governed_inputs,
        required_qualifiers=tuple(dict.fromkeys(q for a in audits for q in a.required_qualifiers)),
        input_refs=tuple(dict.fromkeys(ref for a in audits for ref in a.input_refs)),
    )
