"""Card-blind compact semantic production contract (experiment v0.1)."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompactAtomEvidence(_Strict):
    source: str = Field(pattern=r"^S[0-9]{3}$")
    locator: str = Field(pattern=r"^L[0-9]{4}(?:-L[0-9]{4})?$")
    role: Literal["supporting", "corroborating", "context"]


class CompactAtom(_Strict):
    proposition: str = Field(min_length=1, max_length=500)
    scope_kind: Literal["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]
    scope_label: str | None = None
    temporal_kind: Literal["current", "as_of", "reporting_period", "historical", "undated", "mixed"]
    temporal_value: str | None = None
    epistemic_status: Literal["supported", "explicit_absence"]
    evidence: tuple[CompactAtomEvidence, ...]
    qualifications: tuple[str, ...] = ()

    @model_validator(mode="after")
    def supporting_evidence_required(self) -> "CompactAtom":
        if not any(ref.role == "supporting" for ref in self.evidence):
            raise ValueError("compact atoms require supporting evidence")
        return self


class CompactKnowledgeOutput(_Strict):
    atoms: tuple[CompactAtom, ...]


STRICT_SCHEMA = CompactKnowledgeOutput.model_json_schema()
for node in [STRICT_SCHEMA]:
    if isinstance(node, dict):
        def strictify(value):
            if isinstance(value, dict):
                value.pop("default", None)
                if value.get("type") == "object" and "properties" in value:
                    value["required"] = list(value["properties"])
                for child in value.values(): strictify(child)
            elif isinstance(value, list):
                for child in value: strictify(child)
        strictify(node)


class CompactAtomV02(_Strict):
    proposition: str = Field(min_length=1, max_length=500)
    scope_kind: Literal["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]
    scope_label: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    reporting_period: str | None = None
    epistemic_status: Literal["supported", "explicit_absence"]
    evidence: tuple[CompactAtomEvidence, ...]
    qualifications: tuple[str, ...] = ()

    @model_validator(mode="after")
    def supporting_evidence_required(self) -> "CompactAtomV02":
        if not any(ref.role == "supporting" for ref in self.evidence):
            raise ValueError("compact atoms require supporting evidence")
        return self


class CompactKnowledgeOutputV02(_Strict):
    atoms: tuple[CompactAtomV02, ...]


COMPACT_V02_SCHEMA = CompactKnowledgeOutputV02.model_json_schema()
strictify(COMPACT_V02_SCHEMA)
