"""Immutable, fail-closed handoffs for the bounded semantic Builder lane.

This is deliberately only identity/provenance plumbing.  It does not inspect
or classify evidence text, and it performs no network or provider work.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

FORMAT = "charitygraph.builder-stage-manifest.v1"
STAGES = (
    "cohort", "authorised_corpus", "evidence_registry_packet",
    "extraction_request_set", "structured_output", "semantic_demand_evaluation",
)
BINDING_FOR_STAGE = dict(zip(STAGES, (
    "cohort_sha256", "authorised_corpus_sha256", "evidence_registry_packet_sha256",
    "extraction_request_set_sha256", "structured_output_sha256",
    "semantic_demand_evaluation_sha256",
)))


class StageManifestError(ValueError):
    """A stage is not the exact immutable successor of its predecessor."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    value = dict(manifest)
    value.pop("manifest_sha256", None)
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def make_manifest(*, stage: str, artifact_path: str, artifact_sha256: str,
                  bindings: Mapping[str, str], predecessor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Create a manifest.  Call ``verify_manifest`` before persisting/using it."""
    manifest: dict[str, Any] = {
        "format": FORMAT, "stage": stage,
        "artifact": {"path": artifact_path, "sha256": artifact_sha256},
        "bindings": dict(bindings),
    }
    if predecessor is not None:
        manifest["predecessor_manifest_sha256"] = predecessor.get("manifest_sha256")
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    return manifest


def verify_manifest(manifest: Mapping[str, Any], *, base_dir: Path | None = None,
                    predecessor: Mapping[str, Any] | None = None) -> None:
    if manifest.get("format") != FORMAT or manifest.get("stage") not in STAGES:
        raise StageManifestError("unknown stage-manifest format or stage")
    if manifest.get("manifest_sha256") != manifest_sha256(manifest):
        raise StageManifestError("stage manifest bytes changed")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, Mapping):
        raise StageManifestError("missing bindings")
    cohort = bindings.get("cohort_sha256")
    if not isinstance(cohort, str) or len(cohort) != 64:
        raise StageManifestError("exact cohort binding is mandatory")
    position = STAGES.index(manifest["stage"])
    required = [BINDING_FOR_STAGE[s] for s in STAGES[:position + 1]]
    if any(not isinstance(bindings.get(key), str) or len(bindings[key]) != 64 for key in required):
        raise StageManifestError("missing required stage binding")
    artifact = manifest.get("artifact")
    if not isinstance(artifact, Mapping) or artifact.get("sha256") != bindings[BINDING_FOR_STAGE[manifest["stage"]]]:
        raise StageManifestError("stage artifact is not bound to this stage")
    if base_dir is not None:
        path = base_dir / str(artifact.get("path", ""))
        if not path.is_file() or sha256_file(path) != artifact["sha256"]:
            raise StageManifestError("stage artifact is missing, stale, or changed")
    if position == 0:
        if predecessor is not None or "predecessor_manifest_sha256" in manifest:
            raise StageManifestError("cohort stage cannot have a predecessor")
        return
    if predecessor is None:
        raise StageManifestError("successor requires verified predecessor manifest")
    # The caller supplies an already verified immediate predecessor.  Recursive
    # validation cannot recover older artifact directories from an in-memory
    # manifest; ``verify_chain`` performs that ordered full-chain check.
    if predecessor.get("manifest_sha256") != manifest_sha256(predecessor):
        raise StageManifestError("predecessor manifest bytes changed")
    if predecessor.get("stage") != STAGES[position - 1]:
        raise StageManifestError("predecessor is not the immediately prior stage")
    if manifest.get("predecessor_manifest_sha256") != predecessor.get("manifest_sha256"):
        raise StageManifestError("predecessor manifest identity mismatch")
    previous = predecessor["bindings"]
    for key in [BINDING_FOR_STAGE[s] for s in STAGES[:position]]:
        if bindings.get(key) != previous.get(key):
            raise StageManifestError("successor changed inherited binding: " + key)


def load_manifest(path: Path, *, predecessor_path: Path | None = None) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    predecessor = None if predecessor_path is None else json.loads(predecessor_path.read_text(encoding="utf-8"))
    verify_manifest(manifest, base_dir=path.parent, predecessor=predecessor)
    return manifest


def verify_chain(paths: list[Path], *, through_stage: str = "extraction_request_set") -> list[dict[str, Any]]:
    """Load an ordered chain and verify each artifact in its own directory."""
    expected = STAGES[:STAGES.index(through_stage) + 1]
    if len(paths) != len(expected):
        raise StageManifestError("complete ordered predecessor chain is required")
    manifests: list[dict[str, Any]] = []
    predecessor = None
    for expected_stage, path in zip(expected, paths):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("stage") != expected_stage:
            raise StageManifestError("stage manifests are not in required order")
        verify_manifest(manifest, base_dir=path.parent, predecessor=predecessor)
        manifests.append(manifest)
        predecessor = manifest
    return manifests
