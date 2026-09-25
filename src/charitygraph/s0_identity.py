"""Finalisation and verification for provider-free S0 checkpoints."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .scale_s0 import ScalePreflightError


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_digest(value: Mapping[str, Any]) -> str:
    material = json.loads(json.dumps(value))
    artifacts = material.get("checkpoint_artifacts")
    if isinstance(artifacts, dict):
        artifacts = dict(artifacts)
        artifacts.pop("identity-manifest.json", None)
        artifacts.pop("identity-manifest-canonical-sha256", None)
        material["checkpoint_artifacts"] = artifacts
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_checkpoint(root: str | Path, *, expected_attempt_material_hash: str | None = None) -> dict[str, str]:
    base = Path(root)
    required = ("identity-manifest.json", "locator-packet-manifest.json", "attempt13.sqlite3", "PREFLIGHT-RESULT.json", "CHECKPOINT-ATTEMPT13.md")
    if any(not (base / item).is_file() for item in required):
        raise ScalePreflightError("checkpoint is missing a required artifact")
    manifest = json.loads((base / "identity-manifest.json").read_text(encoding="utf-8"))
    if expected_attempt_material_hash and manifest.get("attempt_material_hash") != expected_attempt_material_hash:
        raise ScalePreflightError("attempt material hash does not match the advertised binding")
    advertised = manifest.get("checkpoint_artifacts")
    if not isinstance(advertised, Mapping):
        raise ScalePreflightError("checkpoint artifact hashes are absent")
    actual = {name: _sha(base / name) for name in ("identity-manifest.json", "locator-packet-manifest.json", "attempt13.sqlite3", "PREFLIGHT-RESULT.json")}
    for name, digest in actual.items():
        if name == "identity-manifest.json":
            continue
        if advertised.get(name) != digest:
            raise ScalePreflightError(f"checkpoint hash mismatch for {name}")
    checkpoint_text = (base / "CHECKPOINT-ATTEMPT13.md").read_text(encoding="utf-8")
    expected_checkpoint = "# Provider-free S0 checkpoint\n\n" + json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if checkpoint_text != expected_checkpoint:
        raise ScalePreflightError("checkpoint bytes do not match the final identity manifest")
    if manifest.get("checkpoint_sha256") and manifest["checkpoint_sha256"] != _sha(base / "CHECKPOINT-ATTEMPT13.md"):
        raise ScalePreflightError("checkpoint self-hash mismatch")
    if advertised.get("identity-manifest-canonical-sha256") != _manifest_digest(manifest):
        raise ScalePreflightError("identity manifest canonical hash mismatch")
    return {"checkpoint_sha256": _sha(base / "CHECKPOINT-ATTEMPT13.md"), **actual, "manifest_material_sha256": _manifest_digest(manifest)}


def finalize_checkpoint(root: str | Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    """Write a self-consistent future checkpoint; never mutates a supplied Attempt-13 path."""
    base = Path(root)
    value = json.loads(json.dumps(manifest))
    value.setdefault("checkpoint_artifacts", {})
    artifacts = value["checkpoint_artifacts"]
    for name in ("locator-packet-manifest.json", "attempt13.sqlite3", "PREFLIGHT-RESULT.json"):
        artifacts[name] = _sha(base / name)
    artifacts.pop("identity-manifest.json", None)
    value["checkpoint_artifacts"] = artifacts
    value["checkpoint_artifacts"]["identity-manifest-canonical-sha256"] = _manifest_digest(value)
    (base / "identity-manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = "# Provider-free S0 checkpoint\n\n" + json.dumps(value, indent=2, sort_keys=True) + "\n"
    (base / "CHECKPOINT-ATTEMPT13.md").write_text(checkpoint, encoding="utf-8")
    return verify_checkpoint(base)
