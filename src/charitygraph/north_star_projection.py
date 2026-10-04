"""Minimal downstream North-Star assignment and deterministic card projection."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from charitygraph.models import (
    CauseBaseCard, FundraisingCampaignObservation, FundraisingPracticeObservation,
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

LENS_SCHEMA=NorthStarLensOutput.model_json_schema()


class FundraisingProjection(_Strict):
    """Lossless typed projection; legacy flat observations are intentionally absent."""

    practices: tuple[FundraisingPracticeObservation, ...]
    campaigns: tuple[FundraisingCampaignObservation, ...]
    provider_relationships: tuple[FundraisingProviderRelationship, ...]


def project_fundraising(card: CauseBaseCard) -> FundraisingProjection:
    """Project only canonical typed assertions without inventing an adaptation."""
    return FundraisingProjection(
        practices=tuple(card.fundraising_practice_observed),
        campaigns=tuple(card.fundraising_campaign_observed),
        provider_relationships=tuple(card.fundraising_provider_relationships),
    )
