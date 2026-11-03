"""Minimum typed knowledge contracts and promotion boundaries."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from .canonical import canonical_sha256
from .common import (
    ArtifactRecord, ArtifactRef, CanonicalValue, LineageEdge, ProducerRef, SchemaRef, Sha256,
    StrictModel, utc_datetime, require_nonblank,
)
from .ids import deterministic_id, validate_typed_id


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


def _prefix(value: str, prefix: str, field_name: str) -> str:
    try:
        return validate_typed_id(value, prefix)  # type: ignore[arg-type]
    except ValueError as exc:
        raise ValueError(f"{field_name} must use {prefix} typed ID") from exc


class ExternalIdentifier(StrictModel):
    scheme: str
    value: str
    issuing_authority: str | None = None
    source_record_ids: tuple[str, ...] = ()
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("scheme", "value")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("source_record_ids")
    @classmethod
    def _source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(not item.strip() for item in value):
            raise ValueError("source_record_ids must be unique nonblank IDs")
        return value

    @model_validator(mode="after")
    def _date_order(self) -> "ExternalIdentifier":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        return self


class SubjectRecord(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("subject-record"), validation_alias="schema", serialization_alias="schema")
    subject_id: str
    subject_kind: Literal[
        "unknown", "organisation", "organisation_group", "legal_entity", "fund",
        "organisational_unit", "program", "service", "other",
    ]
    lifecycle_status: Literal["active", "inactive", "merged", "split", "succeeded", "tombstoned"]
    display_name: str | None = None
    external_identifiers: tuple[ExternalIdentifier, ...] = ()
    identity_authority_refs: tuple[ArtifactRef, ...] = ()
    identity_policy_id: str
    predecessor_subject_ids: tuple[str, ...] = ()
    successor_subject_ids: tuple[str, ...] = ()
    lifecycle_reason: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "subjectrecord:", "record_id")

    @field_validator("subject_id")
    @classmethod
    def _subject_prefix(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("identity_policy_id")
    @classmethod
    def _policy(cls, value: str) -> str:
        return require_nonblank(value, "identity_policy_id")

    @model_validator(mode="after")
    def _identity_and_lifecycle(self) -> "SubjectRecord":
        if self.lifecycle_status == "active" and not self.identity_authority_refs:
            raise ValueError("active subjects require identity-authority references")
        if self.subject_id in self.predecessor_subject_ids or self.subject_id in self.successor_subject_ids:
            raise ValueError("a subject cannot list itself as predecessor or successor")
        if len(set(self.predecessor_subject_ids)) != len(self.predecessor_subject_ids):
            raise ValueError("predecessor_subject_ids must be unique")
        if len(set(self.successor_subject_ids)) != len(self.successor_subject_ids):
            raise ValueError("successor_subject_ids must be unique")
        if self.lifecycle_status in {"merged", "split"} and not self.successor_subject_ids:
            raise ValueError("merged/split subjects require a successor")
        if self.lifecycle_status == "succeeded" and not self.predecessor_subject_ids:
            raise ValueError("succeeded subjects require a predecessor")
        if self.lifecycle_status == "tombstoned" and not self.lifecycle_reason:
            raise ValueError("tombstoned subjects require a lifecycle reason")
        pairs = [(item.scheme, item.value) for item in self.external_identifiers]
        if len(set(pairs)) != len(pairs):
            raise ValueError("external identifier scheme/value pairs must be unique")
        return self


class SourceRecord(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("source-record"), validation_alias="schema", serialization_alias="schema")
    source_family: str
    source_role: str
    source_version: str | None = None
    source_locator: str
    retrieved_at: datetime | None = None
    observed_at: datetime | date
    media_type: str | None = None
    payload_ref: str
    payload_hash: Sha256
    rights_policy_id: str | None = None
    attribution: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "srcrec:", "record_id")

    @field_validator("source_family", "source_role", "source_locator", "payload_ref", "payload_hash")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("retrieved_at")
    @classmethod
    def _retrieved(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_datetime(value)

    @model_validator(mode="after")
    def _identity(self) -> "SourceRecord":
        expected = deterministic_id(
            "srcrec:",
            {"source_family": self.source_family, "source_version": self.source_version,
             "source_locator": self.source_locator, "payload_hash": self.payload_hash},
        )
        if self.record_id != expected:
            raise ValueError("SourceRecord record_id does not match its deterministic identity")
        return self


class EvidenceFragment(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("evidence-fragment"), validation_alias="schema", serialization_alias="schema")
    source_record: ArtifactRef
    fragment_kind: Literal["text", "table_cell", "table_region", "visual_region", "structured_field"]
    locator: str
    content_ref: str
    fragment_hash: Sha256
    selection_method: str
    selection_policy_version: str
    observed_at: datetime | date

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "evidence:", "record_id")

    @field_validator("locator", "content_ref", "fragment_hash", "selection_method", "selection_policy_version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _identity(self) -> "EvidenceFragment":
        expected = deterministic_id(
            "evidence:",
            {"source_record_id": self.source_record.artifact_id, "locator": self.locator,
             "fragment_hash": self.fragment_hash, "selection_method": self.selection_method,
             "selection_policy_version": self.selection_policy_version},
        )
        if self.record_id != expected:
            raise ValueError("EvidenceFragment record_id does not match its deterministic identity")
        return self


class ObservationTime(StrictModel):
    effective_from: date | datetime | None = None
    effective_to: date | datetime | None = None
    reporting_period: str | None = None
    observed_at: date | datetime
    assessed_at: datetime | None = None

    @field_validator("assessed_at")
    @classmethod
    def _assessed(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_datetime(value)

    @model_validator(mode="after")
    def _temporal_order(self) -> "ObservationTime":
        if self.effective_from is not None and self.effective_to is not None:
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to cannot precede effective_from")
        return self


OutcomeState = Literal[
    "resolved", "supported", "contradicted", "unknown", "insufficient_evidence",
    "not_applicable", "not_attempted", "withheld", "acquisition_failure",
    "extraction_failure", "model_failure",
]

# Structured activity/ecosystem roles.  These are intentionally narrower than
# the legacy relationship_type vocabulary so unsupported values cannot be
# silently promoted into an operator/delivery/funding meaning.
RelationshipRole = Literal[
    "operator", "deliverer", "funder", "sponsor", "partner", "auspice",
    "network_context",
]

LifecycleState = Literal[
    "candidate", "accepted", "edited", "rejected", "superseded",
    "contradicted", "withdrawn", "held", "unresolved",
]


def _unique_ids(value: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field_name} must contain nonblank IDs")
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} must be unique")
    return value


class ScopeRecord(ArtifactRecord):
    """A bounded subject context; scope is not a free-text propagation hint."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "scope_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("scope-record"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    subject_id: str
    scope_kind: Literal[
        "organisation", "program", "service", "project", "campaign",
        "site", "geographic", "reporting_group", "other",
    ]
    label: str | None = None
    parent_scope_id: str | None = None
    valid_from: date | datetime | None = None
    valid_to: date | datetime | None = None
    lifecycle_status: Literal["active", "inactive", "superseded", "withdrawn"] = "active"

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "scope:", "scope_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("parent_scope_id")
    @classmethod
    def _parent(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "scope:", "parent_scope_id")

    @field_validator("label")
    @classmethod
    def _label(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value, "label")

    @model_validator(mode="after")
    def _range(self) -> "ScopeRecord":
        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        if self.parent_scope_id == self.record_id:
            raise ValueError("a scope cannot be its own parent")
        return self

    @property
    def scope_id(self) -> str:
        return self.record_id


class PartyRole(ArtifactRecord):
    """A contextual role held by a party without creating a second identity model."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "party_role_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("party-role"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    party_id: str
    role: str
    context_record_id: str | None = None
    scope_id: str | None = None
    valid_from: date | datetime | None = None
    valid_to: date | datetime | None = None
    status: Literal["active", "inactive", "withdrawn"] = "active"

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "partyrole:", "party_role_id")

    @field_validator("party_id", "role")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "scope:", "scope_id")

    @model_validator(mode="after")
    def _range(self) -> "PartyRole":
        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        return self


class Observation(ArtifactRecord):
    """Append-only report of what a source, process, observer or model encountered."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "observation_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("observation"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    subject_id: str
    scope_id: str | None = None
    predicate: str
    value: CanonicalValue | None = None
    outcome_state: OutcomeState = "resolved"
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    observation_time: ObservationTime
    method: str
    lifecycle_status: LifecycleState = "candidate"
    confidence: str | None = None
    qualifications: tuple[str, ...] = ()
    supersedes_observation_id: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "observation:", "observation_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "scope:", "scope_id")

    @field_validator("predicate", "method")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    _evidence = field_validator("evidence_locator_ids")(
        lambda value: _unique_ids(value, "evidence_locator_ids")
    )
    _sources = field_validator("source_record_ids")(
        lambda value: _unique_ids(value, "source_record_ids")
    )

    @field_validator("supersedes_observation_id")
    @classmethod
    def _supersedes(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "observation:", "supersedes_observation_id")

    @model_validator(mode="after")
    def _lifecycle(self) -> "Observation":
        supersedes_edges = [edge for edge in self.lineage if edge.edge_type == "supersedes"]
        if self.supersedes_observation_id is None and supersedes_edges:
            raise ValueError("supersedes edges require supersedes_observation_id")
        if self.supersedes_observation_id is not None:
            if self.supersedes_observation_id == self.record_id:
                raise ValueError("an observation cannot supersede itself")
            if len(supersedes_edges) != 1:
                raise ValueError("a replacement observation requires exactly one supersedes edge")
            edge = supersedes_edges[0]
            if edge.source_artifact_id != self.record_id or edge.target_artifact_id != self.supersedes_observation_id:
                raise ValueError("supersedes edge must run from the new observation to supersedes_observation_id")
            if self.lifecycle_status == "superseded":
                raise ValueError("a superseding observation must remain accepted or edited")
        return self


class Assertion(ArtifactRecord):
    """A governed proposition whose history remains reconstructible."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "assertion_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("assertion"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    subject_id: str
    scope_id: str | None = None
    predicate: str
    value: CanonicalValue | None = None
    outcome_state: OutcomeState = "resolved"
    observation_ids: tuple[str, ...] = ()
    evidence_locator_ids: tuple[str, ...] = ()
    assertion_time: ObservationTime
    method: str
    lifecycle_status: LifecycleState = "accepted"
    confidence: str | None = None
    publication_eligibility: Literal["eligible", "ineligible", "review_required", "withheld"] = "review_required"
    supersedes_assertion_id: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "assertion:", "assertion_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "scope:", "scope_id")

    @field_validator("predicate", "method")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    _observations = field_validator("observation_ids")(
        lambda value: _unique_ids(value, "observation_ids")
    )
    _evidence = field_validator("evidence_locator_ids")(
        lambda value: _unique_ids(value, "evidence_locator_ids")
    )

    @field_validator("supersedes_assertion_id")
    @classmethod
    def _supersedes(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "assertion:", "supersedes_assertion_id")

    @model_validator(mode="after")
    def _lifecycle(self) -> "Assertion":
        if self.lifecycle_status == "superseded" and self.supersedes_assertion_id is None:
            raise ValueError("superseded assertions require supersedes_assertion_id")
        if self.supersedes_assertion_id == self.record_id:
            raise ValueError("an assertion cannot supersede itself")
        supersedes_edges = [edge for edge in self.lineage if edge.edge_type == "supersedes"]
        if self.supersedes_assertion_id is None and supersedes_edges:
            raise ValueError("supersedes edges require supersedes_assertion_id")
        if self.supersedes_assertion_id is not None:
            if len(supersedes_edges) != 1:
                raise ValueError("a replacement assertion requires exactly one supersedes edge")
            edge = supersedes_edges[0]
            if edge.source_artifact_id != self.record_id or edge.target_artifact_id != self.supersedes_assertion_id:
                raise ValueError("supersedes edge must run from the new assertion to supersedes_assertion_id")
            if self.lifecycle_status == "superseded":
                raise ValueError("a superseding assertion must remain accepted or edited")
        return self


class RelationshipStatement(ArtifactRecord):
    """A typed, directed and scoped relationship between subjects."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "relationship_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("relationship-statement"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    source_subject_id: str = Field(validation_alias=AliasChoices("source_subject_id", "source_id"))
    target_subject_id: str = Field(validation_alias=AliasChoices("target_subject_id", "target_id"))
    relationship_type: str
    # Optional structured role for activity/ecosystem relationships.  The
    # legacy relationship_type/source_role/target_role fields remain intact;
    # this field prevents new role-bearing propositions from relying on
    # unrestricted free text while preserving compatibility with older rows.
    role: RelationshipRole | None = Field(
        default=None,
        validation_alias=AliasChoices("role", "relationship_role"),
        serialization_alias="role",
    )
    scope_id: str | None = None
    source_role: str | None = None
    target_role: str | None = None
    evidence_locator_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    valid_from: date | datetime | None = None
    valid_to: date | datetime | None = None
    status: Literal["candidate", "accepted", "rejected", "withdrawn", "superseded"] = "candidate"

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "relationship:", "relationship_id")

    @field_validator("source_subject_id", "target_subject_id")
    @classmethod
    def _subjects(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("relationship_type")
    @classmethod
    def _relationship_type(cls, value: str) -> str:
        return require_nonblank(value, "relationship_type")

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "scope:", "scope_id")

    _evidence = field_validator("evidence_locator_ids")(
        lambda value: _unique_ids(value, "evidence_locator_ids")
    )
    _observations = field_validator("observation_ids")(
        lambda value: _unique_ids(value, "observation_ids")
    )

    @model_validator(mode="after")
    def _range(self) -> "RelationshipStatement":
        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot precede valid_from")
        if self.source_subject_id == self.target_subject_id:
            raise ValueError("relationship endpoints must be distinct")
        return self


class AdjudicationDecision(ArtifactRecord):
    """A governed decision over candidate knowledge, preserving rejected inputs."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "adjudication_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: _schema("adjudication-decision"),
        validation_alias="schema",
        serialization_alias="schema",
    )
    input_record_ids: tuple[str, ...]
    outcome: Literal[
        "accepted", "edited", "rejected", "insufficient", "withheld",
        "identity_blocked", "scope_blocked", "deferred",
    ]
    rationale: str
    reviewer_id: str
    result_record_id: str | None = None
    decision_time: datetime
    review_policy_id: str
    supersedes_decision_id: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "adjudication:", "adjudication_id")

    _inputs = field_validator("input_record_ids")(
        lambda value: _unique_ids(value, "input_record_ids")
    )

    @field_validator("rationale", "reviewer_id", "review_policy_id")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    _decision_time = field_validator("decision_time")(utc_datetime)

    @model_validator(mode="after")
    def _result(self) -> "AdjudicationDecision":
        if self.outcome in {"accepted", "edited"} and self.result_record_id is None:
            raise ValueError("accepted or edited adjudications require result_record_id")
        if self.result_record_id == self.record_id:
            raise ValueError("an adjudication cannot result in itself")
        return self


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class CandidateObservation(ArtifactRecord, Generic[PayloadT]):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("candidate-observation"), validation_alias="schema", serialization_alias="schema")
    subject_id: str | None = None
    identity_state: Literal["resolved", "ambiguous", "unresolved"]
    scope_id: str | None = None
    domain: str
    payload_schema: SchemaRef
    payload: PayloadT
    evidence: tuple[ArtifactRef, ...]
    claim_basis_proposed: str
    extraction_method: str
    observation_time: ObservationTime
    confidence_proposed: str | None = None
    warnings: tuple[str, ...] = ()
    generation_policy_id: str
    review_state: Literal["unreviewed", "review_required", "held"] = "unreviewed"
    candidate_fingerprint: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "candidate:", "record_id")

    @field_validator("domain", "claim_basis_proposed", "extraction_method", "generation_policy_id")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence")
    @classmethod
    def _evidence_required(cls, value: tuple[ArtifactRef, ...]) -> tuple[ArtifactRef, ...]:
        if not value:
            raise ValueError("candidate observations require evidence")
        return value

    @model_validator(mode="after")
    def _identity_and_fingerprint(self) -> "CandidateObservation[PayloadT]":
        if self.identity_state == "resolved" and self.subject_id is None:
            raise ValueError("resolved candidates require subject_id")
        if self.identity_state in {"ambiguous", "unresolved"} and self.subject_id is not None:
            raise ValueError("ambiguous or unresolved candidates cannot carry a governed subject_id")
        fingerprint = canonical_sha256({
            "subject_id": self.subject_id, "scope_id": self.scope_id, "identity_state": self.identity_state,
            "domain": self.domain, "payload_schema": self.payload_schema,
            "payload_hash": canonical_sha256(self.payload),
            "evidence_hashes": [item.content_hash for item in self.evidence],
            "claim_basis": self.claim_basis_proposed, "extraction_method": self.extraction_method,
            "observation_time": self.observation_time, "confidence": self.confidence_proposed,
            "warnings": self.warnings, "generation_policy_id": self.generation_policy_id,
        })
        if self.candidate_fingerprint is not None and self.candidate_fingerprint != fingerprint:
            raise ValueError("candidate_fingerprint does not match candidate content")
        object.__setattr__(self, "candidate_fingerprint", fingerprint)
        return self


class HumanAuthority(StrictModel):
    kind: Literal["human"] = "human"
    actor_id: str
    role: str
    authority_policy_id: str

    @field_validator("actor_id", "role", "authority_policy_id")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)


class AutomationAuthority(StrictModel):
    kind: Literal["automation_policy"] = "automation_policy"
    policy_id: str
    policy_version: str
    benchmark_artifact_ids: tuple[str, ...]

    @field_validator("policy_id", "policy_version")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("benchmark_artifact_ids")
    @classmethod
    def _benchmarks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value) or any(not item.strip() for item in value):
            raise ValueError("automation authority requires benchmark artefact references")
        return value


DecisionAuthority = Annotated[Union[HumanAuthority, AutomationAuthority], Field(discriminator="kind")]


class DecisionRecord(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("decision-record"), validation_alias="schema", serialization_alias="schema")
    candidate_id: str
    disposition: Literal["accepted", "edited", "rejected", "insufficient", "identity_blocked", "scope_blocked", "held"]
    authority: DecisionAuthority
    rationale: str
    replacement_candidate_id: str | None = None
    supersedes_decision_id: str | None = None
    decided_at: datetime

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "decision:", "record_id")

    @field_validator("candidate_id")
    @classmethod
    def _candidate_id(cls, value: str) -> str:
        return _prefix(value, "candidate:", "candidate_id")

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str) -> str:
        return require_nonblank(value, "rationale")

    _decided_at = field_validator("decided_at")(utc_datetime)

    @model_validator(mode="after")
    def _authority(self) -> "DecisionRecord":
        if self.disposition == "edited" and not self.replacement_candidate_id:
            raise ValueError("edited decisions require replacement_candidate_id")
        if self.disposition != "edited" and self.replacement_candidate_id is not None:
            raise ValueError("only edited decisions may carry a replacement candidate")
        if self.replacement_candidate_id is not None:
            _prefix(self.replacement_candidate_id, "candidate:", "replacement_candidate_id")
        if isinstance(self.authority, HumanAuthority):
            if self.producer.kind != "human":
                raise ValueError("human decisions require a human producer")
        else:
            if self.producer.kind != "automation_policy":
                raise ValueError("automation decisions require an automation-policy producer")
        if self.producer.kind == "model":
            raise ValueError("models cannot create DecisionRecord")
        return self


class CanonicalObservation(ArtifactRecord, Generic[PayloadT]):
    """An immutable promoted proposition; effective state is derived from later edges/events."""

    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("canonical-observation"), validation_alias="schema", serialization_alias="schema")
    subject_id: str
    scope_id: str | None = None
    domain: str
    payload_schema: SchemaRef
    payload: PayloadT
    candidate_id: str
    decision_id: str
    evidence: tuple[ArtifactRef, ...]
    claim_basis: str
    extraction_method: str
    observation_time: ObservationTime
    confidence: str | None = None
    qualifications: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    supersedes_observation_id: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "observation:", "record_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("domain", "claim_basis", "extraction_method")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("candidate_id")
    @classmethod
    def _candidate(cls, value: str) -> str:
        return _prefix(value, "candidate:", "candidate_id")

    @field_validator("decision_id")
    @classmethod
    def _decision(cls, value: str) -> str:
        return _prefix(value, "decision:", "decision_id")

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[ArtifactRef, ...]) -> tuple[ArtifactRef, ...]:
        if not value:
            raise ValueError("canonical observations require evidence")
        return value

    @model_validator(mode="after")
    def _producer_and_append_only_lineage(self) -> "CanonicalObservation[PayloadT]":
        if self.producer.kind == "model":
            raise ValueError("model output cannot directly create a canonical observation")
        supersedes_edges = [edge for edge in self.lineage if edge.edge_type == "supersedes"]
        if self.supersedes_observation_id is None:
            if supersedes_edges:
                raise ValueError("supersedes edges require supersedes_observation_id")
        else:
            _prefix(self.supersedes_observation_id, "observation:", "supersedes_observation_id")
            if len(supersedes_edges) != 1:
                raise ValueError("a replacement observation requires exactly one supersedes edge")
            edge = supersedes_edges[0]
            if edge.source_artifact_id != self.record_id or edge.target_artifact_id != self.supersedes_observation_id:
                raise ValueError("supersedes edge must run from the new observation to supersedes_observation_id")
        return self


class DerivativeArtifact(ArtifactRecord, Generic[PayloadT]):
    """Immutable derivative; later invalidation/supersession events are deferred to the state-event contract."""

    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("derivative-artifact"), validation_alias="schema", serialization_alias="schema")
    derivative_type: Literal["summary", "classification", "embedding", "similarity", "analytic_projection", "other"]
    payload_schema: SchemaRef
    payload: PayloadT
    input_observation_ids: tuple[str, ...]
    generation_policy_id: str
    model_result_ids: tuple[str, ...] = ()
    release_safe: bool = False

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "derivative:", "record_id")

    @field_validator("generation_policy_id")
    @classmethod
    def _policy(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("input_observation_ids")
    @classmethod
    def _inputs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("derivatives require unique canonical input observations")
        for item in value:
            _prefix(item, "observation:", "input_observation_id")
        return value


def _assert_promoted_proposition(candidate: CandidateObservation[PayloadT], observation: CanonicalObservation[PayloadT]) -> None:
    """Require a promoted observation to reproduce the governed candidate proposition exactly."""

    comparisons = (
        ("subject", candidate.subject_id, observation.subject_id),
        ("scope", candidate.scope_id, observation.scope_id),
        ("domain", candidate.domain, observation.domain),
        ("payload schema", candidate.payload_schema, observation.payload_schema),
        ("payload", canonical_sha256(candidate.payload), canonical_sha256(observation.payload)),
        ("evidence", candidate.evidence, observation.evidence),
        ("claim basis", candidate.claim_basis_proposed, observation.claim_basis),
        ("extraction method", candidate.extraction_method, observation.extraction_method),
        ("observation time", candidate.observation_time, observation.observation_time),
        ("confidence", candidate.confidence_proposed, observation.confidence),
        ("warnings", candidate.warnings, observation.warnings),
    )
    for label, candidate_value, observation_value in comparisons:
        if candidate_value != observation_value:
            raise ValueError(f"canonical observation does not reproduce accepted {label}")
    if observation.qualifications:
        raise ValueError("canonical observation cannot introduce qualifications absent from the governed candidate")


def _require_directed_edge(
    edges: tuple[LineageEdge, ...],
    *,
    edge_type: Literal["reviewed_by", "promoted_as"],
    source_id: str,
    target_id: str,
) -> None:
    controlled_edges = [edge for edge in edges if edge.edge_type == edge_type]
    if len(controlled_edges) != 1:
        raise ValueError(f"promotion requires exactly one {edge_type} lineage edge")
    edge = controlled_edges[0]
    if edge.source_artifact_id != source_id or edge.target_artifact_id != target_id:
        raise ValueError(f"promotion requires one directed {edge_type} lineage edge")


def validate_promotion_chain(
    candidate: CandidateObservation[PayloadT],
    decision: DecisionRecord,
    observation: CanonicalObservation[PayloadT],
    replacement_candidate: CandidateObservation[PayloadT] | None = None,
) -> None:
    """Validate an accepted or explicitly edited candidate-to-canonical promotion chain."""

    if decision.candidate_id != candidate.record_id:
        raise ValueError("decision does not reference the original candidate")
    if decision.disposition == "accepted":
        if replacement_candidate is not None:
            raise ValueError("accepted decisions cannot supply a replacement candidate")
        promoted_candidate = candidate
    elif decision.disposition == "edited":
        if replacement_candidate is None:
            raise ValueError("edited decisions require the supplied replacement candidate")
        if decision.replacement_candidate_id != replacement_candidate.record_id:
            raise ValueError("edited decision does not reference the supplied replacement candidate")
        if candidate.subject_id != replacement_candidate.subject_id or candidate.scope_id != replacement_candidate.scope_id:
            raise ValueError("edited replacement candidates must retain the original governed subject and scope")
        promoted_candidate = replacement_candidate
    else:
        raise ValueError("only accepted or edited candidates may become canonical")

    if promoted_candidate.identity_state != "resolved" or promoted_candidate.subject_id != observation.subject_id:
        raise ValueError("promotion requires a resolved candidate with matching subject")
    if observation.candidate_id != promoted_candidate.record_id or observation.decision_id != decision.record_id:
        raise ValueError("canonical observation does not reference the promoted candidate and decision")
    _assert_promoted_proposition(promoted_candidate, observation)
    _require_directed_edge(
        decision.lineage, edge_type="reviewed_by", source_id=candidate.record_id, target_id=decision.record_id,
    )
    _require_directed_edge(
        observation.lineage, edge_type="promoted_as", source_id=promoted_candidate.record_id, target_id=observation.record_id,
    )
