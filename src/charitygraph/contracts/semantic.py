"""Typed semantic task outputs for the private Phase 1 pre-run engine.

These contracts accept model conclusions only after validation; they do not
encode English keyword heuristics or silently convert conclusions to unknown.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import SchemaRef, StrictModel, require_nonblank
from .ids import validate_typed_id


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


class SemanticEvidence(StrictModel):
    evidence_id: str
    role: Literal["supporting", "competing", "context"]
    note: str | None = None

    @field_validator("evidence_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return require_nonblank(value, "evidence_id")

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)


class SemanticConclusion(StrictModel):
    outcome: Literal["resolved", "supported", "insufficient_evidence", "ambiguous", "not_applicable"]
    evidence: tuple[SemanticEvidence, ...] = ()
    rationale: str | None = None
    confidence: Literal["low", "medium", "high"] | None = None

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _support(self) -> "SemanticConclusion":
        if self.outcome in {"resolved", "supported"} and not self.evidence:
            raise ValueError("resolved semantic conclusions require evidence")
        if self.outcome in {"resolved", "supported"} and not self.rationale:
            raise ValueError("resolved semantic conclusions require rationale")
        return self


class ProgramCandidateOutput(StrictModel):
    label: str
    decision: Literal["material_program", "material_service", "non_program", "duplicate_or_alias", "parent_child_proposal", "insufficient_evidence"]
    subject_kind: Literal["program", "service"] | None = None
    duplicate_of_candidate_id: str | None = None
    parent_candidate_id: str | None = None
    conclusion: SemanticConclusion

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("duplicate_of_candidate_id", "parent_candidate_id")
    @classmethod
    def _candidate(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return validate_typed_id(value, "programcandidate:")
        except ValueError as exc:
            raise ValueError("program candidate references must use programcandidate: IDs") from exc

    @model_validator(mode="after")
    def _shape(self) -> "ProgramCandidateOutput":
        if self.decision in {"material_program", "material_service"} and self.subject_kind is None:
            raise ValueError("material program/service decisions require subject_kind")
        if self.decision == "duplicate_or_alias" and self.duplicate_of_candidate_id is None:
            raise ValueError("duplicate decisions require duplicate_of_candidate_id")
        return self


class TaxonomySelection(StrictModel):
    concept_id: str
    role: Literal["primary", "secondary"]
    evidence: tuple[SemanticEvidence, ...]
    rationale: str
    confidence: Literal["low", "medium", "high"] | None = None

    @field_validator("concept_id")
    @classmethod
    def _concept(cls, value: str) -> str:
        try:
            return validate_typed_id(value, "concept:")
        except ValueError as exc:
            raise ValueError("taxonomy selections require concept: IDs") from exc

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[SemanticEvidence, ...]) -> tuple[SemanticEvidence, ...]:
        if not value:
            raise ValueError("taxonomy selections require evidence")
        return value


class TaxonomyAssignmentOutput(StrictModel):
    conclusion: SemanticConclusion
    selections: tuple[TaxonomySelection, ...] = ()

    @model_validator(mode="after")
    def _selection_state(self) -> "TaxonomyAssignmentOutput":
        if self.conclusion.outcome in {"resolved", "supported"} and not self.selections:
            raise ValueError("resolved taxonomy output requires selections")
        return self


class SDGAlignmentOutput(StrictModel):
    conclusion: SemanticConclusion
    sdg_selections: tuple[TaxonomySelection, ...] = ()

    @model_validator(mode="after")
    def _sdg_state(self) -> "SDGAlignmentOutput":
        if self.conclusion.outcome in {"resolved", "supported"} and not self.sdg_selections:
            raise ValueError("resolved SDG output requires at least one alignment")
        return self


class EvidenceSelectionOutput(StrictModel):
    selected_evidence_ids: tuple[str, ...] = ()
    rejected_evidence_ids: tuple[str, ...] = ()
    conclusion: SemanticConclusion

    @model_validator(mode="after")
    def _unique(self) -> "EvidenceSelectionOutput":
        selected = set(self.selected_evidence_ids)
        if selected & set(self.rejected_evidence_ids):
            raise ValueError("evidence cannot be both selected and rejected")
        return self


TASK_OUTPUT_SCHEMAS = {
    "program_decomposition": _schema("program-decomposition-output"),
    "classie_subject_assignment": _schema("classie-subject-assignment-output"),
    "classie_population_assignment": _schema("classie-population-assignment-output"),
    "operational_activity_assignment": _schema("operational-activity-assignment-output"),
    "sdg_alignment": _schema("sdg-alignment-output"),
    "evidence_selection": _schema("evidence-selection-output"),
}

SEMANTIC_OUTPUT_MODELS = {
    "program_decomposition": ProgramCandidateOutput,
    "classie_subject_assignment": TaxonomyAssignmentOutput,
    "classie_population_assignment": TaxonomyAssignmentOutput,
    "operational_activity_assignment": TaxonomyAssignmentOutput,
    "sdg_alignment": SDGAlignmentOutput,
    "evidence_selection": EvidenceSelectionOutput,
}
