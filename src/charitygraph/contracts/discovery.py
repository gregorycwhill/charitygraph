"""Production-native multi-proposal program/service discovery contracts.

This module deliberately models only evidence-grounded subject discovery. It
contains no taxonomy, CLASSIE, SDG, benchmark, or lexical inference logic.
"""

from __future__ import annotations

from typing import Literal, Mapping

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


OperationalStatus = Literal["current", "closing_or_winding_down", "historical", "unknown"]
OperatorRelationship = Literal[
    "operated_by_subject",
    "jointly_operated_or_partnered",
    "supported_or_hosted_by_subject",
    "externally_operated",
    "unclear",
]


class PropositionEvidenceLocatorV3(StrictModel):
    """A proposition-level locator for the v3 discovery result.

    ``quote`` is a locator only; it is never interpreted as proof by this
    contract. Exact containment against supplied evidence is checked by
    :func:`validate_v3_evidence_quotes`.
    """

    evidence_id: str
    role: Literal["supporting", "competing", "context"]
    quote: str | None = None
    note: str | None = None

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id(cls, value: str) -> str:
        return require_nonblank(value, "evidence_id")

    @field_validator("quote", "note")
    @classmethod
    def _text(cls, value: str | None, info) -> str | None:
        return None if value is None else require_nonblank(value, info.field_name)

    @model_validator(mode="after")
    def _quote_required_for_claim_roles(self) -> "PropositionEvidenceLocatorV3":
        if self.role in {"supporting", "competing"} and self.quote is None:
            raise ValueError(f"{self.role} evidence locators require a non-empty verbatim quote")
        return self


# Descriptive alias used by callers that refer to discovery evidence directly.
DiscoveryEvidenceLocatorV3 = PropositionEvidenceLocatorV3
EvidenceLocatorV3 = PropositionEvidenceLocatorV3
SemanticEvidenceV3 = PropositionEvidenceLocatorV3


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


class ProgramServiceProposalV2(StrictModel):
    proposal_key: str = Field(min_length=1, max_length=128)
    label: str
    disposition: DiscoveryDisposition
    operational_status: OperationalStatus
    evidence: tuple[SemanticEvidence, ...]
    rationale: str
    confidence: Literal["low", "medium", "high"] | None = None
    competing_interpretation: str | None = None

    _label = field_validator("label")(lambda value: require_nonblank(value, "label"))
    _rationale = field_validator("rationale")(lambda value: require_nonblank(value, "rationale"))
    _competing = field_validator("competing_interpretation")(lambda value: None if value is None else require_nonblank(value, "competing_interpretation"))

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[SemanticEvidence, ...]) -> tuple[SemanticEvidence, ...]:
        if not value or len({item.evidence_id for item in value}) != len(value):
            raise ValueError("every discovery proposal requires unique evidence references")
        return value


class ProgramServiceDiscoveryOutputV2(StrictModel):
    proposals: tuple[ProgramServiceProposalV2, ...] = ()

    @model_validator(mode="after")
    def _unique_keys(self) -> "ProgramServiceDiscoveryOutputV2":
        keys = [item.proposal_key for item in self.proposals]
        if len(set(keys)) != len(keys):
            raise ValueError("discovery proposal_key values must be unique")
        return self


class ProgramServiceProposalV3(StrictModel):
    proposal_key: str = Field(min_length=1, max_length=128)
    label: str
    disposition: DiscoveryDisposition
    operator_relationship: OperatorRelationship
    parent_proposal_key: str | None = None
    operational_status: OperationalStatus
    evidence: tuple[PropositionEvidenceLocatorV3, ...]
    operational_status_evidence: tuple[PropositionEvidenceLocatorV3, ...] = ()
    rationale: str
    confidence: Literal["low", "medium", "high"] | None = None
    competing_interpretation: str | None = None

    _label = field_validator("label")(lambda value: require_nonblank(value, "label"))
    _rationale = field_validator("rationale")(lambda value: require_nonblank(value, "rationale"))

    @field_validator("parent_proposal_key", "competing_interpretation")
    @classmethod
    def _optional_text(cls, value: str | None, info) -> str | None:
        return None if value is None else require_nonblank(value, info.field_name)

    @field_validator("evidence", "operational_status_evidence")
    @classmethod
    def _unique_evidence(cls, value: tuple[PropositionEvidenceLocatorV3, ...], info):
        if info.field_name == "evidence" and not value:
            raise ValueError("every v3 discovery proposal requires evidence")
        if len({(item.evidence_id, item.role, item.quote) for item in value}) != len(value):
            raise ValueError(f"{info.field_name} locators must be unique")
        return value

    @model_validator(mode="after")
    def _status_evidence(self) -> "ProgramServiceProposalV3":
        if self.operational_status != "unknown" and not any(
            item.role == "supporting" for item in self.operational_status_evidence
        ):
            raise ValueError("non-unknown operational status requires supporting status evidence")
        return self


class ProgramServiceDiscoveryOutputV3(StrictModel):
    proposals: tuple[ProgramServiceProposalV3, ...] = ()

    @model_validator(mode="after")
    def _structure(self) -> "ProgramServiceDiscoveryOutputV3":
        by_key = {item.proposal_key: item for item in self.proposals}
        if len(by_key) != len(self.proposals):
            raise ValueError("discovery proposal_key values must be unique")
        for item in self.proposals:
            if item.parent_proposal_key is not None and item.parent_proposal_key not in by_key:
                raise ValueError(f"unknown parent_proposal_key {item.parent_proposal_key}")
            if item.parent_proposal_key == item.proposal_key:
                raise ValueError("a proposal cannot parent itself")
        # Follow parent pointers to reject every directed cycle.
        for start in by_key:
            seen: set[str] = set()
            current = start
            while by_key[current].parent_proposal_key is not None:
                if current in seen:
                    raise ValueError("parent_proposal_key relationships must be acyclic")
                seen.add(current)
                current = by_key[current].parent_proposal_key  # type: ignore[assignment]
        return self

    def validate_evidence_quotes(self, evidence_content: Mapping[str, str]) -> "ProgramServiceDiscoveryOutputV3":
        return validate_v3_evidence_quotes(self, evidence_content)


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

def discovery_schema_v2(evidence_ids: tuple[str, ...] | list[str]) -> dict:
    ids = list(evidence_ids)
    evidence_item = {"type": "object", "additionalProperties": False, "properties": {"evidence_id": {"type": "string", "enum": ids}, "role": {"type": "string", "enum": ["supporting", "competing", "context"]}, "note": {"type": ["string", "null"]}}, "required": ["evidence_id", "role", "note"]}
    proposal = {"type": "object", "additionalProperties": False, "properties": {"proposal_key": {"type": "string", "minLength": 1, "maxLength": 128}, "label": {"type": "string", "minLength": 1}, "disposition": {"type": "string", "enum": list(DiscoveryDisposition.__args__)}, "operational_status": {"type": "string", "enum": list(OperationalStatus.__args__)}, "evidence": {"type": "array", "items": evidence_item, "minItems": 1}, "rationale": {"type": "string", "minLength": 1}, "confidence": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]}, "competing_interpretation": {"type": ["string", "null"]}}, "required": ["proposal_key", "label", "disposition", "operational_status", "evidence", "rationale", "confidence", "competing_interpretation"]}
    return {"type": "object", "additionalProperties": False, "properties": {"proposals": {"type": "array", "items": proposal, "minItems": 0}}, "required": ["proposals"]}


def discovery_schema_v2_hash(evidence_ids: tuple[str, ...] | list[str]) -> str:
    return canonical_sha256(discovery_schema_v2(evidence_ids))


def _v3_evidence_schema(evidence_ids: tuple[str, ...] | list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "evidence_id": {"type": "string", "enum": list(evidence_ids)},
            "role": {"type": "string", "enum": ["supporting", "competing", "context"]},
            "quote": {"type": ["string", "null"]},
            "note": {"type": ["string", "null"]},
        },
        "required": ["evidence_id", "role", "quote", "note"],
    }


def discovery_schema_v3(evidence_ids: tuple[str, ...] | list[str]) -> dict:
    """Build the strict provider schema for the v3 discovery contract."""

    evidence = _v3_evidence_schema(evidence_ids)
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "proposal_key": {"type": "string", "minLength": 1, "maxLength": 128},
            "label": {"type": "string", "minLength": 1},
            "disposition": {"type": "string", "enum": list(DiscoveryDisposition.__args__)},
            "operator_relationship": {"type": "string", "enum": list(OperatorRelationship.__args__)},
            "parent_proposal_key": {"type": ["string", "null"]},
            "operational_status": {"type": "string", "enum": list(OperationalStatus.__args__)},
            "evidence": {"type": "array", "items": evidence, "minItems": 1},
            "operational_status_evidence": {"type": "array", "items": evidence, "minItems": 0},
            "rationale": {"type": "string", "minLength": 1},
            "confidence": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]},
            "competing_interpretation": {"type": ["string", "null"]},
        },
        "required": [
            "proposal_key", "label", "disposition", "operator_relationship",
            "parent_proposal_key", "operational_status", "evidence", "operational_status_evidence",
            "rationale", "confidence", "competing_interpretation",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"proposals": {"type": "array", "items": proposal, "minItems": 0}},
        "required": ["proposals"],
    }


def discovery_schema_v3_hash(evidence_ids: tuple[str, ...] | list[str]) -> str:
    return canonical_sha256(discovery_schema_v3(evidence_ids))


def validate_v3_evidence_quotes(
    output: ProgramServiceDiscoveryOutputV3,
    evidence_content: Mapping[str, str],
) -> ProgramServiceDiscoveryOutputV3:
    """Validate exact quote containment against task-supplied evidence.

    Only CRLF-to-LF conversion is allowed for comparison. Natural-language
    whitespace is otherwise left untouched; no semantic or fuzzy matching is
    performed.
    """

    for proposal in output.proposals:
        locators = (*proposal.evidence, *proposal.operational_status_evidence)
        for locator in locators:
            if locator.quote is None:
                continue
            if locator.evidence_id not in evidence_content:
                raise ValueError(f"quote references evidence not supplied to task: {locator.evidence_id}")
            content = evidence_content[locator.evidence_id].replace("\r\n", "\n")
            quote = locator.quote.replace("\r\n", "\n")
            if quote not in content:
                raise ValueError(f"quote is not a verbatim contiguous excerpt of {locator.evidence_id}")
    return output


DISCOVERY_OUTPUT_SCHEMA_V3 = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:program-service-discovery-output:3.0",
    schema_version="3.0",
)


def discovery_output_schema_ref_v3(evidence_ids: tuple[str, ...] | list[str]) -> SchemaRef:
    return SchemaRef(
        schema_id=DISCOVERY_OUTPUT_SCHEMA_V3.schema_id,
        schema_version="3.0-" + discovery_schema_v3_hash(evidence_ids)[:16],
    )




DISCOVERY_OUTPUT_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:program-service-discovery-output:1.0",
    schema_version="1.0",
)

def discovery_output_schema_ref(evidence_ids: tuple[str, ...] | list[str]) -> SchemaRef:
    return SchemaRef(schema_id=DISCOVERY_OUTPUT_SCHEMA.schema_id, schema_version="1.0-" + discovery_schema_hash(evidence_ids)[:16])


DISCOVERY_OUTPUT_SCHEMA_V2 = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:program-service-discovery-output:2.0",
    schema_version="2.0",
)


def discovery_output_schema_ref_v2(evidence_ids: tuple[str, ...] | list[str]) -> SchemaRef:
    return SchemaRef(schema_id=DISCOVERY_OUTPUT_SCHEMA_V2.schema_id, schema_version="2.0-" + discovery_schema_v2_hash(evidence_ids)[:16])
