"""Deterministic source-record and program-candidate contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ArtifactRecord, SchemaRef, require_nonblank
from .ids import validate_typed_id


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


class ProgramCandidate(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("program-candidate"), validation_alias="schema", serialization_alias="schema")
    subject_id: str
    source_record_id: str | None = None
    model_result_id: str | None = None
    evidence_ids: tuple[str, ...]
    label: str
    candidate_kind: Literal["explicit_program", "explicit_service", "structured_segment", "non_program", "ambiguous"]
    extraction_method: Literal["structured", "segmented", "model_task"]
    source_locator: str | None = None
    status: Literal["candidate", "accepted", "rejected", "held"] = "candidate"

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        try:
            return validate_typed_id(value, "programcandidate:")
        except ValueError as exc:
            raise ValueError("record_id must use programcandidate: typed ID") from exc

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        try:
            return validate_typed_id(value, "subject:")
        except ValueError as exc:
            raise ValueError("subject_id must use subject: typed ID") from exc

    @field_validator("source_record_id", "label")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("model_result_id")
    @classmethod
    def _model_result(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return validate_typed_id(value, "modelresult:")
        except ValueError as exc:
            raise ValueError("model_result_id must use modelresult: typed ID") from exc

    @field_validator("evidence_ids")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("program candidates require unique evidence references")
        return tuple(require_nonblank(item, "evidence_id") for item in value)

    @field_validator("source_locator")
    @classmethod
    def _locator(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _kind(self) -> "ProgramCandidate":
        if self.candidate_kind in {"explicit_program", "explicit_service"} and self.status == "rejected":
            raise ValueError("explicit program/service candidates cannot be rejected without review")
        if self.extraction_method in {"structured", "segmented"}:
            if self.source_record_id is None or self.model_result_id is not None:
                raise ValueError("structured/segmented candidates require source_record_id and no model_result_id")
        elif self.extraction_method == "model_task":
            if self.model_result_id is None or self.source_record_id is not None:
                raise ValueError("model-task candidates require model_result_id and no source_record_id")
        return self
