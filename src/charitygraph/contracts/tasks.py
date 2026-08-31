"""Logical model-task, result, embedding and physical-run contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from .canonical import canonical_sha256
from .common import (
    ArtifactRecord, CanonicalObject, CanonicalValue, SchemaRef, Sha256, StrictModel, VersionedPolicy,
    VersionedTool, utc_datetime, require_nonblank,
)
from .ids import deterministic_id, validate_typed_id


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


def _prefix(value: str, prefix: str, field_name: str) -> str:
    try:
        return validate_typed_id(value, prefix)  # type: ignore[arg-type]
    except ValueError as exc:
        raise ValueError(f"{field_name} must use {prefix} typed ID") from exc


ModelTaskType = Literal[
    "page_text_recovery", "relevance_screening", "structured_extraction",
    "semantic_interpretation", "taxonomy_mapping", "adjudication",
    "editorial_synthesis", "embedding", "direct_service_semantics",
]
PaidOutputCategory = Literal[
    "text_recovery", "vision_recovery", "relevance", "extraction", "semantic_judgement",
    "taxonomy", "adjudication", "writing", "embedding", "repair", "retry", "tool",
]


class EvidenceInput(StrictModel):
    evidence_id: str
    content_hash: Sha256
    selection_hash: Sha256

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id(cls, value: str) -> str:
        return require_nonblank(value, "evidence_id")


def model_task_cache_key(
    *,
    task_type: ModelTaskType,
    task_schema: SchemaRef,
    output_schema: SchemaRef,
    evidence_inputs: tuple[EvidenceInput, ...],
    prompt_template_id: str,
    prompt_template_version: str,
    policy_refs: tuple[VersionedPolicy, ...],
    provider_id: str,
    model_snapshot: str,
    parameters: CanonicalObject,
    material_tool_versions: tuple[VersionedTool, ...],
) -> str:
    """Calculate the exact material cache identity from the approved policy."""

    return canonical_sha256({
        "task_type": task_type,
        "task_schema": task_schema,
        "ordered_evidence": [
            {"content_hash": item.content_hash, "selection_hash": item.selection_hash}
            for item in evidence_inputs
        ],
        "prompt_template_id": prompt_template_id,
        "prompt_template_version": prompt_template_version,
        "policy_refs": sorted((item.policy_id, item.version) for item in policy_refs),
        "provider_id": provider_id,
        "model_snapshot": model_snapshot,
        "parameters": parameters,
        "material_tool_versions": sorted((item.tool_id, item.version) for item in material_tool_versions),
        "output_schema": output_schema,
    })


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class ModelTask(ArtifactRecord, Generic[PayloadT]):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("model-task"), validation_alias="schema", serialization_alias="schema")
    subject_id: str
    scope_id: str | None = None
    cohort_id: str | None = None
    task_type: ModelTaskType
    task_schema: SchemaRef
    output_schema: SchemaRef
    evidence_inputs: tuple[EvidenceInput, ...]
    prompt_template_id: str
    prompt_template_version: str
    policy_refs: tuple[VersionedPolicy, ...] = ()
    provider_id: str
    model_snapshot: str
    parameters: CanonicalObject = Field(default_factory=dict)
    material_tool_versions: tuple[VersionedTool, ...] = ()
    cache_key: Sha256 | None = None
    paid_output_categories: tuple[PaidOutputCategory, ...]

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "modeltask:", "record_id")

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value, "scope_id")

    @field_validator("cohort_id")
    @classmethod
    def _cohort(cls, value: str | None) -> str | None:
        return None if value is None else _prefix(value, "cohort:", "cohort_id")

    @field_validator("prompt_template_id", "prompt_template_version", "provider_id", "model_snapshot")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence_inputs")
    @classmethod
    def _evidence(cls, value: tuple[EvidenceInput, ...]) -> tuple[EvidenceInput, ...]:
        if not value:
            raise ValueError("ModelTask requires at least one evidence input")
        return value

    @field_validator("paid_output_categories")
    @classmethod
    def _paid_categories(cls, value: tuple[PaidOutputCategory, ...]) -> tuple[PaidOutputCategory, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("every ModelTask requires one or more unique paid-output categories")
        return value

    @model_validator(mode="after")
    def _cache_and_identity(self) -> "ModelTask[PayloadT]":
        if len({(item.policy_id, item.version) for item in self.policy_refs}) != len(self.policy_refs):
            raise ValueError("policy references must be unique")
        if len({(item.tool_id, item.version) for item in self.material_tool_versions}) != len(self.material_tool_versions):
            raise ValueError("tool references must be unique")
        expected_cache = model_task_cache_key(
            task_type=self.task_type, task_schema=self.task_schema, output_schema=self.output_schema,
            evidence_inputs=self.evidence_inputs, prompt_template_id=self.prompt_template_id,
            prompt_template_version=self.prompt_template_version, policy_refs=self.policy_refs,
            provider_id=self.provider_id, model_snapshot=self.model_snapshot, parameters=self.parameters,
            material_tool_versions=self.material_tool_versions,
        )
        if self.cache_key is not None and self.cache_key != expected_cache:
            raise ValueError("cache_key does not match material task identity")
        object.__setattr__(self, "cache_key", expected_cache)
        expected_record = deterministic_id(
            "modeltask:",
            {"subject_id": self.subject_id, "scope_id": self.scope_id, "task_type": self.task_type,
             "cache_key": expected_cache, "output_schema": self.output_schema},
        )
        if self.record_id != expected_record:
            raise ValueError("ModelTask record_id does not match task identity")
        return self


class NamedUsage(StrictModel):
    name: str
    units: int

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return require_nonblank(value, "name")

    @field_validator("units")
    @classmethod
    def _units(cls, value: int) -> int:
        if value < 0:
            raise ValueError("usage units cannot be negative")
        return value


class ProviderUsage(StrictModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    embedding_input_tokens: int = 0
    image_units: int = 0
    tool_calls: int = 0
    other_billable_units: tuple[NamedUsage, ...] = ()

    @model_validator(mode="after")
    def _nonnegative_and_subset(self) -> "ProviderUsage":
        if any(value < 0 for value in (
            self.input_tokens, self.cached_input_tokens, self.output_tokens,
            self.embedding_input_tokens, self.image_units, self.tool_calls,
        )):
            raise ValueError("provider usage counts cannot be negative")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        if len({item.name for item in self.other_billable_units}) != len(self.other_billable_units):
            raise ValueError("other billable usage names must be unique")
        return self


class ModelResult(ArtifactRecord, Generic[PayloadT]):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("model-result"), validation_alias="schema", serialization_alias="schema")
    model_task_id: str
    task_run_id: str
    output_schema: SchemaRef
    output: PayloadT
    output_hash: Sha256 | None = None
    validation_status: Literal["valid", "invalid", "held"]
    validation_errors: tuple[str, ...] = ()
    raw_response_ref: str
    completed_at: datetime
    provider_id: str
    model_snapshot: str

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "modelresult:", "record_id")

    @field_validator("model_task_id", "task_run_id")
    @classmethod
    def _task_ids(cls, value: str, info) -> str:
        prefix = "modeltask:" if info.field_name == "model_task_id" else "taskrun:"
        return _prefix(value, prefix, info.field_name)

    @field_validator("raw_response_ref", "provider_id", "model_snapshot")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    _completed_at = field_validator("completed_at")(utc_datetime)

    @model_validator(mode="after")
    def _validation(self) -> "ModelResult[PayloadT]":
        expected_hash = canonical_sha256(self.output)
        if self.output_hash is not None and self.output_hash != expected_hash:
            raise ValueError("output_hash does not match output")
        object.__setattr__(self, "output_hash", expected_hash)
        if self.validation_status == "invalid" and not self.validation_errors:
            raise ValueError("invalid model results require validation errors")
        if self.validation_status == "valid" and self.validation_errors:
            raise ValueError("valid model results cannot carry validation errors")
        return self


class EmbeddingResult(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("embedding-result"), validation_alias="schema", serialization_alias="schema")
    model_task_id: str
    task_run_id: str
    source_text_artifact_id: str
    source_text_hash: Sha256
    embedding_model_snapshot: str
    dimensions: int
    vector_ref: str
    vector_hash: Sha256
    validation_status: Literal["valid", "invalid", "held"]
    validation_errors: tuple[str, ...] = ()
    completed_at: datetime

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "embedding:", "record_id")

    @field_validator("model_task_id", "task_run_id")
    @classmethod
    def _task_ids(cls, value: str, info) -> str:
        prefix = "modeltask:" if info.field_name == "model_task_id" else "taskrun:"
        return _prefix(value, prefix, info.field_name)

    @field_validator("source_text_artifact_id", "embedding_model_snapshot", "vector_ref")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("dimensions")
    @classmethod
    def _dimensions(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("embedding dimensions must be positive")
        return value

    _completed_at = field_validator("completed_at")(utc_datetime)

    @model_validator(mode="after")
    def _validation(self) -> "EmbeddingResult":
        if self.validation_status == "invalid" and not self.validation_errors:
            raise ValueError("invalid embeddings require validation errors")
        if self.validation_status == "valid" and self.validation_errors:
            raise ValueError("valid embeddings cannot carry validation errors")
        return self


class TaskRun(ArtifactRecord):
    record_id: str
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("task-run"), validation_alias="schema", serialization_alias="schema")
    model_task_ids: tuple[str, ...]
    subject_id: str
    provider_id: str
    model_snapshot: str
    provider_request_id: str | None = None
    provider_batch_id: str | None = None
    attempt_number: int = 1
    status: Literal["planned", "submitted", "running", "succeeded", "failed", "cancelled", "held"] = "planned"
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    usage: ProviderUsage | None = None
    pricing_snapshot_id: str | None = None
    fx_snapshot_id: str | None = None
    cost_reservation_id: str | None = None
    raw_response_ref: str | None = None
    error_class: str | None = None
    error_message_redacted: str | None = None
    retryable: bool | None = None

    @field_validator("record_id")
    @classmethod
    def _record_prefix(cls, value: str) -> str:
        return _prefix(value, "taskrun:", "record_id")

    @field_validator("model_task_ids")
    @classmethod
    def _task_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("TaskRun requires unique model task IDs")
        for item in value:
            _prefix(item, "modeltask:", "model_task_id")
        return value

    @field_validator("subject_id")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _prefix(value, "subject:", "subject_id")

    @field_validator("provider_id", "model_snapshot")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("attempt_number")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if value < 1:
            raise ValueError("attempt_number starts at one")
        return value

    @field_validator("submitted_at", "started_at", "completed_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_datetime(value)

    @model_validator(mode="after")
    def _status(self) -> "TaskRun":
        if self.completed_at is not None and self.status not in {"succeeded", "failed", "cancelled", "held"}:
            raise ValueError("non-terminal task runs cannot have completed_at")
        if self.status == "succeeded" and (self.usage is None or self.pricing_snapshot_id is None):
            raise ValueError("successful paid TaskRuns require usage and pricing references")
        if self.pricing_snapshot_id is not None:
            _prefix(self.pricing_snapshot_id, "pricing:", "pricing_snapshot_id")
        if self.fx_snapshot_id is not None:
            _prefix(self.fx_snapshot_id, "fx:", "fx_snapshot_id")
        if self.cost_reservation_id is not None:
            _prefix(self.cost_reservation_id, "reservation:", "cost_reservation_id")
        if self.raw_response_ref is not None:
            require_nonblank(self.raw_response_ref, "raw_response_ref")
        return self


ModelTask.model_rebuild(_types_namespace={"CanonicalObject": CanonicalObject, "CanonicalValue": CanonicalValue})

def validate_task_run_tasks(task_run: TaskRun, tasks: tuple[ModelTask[BaseModel], ...]) -> None:
    by_id = {task.record_id: task for task in tasks}
    if set(by_id) != set(task_run.model_task_ids):
        raise ValueError("TaskRun task references are incomplete or contain extras")
    if any(task.subject_id != task_run.subject_id for task in by_id.values()):
        raise ValueError("a physical TaskRun cannot contain tasks from multiple subjects")
    if any(task.provider_id != task_run.provider_id or task.model_snapshot != task_run.model_snapshot for task in by_id.values()):
        raise ValueError("TaskRun provider/model does not match its logical tasks")
