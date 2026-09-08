"""Provider-free prospective evidence addressing for the Phase-5 corpus."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import EvidenceLocator
from .evidence_store import ContentAddressedArtifactStore
from .native_program_discovery import build_discovery_task_v2
from .phase5_execution_packet import ExecutionPacketUnready, materialize_execution_packet
from .phase5_semantic_contracts import REGISTRY, executable_contract_for
from .runtime import SQLiteCatalog


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_manifests(corpus_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(corpus_dir.glob("*.json"))]


def _acnc_member(manifest: dict[str, Any]) -> dict[str, Any]:
    matches = [m for m in manifest.get("material_members", []) if m.get("source_family") == "acnc_register"]
    if len(matches) != 1:
        raise ValueError(f"expected one ACNC Register member for {manifest.get('subject_id')}")
    return matches[0]


def preflight(*, corpus_dir: Path, catalog_path: Path, store_roots: tuple[Path, ...]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    catalog = SQLiteCatalog(catalog_path).open()
    try:
        with catalog._connection() as conn:
            for manifest in _read_manifests(corpus_dir):
                subject = str(manifest["subject_id"])
                try:
                    member = _acnc_member(manifest)
                    if member.get("acquisition") != "available" or member.get("subject_binding") != "bound":
                        raise ValueError("ACNC member is not available and bound")
                    if len(member.get("source_record_ids", [])) != 1 or len(member.get("artifact_ids", [])) != 1:
                        raise ValueError("ACNC member does not have exactly one source record and artifact")
                    source_id, artifact_id = member["source_record_ids"][0], member["artifact_ids"][0]
                    source = conn.execute("SELECT * FROM source_records WHERE source_record_id=?", (source_id,)).fetchone()
                    if source is None or source["source_family"] != "acnc_register":
                        raise ValueError("governed ACNC source record is missing")
                    if source["payload_ref"] != artifact_id or not source["payload_hash"]:
                        raise ValueError("source payload/artifact lineage disagrees")
                    content = None
                    for root in store_roots:
                        try:
                            content = ContentAddressedArtifactStore(root, allowed_roots=(root.parent,)).read(artifact_id)
                            break
                        except Exception:
                            pass
                    if content is None:
                        raise ValueError("retained artifact is unavailable")
                    digest = hashlib.sha256(content).hexdigest()
                    if digest != str(source["payload_hash"]) or digest != artifact_id.split(":", 1)[1]:
                        raise ValueError("retained artifact hash mismatch")
                    if not content:
                        raise ValueError("retained ACNC material is empty")
                    failures.append({"subject_id": subject, "status": "eligible", "source_record_id": source_id, "artifact_id": artifact_id, "material_hash": digest, "source_locator": source["source_locator"], "byte_count": len(content)})
                except Exception as exc:
                    failures.append({"subject_id": subject, "status": "failed", "reason": str(exc)})
    finally:
        catalog.close()
    return failures


def canonical_locator(row: dict[str, Any]) -> EvidenceLocator:
    """A document locator bound to the governed source record.

    The source record's payload hash is the existing Builder content authority;
    artifact-index membership is deliberately not required for this projection.
    """
    return EvidenceLocator(kind="document", source_record_id=row["source_record_id"], locator=row["source_locator"])


def canonical_discovery_proof_task(*, subject_id: str, evidence_corpus_hash: str, logical_task_id: str) -> dict[str, Any]:
    """Construct the proof task from the production-bound registry identity."""
    contract = next(contract for contract in REGISTRY if "program-service-discovery-v2" in contract.claim_families and contract.executable)
    return {
        "logical_task_id": logical_task_id,
        "subject_id": subject_id,
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "claim_family_id": "program-service-discovery-v2",
        "prompt_policy_version": contract.planner_prompt_policy_version,
        "schema_version": contract.planner_schema_version,
        "evidence_corpus_hash": evidence_corpus_hash,
        "difficulty": contract.route_class,
    }


def address(*, corpus_dir: Path, catalog_path: Path, store_roots: tuple[Path, ...], output_root: Path, now: str | None = None) -> dict[str, Any]:
    rows = preflight(corpus_dir=corpus_dir, catalog_path=catalog_path, store_roots=store_roots)
    if any(row["status"] != "eligible" for row in rows) or len(rows) != 100:
        raise RuntimeError("PHASE5_TOP100_ACNC_EVIDENCE_ADDRESSING_BLOCKED: atomic preflight did not pass 100/100")
    timestamp = now or _utc_now()
    catalog = SQLiteCatalog(catalog_path).open()
    locator_rows: list[dict[str, Any]] = []
    try:
        # Artifact admission is historical and immutable; this tranche performs no artifact writes.
        for row in rows:
            registered = catalog.register_evidence_locator(canonical_locator(row), now=timestamp)
            locator_rows.append({"subject_id": row["subject_id"], "source_family": "acnc_register", "source_record_id": row["source_record_id"], "artifact_id": row["artifact_id"], "material_hash": row["material_hash"], "evidence_locator_id": registered["evidence_locator_id"], "prospective_created_at": registered["created_at"]})
    finally:
        catalog.close()
    parent = []
    for manifest in _read_manifests(corpus_dir):
        item = json.loads(json.dumps(manifest))
        member = _acnc_member(item)
        locator = next(row["evidence_locator_id"] for row in locator_rows if row["subject_id"] == item["subject_id"])
        member["evidence_locator_ids"] = [locator]
        parent.append(item)
    projection = {"projection_version": "phase5-top100-acnc-addressed-v1", "parent_clean_corpus_profile": "phase5-top100-baseline-corpus-v1-clean", "parent_corpus_ids": sorted(m["corpus_id"] for m in parent), "addressing_operation": "prospective_acnc_register_full_retained_payload", "created_at": timestamp, "members": locator_rows, "corpora": parent}
    projection["projection_hash"] = _sha({k: v for k, v in projection.items() if k != "projection_hash"})
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "addressed-projection.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return projection


def prove_discovery(*, projection: dict[str, Any], catalog_path: Path, runtime_root: Path, store_root: Path) -> dict[str, Any]:
    results = []
    catalog = SQLiteCatalog(catalog_path).open()
    try:
        for manifest in projection["corpora"]:
            member = _acnc_member(manifest)
            task = canonical_discovery_proof_task(subject_id=manifest["subject_id"], evidence_corpus_hash=manifest["material_identity_hash"], logical_task_id=f"semtask:phase5-acnc-addressing:{manifest['subject_id']}")
            contract = executable_contract_for(task)
            build_discovery_task_v2(catalog, subject_id=manifest["subject_id"], evidence_ids=member["evidence_locator_ids"], prompt_template_id=contract.prompt_id, prompt_template_version=contract.contract_version, provider_id="openai", model_snapshot="gpt-5.6-luna")
            try:
                packet = materialize_execution_packet(task=task, corpus={"subject_id": manifest["subject_id"], "material_members": [member]}, contract=contract, runtime_root=runtime_root, catalog_path=catalog_path, model="gpt-5.6-luna", reasoning_effort="low", service_tier="default")
                results.append({"subject_id": manifest["subject_id"], "status": "ready", "evidence_ids": [item.evidence_id for item in packet.evidence_units], "packet_hash": packet.packet_hash})
            except (ExecutionPacketUnready, Exception) as exc:
                results.append({"subject_id": manifest["subject_id"], "status": "blocked", "reason": str(exc)})
    finally:
        catalog.close()
    return {"ready": sum(x["status"] == "ready" for x in results), "blocked": [x for x in results if x["status"] != "ready"], "results": results}
