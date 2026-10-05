"""Evidence-bound §8 Giving Offer contract; it does not model payments or allocation."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import CanonicalValue, ProducerRef, SchemaRef, StrictModel, require_nonblank
from .knowledge import Observation, ObservationTime


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


FundabilityCoverage = Literal["supported", "conditional", "explicitly_unavailable", "not_found_in_reviewed_public_giving_channels", "source_silent", "not_acquired", "not_processed", "stale", "unknown"]
DestinationResolution = Literal["resolved", "candidate", "ambiguous", "unresolved"]
Audience = Literal["public", "major_donor", "institutional", "corporate", "member", "unknown"]
DesignationType = Literal["unrestricted", "source_stated_designation", "source_stated_preference", "source_reported_restricted", "contractual_restriction", "negotiated", "unknown"]
EndpointType = Literal["first_party_form", "official_third_party_form", "contact_route", "phone", "email", "offline_instruction", "other"]
OfferStatus = Literal["current", "historical", "stale", "closed", "unknown"]
FundabilityPredicate = Literal["giving_offer_observed", "offer_audience_observed", "designation_available_observed", "designation_explicitly_unavailable_observed", "designation_terms_observed", "redirection_terms_observed", "excess_funds_terms_observed", "shared_cost_terms_observed", "gift_condition_observed", "commitment_pattern_observed", "action_endpoint_observed"]


class FundabilityEvidenceRef(StrictModel):
    locator: str
    source_record_id: str
    source_role: Literal["first_party", "officially_linked_third_party", "formal_policy", "annual_report", "other"]
    lineage_id: str

    @field_validator("locator", "source_record_id", "lineage_id")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)


class FundabilityProposition(StrictModel):
    """One atomic observation. Destination identity is deliberately independent of offer acceptance."""
    predicate: FundabilityPredicate
    giving_context_id: str
    accepting_subject_id: str
    giving_offer_group_id: str | None = None
    destination_source_label: str | None = None
    destination_scope_id: str | None = None
    destination_resolution: DestinationResolution = "unresolved"
    audience: Audience = "unknown"
    resource_type: Literal["money"] = "money"
    instrument: str | None = None
    commitment_pattern: str | None = None
    designation_type: DesignationType = "unknown"
    status: OfferStatus = "unknown"
    endpoint_type: EndpointType | None = None
    endpoint_url: str | None = None
    coverage_state: FundabilityCoverage = "unknown"
    observation_time: ObservationTime
    evidence: tuple[FundabilityEvidenceRef, ...] = ()
    detail: CanonicalValue | None = None
    qualification: str | None = None

    @field_validator("giving_context_id", "accepting_subject_id", "giving_offer_group_id", "destination_source_label", "destination_scope_id", "instrument", "commitment_pattern", "endpoint_url", "qualification")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _invariants(self) -> "FundabilityProposition":
        if self.destination_resolution == "resolved" and self.destination_scope_id is None:
            raise ValueError("resolved destination requires governed destination_scope_id")
        if self.destination_resolution != "resolved" and self.destination_scope_id is not None:
            raise ValueError("only resolved destination may bind a governed scope")
        if self.coverage_state in {"supported", "explicitly_unavailable"} and not self.evidence:
            raise ValueError("positive or explicit-negative propositions require evidence")
        if self.predicate == "designation_explicitly_unavailable_observed" and self.coverage_state != "explicitly_unavailable":
            raise ValueError("explicit unavailability requires explicitly_unavailable coverage")
        if self.coverage_state == "explicitly_unavailable" and self.predicate != "designation_explicitly_unavailable_observed":
            raise ValueError("explicit unavailability is limited to its explicit predicate")
        if self.predicate == "action_endpoint_observed" and (self.endpoint_type is None or self.detail is None):
            raise ValueError("action endpoint requires endpoint type and substantive detail")
        if self.endpoint_type == "official_third_party_form" and not any(item.source_role == "officially_linked_third_party" for item in self.evidence):
            raise ValueError("third-party endpoint requires official-link provenance")
        return self


class FundabilityV1(StrictModel):
    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("fundability-v1"), validation_alias="schema", serialization_alias="schema")
    propositions: tuple[FundabilityProposition, ...]

    @model_validator(mode="after")
    def _contexts(self) -> "FundabilityV1":
        if not self.propositions:
            raise ValueError("fundability output requires propositions or a separate coverage record")
        return self


def project_observation(proposition: FundabilityProposition, *, record_id: str, subject_id: str, created_at: datetime, producer: ProducerRef | dict, method: str = "fundability_semantic_task") -> Observation:
    """Project only §8 fact content. It never creates §13 allocation or §14 funding facts."""
    if proposition.coverage_state in {"supported", "explicitly_unavailable"} and not proposition.evidence:
        raise ValueError("supported projection requires retained evidence")
    if subject_id != proposition.accepting_subject_id:
        raise ValueError("§8 offer observation must be attached to its accepting subject")
    value: dict[str, CanonicalValue] = {
        "giving_context_id": proposition.giving_context_id, "accepting_subject_id": proposition.accepting_subject_id,
        "destination_resolution": proposition.destination_resolution, "audience": proposition.audience,
        "resource_type": proposition.resource_type, "designation_type": proposition.designation_type,
        "status": proposition.status, "coverage_state": proposition.coverage_state,
    }
    for name in ("giving_offer_group_id", "destination_source_label", "destination_scope_id", "instrument", "commitment_pattern", "endpoint_type", "endpoint_url", "detail", "qualification"):
        item = getattr(proposition, name)
        if item is not None:
            value[name] = item
    outcome = "supported" if proposition.coverage_state == "supported" else "resolved" if proposition.coverage_state == "explicitly_unavailable" else "unknown"
    return Observation(record_id=record_id, created_at=created_at, producer=producer, subject_id=subject_id,
        scope_id=proposition.destination_scope_id, predicate=f"fundability.{proposition.predicate}", value=value,
        outcome_state=outcome, evidence_locator_ids=tuple(item.locator for item in proposition.evidence),
        source_record_ids=tuple(dict.fromkeys(item.source_record_id for item in proposition.evidence)),
        observation_time=proposition.observation_time, method=method)


__all__ = ["FundabilityCoverage", "DestinationResolution", "Audience", "DesignationType", "EndpointType", "OfferStatus", "FundabilityPredicate", "FundabilityEvidenceRef", "FundabilityProposition", "FundabilityV1", "project_observation"]
