"""Minimal downstream North-Star assignment and deterministic card projection."""
from __future__ import annotations
from typing import ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .integrated_card import NORTH_STAR_PROJECTION_VNEXT

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
    """Historical lens response; section numbers are permanently v0.1."""

    projection_contract_id: ClassVar[Literal["north-star-v0.1"]] = "north-star-v0.1"
    assignments: tuple[SectionAssignment, ...]


class SectionAssignmentVNext(_Strict):
    observation_key: str = Field(pattern=r"^O[0-9]{3}$")
    section_ids: tuple[int, ...] = ()
    note: str | None = None

    @model_validator(mode="after")
    def valid_sections(self):
        if any(section not in NORTH_STAR_PROJECTION_VNEXT.section_titles for section in self.section_ids):
            raise ValueError("section IDs must exist in north-star-vNext")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("section IDs must be unique")
        return self


class NorthStarLensOutputVNext(_Strict):
    projection_contract_id: Literal["north-star-vNext"]
    assignments: tuple[SectionAssignmentVNext, ...]


# Keep the historical lens wire schema stable for retained v0.1 outputs.
LENS_SCHEMA = NorthStarLensOutput.model_json_schema()
LENS_SCHEMA_VNEXT = NorthStarLensOutputVNext.model_json_schema()
