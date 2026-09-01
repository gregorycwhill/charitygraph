"""Bounded Section 16 conduct/compliance provider and domain contracts.

The wire models are transport-only.  They deliberately contain no Builder
schema identity, task identity, authority ranking or open-ended value maps;
``wire_to_domain`` injects the existing domain schema and performs only
mechanical binding and temporal validation.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Mapping, Union

from pydantic import Field, StrictStr, field_validator, model_validator

from .common import CanonicalValue, ProducerRef, SchemaRef, StrictModel, require_nonblank
from .direct_service import DirectServiceEvidenceRef
from .knowledge import Observation, ObservationTime


ConductPropositionClass = Literal[
    "complaint", "allegation", "investigation", "proceeding", "finding",
    "enforcement_action", "sanction_or_penalty", "undertaking_or_agreement",
    "remediation_or_corrective_action", "subject_response", "appeal_or_review",
    "correction_or_variation", "overturning", "matter_status",
]
ConductProceduralStatus = Literal[
    "pending", "ongoing", "in_force", "completed", "fulfilled",
    "no_longer_in_force", "withdrawn", "varied", "overturned", "stayed",
    "closed", "unknown",
]
PropositionOwnerKind = Literal["source_publisher", "target_subject", "other_named_party", "unknown"]


class ConductWireSourcePublisher(StrictModel):
    kind: Literal["source_publisher"]


class ConductWireTargetSubject(StrictModel):
    kind: Literal["target_subject"]


class ConductWireUnknownOwner(StrictModel):
    kind: Literal["unknown"]


class ConductWireOtherNamedParty(StrictModel):
    kind: Literal["other_named_party"]
    label: StrictStr

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        return require_nonblank(value, "owner.label")


ConductWireOwner = Annotated[
    Union[ConductWireSourcePublisher, ConductWireTargetSubject, ConductWireOtherNamedParty, ConductWireUnknownOwner],
    Field(discriminator="kind"),
]


class ConductComplianceWireTemporal(StrictModel):
    effective_from: StrictStr | None = None
    effective_to: StrictStr | None = None
    reporting_period: StrictStr | None = None


class ConductComplianceWireEvidenceRef(StrictModel):
    evidence_key: StrictStr
    role: Literal["supporting", "corroborating", "context"]

    @field_validator("evidence_key")
    @classmethod
    def _evidence_key(cls, value: str) -> str:
        return require_nonblank(value, "evidence_key")


class ConductComplianceWireProposition(StrictModel):
    proposition_class: ConductPropositionClass
    procedural_status: ConductProceduralStatus
    scope_id: StrictStr
    owner: ConductWireOwner
    statement: StrictStr
    qualification: StrictStr | None = None
    temporal: ConductComplianceWireTemporal | None = None
    evidence: tuple[ConductComplianceWireEvidenceRef, ...] = ()

    @field_validator("scope_id", "statement")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("qualification")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _shape(self) -> "ConductComplianceWireProposition":
        if not any(item.role == "supporting" for item in self.evidence):
            raise ValueError("non-empty conduct propositions require supporting evidence")
        if len({item.evidence_key for item in self.evidence}) != len(self.evidence):
            raise ValueError("conduct evidence locators must be unique")
        return self


class ConductComplianceWireOutput(StrictModel):
    """Provider-only output; empty propositions are valid for sparse controls."""

    propositions: tuple[ConductComplianceWireProposition, ...] = ()


class ConductComplianceSemanticProposition(StrictModel):
    proposition_class: ConductPropositionClass
    procedural_status: ConductProceduralStatus
    scope_id: str
    proposition_owner_kind: PropositionOwnerKind
    proposition_owner_label: str | None = None
    statement: str
    qualification: str | None = None
    observation_time: ObservationTime | None = None
    evidence: tuple[DirectServiceEvidenceRef, ...]

    @model_validator(mode="after")
    def _shape(self) -> "ConductComplianceSemanticProposition":
        if self.proposition_owner_kind == "other_named_party" and not self.proposition_owner_label:
            raise ValueError("other_named_party requires proposition_owner_label")
        if self.proposition_owner_kind != "other_named_party" and self.proposition_owner_label is not None:
            raise ValueError("proposition_owner_label is limited to other_named_party")
        if not any(item.role == "supporting" for item in self.evidence):
            raise ValueError("non-empty conduct propositions require supporting evidence")
        return self


class ConductComplianceSemanticOutput(StrictModel):
    schema_ref: SchemaRef = Field(
        default=SchemaRef(
            schema_id="urn:charitygraph:builder:schema:conduct-compliance-semantic-output:1.0",
            schema_version="1.0",
        ),
        validation_alias="schema",
        serialization_alias="schema",
    )
    propositions: tuple[ConductComplianceSemanticProposition, ...] = ()


def _parse_temporal(value: ConductComplianceWireTemporal | None, *, observed_at: datetime | date | str | None) -> ObservationTime | None:
    if value is None:
        return None

    def parse(raw: str | None, field: str):
        if raw is None:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")) if ("T" in raw or " " in raw) else date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"invalid {field} temporal value") from exc

    if observed_at is None:
        raise ValueError("Builder observation timestamp is required when temporal is supplied")
    observed_value = parse(observed_at, "observed_at") if isinstance(observed_at, str) else observed_at
    return ObservationTime(
        effective_from=parse(value.effective_from, "effective_from"),
        effective_to=parse(value.effective_to, "effective_to"),
        reporting_period=value.reporting_period,
        observed_at=observed_value,
    )


def wire_to_domain(
    wire: ConductComplianceWireOutput,
    *,
    allowed_scope_ids: set[str] | None = None,
    evidence_key_map: Mapping[str, str] | None = None,
    observed_at: datetime | date | str | None = None,
) -> ConductComplianceSemanticOutput:
    """Convert a validated wire response using only exact task bindings."""
    if allowed_scope_ids is not None and not allowed_scope_ids:
        raise ValueError("Section 16 task must provide at least one visible scope")
    if evidence_key_map is not None and len(set(evidence_key_map.values())) != len(evidence_key_map):
        raise ValueError("evidence key map must bind each canonical locator once")
    converted: list[ConductComplianceSemanticProposition] = []
    for item in wire.propositions:
        if allowed_scope_ids is not None and item.scope_id not in allowed_scope_ids:
            raise ValueError(f"unknown conduct scope_id: {item.scope_id}")
        if evidence_key_map is not None:
            unknown = [ref.evidence_key for ref in item.evidence if ref.evidence_key not in evidence_key_map]
            if unknown:
                raise ValueError("conduct evidence key is not present in the task bundle")
        converted.append(
            ConductComplianceSemanticProposition(
                proposition_class=item.proposition_class,
                procedural_status=item.procedural_status,
                scope_id=item.scope_id,
                proposition_owner_kind=item.owner.kind,
                proposition_owner_label=getattr(item.owner, "label", None),
                statement=item.statement,
                qualification=item.qualification,
                observation_time=_parse_temporal(item.temporal, observed_at=observed_at),
                evidence=tuple(DirectServiceEvidenceRef(locator=evidence_key_map[ref.evidence_key] if evidence_key_map is not None else ref.evidence_key, role=ref.role) for ref in item.evidence),
            )
        )
    return ConductComplianceSemanticOutput(propositions=tuple(converted))


def project_observation(
    proposition: ConductComplianceSemanticProposition,
    *,
    record_id: str,
    subject_id: str,
    source_record_ids: tuple[str, ...],
    created_at: datetime,
    producer: ProducerRef | dict,
) -> Observation:
    """Project one proposition into the existing append-only observation model."""
    if not source_record_ids:
        raise ValueError("conduct observations require source record IDs")
    payload: dict[str, CanonicalValue] = {
        "statement": proposition.statement,
        "procedural_status": proposition.procedural_status,
        "proposition_owner_kind": proposition.proposition_owner_kind,
    }
    if proposition.proposition_owner_label is not None:
        payload["proposition_owner_label"] = proposition.proposition_owner_label
    if proposition.qualification is not None:
        payload["qualification"] = proposition.qualification
    return Observation(
        record_id=record_id,
        created_at=created_at,
        producer=producer,
        subject_id=subject_id,
        scope_id=None if proposition.scope_id == subject_id else proposition.scope_id,
        predicate=f"conduct_compliance.{proposition.proposition_class}",
        value=payload,
        outcome_state="supported",
        evidence_locator_ids=tuple(item.locator for item in proposition.evidence),
        source_record_ids=source_record_ids,
        observation_time=proposition.observation_time or {"observed_at": created_at},
        method="conduct_compliance_semantic_task",
    )


def review_flags(proposition: ConductComplianceSemanticProposition) -> tuple[str, ...]:
    """Return structural assurance flags; this function never parses prose."""
    flags: list[str] = []
    if proposition.proposition_class == "allegation":
        flags.append("allegation_without_formal_finding")
    if proposition.procedural_status in {"varied", "overturned", "stayed"}:
        flags.append(f"status_{proposition.procedural_status}")
    if proposition.proposition_owner_kind == "unknown":
        flags.append("proposition_owner_ambiguous")
    if proposition.procedural_status == "no_longer_in_force" and proposition.observation_time is None:
        flags.append("current_status_ambiguous")
    return tuple(flags)


__all__ = [
    "ConductPropositionClass", "ConductProceduralStatus", "PropositionOwnerKind",
    "ConductComplianceWireTemporal", "ConductComplianceWireEvidenceRef",
    "ConductComplianceWireProposition", "ConductComplianceWireOutput", "ConductWireOwner",
    "ConductComplianceSemanticProposition", "ConductComplianceSemanticOutput",
    "wire_to_domain", "project_observation", "review_flags",
]
