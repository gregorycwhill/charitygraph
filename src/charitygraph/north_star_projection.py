"""Minimal downstream North-Star assignment and deterministic card projection."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from charitygraph.models import (
    CauseBaseCard, CoverageObservation, EvidenceRef, FundraisingCampaignObservation,
    FundraisingPracticeObservation, FundraisingProviderRelationship,
)
from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink

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

LENS_SCHEMA=NorthStarLensOutput.model_json_schema()


class FundraisingProjection(_Strict):
    """A review-only North-Star card/API section over governed inputs.

    This is intentionally a projection, rather than a new stored aggregate.
    Money is retained only at its explicitly supported scope and is never
    allocated to a practice, campaign, or provider by this compiler.
    """

    practices: tuple[FundraisingPracticeObservation, ...]
    campaigns: tuple[FundraisingCampaignObservation, ...]
    provider_relationships: tuple[FundraisingProviderRelationship, ...]
    money: tuple[FundraisingMoneyScopeLink, ...] = ()
    coverage: tuple[CoverageObservation, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()


_FUNDRAISING_CAPABILITIES = frozenset({
    "fundraising_practices",
    "fundraising_campaigns",
    "fundraising_provider_relationships",
    "fundraising_money",
    "fundraising_expenditure",
})


def _projection_evidence_ids(
    practices: tuple[FundraisingPracticeObservation, ...],
    campaigns: tuple[FundraisingCampaignObservation, ...],
    providers: tuple[FundraisingProviderRelationship, ...],
    money: tuple[FundraisingMoneyScopeLink, ...],
    coverage: tuple[CoverageObservation, ...],
) -> set[str]:
    return {
        evidence_id
        for observation in (*practices, *campaigns, *providers)
        for evidence_id in observation.evidence_ids
    } | {
        evidence_id
        for link in money
        for evidence_id in (
            *link.measurement.evidence_ids,
            *link.linkage_evidence_ids,
        )
    } | {
        evidence_id
        for item in coverage
        for evidence_id in item.evidence_ids
    }


def project_fundraising(
    card: CauseBaseCard,
    money_links: tuple[FundraisingMoneyScopeLink, ...] = (),
) -> FundraisingProjection:
    """Compile the governed fundraising slice for a card/API consumer.

    ``money_links`` stays an explicit compiler input until a separately
    governed persistence migration adds it to ``CauseBaseCard``.  Requiring
    this input avoids silently serialising a new public-card field.
    """
    practices = tuple(card.fundraising_practice_observed)
    campaigns = tuple(card.fundraising_campaign_observed)
    providers = tuple(card.fundraising_provider_relationships)
    coverage = tuple(item for item in card.coverage if item.capability in _FUNDRAISING_CAPABILITIES)
    known_evidence_ids = {item.evidence_id for item in card.evidence}
    requested_evidence_ids = _projection_evidence_ids(practices, campaigns, providers, money_links, coverage)
    missing_evidence_ids = requested_evidence_ids - known_evidence_ids
    if missing_evidence_ids:
        raise ValueError(f"fundraising projection references evidence absent from card: {sorted(missing_evidence_ids)}")
    for link in money_links:
        reporting_entity = link.reporting_entity_causebase_id or link.measurement.reporting_subject_causebase_id
        if reporting_entity != card.causebase_id:
            raise ValueError("fundraising money link reporting entity does not match card subject")
    return FundraisingProjection(
        practices=practices,
        campaigns=campaigns,
        provider_relationships=providers,
        money=money_links,
        coverage=coverage,
        evidence=tuple(item for item in card.evidence if item.evidence_id in requested_evidence_ids),
    )


def render_fundraising_card(projection: FundraisingProjection) -> str:
    """Render a compact deterministic view without making performance claims."""
    lines = ["## Fundraising and linked financial facts", "", "### Practices"]
    lines.extend(
        f"- `{item.observation_id}`: {item.source_native_phrase}; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.practices
    )
    if not projection.practices:
        lines.append("- No practice observation is asserted; see coverage.")
    lines.extend(["", "### Campaigns"])
    lines.extend(
        f"- `{item.observation_id}`: {item.campaign_name}; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.campaigns
    )
    if not projection.campaigns:
        lines.append("- No campaign observation is asserted; see coverage.")
    lines.extend(["", "### Providers"])
    lines.extend(
        f"- `{item.relationship_id}`: `{item.provider_role}`; lifecycle `{item.lifecycle}`; "
        f"scope `{item.scope.scope_kind}`; evidence `{', '.join(item.evidence_ids)}`"
        for item in projection.provider_relationships
    )
    if not projection.provider_relationships:
        lines.append("- No provider relationship is asserted; see coverage.")
    lines.extend(["", "### Money facts"])
    for link in projection.money:
        measurement = link.measurement
        scope = link.attributed_scope_kind if link.linkage_status == "explicit" else "organisation (not attributed)"
        lines.append(
            f"- `{measurement.observation_id}`: {measurement.amount.normalised_amount} "
            f"{measurement.amount.normalised_currency}; `{measurement.measure_kind}`; period "
            f"`{measurement.period.label}`; scope `{scope}`; linkage `{link.linkage_status}`; "
            f"evidence `{', '.join(measurement.evidence_ids)}`"
        )
    if not projection.money:
        lines.append("- No compatible money fact is available; see coverage.")
    lines.extend(["", "### Coverage"])
    lines.extend(
        f"- `{item.capability}`: `{item.status}`" + (f" â€” {item.freshness_note}" if item.freshness_note else "")
        for item in projection.coverage
    )
    if not projection.coverage:
        lines.append("- No fundraising coverage observation is available.")
    return "\n".join(lines) + "\n"
