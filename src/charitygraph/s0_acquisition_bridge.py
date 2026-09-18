"""Offline, mandate-bound bridge from S0 source plans to frozen packets.

This module deliberately contains no HTTP client and no provider entry point.
Callers supply fixture bytes (or a separately governed transport result); the
bridge owns the authority, snapshot, representation, corpus and packet
bindings that make those bytes usable by the existing S0 preflight.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable, Mapping

from charitygraph.scale_s0 import (
    DocumentRepresentation, FrozenPacket, HaltController, LogicalTaskRegistry,
    PolicyArtifact, ProcessingDisposition, RepresentationPolicy, RoutingPolicy,
    ScaleMandate, ScalePreflightError, SourceAuthorisation,
)


def _hash(value: object) -> str:
    def default(item: object) -> object:
        return asdict(item) if hasattr(item, "__dataclass_fields__") else str(item)
    return sha256(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _utc(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ScalePreflightError("bridge timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class MandatePopulation:
    """Canonical population whose membership is derived only from the mandate."""
    mandate_id: str
    subject_ids: tuple[str, ...]
    population_hash: str

    @classmethod
    def from_mandate(cls, mandate: ScaleMandate, supplied: Iterable[str]) -> "MandatePopulation":
        expected = tuple(sorted(mandate.subject_ids))
        actual = tuple(sorted(str(item) for item in supplied))
        if len(actual) != len(set(actual)) or actual != expected:
            raise ScalePreflightError("population differs from the immutable mandate")
        # The authority package pins the policy artefact hash.  This local
        # digest identifies the order-independent exact subject membership.
        return cls(mandate.mandate_id, expected, _hash({"mandate": mandate.identity_hash, "subjects": expected}))


@dataclass(frozen=True)
class SourcePlan:
    mandate_id: str
    mandate_hash: str
    slice_id: str
    subject_id: str
    subject_scope: str
    source_family: str
    acquisition_mechanism: str
    policy_classification: str
    source_role: str
    authority_role: str
    requirement: str
    locator: str
    source_universe_policy_hash: str
    created_at: str

    @property
    def plan_id(self) -> str:
        return "source-plan:" + _hash(asdict(self))


class SourcePlanner:
    """Central source discovery boundary; it cannot accept semantic URLs."""
    _families = frozenset({"acnc_register", "acnc_ais", "abr_dgr", "official_website", "latest_authorised_annual_report", "fundraising_registry", "specialist"})

    def __init__(self, mandate: ScaleMandate) -> None:
        self.mandate = mandate

    def plan(self, *, subject_id: str, scope_id: str, source_family: str, acquisition_mechanism: str,
             policy_classification: str, source_role: str, authority_role: str, requirement: str,
             locator: str = "", created_at: datetime | None = None) -> SourcePlan:
        if subject_id not in self.mandate.subject_ids or not scope_id:
            raise ScalePreflightError("source plan is outside the mandate population or scope")
        if source_family not in self._families or source_family not in self.mandate.applicable_source_families:
            raise ScalePreflightError("source family is outside the governed source universe")
        if requirement not in {"mandatory", "conditional", "specialist"}:
            raise ScalePreflightError("source plan requirement is invalid")
        if requirement == "mandatory" and source_family not in self.mandate.mandatory_source_families:
            raise ScalePreflightError("mandatory plan is not mandated")
        if requirement == "specialist" and source_family != "specialist":
            raise ScalePreflightError("specialist plan must use the specialist family")
        return SourcePlan(self.mandate.mandate_id, self.mandate.identity_hash, self.mandate.slice_id, subject_id,
                          scope_id, source_family, acquisition_mechanism, policy_classification, source_role,
                          authority_role, requirement, locator, self.mandate.policy_hashes["source_universe"], _utc(created_at))


@dataclass(frozen=True)
class OfflineResponse:
    content: bytes
    media_type: str
    locator: str
    status: int = 200
    redirected_locator: str | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    plan_id: str
    source_id: str
    source_record_id: str
    snapshot_hash: str
    media_type: str
    locator: str
    retrieved_at: str
    acquisition_state: str
    representation: DocumentRepresentation
    representation_mode: str
    artifact_id: str


class GovernedAcquisition:
    """Consumes fixture/transport bytes only after plan and authority checks."""
    def __init__(self, mandate: ScaleMandate, halts: HaltController | None = None) -> None:
        self.mandate, self.halts = mandate, halts or HaltController()
        self._snapshots: dict[str, SourceSnapshot] = {}

    def acquire(self, plan: SourcePlan, authorisation: SourceAuthorisation, response: OfflineResponse,
                *, representation: DocumentRepresentation, representation_mode: str, artifact_store: object | None = None,
                now: datetime | None = None) -> SourceSnapshot:
        if plan.mandate_id != self.mandate.mandate_id or plan.mandate_hash != self.mandate.identity_hash:
            raise ScalePreflightError("source plan is stale or substituted")
        if plan.subject_id not in self.mandate.subject_ids or plan.source_family != authorisation.source_family:
            raise ScalePreflightError("source authorisation is outside its plan")
        if self.halts.active(slice_id=plan.slice_id, task_key="source-acquisition", subject_id=plan.subject_id):
            raise ScalePreflightError("hard halt prevents acquisition")
        if authorisation.access_classification == "TECHNICALLY_WITHHELD" or authorisation.technical_access_state != "accessible":
            raise ScalePreflightError("technical access control prevents acquisition")
        if authorisation.access_classification == "SEPARATELY_LICENSED_OR_CONTROLLED" and not authorisation.specialist_authorisation_id:
            raise ScalePreflightError("controlled source lacks specific authority")
        if authorisation.access_classification == "OPEN_WEB_PUBLIC" and authorisation.rights_transmission_status not in {"permitted_open_web_policy", "permitted"}:
            raise ScalePreflightError("open web source lacks rights-policy authority")
        if response.status != 200 or not response.content or (response.redirected_locator and response.redirected_locator != response.locator):
            raise ScalePreflightError("fixture acquisition is unavailable or redirects outside its plan")
        RepresentationPolicy(representation, representation_mode, representation == DocumentRepresentation.VISUALLY_MATERIAL_PDF).validate()
        digest = sha256(response.content).hexdigest()
        key = _hash({"plan": plan.plan_id, "locator": response.locator, "snapshot": digest})
        existing = self._snapshots.get(key)
        if existing:
            return existing
        artifact_id = "srcblob:" + digest
        if artifact_store is not None:
            stored = artifact_store.put(response.content, artifact_kind="source", created_at=now)
            artifact_id = stored.artifact_id
        source_id = "source:" + _hash({"plan": plan.plan_id, "snapshot": digest})
        snapshot = SourceSnapshot(plan.plan_id, source_id, "source-record:" + _hash({"source": source_id}), digest,
                                  response.media_type, response.locator, _utc(now), "acquired", representation,
                                  representation_mode, artifact_id)
        self._snapshots[key] = snapshot
        return snapshot


@dataclass(frozen=True)
class FrozenCorpus:
    mandate_id: str
    mandate_hash: str
    slice_id: str
    subject_id: str
    source_record_ids: tuple[str, ...]
    snapshot_hashes: tuple[str, ...]
    representations: tuple[str, ...]
    exclusions: tuple[str, ...]
    frozen_at: str

    @property
    def corpus_id(self) -> str:
        return "corpus:" + _hash(asdict(self))


def freeze_corpus(mandate: ScaleMandate, subject_id: str, snapshots: Iterable[SourceSnapshot], *, exclusions: Iterable[str] = (), now: datetime | None = None) -> FrozenCorpus:
    rows = tuple(sorted(snapshots, key=lambda item: item.source_record_id))
    if subject_id not in mandate.subject_ids or not rows or any(not item.snapshot_hash for item in rows):
        raise ScalePreflightError("corpus requires governed snapshots for one mandated subject")
    return FrozenCorpus(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, subject_id,
                        tuple(item.source_record_id for item in rows), tuple(item.snapshot_hash for item in rows),
                        tuple(item.representation.value for item in rows), tuple(sorted(exclusions)), _utc(now))


@dataclass(frozen=True)
class TaskApplicability:
    task_id: str
    task_version: str
    subject_id: str
    scope_id: str
    state: str
    corpus_id: str
    reason: str


def task_applicability(registry: LogicalTaskRegistry, mandate: ScaleMandate, corpus: FrozenCorpus, *, scope_id: str) -> tuple[TaskApplicability, ...]:
    if corpus.mandate_id != mandate.mandate_id or corpus.mandate_hash != mandate.identity_hash:
        raise ScalePreflightError("corpus is not bound to this mandate")
    states: list[TaskApplicability] = []
    parsed = set(corpus.representations)
    for task in registry.contracts:
        if task.task_id not in mandate.enabled_task_ids:
            continue
        state = "HUMAN_ONLY" if task.default_routing.value == "human_decision" else "APPLICABLE"
        if task.family == "finance_source_native" and DocumentRepresentation.NATIVE_STRUCTURED.value not in parsed:
            state = "SOURCE_NOT_ACQUIRED"
        if DocumentRepresentation.PARSING_FAILURE.value in parsed and state == "APPLICABLE":
            state = "REPRESENTATION_FAILED"
        states.append(TaskApplicability(task.task_id, task.version, corpus.subject_id, scope_id, state, corpus.corpus_id, "representation-and-source-role-derived"))
    return tuple(states)


def frozen_packets(mandate: ScaleMandate, registry: LogicalTaskRegistry, corpus: FrozenCorpus,
                   snapshots: Iterable[SourceSnapshot], applicability: Iterable[TaskApplicability], *, now: datetime | None = None) -> tuple[FrozenPacket, ...]:
    by_record = {item.source_record_id: item for item in snapshots}
    packets: list[FrozenPacket] = []
    for item in applicability:
        if item.state != "APPLICABLE":
            continue
        task = registry.get(item.task_id, item.task_version)
        source_ids = tuple(by_record[record].source_id for record in corpus.source_record_ids)
        source_hashes = tuple(by_record[record].snapshot_hash for record in corpus.source_record_ids)
        material = {"mandate": mandate.identity_hash, "corpus": corpus.corpus_id, "task": task.key, "sources": source_hashes}
        packets.append(FrozenPacket("packet:" + _hash(material), task.task_id, task.version, corpus.subject_id, item.scope_id,
                                    source_ids, source_hashes, task.input_profile_id, task.output_schema_id,
                                    task.default_routing, "provider-request:" + _hash(material), _hash(material),
                                    mandate_id=mandate.mandate_id, slice_id=mandate.slice_id, frozen_at=_utc(now)))
    return tuple(packets)
