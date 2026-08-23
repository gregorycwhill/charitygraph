"""Strict primitives shared by the isolated Builder vNext contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.types import StringConstraints
from typing_extensions import Annotated, TypeAliasType


JsonValue = TypeAliasType("JsonValue", None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"])
CanonicalScalar: TypeAlias = None | bool | int | str | Decimal | date | datetime | Enum
CanonicalValue = TypeAliasType("CanonicalValue", CanonicalScalar | tuple["CanonicalValue", ...] | list["CanonicalValue"] | dict[str, "CanonicalValue"])
CanonicalObject: TypeAlias = dict[str, CanonicalValue]

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

IdPrefix: TypeAlias = Literal[
    "subject:", "subjectrecord:", "srcrec:", "evidence:", "candidate:",
    "decision:", "observation:", "derivative:", "modeltask:", "modelresult:",
    "embedding:", "taskrun:", "cohort:", "pricing:", "fx:", "reservation:",
    "costledger:", "run:",
]

LineageType = Literal[
    "acquired_as", "parsed_from", "bound_to", "excerpted_from", "proposed_from",
    "reviewed_by", "promoted_as", "derived_from", "supersedes", "invalidates",
    "projected_as", "included_in_release",
]


def require_nonblank(value: str, field_name: str = "value") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


def utc_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


class StrictModel(BaseModel):
    """Base configuration shared by every persisted PR2 model."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True, populate_by_name=True, serialize_by_alias=True)


class VersionedPolicy(StrictModel):
    policy_id: str
    version: str

    _policy_id = field_validator("policy_id")(lambda value: require_nonblank(value, "policy_id"))
    _version = field_validator("version")(lambda value: require_nonblank(value, "version"))


class VersionedTool(StrictModel):
    tool_id: str
    version: str

    _tool_id = field_validator("tool_id")(lambda value: require_nonblank(value, "tool_id"))
    _version = field_validator("version")(lambda value: require_nonblank(value, "version"))


class SchemaRef(StrictModel):
    schema_id: str
    schema_version: str

    @field_validator("schema_id", "schema_version")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("schema_id")
    @classmethod
    def _private_schema_id(cls, value: str) -> str:
        if not value.startswith("urn:charitygraph:builder:schema:"):
            raise ValueError("private Builder schemas must use the CharityGraph URN")
        return value


class ProducerRef(StrictModel):
    kind: Literal["code", "human", "automation_policy", "model"]
    producer_id: str
    version: str | None = None

    _producer_id = field_validator("producer_id")(lambda value: require_nonblank(value, "producer_id"))
    _version = field_validator("version")(
        lambda value: None if value is None else require_nonblank(value, "version")
    )


class ArtifactRef(StrictModel):
    artifact_id: str
    content_hash: Sha256
    schema_ref: SchemaRef = Field(validation_alias="schema", serialization_alias="schema")

    _artifact_id = field_validator("artifact_id")(lambda value: require_nonblank(value, "artifact_id"))


class LineageEdge(StrictModel):
    edge_type: LineageType
    source_artifact_id: str
    target_artifact_id: str

    @field_validator("source_artifact_id", "target_artifact_id")
    @classmethod
    def _artifact_ids(cls, value: str) -> str:
        return require_nonblank(value, "artifact_id")


class ArtifactRecord(StrictModel):
    """Common immutable envelope; domain payloads remain typed subclasses."""

    record_id: str
    schema_ref: SchemaRef = Field(validation_alias="schema", serialization_alias="schema")
    created_at: datetime
    producer: ProducerRef
    about_subject_ids: tuple[str, ...] = ()
    lineage: tuple[LineageEdge, ...] = ()
    content_hash: Sha256 | None = None

    _record_id = field_validator("record_id")(lambda value: require_nonblank(value, "record_id"))
    _created_at = field_validator("created_at")(utc_datetime)

    @field_validator("about_subject_ids")
    @classmethod
    def _subjects_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("about_subject_ids must contain nonblank identifiers")
        if len(set(value)) != len(value):
            raise ValueError("about_subject_ids must be unique")
        return value

    @model_validator(mode="after")
    def _lineage_touches_record(self) -> "ArtifactRecord":
        if any(
            self.record_id not in {edge.source_artifact_id, edge.target_artifact_id}
            for edge in self.lineage
        ):
            raise ValueError("every lineage edge must involve this record")
        return self
