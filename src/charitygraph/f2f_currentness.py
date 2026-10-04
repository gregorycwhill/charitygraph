"""Evidence-bounded lifecycle decisions for face-to-face fundraising.

This module deliberately does *not* classify prose.  An upstream, governed
source adapter supplies the source-native semantic fields below.  The policy is
then mechanical: it records exactly what that source role can establish and
refuses to fill in unasserted delivery details.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Currentness = Literal[
    "current", "recent", "historical", "discontinued", "unknown",
    "not_found_in_scoped_source",
]
SourceRole = Literal[
    "pfra_membership", "agency_client", "first_party_f2f_page",
    "annual_report_statement", "historical_campaign_story",
    "explicit_cessation", "scoped_source_inventory", "other",
]
Binding = Literal["confirmed", "ambiguous", "unresolved"]
ScopeKind = Literal["organisation", "organisation_group", "program", "campaign", "geography", "unknown"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class F2FScope(_Strict):
    """The bounded universe to which a source statement applies."""

    kind: ScopeKind = "unknown"
    identifier: str | None = None
    geography: str | None = None
    description: str | None = None


class F2FSourceEvidence(_Strict):
    """A source-adapter output, preserving wording and its temporal meaning."""

    evidence_id: str = Field(min_length=1)
    source_role: SourceRole
    subject_binding: Binding
    source_wording: str = Field(min_length=1)
    observed_at: date
    valid_from: date | None = None
    valid_to: date | None = None
    scope: F2FScope = Field(default_factory=F2FScope)
    source_currentness: Currentness = "unknown"
    # These are only source-native explicit assertions.  None means the source
    # did not state the detail; false is an explicit negative assertion.
    setting: str | None = None
    delivery_agency: str | None = None
    regular_giving: bool | None = None
    source_coverage_description: str | None = None

    @model_validator(mode="after")
    def temporal_range_is_ordered(self):
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from cannot follow valid_to")
        if self.source_currentness == "not_found_in_scoped_source" and not self.source_coverage_description:
            raise ValueError("scoped source silence requires its coverage universe")
        return self


class F2FCurrentnessDecision(_Strict):
    """A governed decision about F2F practice, not a timeless boolean."""

    currentness: Currentness
    scope: F2FScope
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    source_role: SourceRole
    observed_at: date
    valid_from: date | None = None
    valid_to: date | None = None
    practice_observed: bool | None = None
    setting: str | None = None
    delivery_agency: str | None = None
    regular_giving: bool | None = None
    coverage_universe: str | None = None
    decision_basis: str


_ROLE_ALLOWED_CURRENTNESS: dict[SourceRole, frozenset[Currentness]] = {
    # Membership is industry evidence about membership, not proof of a charity's
    # particular deployment, arrangement, or present use of F2F.
    "pfra_membership": frozenset({"current", "recent", "historical", "discontinued", "unknown"}),
    "agency_client": frozenset({"current", "recent", "historical", "discontinued", "unknown"}),
    "first_party_f2f_page": frozenset({"current", "recent", "historical", "discontinued", "unknown"}),
    "annual_report_statement": frozenset({"recent", "historical", "unknown"}),
    "historical_campaign_story": frozenset({"historical", "unknown"}),
    "explicit_cessation": frozenset({"discontinued", "unknown"}),
    "scoped_source_inventory": frozenset({"not_found_in_scoped_source", "unknown"}),
    "other": frozenset({"unknown"}),
}


def decide_f2f_currentness(evidence: F2FSourceEvidence) -> F2FCurrentnessDecision:
    """Apply source-role semantics without a date-based universal freshness cut-off.

    ``recent`` is retained only when the adapter/source expressly gives that
    status; the policy does not manufacture it from elapsed days.  An ambiguous
    binding always wins, because names/domains do not resolve a subject.
    """
    if evidence.subject_binding != "confirmed":
        return F2FCurrentnessDecision(
            currentness="unknown", scope=evidence.scope, evidence_ids=(evidence.evidence_id,),
            source_role=evidence.source_role, observed_at=evidence.observed_at,
            valid_from=evidence.valid_from, valid_to=evidence.valid_to,
            decision_basis="subject binding is not confirmed; no F2F claim is promoted",
        )

    if evidence.source_currentness not in _ROLE_ALLOWED_CURRENTNESS[evidence.source_role]:
        raise ValueError(
            f"{evidence.source_role} cannot deterministically support "
            f"{evidence.source_currentness} currentness"
        )

    if evidence.source_role == "pfra_membership":
        return F2FCurrentnessDecision(
            currentness="unknown", scope=evidence.scope, evidence_ids=(evidence.evidence_id,),
            source_role=evidence.source_role, observed_at=evidence.observed_at,
            valid_from=evidence.valid_from, valid_to=evidence.valid_to,
            decision_basis="PFRA membership is industry membership evidence, not evidence of a specific charity F2F practice",
        )

    if evidence.source_role == "scoped_source_inventory":
        return F2FCurrentnessDecision(
            currentness=evidence.source_currentness, scope=evidence.scope,
            evidence_ids=(evidence.evidence_id,), source_role=evidence.source_role,
            observed_at=evidence.observed_at, valid_from=evidence.valid_from,
            valid_to=evidence.valid_to, coverage_universe=evidence.source_coverage_description,
            practice_observed=False if evidence.source_currentness == "not_found_in_scoped_source" else None,
            decision_basis="source inventory result is bounded to its declared coverage universe",
        )

    practice = True if evidence.source_currentness != "unknown" else None
    return F2FCurrentnessDecision(
        currentness=evidence.source_currentness, scope=evidence.scope,
        evidence_ids=(evidence.evidence_id,), source_role=evidence.source_role,
        observed_at=evidence.observed_at, valid_from=evidence.valid_from, valid_to=evidence.valid_to,
        practice_observed=practice, setting=evidence.setting,
        delivery_agency=evidence.delivery_agency, regular_giving=evidence.regular_giving,
        decision_basis="source-native currentness and explicit scope/detail assertions only",
    )
