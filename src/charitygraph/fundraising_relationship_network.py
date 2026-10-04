"""Review-only provider and platform relationships for fundraising discovery.

This compiler consumes structured evidence; it never reads prose or resolves
names.  A relationship can seed a bounded evidence-discovery queue only when
both the charity and provider identities are explicitly resolved.  It never
becomes a standing-practice observation.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fundraising_evidence_roles import FundraisingEvidence


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


IdentityState = Literal["resolved", "candidate", "ambiguous", "unresolved"]
ProviderKind = Literal["agency", "platform"]
RelationshipLifecycle = Literal["current", "historical", "ended", "unknown"]
DiscoveryDisposition = Literal["candidate_evidence_discovery", "review_only", "do_not_seed"]


class ProviderIdentity(_Strict):
    """An identity result supplied by the common identity-resolution layer."""

    identity_state: IdentityState
    subject_id: str | None = Field(default=None, min_length=1)
    display_name: str | None = None
    binding_basis: str = Field(min_length=1)

    @model_validator(mode="after")
    def resolved_identity_has_a_durable_subject(self):
        if self.identity_state == "resolved" and not self.subject_id:
            raise ValueError("a resolved provider identity requires subject_id")
        if self.identity_state != "resolved" and self.subject_id is not None:
            raise ValueError("only a resolved provider identity may carry subject_id")
        return self


class FundraisingProviderNetworkInput(_Strict):
    """One directed charity-to-provider assertion, retained even when refused."""

    relationship_id: str = Field(pattern=r"^frn_[a-z0-9][a-z0-9_-]*$")
    charity_subject_id: str = Field(min_length=1)
    provider: ProviderIdentity
    provider_kind: ProviderKind
    evidence: FundraisingEvidence
    lifecycle: RelationshipLifecycle = "unknown"
    relationship_scope: Literal["organisation", "campaign", "program"]
    relationship_scope_id: str = Field(min_length=1)
    valid_from: date | None = None
    valid_to: date | None = None
    ended_on: date | None = None

    @model_validator(mode="after")
    def directed_and_temporally_explicit(self):
        if "provider" not in self.evidence.asserted_facets:
            raise ValueError("provider relationship evidence must explicitly assert the provider facet")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("relationship valid_from cannot follow valid_to")
        if self.lifecycle == "ended" and self.ended_on is None:
            raise ValueError("an ended provider relationship requires explicit ended_on")
        if self.lifecycle != "ended" and self.ended_on is not None:
            raise ValueError("only an ended provider relationship may carry ended_on")
        if self.provider.identity_state == "resolved" and self.provider.subject_id == self.charity_subject_id:
            raise ValueError("a charity cannot be its own fundraising provider")
        return self


class FundraisingProviderNetworkRelationship(_Strict):
    """Compiled review record; `discovery_disposition` is not a practice claim."""

    contract_version: Literal["fundraising-provider-network-v1-review"] = "fundraising-provider-network-v1-review"
    relationship_id: str
    from_charity_subject_id: str
    to_provider_subject_id: str | None
    provider_identity_state: IdentityState
    provider_kind: ProviderKind
    lifecycle: RelationshipLifecycle
    relationship_scope: str
    relationship_scope_id: str
    valid_from: date | None
    valid_to: date | None
    ended_on: date | None
    evidence_id: str
    source_id: str
    source_role: str
    locator: str
    source_wording: str
    charity_binding_basis: str
    provider_binding_basis: str
    observed_at: date
    coverage: str
    review_status: str
    discovery_disposition: DiscoveryDisposition
    practice_observed: Literal[None] = None
    rationale: str


def _disposition(item: FundraisingProviderNetworkInput) -> tuple[DiscoveryDisposition, str]:
    if item.evidence.coverage != "observed":
        return "do_not_seed", "coverage is not an observed relationship assertion"
    if item.evidence.subject_binding != "confirmed":
        return "do_not_seed", "charity binding is not confirmed"
    if item.provider.identity_state != "resolved":
        return "do_not_seed", "provider identity is not resolved; retain for identity review only"
    if item.lifecycle == "ended":
        return "review_only", "former provider relationship is retained but cannot seed current discovery"
    if item.evidence.review_status != "reviewed":
        return "review_only", "relationship is bound but requires review before discovery use"
    return "candidate_evidence_discovery", "explicit resolved directed relationship may seed candidate evidence discovery only"


def compile_provider_network(
    inputs: tuple[FundraisingProviderNetworkInput, ...],
) -> tuple[FundraisingProviderNetworkRelationship, ...]:
    """Compile without deduplicating or choosing between competing assertions.

    Duplicate directed claims are retained as separate evidence records.  This
    avoids silently merging former and current relationships or resolving an
    identity ambiguity by name similarity.
    """
    if len({item.relationship_id for item in inputs}) != len(inputs):
        raise ValueError("provider network relationship IDs must be unique")
    records = []
    for item in inputs:
        disposition, rationale = _disposition(item)
        records.append(FundraisingProviderNetworkRelationship(
            relationship_id=item.relationship_id, from_charity_subject_id=item.charity_subject_id,
            to_provider_subject_id=item.provider.subject_id, provider_identity_state=item.provider.identity_state,
            provider_kind=item.provider_kind, lifecycle=item.lifecycle,
            relationship_scope=item.relationship_scope, relationship_scope_id=item.relationship_scope_id,
            valid_from=item.valid_from, valid_to=item.valid_to, ended_on=item.ended_on,
            evidence_id=item.evidence.evidence_id, source_id=item.evidence.source_id,
            source_role=item.evidence.source_role, locator=item.evidence.locator,
            source_wording=item.evidence.source_wording,
            charity_binding_basis=item.evidence.binding_basis, provider_binding_basis=item.provider.binding_basis,
            observed_at=item.evidence.observed_at, coverage=item.evidence.coverage,
            review_status=item.evidence.review_status, discovery_disposition=disposition,
            rationale=rationale,
        ))
    return tuple(sorted(records, key=lambda record: (record.observed_at, record.relationship_id)))
