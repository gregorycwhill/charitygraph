"""Packet-local candidate extraction for North Star v0.3 sections 15 and 17.

This module deliberately has no importer from candidates to ``Observation``.
Admission remains an S0 review decision; this is an instrumented, fail-closed
bridge from an immutable evidence packet to review material only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ethos_history import EthosRole, HistoryFamily, HistorySourceRole, EventStatus, notable_event_candidate_id
from .openai_client import ApiUsage, estimate_response_cost, responses_create
from .s0_ethos_notability_routing import route_task_metadata

CONTRACT_ID = "ethos-notability-extraction-v1"
PROMPT_VERSION = "ethos-notability-extraction-prompt-v1"
SCHEMA_VERSION = "ethos-notability-extraction-schema-v1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PacketEvidence(_Strict):
    evidence_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    lineage_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_role: Literal["supporting", "corroborating", "context"]
    retrieved_at: datetime | None = None
    event_or_effective_date: str | None = None


class FrozenEthosNotabilityPacket(_Strict):
    packet_id: str = Field(min_length=1)
    packet_hash: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    permitted_scope_ids: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[PacketEvidence, ...] = Field(min_length=1)
    contract_id: Literal["ethos-notability-extraction-v1"] = CONTRACT_ID

    @model_validator(mode="after")
    def packet_is_bound(self):
        if len({x.evidence_id for x in self.evidence}) != len(self.evidence):
            raise ValueError("packet evidence IDs must be unique")
        return self


class EthosCandidate(_Strict):
    """Candidate-only form; not ``EthosObservation`` and never governed data."""
    subject_id: str
    scope_id: str
    epistemic_role: EthosRole
    descriptor: str = Field(min_length=1)
    source_role: Literal["supporting", "corroborating", "context"]
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    qualification: str | None = None
    material_disagreement: str | None = None
    currentness: Literal["current", "historical", "unknown"] = "unknown"


class HistoryCandidate(_Strict):
    """Candidate-only form; section 16 fields are intentionally unavailable."""
    subject_id: str
    scope_id: str
    event_family: HistoryFamily
    statement: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    source_roles: tuple[HistorySourceRole, ...] = Field(min_length=1)
    event_date: str | None = None
    event_date_qualification: str | None = None
    related_subject_id: str | None = None
    relationship_kind: Literal["predecessor", "successor", "parent", "affiliate", "network", "person", "other"] | None = None
    procedural_status: EventStatus | None = None
    qualification: str | None = None
    uncertainty: str | None = None


class CandidateBundle(_Strict):
    outcome: Literal["candidates", "abstain", "unresolved"]
    ethos_candidates: tuple[EthosCandidate, ...] = ()
    history_candidates: tuple[HistoryCandidate, ...] = ()
    reason: str | None = None

    @model_validator(mode="after")
    def outcome_matches_content(self):
        has = bool(self.ethos_candidates or self.history_candidates)
        if self.outcome == "candidates" and not has:
            raise ValueError("candidates outcome requires at least one candidate")
        if self.outcome != "candidates" and has:
            raise ValueError("abstain/unresolved cannot include candidates")
        return self


OUTPUT_SCHEMA = CandidateBundle.model_json_schema()
def _strictify(value: Any) -> None:
    if isinstance(value, dict):
        value.pop("default", None)
        if value.get("type") == "object" and "properties" in value:
            value["required"] = list(value["properties"])
        for child in value.values(): _strictify(child)
    elif isinstance(value, list):
        for child in value: _strictify(child)
_strictify(OUTPUT_SCHEMA)

PROMPT = """You extract only §15 Ethos and §17 Notable History candidate material.
The supplied frozen packet is the complete admissible evidence universe: do not browse,
retrieve, use background knowledge, or invent a fact. Return JSON matching the schema.
Every positive candidate requires exact packet evidence_ids. Abstain when unsupported.
Do not infer ethos from beneficiaries, names, geography, imagery, people, parents/networks,
tone, or omission. Do not transfer parent/network, predecessor/successor, historical/current,
or award/recognition meaning. Preserve qualifications and disagreement. An inquiry/review can
be a §17 occurrence only; never make it a §16 allegation, finding, sanction, or remediation.
Keep different scope, time, or source-role claims separate. This output is candidate/review
material, never a governed observation or public assertion."""


def artifact_hash(value: str | Mapping[str, Any]) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


class ExtractionProvider(Protocol):
    def extract(self, *, prompt: str, packet: FrozenEthosNotabilityPacket, schema: Mapping[str, Any]) -> "ProviderResponse": ...


@dataclass(frozen=True)
class ProviderResponse:
    raw_response: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: str | None = None
    attempts: int = 1
    escalation_reason: str | None = None


class OpenAIResponsesExtractionProvider:
    """Production-capable adapter over the repository's established Responses client."""
    def __init__(self, model: str = "gpt-5.6-luna") -> None: self.model = model
    def extract(self, *, prompt: str, packet: FrozenEthosNotabilityPacket, schema: Mapping[str, Any]) -> ProviderResponse:
        result = responses_create(model=self.model, input_text=prompt + "\nPACKET:\n" + packet.model_dump_json(), text_format={"type":"json_schema", "name":SCHEMA_VERSION.replace("-", "_"), "strict":True, "schema":dict(schema)}, max_output_tokens=4000, max_attempts=1, timeout_seconds=120, reasoning={"effort":"none"})
        cost = estimate_response_cost(result.model, result.usage)
        return ProviderResponse(result.output_text, "openai.responses", result.model, result.usage.input_tokens, result.usage.output_tokens, result.usage.total_tokens, str(cost) if cost is not None else None, result.transport_requests)


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    reasons: tuple[str, ...]
    bundle: CandidateBundle | None


def validate_bundle(packet: FrozenEthosNotabilityPacket, raw: str | Mapping[str, Any]) -> ValidationResult:
    try: bundle = CandidateBundle.model_validate_json(raw) if isinstance(raw, str) else CandidateBundle.model_validate(raw)
    except Exception as exc: return ValidationResult(False, ("malformed_schema:" + str(exc).splitlines()[0],), None)
    ids = {x.evidence_id: x for x in packet.evidence}; reasons: list[str] = []
    for candidate in (*bundle.ethos_candidates, *bundle.history_candidates):
        if candidate.subject_id != packet.subject_id: reasons.append("wrong_subject")
        if candidate.scope_id not in packet.permitted_scope_ids: reasons.append("wrong_scope")
        if not set(candidate.evidence_ids).issubset(ids): reasons.append("out_of_packet_evidence")
        if isinstance(candidate, HistoryCandidate):
            if candidate.relationship_kind is None and candidate.related_subject_id is not None: reasons.append("related_subject_without_relationship")
            if candidate.relationship_kind is not None and candidate.related_subject_id is None: reasons.append("relationship_without_related_subject")
            if candidate.event_family in {"merger", "split", "succession"} and candidate.related_subject_id is None: reasons.append("lineage_event_without_related_subject")
            if candidate.event_family == "public_inquiry_or_review" and candidate.procedural_status is None: reasons.append("inquiry_requires_procedural_status")
            if candidate.event_date:
                try: datetime.fromisoformat(candidate.event_date)
                except ValueError: reasons.append("malformed_event_date")
                retrieved_dates = {x.retrieved_at.date().isoformat() for x in ids.values() if x.retrieved_at}
                if candidate.event_date in retrieved_dates: reasons.append("source_date_used_as_event_date")
    return ValidationResult(not reasons, tuple(sorted(set(reasons))), bundle if not reasons else None)


def s0_handoff(packet: FrozenEthosNotabilityPacket, validation: ValidationResult) -> dict[str, Any]:
    """Metadata-only handoff.  No projection/admission path is available here."""
    if not validation.accepted or validation.bundle is None:
        return {"state":"REJECTED", "reasons":validation.reasons, "candidate_count":0}
    entries=[]
    for candidate in validation.bundle.ethos_candidates:
        entries.append({"kind":"ethos_candidate", "candidate_state":"REVIEW_MATERIAL", "route":route_task_metadata(section_id=15, risk_family=candidate.epistemic_role, unresolved=validation.bundle.outcome=="unresolved")})
    for candidate in validation.bundle.history_candidates:
        entries.append({"kind":"history_candidate", "candidate_state":"REVIEW_MATERIAL", "event_identity":notable_event_candidate_id(subject_id=candidate.subject_id, scope_id=candidate.scope_id, event_family=candidate.event_family, event_date=datetime.fromisoformat(candidate.event_date).date() if candidate.event_date and len(candidate.event_date)==10 else None, statement=candidate.statement, related_subject_id=candidate.related_subject_id), "route":route_task_metadata(section_id=17, risk_family="historical_temporal", unresolved=validation.bundle.outcome=="unresolved")})
    return {"state":"REVIEW_REQUIRED", "candidate_count":len(entries), "entries":entries}


def run_extraction(packet: FrozenEthosNotabilityPacket, provider: ExtractionProvider, *, ledger_path: Path | None = None) -> dict[str, Any]:
    response = provider.extract(prompt=PROMPT, packet=packet, schema=OUTPUT_SCHEMA)
    validation = validate_bundle(packet, response.raw_response)
    result = {"contract_id":CONTRACT_ID, "contract_hash":artifact_hash(CONTRACT_ID), "prompt_version":PROMPT_VERSION, "prompt_hash":artifact_hash(PROMPT), "schema_version":SCHEMA_VERSION, "schema_hash":artifact_hash(OUTPUT_SCHEMA), "packet_id":packet.packet_id, "packet_hash":packet.packet_hash, "raw_provider_response":response.raw_response, "provider":response.provider, "model":response.model, "token_telemetry":{"input":response.input_tokens,"output":response.output_tokens,"total":response.total_tokens,"cost_usd":response.cost_usd}, "attempt":response.attempts, "escalation_reason":response.escalation_reason, "validation":{"accepted":validation.accepted,"reasons":validation.reasons}, "handoff":s0_handoff(packet, validation)}
    if ledger_path:
        ledger_path.parent.mkdir(parents=True, exist_ok=True); ledger_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result
