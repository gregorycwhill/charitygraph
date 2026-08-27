"""Production-native multi-proposal program/service discovery contracts.

This module deliberately models only evidence-grounded subject discovery. It
contains no taxonomy, CLASSIE, SDG, benchmark, or lexical inference logic.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .canonical import canonical_sha256
from .common import SchemaRef, StrictModel, require_nonblank
from .semantic import SemanticEvidence


DiscoveryDisposition = Literal[
    "program",
    "service",
    "project",
    "campaign",
    "category_or_portfolio",
    "organisational_practice",
    "insufficient_evidence",
]


class ProgramServiceProposal(StrictModel):
    proposal_key: str = Field(min_length=1, max_length=128)
    label: str
    disposition: DiscoveryDisposition
    durable: bool | None
    evidence: tuple[SemanticEvidence, ...]
    rationale: str
    confidence: Literal["low", "medium", "high"] | None = None
    competing_interpretation: str | None = None

    _label = field_validator("label")(lambda value: require_nonblank(value, "label"))
    _rationale = field_validator("rationale")(lambda value: require_nonblank(value, "rationale"))
    _competing = field_validator("competing_interpretation")(
        lambda value: None if value is None else require_nonblank(value, "competing_interpretation")
    )

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[SemanticEvidence, ...]) -> tuple[SemanticEvidence, ...]:
        if not value or len({item.evidence_id for item in value}) != len(value):
            raise ValueError("every discovery proposal requires unique evidence references")
        return value


class ProgramServiceDiscoveryOutput(StrictModel):
    proposals: tuple[ProgramServiceProposal, ...] = ()

    @model_validator(mode="after")
    def _unique_keys(self) -> "ProgramServiceDiscoveryOutput":
        keys = [item.proposal_key for item in self.proposals]
        if len(set(keys)) != len(keys):
            raise ValueError("discovery proposal_key values must be unique")
        return self


def discovery_schema(evidence_ids: tuple[str, ...] | list[str]) -> dict:
    """Build the provider strict schema for one exact evidence binding."""

    ids = list(evidence_ids)
    evidence_item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "evidence_id": {"type": "string", "enum": ids},
            "role": {"type": "string", "enum": ["supporting", "competing", "context"]},
            "note": {"type": ["string", "null"]},
        },
        "required": ["evidence_id", "role", "note"],
    }
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "proposal_key": {"type": "string", "minLength": 1, "maxLength": 128},
            "label": {"type": "string", "minLength": 1},
            "disposition": {"type": "string", "enum": list(DiscoveryDisposition.__args__)},
            "durable": {"type": ["boolean", "null"]},
            "evidence": {"type": "array", "items": evidence_item, "minItems": 1},
            "rationale": {"type": "string", "minLength": 1},
            "confidence": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]},
            "competing_interpretation": {"type": ["string", "null"]},
        },
        "required": ["proposal_key", "label", "disposition", "durable", "evidence", "rationale", "confidence", "competing_interpretation"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"proposals": {"type": "array", "items": proposal, "minItems": 0}},
        "required": ["proposals"],
    }


def discovery_schema_hash(evidence_ids: tuple[str, ...] | list[str]) -> str:
    return canonical_sha256(discovery_schema(evidence_ids))


DISCOVERY_OUTPUT_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:program-service-discovery-output:1.0",
    schema_version="1.0",
)

def discovery_output_schema_ref(evidence_ids: tuple[str, ...] | list[str]) -> SchemaRef:
    return SchemaRef(schema_id=DISCOVERY_OUTPUT_SCHEMA.schema_id, schema_version="1.0-" + discovery_schema_hash(evidence_ids)[:16])
