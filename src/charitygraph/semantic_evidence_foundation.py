"""Durable, provider-free retained-representation and readiness mechanics.

This module intentionally has no discovery, network, or semantic-provider
dependency.  It binds derived bytes to an already retained source object and
allows a future executor to fail closed before crossing a provider boundary.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .evidence_store import ContentAddressedArtifactStore


class EvidenceFoundationError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    encoded = _canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == encoded:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceFoundationError(f"unreadable retained manifest: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceFoundationError("retained manifest must be an object")
    return value


@dataclass(frozen=True)
class RetainedRepresentation:
    representation_id: str
    representation_hash: str
    artifact_id: str
    content_hash: str
    source_artifact_id: str
    source_record_id: str
    source_version: str
    subject_id: str
    source_family: str
    source_role: str
    retrieved_at: str
    provenance_ids: tuple[str, ...]
    locator: dict[str, Any]

    def material(self) -> dict[str, Any]:
        return {"representation_id": self.representation_id, "artifact_id": self.artifact_id,
                "content_hash": self.content_hash, "source_artifact_id": self.source_artifact_id,
                "source_record_id": self.source_record_id, "source_version": self.source_version,
                "subject_id": self.subject_id, "source_family": self.source_family,
                "source_role": self.source_role, "retrieved_at": self.retrieved_at,
                "provenance_ids": list(self.provenance_ids), "locator": self.locator}


class DurableRepresentationStore:
    """Private archive layout: immutable objects plus hash-addressed manifests."""
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.objects = ContentAddressedArtifactStore(self.root / "objects", allowed_roots=(self.root,))

    def _path(self, representation_hash: str) -> Path:
        return self.root / "representations" / "sha256" / representation_hash[:2] / f"{representation_hash}.json"

    def put(self, content: bytes, *, source_artifact_id: str, source_record_id: str,
            source_version: str, subject_id: str, source_family: str, source_role: str,
            retrieved_at: str, provenance_ids: Iterable[str], locator: dict[str, Any]) -> RetainedRepresentation:
        if not all(isinstance(v, str) and v for v in (source_artifact_id, source_record_id, source_version, subject_id, source_family, source_role, retrieved_at)):
            raise EvidenceFoundationError("representation binding fields must be nonblank strings")
        if not source_artifact_id.startswith("srcblob:"):
            raise EvidenceFoundationError("representation must bind a retained source object")
        provenance = tuple(sorted(set(str(v) for v in provenance_ids)))
        if not provenance:
            raise EvidenceFoundationError("representation requires provenance identities")
        if not isinstance(locator, dict):
            raise EvidenceFoundationError("representation locator must be structured metadata")
        artifact = self.objects.put_derived(content, input_artifact_ids=(source_artifact_id,))
        material = {"artifact_id": artifact.artifact_id, "content_hash": artifact.content_hash,
                    "source_artifact_id": source_artifact_id, "source_record_id": source_record_id,
                    "source_version": source_version, "subject_id": subject_id, "source_family": source_family,
                    "source_role": source_role, "retrieved_at": retrieved_at,
                    "provenance_ids": list(provenance), "locator": locator}
        identity = _sha(material)
        value = {"contract": "cg-retained-representation-v1", "representation_id": f"representation:{identity}",
                 "representation_hash": identity, **material}
        _write_json(self._path(identity), value)
        return self.read(f"representation:{identity}")

    def read(self, representation_id: str) -> RetainedRepresentation:
        if not representation_id.startswith("representation:"):
            raise EvidenceFoundationError("invalid representation identity")
        identity = representation_id.split(":", 1)[1]
        value = _read_json(self._path(identity))
        material = {k: value.get(k) for k in ("artifact_id", "content_hash", "source_artifact_id", "source_record_id", "source_version", "subject_id", "source_family", "source_role", "retrieved_at", "provenance_ids", "locator")}
        if value.get("contract") != "cg-retained-representation-v1" or value.get("representation_id") != representation_id or value.get("representation_hash") != identity or _sha(material) != identity:
            raise EvidenceFoundationError("representation manifest identity mismatch")
        content = self.objects.read(str(value["artifact_id"]))
        if hashlib.sha256(content).hexdigest() != value["content_hash"]:
            raise EvidenceFoundationError("representation bytes fail content integrity")
        return RetainedRepresentation(representation_id, identity, str(value["artifact_id"]), str(value["content_hash"]), str(value["source_artifact_id"]), str(value["source_record_id"]), str(value["source_version"]), str(value["subject_id"]), str(value["source_family"]), str(value["source_role"]), str(value["retrieved_at"]), tuple(value["provenance_ids"]), dict(value["locator"]))

    def freeze_view(self, representation_ids: Iterable[str], *, view_kind: str) -> dict[str, Any]:
        reps = [self.read(value) for value in sorted(set(representation_ids))]
        if not reps or not view_kind:
            raise EvidenceFoundationError("a frozen view requires representations and a kind")
        members = [{"representation_id": r.representation_id, "representation_hash": r.representation_hash,
                    "content_hash": r.content_hash, "source_record_id": r.source_record_id,
                    "provenance_ids": list(r.provenance_ids)} for r in reps]
        material = {"view_kind": view_kind, "members": members}
        identity = _sha(material)
        value = {"contract": "cg-frozen-evidence-view-v1", "view_id": f"evidence-view:{identity}", "view_hash": identity, **material}
        _write_json(self.root / "views" / "sha256" / identity[:2] / f"{identity}.json", value)
        return value

    def replay_view(self, view_id: str) -> dict[str, Any]:
        if not view_id.startswith("evidence-view:"):
            raise EvidenceFoundationError("invalid frozen view identity")
        identity = view_id.split(":", 1)[1]
        value = _read_json(self.root / "views" / "sha256" / identity[:2] / f"{identity}.json")
        material = {"view_kind": value.get("view_kind"), "members": value.get("members")}
        if value.get("contract") != "cg-frozen-evidence-view-v1" or value.get("view_id") != view_id or value.get("view_hash") != identity or _sha(material) != identity:
            raise EvidenceFoundationError("frozen view identity mismatch")
        replayed = []
        for member in value["members"]:
            rep = self.read(member["representation_id"])
            if rep.representation_hash != member["representation_hash"] or rep.content_hash != member["content_hash"] or rep.source_record_id != member["source_record_id"] or list(rep.provenance_ids) != member["provenance_ids"]:
                raise EvidenceFoundationError("frozen view member provenance mismatch")
            replayed.append({"representation_id": rep.representation_id, "content_hash": rep.content_hash,
                             "provenance_ids": list(rep.provenance_ids), "content": self.objects.read(rep.artifact_id)})
        return {"view_id": view_id, "view_hash": identity, "members": replayed}


REQUIRED_READINESS_CHECKS = ("durable_store_integrity", "offline_replay", "organisation_identity_universe", "cohort_frozen", "source_acquisition_complete", "ethos_reference_evaluable", "history_reference_evaluable", "provenance_integrity", "provider_ledger_reconciled", "semantic_network_disabled")


def build_readiness_artifact(checks: dict[str, dict[str, Any]], *, context: dict[str, Any]) -> dict[str, Any]:
    missing = set(REQUIRED_READINESS_CHECKS) - set(checks)
    if missing:
        raise EvidenceFoundationError("readiness checks missing: " + ",".join(sorted(missing)))
    normalized = {key: {"passed": bool(checks[key].get("passed")), "detail": str(checks[key].get("detail", ""))} for key in REQUIRED_READINESS_CHECKS}
    state = "READY" if all(item["passed"] for item in normalized.values()) else "NOT_READY"
    material = {"contract": "cg-semantic-experiment-readiness-v1", "state": state, "checks": normalized, "context": context}
    return {**material, "artifact_hash": _sha(material)}


def write_readiness_artifact(path: str | Path, checks: dict[str, dict[str, Any]], *, context: dict[str, Any]) -> dict[str, Any]:
    result = build_readiness_artifact(checks, context=context)
    _write_json(Path(path), result)
    return result


def require_ready_readiness(path: str | Path) -> dict[str, Any]:
    value = _read_json(Path(path))
    material = {key: value.get(key) for key in ("contract", "state", "checks", "context")}
    if value.get("contract") != "cg-semantic-experiment-readiness-v1" or value.get("artifact_hash") != _sha(material):
        raise EvidenceFoundationError("readiness artifact integrity mismatch")
    if value.get("state") != "READY" or any(not value["checks"].get(key, {}).get("passed") for key in REQUIRED_READINESS_CHECKS):
        raise EvidenceFoundationError("semantic provider crossing blocked: prerequisites are NOT_READY")
    return value
