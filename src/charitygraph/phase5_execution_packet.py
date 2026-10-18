"""Provider-independent Phase-5 semantic execution packets."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence_store import ContentAddressedArtifactStore
from .native_discovery_executor import render_discovery_prompt
from .phase5_semantic_contracts import SemanticContract, sha256_json


class ExecutionPacketUnready(RuntimeError):
    """Required governed packet material cannot be resolved exactly."""


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    artifact_id: str
    source_artifact_id: str
    content_hash: str
    byte_count: int
    content: str
    source_record_id: str
    source_family: str
    source_role: str
    source_locator: str
    locator_ids: tuple[str, ...]


@dataclass(frozen=True)
class GovernedScope:
    scope_id: str
    scope_kind: str
    label: str


@dataclass(frozen=True)
class GovernedIdentityBinding:
    binding_id: str
    scheme: str
    identifier_value: str
    issuing_authority: str
    valid_from: str | None
    valid_to: str | None
    source_record_ids: tuple[str, ...]
    material_hash: str


@dataclass(frozen=True)
class SemanticExecutionPacket:
    logical_task_id: str
    subject_id: str
    semantic_contract_id: str
    semantic_contract_hash: str
    evidence_corpus_hash: str
    evidence_units: tuple[EvidenceUnit, ...]
    scopes: tuple[GovernedScope, ...]
    identity_bindings: tuple[GovernedIdentityBinding, ...]
    supplied_concept_ids: tuple[str, ...]
    route: dict[str, Any]
    packet_hash: str
    demand: dict[str, Any] | None = None

    def material(self) -> dict[str, Any]:
        return {
            "logical_task_id": self.logical_task_id,
            "subject_id": self.subject_id,
            "semantic_contract_id": self.semantic_contract_id,
            "semantic_contract_hash": self.semantic_contract_hash,
            "evidence_corpus_hash": self.evidence_corpus_hash,
            "evidence_units": [
                {"evidence_id": item.evidence_id, "artifact_id": item.artifact_id, "source_artifact_id": item.source_artifact_id, "content_hash": item.content_hash, "byte_count": item.byte_count, "content": item.content, "source_record_id": item.source_record_id, "source_family": item.source_family, "source_role": item.source_role, "source_locator": item.source_locator, "locator_ids": list(item.locator_ids)}
                for item in self.evidence_units
            ],
            "scopes": [{"scope_id": item.scope_id, "scope_kind": item.scope_kind, "label": item.label} for item in self.scopes],
            "identity_bindings": [item.__dict__ for item in self.identity_bindings],
            "supplied_concept_ids": list(self.supplied_concept_ids),
            "route": self.route,
            "demand": self.demand,
        }


def _read_catalog_metadata(catalog_path: Path, source_record_ids: set[str], subject_id: str, evidence_locator_ids: tuple[str, ...] = ()) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], tuple[GovernedScope, ...], tuple[GovernedIdentityBinding, ...]]:
    if not catalog_path.is_file() or catalog_path.stat().st_size == 0:
        raise ExecutionPacketUnready(f"governed catalogue is missing or empty: {catalog_path}")
    uri = f"file:{catalog_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        records: dict[str, dict[str, Any]] = {}
        locators: dict[str, dict[str, Any]] = {}
        for record_id in sorted(source_record_ids):
            row = conn.execute("SELECT source_record_id, source_family, source_role, source_locator, payload_ref, payload_hash FROM source_records WHERE source_record_id=?", (record_id,)).fetchone()
            if row is None:
                raise ExecutionPacketUnready(f"governed source record is missing: {record_id}")
            records[record_id] = {"source_record_id": row[0], "source_family": row[1], "source_role": row[2], "source_locator": row[3], "payload_ref": row[4], "payload_hash": row[5]}
        for locator_id in evidence_locator_ids:
            row = conn.execute("SELECT evidence_locator_id, artifact_id, source_record_id, kind, locator_json, material_hash FROM evidence_locators WHERE evidence_locator_id=?", (locator_id,)).fetchone()
            if row is None:
                raise ExecutionPacketUnready(f"governed evidence locator is missing: {locator_id}")
            if row["source_record_id"] not in records:
                raise ExecutionPacketUnready(f"evidence locator is not bound to the retained source record: {locator_id}")
            locators[locator_id] = dict(row)
        scopes = tuple(GovernedScope(str(row[0]), str(row[1]), str(row[2] or "")) for row in conn.execute("SELECT scope_id, scope_kind, label FROM subject_scopes WHERE subject_id=? AND lifecycle_status='active' ORDER BY scope_id", (subject_id,)).fetchall())
        identities: list[GovernedIdentityBinding] = []
        for row in conn.execute("SELECT external_identifier_id, scheme, identifier_value, issuing_authority, valid_from, valid_to, material_json, material_hash FROM external_identifiers WHERE subject_id=? AND status='active' ORDER BY scheme, identifier_value, issuing_authority", (subject_id,)).fetchall():
            try:
                material = json.loads(str(row[6]))
            except json.JSONDecodeError as exc:
                raise ExecutionPacketUnready(f"governed identity binding is not structured JSON: {row[0]}") from exc
            source_record_ids = material.get("source_record_ids") if isinstance(material, dict) else None
            if not isinstance(source_record_ids, list) or not source_record_ids or any(not isinstance(item, str) or not item for item in source_record_ids):
                raise ExecutionPacketUnready(f"governed identity binding lacks source-record provenance: {row[0]}")
            identities.append(GovernedIdentityBinding(
                binding_id=str(row[0]), scheme=str(row[1]), identifier_value=str(row[2]), issuing_authority=str(row[3]),
                valid_from=None if row[4] is None else str(row[4]), valid_to=None if row[5] is None else str(row[5]),
                source_record_ids=tuple(source_record_ids), material_hash=str(row[7]),
            ))
    finally:
        conn.close()
    return records, locators, scopes, tuple(identities)


def _decode_retained(content: bytes, artifact_id: str) -> str:
    if content.startswith(b"%PDF"):
        raise ExecutionPacketUnready(f"PDF evidence has no retained deterministic text representation: {artifact_id}")
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExecutionPacketUnready(f"retained evidence is not deterministically text-readable: {artifact_id}") from exc
    try:
        representation = json.loads(decoded)
    except json.JSONDecodeError:
        return decoded
    if not isinstance(representation, dict) or not isinstance(representation.get("pages"), list):
        return decoded
    return render_source_native_pages(representation, artifact_id)


def render_source_native_pages(representation: dict[str, Any], artifact_id: str = "representation") -> str:
    """Render retained document pages with deterministic source-native locators.

    This is a transport representation only: it preserves every retained page
    in order and adds its source page number/ordinal.  It performs no lexical
    relevance ranking, extraction, or interpretation.
    """
    pages = representation.get("pages")
    if not isinstance(pages, list):
        raise ExecutionPacketUnready(f"retained document representation has no page list: {artifact_id}")
    text: list[str] = []
    for ordinal, page in enumerate(pages, start=1):
        if not isinstance(page, dict) or not isinstance(page.get("text"), str):
            continue
        page_number = page.get("page_number", ordinal)
        if not isinstance(page_number, int) or page_number < 1:
            page_number = ordinal
        text.append(f"[source_native_page:{page_number}]\n{page['text']}")
    if not text:
        raise ExecutionPacketUnready(f"retained document representation has no deterministic text: {artifact_id}")
    return "\n\n".join(text)


def _materialize_units(corpus: dict[str, Any], store: ContentAddressedArtifactStore, catalog_path: Path, *, require_locators: bool = False) -> tuple[EvidenceUnit, ...]:
    members = sorted(corpus.get("material_members", []), key=lambda item: (item.get("source_family", ""), tuple(item.get("source_record_ids", []))))
    source_ids = {str(record_id) for member in members for record_id in member.get("source_record_ids", [])}
    locator_ids = tuple(str(value) for member in members for value in member.get("evidence_locator_ids", []))
    if require_locators and not locator_ids:
        raise ExecutionPacketUnready("Discovery V2 packet has no governed evidence-locator IDs")
    records, locators, _, _ = _read_catalog_metadata(catalog_path, source_ids, str(corpus["subject_id"]), locator_ids)
    units: list[EvidenceUnit] = []
    for member in members:
        record_ids = [str(value) for value in member.get("source_record_ids", [])]
        if not record_ids:
            continue
        member_locator_ids = tuple(str(value) for value in member.get("evidence_locator_ids", []))
        if require_locators and not member_locator_ids:
            raise ExecutionPacketUnready(f"direct-service evidence locators are absent for {record_ids[0]}")
        artifact_ids = [str(value) for value in (member.get("representation_artifact_ids") or member.get("artifact_ids") or [])]
        if not artifact_ids:
            raise ExecutionPacketUnready(f"no retained artifact or representation for {record_ids[0]}")
        for index, artifact_id in enumerate(artifact_ids):
            try:
                content_bytes = store.read(artifact_id)
            except Exception as exc:
                raise ExecutionPacketUnready(f"retained artifact cannot be read and hash-verified: {artifact_id}") from exc
            digest = hashlib.sha256(content_bytes).hexdigest()
            expected = artifact_id.split(":", 1)[1]
            if digest != expected:
                raise ExecutionPacketUnready(f"retained artifact hash mismatch: {artifact_id}")
            record = records[record_ids[min(index, len(record_ids) - 1)]]
            if record["payload_hash"] and artifact_id.startswith("srcblob:") and record["payload_hash"] != digest:
                raise ExecutionPacketUnready(f"source record payload hash disagrees with artifact: {record['source_record_id']}")
            represented = member_locator_ids if require_locators else (record["source_record_id"],)
            for evidence_id in represented:
                locator = locators.get(evidence_id)
                if require_locators and locator is None:
                    raise ExecutionPacketUnready(f"governed evidence locator is missing: {evidence_id}")
                if locator is not None and locator.get("artifact_id") and locator["artifact_id"] != artifact_id:
                    raise ExecutionPacketUnready(f"evidence locator does not resolve to the retained artifact: {evidence_id}")
                units.append(EvidenceUnit(
                    evidence_id=evidence_id, artifact_id=artifact_id,
                    source_artifact_id=record["payload_ref"], content_hash=digest,
                    byte_count=len(content_bytes), content=_decode_retained(content_bytes, artifact_id),
                    source_record_id=record["source_record_id"], source_family=record["source_family"],
                    source_role=record["source_role"], source_locator=record["source_locator"], locator_ids=(evidence_id,) if require_locators else (),
                ))
    if not units:
        raise ExecutionPacketUnready("corpus contains no materializable evidence units")
    return tuple(units)


def materialize_execution_packet(*, task: dict[str, Any], corpus: dict[str, Any], contract: SemanticContract, runtime_root: Path, catalog_path: Path, model: str, reasoning_effort: str, service_tier: str) -> SemanticExecutionPacket:
    require_locators = contract.task_profile in {"program_service_discovery", "direct_service_semantics"}
    if require_locators:
        source_ids = {str(record_id) for member in corpus.get("material_members", []) for record_id in member.get("source_record_ids", [])}
        _, _, existing_scopes, _ = _read_catalog_metadata(catalog_path, source_ids, task["subject_id"])
        if contract.task_profile == "direct_service_semantics" and not existing_scopes:
            raise ExecutionPacketUnready(f"direct-service packet lacks frozen evidence locators and governed active scopes for {task['subject_id']}")
    units = _materialize_units(corpus, ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,)), catalog_path, require_locators=require_locators)
    _, _, scopes, identity_bindings = _read_catalog_metadata(catalog_path, {item.source_record_id for item in units}, task["subject_id"])
    if contract.task_profile == "direct_service_semantics" and not scopes:
        raise ExecutionPacketUnready(f"no governed active scopes for direct-service subject: {task['subject_id']}")
    if contract.task_profile == "direct_service_semantics" and any(scope.scope_id.startswith("srcrec:") for scope in scopes):
        raise ExecutionPacketUnready("source record IDs cannot be used as direct-service scope IDs")
    route = {"model": model, "reasoning_effort": reasoning_effort, "service_tier": service_tier}
    demand = task.get("demand")
    if demand is not None and not isinstance(demand, dict):
        raise ExecutionPacketUnready("task demand binding must be an object")
    proposition_ids = () if not isinstance(demand, dict) else tuple(item["proposition_id"] for item in __import__("charitygraph.frozen_experiment", fromlist=["demand_propositions"]).demand_propositions(demand.get("semantic_signature")))
    requirement_ids = () if not isinstance(demand, dict) else tuple(item["requirement_id"] for item in __import__("charitygraph.frozen_experiment", fromlist=["demand_requirements"]).demand_requirements(demand.get("semantic_signature")))
    identity_hash = contract.schema_hash_for_packet(tuple(item.evidence_id for item in units), proposition_ids, requirement_ids)
    material = {"logical_task_id": task["logical_task_id"], "subject_id": task["subject_id"], "semantic_contract_id": contract.contract_id, "semantic_contract_hash": identity_hash, "evidence_corpus_hash": task["evidence_corpus_hash"], "evidence_units": [item.__dict__ for item in units], "scopes": [item.__dict__ for item in scopes], "identity_bindings": [item.__dict__ for item in identity_bindings], "supplied_concept_ids": [], "route": route, "demand": demand}
    return SemanticExecutionPacket(task["logical_task_id"], task["subject_id"], contract.contract_id, identity_hash, task["evidence_corpus_hash"], units, scopes, identity_bindings, (), route, sha256_json(material), demand)


def render_packet_prompt(packet: SemanticExecutionPacket, contract: SemanticContract) -> str:
    pairs = tuple((item.evidence_id, item.content) for item in packet.evidence_units)
    if contract.task_profile == "program_service_discovery":
        return render_discovery_prompt(packet.subject_id, pairs, v2=True)
    if contract.task_profile == "direct_service_semantics":
        scope_text = "\n".join(f"{scope.scope_id} | {scope.scope_kind} | {scope.label}" for scope in packet.scopes)
        evidence_text = "\n\n".join(f"[{item.locator_ids[0]}]\n{item.content}" for item in packet.evidence_units)
        return contract.prompt_template.replace("{subject_id}", packet.subject_id).replace("{scope_text}", scope_text).replace("{evidence}", evidence_text)
    if contract.task_profile == "evidence_selection":
        demand = getattr(packet, "demand", None)
        if not isinstance(demand, dict) or not isinstance(demand.get("demand_id"), str) or not isinstance(demand.get("semantic_signature"), str):
            raise ExecutionPacketUnready("frozen evidence assessment requires a pinned demand ID and signature")
        evidence_text = "\n\n".join(f"[{item.evidence_id}]\n{item.content}" for item in packet.evidence_units)
        from .frozen_experiment import demand_propositions, demand_requirements
        propositions = demand_propositions(demand["semantic_signature"])
        proposition_text = "\n".join(f"{item['proposition_id']} | {item['proposition']}" for item in propositions)
        requirement_text = json.dumps(demand_requirements(demand["semantic_signature"]), ensure_ascii=False, sort_keys=True)
        identity_text = json.dumps([item.__dict__ for item in packet.identity_bindings], ensure_ascii=False, sort_keys=True) or "[]"
        return (contract.prompt_template.replace("{subject_id}", packet.subject_id)
                .replace("{demand_id}", demand["demand_id"])
                .replace("{identity_bindings}", identity_text)
                .replace("{propositions}", proposition_text)
                .replace("{demand_requirements}", requirement_text)
                .replace("{evidence}", evidence_text))
    raise ExecutionPacketUnready(f"no executable packet renderer for {contract.task_profile}")


__all__ = ["ExecutionPacketUnready", "EvidenceUnit", "GovernedScope", "GovernedIdentityBinding", "SemanticExecutionPacket", "materialize_execution_packet", "render_packet_prompt", "render_source_native_pages"]
