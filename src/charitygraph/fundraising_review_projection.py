"""Deterministic, review-only fundraising profile projection.

This is deliberately a read model over governed assertions.  It does not
classify source prose, allocate an organisation-level amount to a method, or
derive fundraising performance measures.
"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .finance_measurement import FundraisingMoneyMeasurement
from .fundraising_money_linkage import FundraisingMoneyScopeLink
from .models import FundraisingCampaignObservation, FundraisingPracticeObservation, FundraisingProviderRelationship


REVIEW_CONTRACT_VERSION = "fundraising-review-profile-v1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewCoverage(_Strict):
    capability: Literal["practices", "campaigns", "providers", "money"]
    status: Literal["observed", "not_found_in_scoped_source", "not_yet_processed", "unavailable", "unknown"]
    scope: str
    note: str


class FundraisingReviewSubject(_Strict):
    subject_id: str = Field(pattern=r"^cb_[a-z0-9][a-z0-9_-]*$")
    display_name: str
    evidence_set_id: str
    practices: tuple[FundraisingPracticeObservation, ...] = ()
    campaigns: tuple[FundraisingCampaignObservation, ...] = ()
    providers: tuple[FundraisingProviderRelationship, ...] = ()
    money: tuple[FundraisingMoneyScopeLink, ...] = ()
    coverage: tuple[ReviewCoverage, ...]


class FundraisingReviewArtifact(_Strict):
    contract_version: Literal["fundraising-review-profile-v1"] = REVIEW_CONTRACT_VERSION
    capability_scope: Literal["review_only_representative_slice"] = "review_only_representative_slice"
    subjects: tuple[FundraisingReviewSubject, ...]

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @property
    def sha256(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def render_markdown(artifact: FundraisingReviewArtifact) -> str:
    """Render stable review text while preserving source scope and unknowns."""
    lines = [
        "# Fundraising review profile",
        "",
        f"- Contract: `{artifact.contract_version}`",
        f"- Capability: `{artifact.capability_scope}` (not the whole product)",
        f"- Deterministic input hash: `{artifact.sha256}`",
        "- Money is displayed at its explicit attributed scope; an organisation-level fact is not attributed to a practice, campaign or provider.",
    ]
    for subject in artifact.subjects:
        lines += ["", f"## {subject.display_name} (`{subject.subject_id}`)", f"- Evidence set: `{subject.evidence_set_id}`", "", "### Practices"]
        lines += [f"- `{p.observation_id}`: {p.source_native_phrase}; lifecycle `{p.lifecycle}`; scope `{p.scope.scope_kind}`; evidence `{', '.join(p.evidence_ids) or 'none'}`" for p in subject.practices] or ["- Unknown or not processed; see coverage."]
        lines += ["", "### Campaigns"]
        lines += [f"- `{c.observation_id}`: {c.campaign_name}; lifecycle `{c.lifecycle}`; scope `{c.scope.scope_kind}`; evidence `{', '.join(c.evidence_ids) or 'none'}`" for c in subject.campaigns] or ["- Unknown or not processed; see coverage."]
        lines += ["", "### Providers"]
        lines += [f"- `{p.relationship_id}`: `{p.provider_role}` to `{p.relationship.target_causebase_id}`; lifecycle `{p.lifecycle}`; evidence `{', '.join(p.evidence_ids) or 'none'}`" for p in subject.providers] or ["- No provider relationship is asserted in this review set."]
        lines += ["", "### Money facts"]
        if subject.money:
            for link in subject.money:
                measurement: FundraisingMoneyMeasurement = link.measurement
                scope = link.attributed_scope_kind if link.linkage_status == "explicit" else "organisation (not attributed)"
                lines.append(f"- `{measurement.observation_id}`: {measurement.amount.normalised_amount} {measurement.amount.normalised_currency}; `{measurement.measure_kind}`; period `{measurement.period.label}`; scope `{scope}`; linkage `{link.linkage_status}`; source wording: {measurement.source_wording}")
        else:
            lines.append("- No money fact available in the selected evidence.")
        lines += ["", "### Coverage"]
        lines += [f"- `{c.capability}`: `{c.status}` — {c.note} (scope: {c.scope})" for c in subject.coverage]
    return "\n".join(lines) + "\n"
