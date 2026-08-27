"""Versioned taxonomy registry and assignment contracts for the private Phase 1 engine."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ArtifactRecord, SchemaRef, require_nonblank
from .ids import validate_typed_id


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


def _id(value: str, prefix: str, field: str) -> str:
    try:
        return validate_typed_id(value, prefix)
    except ValueError as exc:
        raise ValueError(f"{field} must use {prefix} typed ID") from exc


SchemeDisposition = Literal[
    "adopted", "incorporated", "adapted", "mapped", "reference_only",
    "deferred", "rejected", "retired",
]
MappingPredicate = Literal[
    "exact_match", "close_match", "broader_match", "narrower_match",
    "related_match", "no_match",
]
AssignmentMethod = Literal[
    "source-reported", "deterministic", "model-assessed",
    "human-reviewed", "community-proposed",
]


class TaxonomyScheme(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("taxonomy-scheme"), validation_alias="schema", serialization_alias="schema")
    scheme_id: str
    owner: str
    purpose: str
    jurisdiction: str | None = None
    disposition: SchemeDisposition
    licence: str
    reuse_policy: str
    attribution: str
    maintenance_policy: str | None = None
    deprecation_policy: str | None = None
    steward: str
    review_status: str

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _id(value, "scheme:", "record_id")

    @field_validator("scheme_id", "owner", "purpose", "licence", "reuse_policy", "attribution", "steward", "review_status")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("jurisdiction", "maintenance_policy", "deprecation_policy")
    @classmethod
    def _optional(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)


class TaxonomyVersion(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("taxonomy-version"), validation_alias="schema", serialization_alias="schema")
    scheme_id: str
    version: str
    release_date: date
    jurisdiction_scope: str | None = None
    source_locator: str | None = None
    status: Literal["current", "historical", "deprecated", "frozen"] = "current"
    licence: str
    reuse_policy: str
    attribution: str

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _id(value, "schemever:", "record_id")

    @field_validator("scheme_id", "version", "licence", "reuse_policy", "attribution")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("jurisdiction_scope", "source_locator")
    @classmethod
    def _optional(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)


class TaxonomyConcept(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("taxonomy-concept"), validation_alias="schema", serialization_alias="schema")
    scheme_version_id: str
    external_concept_id: str
    preferred_label: str
    definition: str | None = None
    parent_concept_ids: tuple[str, ...] = ()
    active: bool = True
    deprecated: bool = False
    replacement_concept_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _id(value, "concept:", "record_id")

    @field_validator("scheme_version_id")
    @classmethod
    def _version(cls, value: str) -> str:
        return _id(value, "schemever:", "scheme_version_id")

    @field_validator("external_concept_id", "preferred_label")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("definition")
    @classmethod
    def _definition(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("parent_concept_ids", "replacement_concept_ids")
    @classmethod
    def _concept_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("concept references must be unique")
        return tuple(_id(item, "concept:", "concept_id") for item in value)

    @model_validator(mode="after")
    def _deprecation(self) -> "TaxonomyConcept":
        if self.deprecated and not self.replacement_concept_ids and self.active:
            raise ValueError("deprecated active concepts require replacement concepts or inactive state")
        return self


class ConceptMapping(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("concept-mapping"), validation_alias="schema", serialization_alias="schema")
    source_concept_id: str
    target_concept_id: str
    predicate: MappingPredicate
    method: str
    evidence_ids: tuple[str, ...] = ()
    reason: str | None = None
    review_state: Literal["unreviewed", "review_required", "accepted", "rejected", "held"] = "review_required"

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _id(value, "mapping:", "record_id")

    @field_validator("source_concept_id", "target_concept_id")
    @classmethod
    def _concept(cls, value: str) -> str:
        return _id(value, "concept:", "concept_id")

    @field_validator("method")
    @classmethod
    def _method(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence_ids")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("mapping evidence references must be unique")
        return tuple(require_nonblank(item, "evidence_id") for item in value)

    @model_validator(mode="after")
    def _distinct(self) -> "ConceptMapping":
        if self.source_concept_id == self.target_concept_id:
            raise ValueError("a concept cannot map to itself")
        return self


class TaxonomyAssignment(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("taxonomy-assignment"), validation_alias="schema", serialization_alias="schema")
    subject_id: str
    scope_id: str | None = None
    scheme_version_id: str
    concept_id: str
    role: Literal["primary", "secondary"]
    assignment_method: AssignmentMethod
    evidence_ids: tuple[str, ...] = ()
    rationale: str | None = None
    confidence: str | None = None
    outcome_state: Literal["resolved", "supported", "unknown", "insufficient_evidence", "withheld"] = "resolved"
    lifecycle_status: Literal["candidate", "accepted", "edited", "rejected", "held"] = "candidate"
    publication_eligibility: Literal["eligible", "ineligible", "review_required", "withheld"] = "withheld"
    publication_policy_id: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        return _id(value, "assignment:", "record_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _id(value, "subject:", "subject_id")

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else _id(value, "scope:", "scope_id")

    @field_validator("scheme_version_id")
    @classmethod
    def _version(cls, value: str) -> str:
        return _id(value, "schemever:", "scheme_version_id")

    @field_validator("concept_id")
    @classmethod
    def _concept(cls, value: str) -> str:
        return _id(value, "concept:", "concept_id")

    @field_validator("evidence_ids")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("assignment evidence references must be unique")
        return tuple(require_nonblank(item, "evidence_id") for item in value)

    @field_validator("rationale", "confidence")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _evidence_for_resolution(self) -> "TaxonomyAssignment":
        if self.outcome_state in {"resolved", "supported"} and not self.evidence_ids:
            raise ValueError("resolved taxonomy assignments require evidence")
        return self
