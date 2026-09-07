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
class SemanticExecutionPacket:
    logical_task_id: str
    subject_id: str
    semantic_contract_id: str
    semantic_contract_hash: str
    evidence_corpus_hash: str
    evidence_units: tuple[EvidenceUnit, ...]
    scopes: tuple[GovernedScope, ...]
    supplied_concept_ids: tuple[str, ...]
    route: dict[str, Any]
    packet_hash: str

    def material(self) -> dict[str, Any]:
        return {
            "logical_task_id": self.logical_task_id,
            "subject_id": self.subject_id,
            "semantic_contract_id": self.semantic_contract_id,
            "semantic_contract_hash": self.semantic_contract_hash,
            "evidence_corpus_hash": self.evidence_corpus_hash,
            "evidence_units": [
                {"evidence_id": item.evidence_id, "artifact_id": item.artifact_id, "content_hash": item.content_hash, "byte_count": item.byte_count, "content": item.content, "source_record_id": item.source_record_id, "source_family": item.source_family, "source_role": item.source_role, "source_locator": item.source_locator, "locator_ids": list(item.locator_ids)}
                for item in self.evidence_units
            ],
            "scopes": [{"scope_id": item.scope_id, "scope_kind": item.scope_kind, "label": item.label} for item in self.scopes],
            "supplied_concept_ids": list(self.supplied_concept_ids),
            "route": self.route,
        }


def _read_catalog_metadata(catalog_path: Path, source_record_ids: set[str], subject_id: str) -> tuple[dict[str, dict[str, Any]], tuple[GovernedScope, ...]]:
    if not catalog_path.is_file() or catalog_path.stat().st_size == 0:
        raise ExecutionPacketUnready(f"governed catalogue is missing or empty: {catalog_path}")
    uri = f"file:{catalog_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        records: dict[str, dict[str, Any]] = {}
        for record_id in sorted(source_record_ids):
            row = conn.execute("SELECT source_record_id, source_family, source_role, source_locator, payload_ref, payload_hash FROM source_records WHERE source_record_id=?", (record_id,)).fetchone()
            if row is None:
                raise ExecutionPacketUnready(f"governed source record is missing: {record_id}")
            records[record_id] = {"source_record_id": row[0], "source_family": row[1], "source_role": row[2], "source_locator": row[3], "payload_ref": row[4], "payload_hash": row[5]}
        scopes = tuple(GovernedScope(str(row[0]), str(row[1]), str(row[2] or "")) for row in conn.execute("SELECT scope_id, scope_kind, label FROM subject_scopes WHERE subject_id=? AND lifecycle_status='active' ORDER BY scope_id", (subject_id,)).fetchall())
    finally:
        conn.close()
    return records, scopes


def _decode_retained(content: bytes, artifact_id: str) -> str:
    if content.startswith(b"%PDF"):
        raise ExecutionPacketUnready(f"PDF evidence has no retained deterministic text representation: {artifact_id}")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExecutionPacketUnready(f"retained evidence is not deterministically text-readable: {artifact_id}") from exc


def _materialize_units(corpus: dict[str, Any], store: ContentAddressedArtifactStore, catalog_path: Path, *, require_locators: bool = False) -> tuple[EvidenceUnit, ...]:
    members = sorted(corpus.get("material_members", []), key=lambda item: (item.get("source_family", ""), tuple(item.get("source_record_ids", []))))
    source_ids = {str(record_id) for member in members for record_id in member.get("source_record_ids", [])}
    records, _ = _read_catalog_metadata(catalog_path, source_ids, str(corpus["subject_id"]))
    units: list[EvidenceUnit] = []
    for member in members:
        record_ids = [str(value) for value in member.get("source_record_ids", [])]
        if not record_ids:
            continue
        locator_ids = tuple(str(value) for value in member.get("evidence_locator_ids", []))
        if require_locators and not locator_ids:
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
            units.append(EvidenceUnit(
                evidence_id=record["source_record_id"], artifact_id=artifact_id, content_hash=digest,
                byte_count=len(content_bytes), content=_decode_retained(content_bytes, artifact_id),
                source_record_id=record["source_record_id"], source_family=record["source_family"],
                source_role=record["source_role"], source_locator=record["source_locator"], locator_ids=locator_ids,
            ))
    if not units:
        raise ExecutionPacketUnready("corpus contains no materializable evidence units")
    return tuple(units)


def materialize_execution_packet(*, task: dict[str, Any], corpus: dict[str, Any], contract: SemanticContract, runtime_root: Path, catalog_path: Path, model: str, reasoning_effort: str, service_tier: str) -> SemanticExecutionPacket:
    require_locators = contract.task_profile == "direct_service_semantics"
    if require_locators:
        source_ids = {str(record_id) for member in corpus.get("material_members", []) for record_id in member.get("source_record_ids", [])}
        _, existing_scopes = _read_catalog_metadata(catalog_path, source_ids, task["subject_id"])
        if not existing_scopes:
            raise ExecutionPacketUnready(f"direct-service packet lacks frozen evidence locators and governed active scopes for {task['subject_id']}")
    units = _materialize_units(corpus, ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,)), catalog_path, require_locators=require_locators)
    _, scopes = _read_catalog_metadata(catalog_path, {item.source_record_id for item in units}, task["subject_id"])
    if require_locators and not scopes:
        raise ExecutionPacketUnready(f"no governed active scopes for direct-service subject: {task['subject_id']}")
    if contract.task_profile == "direct_service_semantics" and any(scope.scope_id.startswith("srcrec:") for scope in scopes):
        raise ExecutionPacketUnready("source record IDs cannot be used as direct-service scope IDs")
    route = {"model": model, "reasoning_effort": reasoning_effort, "service_tier": service_tier}
    material = {"logical_task_id": task["logical_task_id"], "subject_id": task["subject_id"], "semantic_contract_id": contract.contract_id, "semantic_contract_hash": contract.identity_hash(tuple(item.evidence_id for item in units)), "evidence_corpus_hash": task["evidence_corpus_hash"], "evidence_units": [item.__dict__ for item in units], "scopes": [item.__dict__ for item in scopes], "supplied_concept_ids": [], "route": route}
    return SemanticExecutionPacket(task["logical_task_id"], task["subject_id"], contract.contract_id, contract.identity_hash(tuple(item.evidence_id for item in units)), task["evidence_corpus_hash"], units, scopes, (), route, sha256_json(material))


def render_packet_prompt(packet: SemanticExecutionPacket, contract: SemanticContract) -> str:
    pairs = tuple((item.evidence_id, item.content) for item in packet.evidence_units)
    if contract.task_profile == "program_service_discovery":
        return render_discovery_prompt(packet.subject_id, pairs, v2=True)
    if contract.task_profile == "direct_service_semantics":
        scope_text = "\n".join(f"{scope.scope_id} | {scope.scope_kind} | {scope.label}" for scope in packet.scopes)
        evidence_text = "\n\n".join(f"[{item.locator_ids[0]}]\n{item.content}" for item in packet.evidence_units)
        return contract.prompt_template.replace("{subject_id}", packet.subject_id).replace("{scope_text}", scope_text).replace("{evidence}", evidence_text)
    raise ExecutionPacketUnready(f"no executable packet renderer for {contract.task_profile}")


__all__ = ["ExecutionPacketUnready", "EvidenceUnit", "GovernedScope", "SemanticExecutionPacket", "materialize_execution_packet", "render_packet_prompt"]
