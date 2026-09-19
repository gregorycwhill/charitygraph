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
from io import BytesIO
import json
from pathlib import Path
from typing import Iterable, Mapping

from charitygraph.contracts import AcquisitionReceipt, PropositionAuthorityRole, SourceDefinition, SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.document_v2.pipeline import extract_document
from charitygraph.scale_s0 import (
    DocumentRepresentation, FrozenPacket, HaltController, LogicalTaskRegistry,
    PolicyArtifact, ProcessingDisposition, RepresentationPolicy, RoutingPolicy,
    ScaleMandate, ScalePreflightError, ScaleS0Preflight, SourceAuthorisation,
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

    @property
    def snapshot_id(self) -> str:
        return self.source_id


@dataclass(frozen=True)
class RepresentationRecord:
    representation_id: str
    snapshot_id: str
    snapshot_hash: str
    representation_kind: str
    representation_mode: str
    document_hash: str
    selected_pages: tuple[int, ...]
    rendered_page_artifact_ids: tuple[str, ...]
    lineage: Mapping[str, object]
    created_at: str


def represent_document(snapshot: SourceSnapshot, document: Path, *, visually_material: bool,
                       artifact_store: object | None = None, cache_root: Path | None = None,
                       now: datetime | None = None) -> RepresentationRecord:
    """Run document-v2 locally and bind its exact output to one source snapshot."""
    payload = document.read_bytes()
    if sha256(payload).hexdigest() != snapshot.snapshot_hash:
        raise ScalePreflightError("document bytes do not match the frozen source snapshot")
    result = extract_document(document, cache_root=cache_root)
    if result.get("status") != "completed":
        kind, mode, pages, rendered = DocumentRepresentation.PARSING_FAILURE.value, "not_processable", (), ()
    elif visually_material:
        # A visual document is usable only with an explicitly rendered page;
        # native text extraction alone can never silently satisfy this path.
        try:
            import pdfplumber
            with pdfplumber.open(document) as pdf:
                image = pdf.pages[0].to_image(resolution=72).original
            buffer = BytesIO(); image.save(buffer, format="PNG")
            rendering = buffer.getvalue()
        except Exception as error:
            raise ScalePreflightError("visual document could not produce a rendered-page representation") from error
        if not rendering:
            raise ScalePreflightError("visual document rendered-page representation is empty")
        artifact_id = "rendered-page:" + sha256(rendering).hexdigest()
        if artifact_store is not None:
            artifact_id = artifact_store.put_derived(rendering, input_artifact_ids=(snapshot.artifact_id,), created_at=now).artifact_id
        kind, mode, pages, rendered = DocumentRepresentation.VISUALLY_MATERIAL_PDF.value, "page_rendered_visual", (1,), (artifact_id,)
    else:
        kind, mode, pages, rendered = DocumentRepresentation.RELIABLE_TEXT.value, "text_extraction_only", tuple(page["page"] for page in result.get("pages", ())), ()
    material = {"snapshot": snapshot.snapshot_id, "snapshot_hash": snapshot.snapshot_hash, "kind": kind, "mode": mode,
                "document_hash": result.get("document", {}).get("sha256", snapshot.snapshot_hash), "pages": pages,
                "rendered": rendered, "lineage": result.get("lineage", {})}
    return RepresentationRecord("representation:" + _hash(material), snapshot.snapshot_id, snapshot.snapshot_hash, kind, mode,
                                str(material["document_hash"]), pages, rendered, result.get("lineage", {}), _utc(now))


class GovernedAcquisition:
    """Consumes fixture/transport bytes only after plan and authority checks."""
    def __init__(self, mandate: ScaleMandate, halts: HaltController | None = None) -> None:
        self.mandate, self.halts = mandate, halts or HaltController()
        self._snapshots: dict[str, SourceSnapshot] = {}

    def acquire_transport(self, plan: SourcePlan, authorisation: SourceAuthorisation, transport: object,
                          *, representation: DocumentRepresentation, representation_mode: str,
                          artifact_store: object | None = None, catalog: object | None = None,
                          now: datetime | None = None, execution_attempt_id: str | None = None) -> SourceSnapshot:
        """Cross the governed transport boundary, then use this acquisition path."""
        result = transport.fetch(plan, authorisation, self.mandate, halts=self.halts, now=now, catalog=catalog, execution_attempt_id=execution_attempt_id)
        response = OfflineResponse(result.content, result.media_type, result.final_locator, result.status)
        return self.acquire(plan, authorisation, response, representation=representation,
                            representation_mode=representation_mode, artifact_store=artifact_store,
                            catalog=catalog, now=now)

    def acquire(self, plan: SourcePlan, authorisation: SourceAuthorisation, response: OfflineResponse,
                *, representation: DocumentRepresentation, representation_mode: str, artifact_store: object | None = None,
                catalog: object | None = None, now: datetime | None = None) -> SourceSnapshot:
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
        source_record_id = deterministic_id("srcrec:", {"source_family": plan.source_family, "source_version": "s0-bridge-v1",
            "source_locator": response.locator, "payload_hash": digest})
        snapshot = SourceSnapshot(plan.plan_id, source_id, source_record_id, digest,
                                  response.media_type, response.locator, _utc(now), "acquired", representation,
                                  representation_mode, artifact_id)
        if catalog is not None:
            when = now or datetime.now(timezone.utc)
            if when.tzinfo is None:
                raise ScalePreflightError("acquisition timestamp must be timezone-aware")
            definition = SourceDefinition(record_id="srcdef:" + _hash({"family": plan.source_family, "mechanism": plan.acquisition_mechanism}),
                created_at=when, producer={"kind": "code", "producer_id": "scale-s0-acquisition-bridge", "version": "1"},
                definition_version="1", publisher=plan.authority_role, source_class=plan.source_family,
                authority_roles=(PropositionAuthorityRole(proposition=plan.source_role, role=plan.authority_role, basis="mandate-bound source plan"),),
                acquisition_locator=plan.locator or response.locator, acquisition_method=plan.acquisition_mechanism,
                temporal_semantics="retrieved_fixture_snapshot", publication_eligibility="private_review_only",
                steward="CharityGraph S0 acquisition bridge")
            catalog.register_source_definition(definition)
            catalog.register_source_record(SourceRecord(record_id=snapshot.source_record_id, created_at=when,
                producer={"kind": "code", "producer_id": "scale-s0-acquisition-bridge", "version": "1"}, source_family=plan.source_family,
                source_role=plan.source_role, source_version="s0-bridge-v1", source_locator=response.locator,
                retrieved_at=when, observed_at=when, media_type=response.media_type, payload_ref=artifact_id, payload_hash=digest,
                attribution=plan.authority_role))
            catalog.record_acquisition_receipt(AcquisitionReceipt(record_id="acq:" + _hash({"plan": plan.plan_id, "snapshot": digest}),
                created_at=when, producer={"kind": "code", "producer_id": "scale-s0-acquisition-bridge", "version": "1"},
                source_definition_id=definition.record_id, requested_locator=plan.locator or response.locator, resolved_locator=response.locator,
                retrieved_at=when, outcome="available", response_status=response.status, media_type=response.media_type,
                content_hash=digest, byte_size=len(response.content), artifact_id=artifact_id, tool_id=plan.acquisition_mechanism,
                tool_version="1", material_parameters={"source_plan_id": plan.plan_id, "mandate_id": plan.mandate_id, "subject_id": plan.subject_id}))
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
                                    mandate_id=mandate.mandate_id, slice_id=mandate.slice_id, frozen_at=_utc(now), corpus_id=corpus.corpus_id))
    return tuple(packets)


@dataclass(frozen=True)
class PhysicalBundle:
    bundle_id: str
    mandate_id: str
    routing_class: str
    packet_ids: tuple[str, ...]
    packet_hashes: tuple[str, ...]
    frozen_at: str


def bundle_packets(mandate: ScaleMandate, packets: Iterable[FrozenPacket], *, now: datetime | None = None) -> tuple[PhysicalBundle, ...]:
    """Apply the approved compatibility rule without collapsing logical tasks."""
    groups: dict[tuple[str, str], list[FrozenPacket]] = {}
    for packet in packets:
        if packet.routing_class.value == "human_decision":
            raise ScalePreflightError("human-only work cannot become a provider bundle")
        # Packets are compatible only when they have exactly the same frozen
        # corpus material and route.  Strong tasks therefore never enter a
        # low-cost group.
        key = (packet.routing_class.value, _hash((packet.source_snapshot_hashes, packet.subject_id, packet.scope_id)))
        groups.setdefault(key, []).append(packet)
    result: list[PhysicalBundle] = []
    for (route, _), items in sorted(groups.items()):
        ids = tuple(sorted(item.packet_id for item in items))
        hashes = tuple(sorted(item.binding_hash for item in items))
        material = {"mandate": mandate.identity_hash, "route": route, "packets": hashes}
        result.append(PhysicalBundle("bundle:" + _hash(material), mandate.mandate_id, route, ids, hashes, _utc(now)))
    return tuple(result)


def source_authorisations(mandate: ScaleMandate, registry: LogicalTaskRegistry, snapshots: Iterable[SourceSnapshot],
                          plans: Mapping[str, SourcePlan]) -> dict[str, SourceAuthorisation]:
    """Derive preflight source authority from immutable plan/snapshot bindings."""
    result: dict[str, SourceAuthorisation] = {}
    families = tuple(task.family for task in registry.contracts)
    for snapshot in snapshots:
        plan = plans.get(snapshot.plan_id)
        if plan is None or plan.mandate_id != mandate.mandate_id or snapshot.acquisition_state != "acquired":
            raise ScalePreflightError("source snapshot is not governed by this mandate plan")
        classification = plan.policy_classification
        if classification not in {"OPEN_WEB_PUBLIC", "SEPARATELY_LICENSED_OR_CONTROLLED"}:
            raise ScalePreflightError("unavailable or withheld sources cannot enter packet authority")
        result[snapshot.source_id] = SourceAuthorisation(snapshot.source_id, plan.source_family, snapshot.locator,
            plan.authority_role, "permitted_open_web_policy" if classification == "OPEN_WEB_PUBLIC" else "permitted",
            "acquired", "structured" if snapshot.representation == DocumentRepresentation.NATIVE_STRUCTURED else "parsed",
            snapshot.snapshot_hash, families, snapshot.source_record_id, mandate.rights_transmission_policy_id,
            mandate.specialist_source_policy_id if plan.source_family == "specialist" else None, classification, "accessible")
    return result


def persist_bridge(catalog: object, mandate: ScaleMandate, *, plans: Iterable[SourcePlan], snapshots: Iterable[SourceSnapshot],
                   corpora: Iterable[FrozenCorpus], bundles: Iterable[PhysicalBundle], representations: Iterable[RepresentationRecord] = (), execution_attempt_id: str | None = None, offline: bool = False) -> None:
    """Persist all bridge control-plane transitions idempotently in migration 18."""
    plan_rows = {plan.plan_id: plan for plan in plans}
    for plan in plan_rows.values():
        catalog.register_scale_s0_source_plan({**asdict(plan), "plan_id": plan.plan_id}, execution_attempt_id=execution_attempt_id, offline=offline)
    snapshot_rows = tuple(snapshots)
    for snapshot in snapshot_rows:
        if snapshot.plan_id not in plan_rows:
            raise ScalePreflightError("cannot persist a snapshot without its plan")
        catalog.register_scale_s0_source_snapshot({**asdict(snapshot), "snapshot_id": snapshot.snapshot_id,
            "acquired_at": snapshot.retrieved_at, "representation": snapshot.representation.value}, mandate_id=mandate.mandate_id, execution_attempt_id=execution_attempt_id, offline=offline)
    supplied = tuple(representations)
    if not supplied:
        supplied = tuple(RepresentationRecord("representation:" + _hash({"snapshot": snapshot.snapshot_id, "kind": snapshot.representation.value, "mode": snapshot.representation_mode}),
            snapshot.snapshot_id, snapshot.snapshot_hash, snapshot.representation.value, snapshot.representation_mode,
            snapshot.snapshot_hash, (), (), {}, snapshot.retrieved_at) for snapshot in snapshot_rows)
    for representation in supplied:
        catalog.register_scale_s0_representation({**asdict(representation), "representation_kind": representation.representation_kind}, mandate_id=mandate.mandate_id, execution_attempt_id=execution_attempt_id, offline=offline)
    for corpus in corpora:
        catalog.register_scale_s0_frozen_corpus({**asdict(corpus), "corpus_id": corpus.corpus_id}, execution_attempt_id=execution_attempt_id)
    for bundle in bundles:
        catalog.register_scale_s0_physical_bundle(asdict(bundle), execution_attempt_id=execution_attempt_id, offline=offline)


def certified_preflight(mandate: ScaleMandate, registry: LogicalTaskRegistry, routing: RoutingPolicy,
                        policies: Mapping[str, PolicyArtifact], snapshots: Iterable[SourceSnapshot], plans: Mapping[str, SourcePlan],
                        packets: Iterable[FrozenPacket], halts: HaltController | None = None) -> ScaleS0Preflight:
    """Construct the existing preflight boundary; it has no send or reservation action."""
    packet_map = {packet.binding_hash: packet for packet in packets}
    return ScaleS0Preflight(mandate, registry, routing, source_authorisations(mandate, registry, snapshots, plans),
                            halts or HaltController(), packets=packet_map, policies=policies, economics=None)
