"""Minimal downstream North-Star assignment and deterministic card projection."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .projection_compatibility import CompatibilityAudit, EvaluationGrain, PolicyInput, evaluate_compatibility
from .fundraising_money_linkage import FundraisingMoneyScopeLink
from .fundraising_joint_coverage import FundraisingJointCoverage, classify_fundraising_joint_coverage
from .models import (
    CauseBaseCard, CoverageObservation, EvidenceRef,
    FundraisingCampaignObservation, FundraisingPracticeObservation,
    FundraisingProviderRelationship,
)

class _Strict(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)

class SectionAssignment(_Strict):
    observation_key: str = Field(pattern=r"^O[0-9]{3}$")
    section_ids: tuple[int, ...] = ()
    note: str | None = None
    @model_validator(mode="after")
    def valid_sections(self):
        if any(section < 1 or section > 20 for section in self.section_ids): raise ValueError("section IDs must be 1..20")
        if len(set(self.section_ids)) != len(self.section_ids): raise ValueError("section IDs must be unique")
        return self

class NorthStarLensOutput(_Strict):
    assignments: tuple[SectionAssignment, ...]

    def compatibility_audit(
        self,
        inputs: PolicyInput | dict[str, object],
        *,
        grain: EvaluationGrain = EvaluationGrain.SECTION_CARD,
    ) -> CompatibilityAudit:
        """The real pre-projection boundary: validate before cards are emitted."""
        return evaluate_compatibility(inputs, grain=grain)


def project_with_compatibility_gate(
    output: NorthStarLensOutput,
    inputs: PolicyInput | dict[str, object],
) -> tuple[NorthStarLensOutput | None, CompatibilityAudit]:
    """Return no projection when the deterministic gate abstains."""
    audit = output.compatibility_audit(inputs)
    if audit.disposition.value == "ABSTAIN":
        return None, audit
    return output, audit

LENS_SCHEMA=NorthStarLensOutput.model_json_schema()


class FundraisingProjection(_Strict):
    """Review-only card/API view over canonical governed fundraising facts.

    The legacy flat ``fundraising_methods`` field is intentionally absent.
    Money facts retain their source-supported scope; this projection never
    assigns an organisation amount to a practice, campaign, or provider.
    """

    practices: tuple[FundraisingPracticeObservation, ...]
    campaigns: tuple[FundraisingCampaignObservation, ...]
    provider_relationships: tuple[FundraisingProviderRelationship, ...]
    money: tuple[FundraisingMoneyScopeLink, ...] = ()
    coverage: tuple[CoverageObservation, ...] = ()
    joint_coverage: FundraisingJointCoverage
    evidence: tuple[EvidenceRef, ...] = ()


_FUNDRAISING_CAPABILITIES = frozenset({
    "fundraising_practices", "fundraising_campaigns",
    "fundraising_provider_relationships", "fundraising_money",
    "fundraising_expenditure",
})


def _fundraising_evidence_ids(
    practices: tuple[FundraisingPracticeObservation, ...],
    campaigns: tuple[FundraisingCampaignObservation, ...],
    providers: tuple[FundraisingProviderRelationship, ...],
    money: tuple[FundraisingMoneyScopeLink, ...],
    coverage: tuple[CoverageObservation, ...],
) -> set[str]:
    return (
        {evidence_id for item in (*practices, *campaigns, *providers) for evidence_id in item.evidence_ids}
        | {evidence_id for link in money for evidence_id in (*link.measurement.evidence_ids, *link.linkage_evidence_ids)}
        | {evidence_id for item in coverage for evidence_id in item.evidence_ids}
    )


def project_fundraising(
    card: CauseBaseCard, money_links: tuple[FundraisingMoneyScopeLink, ...] = (),
) -> FundraisingProjection:
    """Project canonical typed fundraising observations for card/API consumers."""
    practices = tuple(card.fundraising_practice_observed)
    campaigns = tuple(card.fundraising_campaign_observed)
    providers = tuple(card.fundraising_provider_relationships)
    coverage = tuple(item for item in card.coverage if item.capability in _FUNDRAISING_CAPABILITIES)
    requested = _fundraising_evidence_ids(practices, campaigns, providers, money_links, coverage)
    known = {item.evidence_id for item in card.evidence}
    if missing := requested - known:
        raise ValueError(f"fundraising projection references evidence absent from card: {sorted(missing)}")
    for link in money_links:
        entity = link.reporting_entity_causebase_id or link.measurement.reporting_subject_causebase_id
        if entity != card.causebase_id:
            raise ValueError("fundraising money link reporting entity does not match card subject")
    return FundraisingProjection(
        practices=practices, campaigns=campaigns, provider_relationships=providers,
        money=money_links, coverage=coverage,
        joint_coverage=classify_fundraising_joint_coverage(card, money_links),
        evidence=tuple(item for item in card.evidence if item.evidence_id in requested),
    )


def render_fundraising_card(projection: FundraisingProjection) -> str:
    """Render a deterministic, non-causal human-readable fundraising section."""
    lines = ["## Fundraising and linked financial facts", "", "### Practices"]
    lines.extend(
        f"- `{item.observation_id}`: {item.source_native_phrase}; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.practices
    )
    if not projection.practices: lines.append("- No practice observation is asserted; see coverage.")
    lines.extend(["", "### Campaigns"])
    lines.extend(
        f"- `{item.observation_id}`: {item.campaign_name}; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.campaigns
    )
    if not projection.campaigns: lines.append("- No campaign observation is asserted; see coverage.")
    lines.extend(["", "### Providers"])
    lines.extend(
        f"- `{item.relationship_id}`: `{item.provider_role}`; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.provider_relationships
    )
    if not projection.provider_relationships: lines.append("- No provider relationship is asserted; see coverage.")
    lines.extend(["", "### Money facts"])
    for link in projection.money:
        fact = link.measurement
        scope = link.attributed_scope_kind if link.linkage_status == "explicit" else "organisation (not attributed)"
        lines.append(
            f"- `{fact.observation_id}`: {fact.amount.normalised_amount} {fact.amount.normalised_currency}; "
            f"`{fact.measure_kind}`; period `{fact.period.label}`; scope `{scope}`; "
            f"linkage `{link.linkage_status}`; evidence `{', '.join(fact.evidence_ids)}`"
        )
    if not projection.money: lines.append("- No compatible money fact is available; see coverage.")
    lines.extend(["", "### Joint coverage"])
    joint = projection.joint_coverage
    lines.append(f"- State `{joint.state}`. {joint.note}")
    lines.extend(["", "### Coverage"])
    lines.extend(f"- `{item.capability}`: `{item.status}`" + (f" — {item.freshness_note}" if item.freshness_note else "") for item in projection.coverage)
    if not projection.coverage: lines.append("- No fundraising coverage observation is available.")
    return "\n".join(lines) + "\n"
