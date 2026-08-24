"""Source, acquisition and evidence-locator contracts for Builder PR A.

These records describe where evidence came from and where it can be found. They
do not assert a proposition and do not create a subject identity.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator

from .common import JsonValue, ProducerRef, SchemaRef, Sha256, StrictModel, require_nonblank, utc_datetime


_SECRET_KEY = re.compile(r"(?:token|secret|password|passwd|api[_-]?key|access[_-]?key|authorization|credential|signature|(?:^|_)sig(?:$|_))", re.I)
_SECRET_TEXT = re.compile(r"(?:authorization\s*:|bearer\s+|basic\s+[A-Za-z0-9+/=]+|-----BEGIN .*PRIVATE KEY-----)", re.I)


def _safe_text(value: str, field: str) -> str:
    value = require_nonblank(value, field)
    if _SECRET_TEXT.search(value):
        raise ValueError(f"{field} must not contain credentials or secret material")
    return value


def _safe_locator(value: str, field: str = "locator") -> str:
    value = _safe_text(value, field)
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid locator") from exc
    if parsed.username or parsed.password:
        raise ValueError(f"{field} must not contain URL credentials")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if _SECRET_KEY.search(key):
            raise ValueError(f"{field} must not contain secret-bearing query parameters")
    return value


def _unique_texts(value: tuple[str, ...], field: str) -> tuple[str, ...]:
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain nonblank strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must be unique")
    return value


class PropositionAuthorityRole(StrictModel):
    """Authority is tied to a proposition, not a global source flag."""

    proposition: str
    role: str
    basis: str | None = None

    _proposition = field_validator("proposition")(lambda value: _safe_text(value, "proposition"))
    _role = field_validator("role")(lambda value: _safe_text(value, "role"))
    _basis = field_validator("basis")(
        lambda value: None if value is None else _safe_text(value, "basis")
    )


class SourceDefinition(StrictModel):
    """Versioned governed source-family or endpoint definition."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "source_definition_id", "definition_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: SchemaRef(
            schema_id="urn:charitygraph:builder:schema:source-definition:1.0", schema_version="1.0"
        ),
        validation_alias="schema",
        serialization_alias="schema",
    )
    created_at: datetime
    producer: ProducerRef
    definition_version: str = "1"
    publisher: str
    owner: str | None = None
    jurisdiction: str | None = None
    source_class: str
    authority_roles: tuple[PropositionAuthorityRole | str, ...] = ()
    acquisition_locator: str
    acquisition_method: str = "http"
    expected_cadence: str | None = None
    temporal_semantics: str
    identifier_expectations: tuple[str, ...] = ()
    scope_expectations: tuple[str, ...] = ()
    rights_policy_id: str | None = None
    licence: str | None = None
    reuse_policy: str | None = None
    attribution: str | None = None
    privacy_classification: Literal["public", "personal", "sensitive", "restricted"] = "public"
    access_constraints: tuple[str, ...] = ()
    publication_eligibility: str
    steward: str
    review_due: date | None = None

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        value = require_nonblank(value, "record_id")
        if not value.startswith("srcdef:"):
            raise ValueError("source definition IDs must use srcdef: prefix")
        return value

    _created = field_validator("created_at")(utc_datetime)

    @field_validator("definition_version", "publisher", "source_class", "temporal_semantics", "publication_eligibility", "steward")
    @classmethod
    def _required(cls, value: str, info: Any) -> str:
        return _safe_text(value, info.field_name)

    @field_validator("owner", "jurisdiction", "expected_cadence", "rights_policy_id", "licence", "reuse_policy", "attribution")
    @classmethod
    def _optional(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _safe_text(value, info.field_name)

    _locator = field_validator("acquisition_locator")(_safe_locator)

    @field_validator("identifier_expectations", "scope_expectations", "access_constraints")
    @classmethod
    def _lists(cls, value: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _unique_texts(value, info.field_name)

    @field_validator("authority_roles", mode="before")
    @classmethod
    def _roles(cls, value: Any) -> tuple[PropositionAuthorityRole | str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        return tuple(
            PropositionAuthorityRole(proposition="unspecified", role=item) if isinstance(item, str) else item
            for item in value
        )

    @model_validator(mode="after")
    def _authority_and_scope(self) -> "SourceDefinition":
        if not self.authority_roles:
            raise ValueError("source definitions require at least one proposition-specific authority role")
        if self.source_class.strip().lower() == "subject":
            raise ValueError("a source definition represents a source family or endpoint, not a subject")
        return self

    @property
    def source_definition_id(self) -> str:
        return self.record_id


class AcquisitionReceipt(StrictModel):
    """One retrieval attempt, including explicit absence and failure states."""

    record_id: str = Field(
        validation_alias=AliasChoices("record_id", "acquisition_id", "receipt_id"),
        serialization_alias="record_id",
    )
    schema_ref: SchemaRef = Field(
        default_factory=lambda: SchemaRef(
            schema_id="urn:charitygraph:builder:schema:acquisition-receipt:1.0", schema_version="1.0"
        ),
        validation_alias="schema",
        serialization_alias="schema",
    )
    created_at: datetime
    producer: ProducerRef
    source_definition_id: str
    requested_locator: str = Field(validation_alias=AliasChoices("requested_locator", "requested_url"))
    resolved_locator: str | None = None
    retrieved_at: datetime | None = None
    effective_at: date | datetime | None = Field(default=None, validation_alias=AliasChoices("effective_at", "effective_date"))
    outcome: Literal["available", "not_modified", "absent", "blocked", "failed", "partial", "unavailable"]
    response_status: int | None = None
    media_type: str | None = None
    content_hash: Sha256 | None = None
    byte_size: int | None = None
    artifact_id: str | None = Field(default=None, validation_alias=AliasChoices("artifact_id", "artefact_id"))
    tool_id: str | None = None
    tool_version: str | None = None
    material_parameters: dict[str, JsonValue] = Field(default_factory=dict, validation_alias=AliasChoices("material_parameters", "parameters"))
    retry_of: str | None = None
    replaces_receipt_id: str | None = None
    error_class: str | None = None

    @field_validator("record_id")
    @classmethod
    def _record(cls, value: str) -> str:
        value = require_nonblank(value, "record_id")
        if not value.startswith("acq:"):
            raise ValueError("acquisition receipt IDs must use acq: prefix")
        return value

    _created = field_validator("created_at")(utc_datetime)
    _retrieved = field_validator("retrieved_at")(
        lambda value: None if value is None else utc_datetime(value)
    )

    @field_validator("source_definition_id", "tool_id", "tool_version", "retry_of", "replaces_receipt_id", "error_class")
    @classmethod
    def _text_optional(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _safe_text(value, info.field_name)

    _requested = field_validator("requested_locator")(_safe_locator)
    _resolved = field_validator("resolved_locator")(
        lambda value: None if value is None else _safe_locator(value, "resolved_locator")
    )

    @field_validator("media_type")
    @classmethod
    def _media(cls, value: str | None) -> str | None:
        return None if value is None else _safe_text(value, "media_type")

    @field_validator("byte_size")
    @classmethod
    def _size(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("byte_size must be non-negative")
        return value

    @field_validator("material_parameters")
    @classmethod
    def _parameters(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)) or (isinstance(item, str) and _SECRET_TEXT.search(item)):
                raise ValueError("material_parameters must not contain credentials or secrets")
        return value

    @model_validator(mode="after")
    def _outcome_fields(self) -> "AcquisitionReceipt":
        successful = self.outcome in {"available", "partial"}
        if successful and (self.content_hash is None or self.artifact_id is None or self.byte_size is None):
            raise ValueError("available/partial acquisitions require content hash, artefact and byte size")
        if self.content_hash is not None and self.byte_size is None:
            raise ValueError("content-bearing acquisitions require byte_size")
        if self.byte_size is not None and self.byte_size == 0 and self.outcome == "available":
            raise ValueError("available acquisition cannot have zero bytes")
        return self

    @property
    def acquisition_id(self) -> str:
        return self.record_id


class EvidenceLocator(StrictModel):
    """Extensible locator with no copied source body."""

    kind: Literal["structured_field", "text_span", "document"]
    artifact_id: str | None = Field(default=None, validation_alias=AliasChoices("artifact_id", "artefact_id"))
    source_record_id: str | None = None
    field_path: str | None = None
    start: int | None = None
    end: int | None = None
    page: int | None = None
    locator: str | None = None
    section: str | None = None

    @field_validator("artifact_id", "source_record_id", "field_path", "locator", "section")
    @classmethod
    def _optional_text(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _safe_text(value, info.field_name)

    @model_validator(mode="after")
    def _shape(self) -> "EvidenceLocator":
        if not self.artifact_id and not self.source_record_id:
            raise ValueError("evidence locators require an artefact or source record reference")
        if self.kind == "structured_field" and not self.field_path:
            raise ValueError("structured_field locators require field_path")
        if self.kind == "text_span":
            if self.start is None or self.end is None or self.start < 0 or self.end < self.start:
                raise ValueError("text_span locators require a valid non-negative start/end")
        if self.kind == "document" and not (self.locator or self.section or self.page is not None):
            raise ValueError("document locators require a document locator, section or page")
        if self.page is not None and self.page < 1:
            raise ValueError("page must be positive")
        return self


class StructuredFieldLocator(EvidenceLocator):
    kind: Literal["structured_field"] = "structured_field"
    field_path: str


class TextSpanLocator(EvidenceLocator):
    kind: Literal["text_span"] = "text_span"
    start: int
    end: int


class DocumentLocator(EvidenceLocator):
    kind: Literal["document"] = "document"
