"""Finalisation and verification for provider-free S0 checkpoints."""
from __future__ import annotations

import hashlib
import json
import re
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


def _checkpoint_artifact_names(
    manifest: Mapping[str, Any],
    explicit: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve the attempt database and checkpoint names from durable identity."""
    explicit = dict(explicit or {})
    database_name = explicit.get("database")
    checkpoint_name = explicit.get("checkpoint")
    attempt_id = manifest.get("attempt_id")
    run_id = manifest.get("run_id")
    attempt_numbers = set()
    for value, pattern in ((attempt_id, r"^attempt:s0:(\d+)$"), (run_id, r"^run:s0:attempt-(\d+)$")):
        if value is not None:
            match = re.fullmatch(pattern, str(value))
            if match is None:
                raise ScalePreflightError("checkpoint attempt identity is invalid")
            attempt_numbers.add(match.group(1))
    if len(attempt_numbers) > 1:
        raise ScalePreflightError("checkpoint attempt identities do not agree")
    if not attempt_numbers and not (database_name and checkpoint_name):
        raise ScalePreflightError("checkpoint artifact names require durable attempt identity")
    if attempt_numbers:
        number = next(iter(attempt_numbers))
        derived_database = f"attempt{number}.sqlite3"
        derived_checkpoint = f"CHECKPOINT-ATTEMPT{number}.md"
        if database_name and database_name != derived_database:
            raise ScalePreflightError("checkpoint database name does not match attempt identity")
        if checkpoint_name and checkpoint_name != derived_checkpoint:
            raise ScalePreflightError("checkpoint name does not match attempt identity")
        database_name = database_name or derived_database
        checkpoint_name = checkpoint_name or derived_checkpoint
    if not database_name or not checkpoint_name:
        raise ScalePreflightError("checkpoint artifact names are incomplete")
    if Path(database_name).name != database_name or Path(checkpoint_name).name != checkpoint_name:
        raise ScalePreflightError("checkpoint artifact names must be basenames")
    return database_name, checkpoint_name


def _resolve_checkpoint_artifacts(
    manifest: Mapping[str, Any],
    explicit: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    advertised = manifest.get("checkpoint_artifacts")
    advertised = advertised if isinstance(advertised, Mapping) else {}
    database_candidates = [name for name in advertised if re.fullmatch(r"attempt\d+\.sqlite3", str(name))]
    checkpoint_candidates = [name for name in advertised if re.fullmatch(r"CHECKPOINT-ATTEMPT\d+\.md", str(name))]
    if len(database_candidates) > 1 or len(checkpoint_candidates) > 1:
        raise ScalePreflightError("checkpoint artifact names are ambiguous")
    explicit = dict(explicit or {})
    if database_candidates:
        explicit.setdefault("database", database_candidates[0])
    if checkpoint_candidates:
        explicit.setdefault("checkpoint", checkpoint_candidates[0])
    return _checkpoint_artifact_names(manifest, explicit)


def _checkpoint_matches_manifest(text: str, manifest: Mapping[str, Any]) -> bool:
    expected = "# Provider-free S0 checkpoint\n\n" + json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if text == expected:
        return True
    legacy_prefix = re.match(r"^# Attempt \d+ provider-free live-boundary checkpoint\n\n", text)
    if legacy_prefix is None:
        return False
    payload = text[legacy_prefix.end():]
    try:
        checkpoint_manifest, end = json.JSONDecoder().raw_decode(payload)
    except json.JSONDecodeError:
        return False
    return checkpoint_manifest == manifest and payload[end:].startswith(
        "\n\nFinal preflight: "
    )


def verify_checkpoint(
    root: str | Path,
    *,
    expected_attempt_material_hash: str | None = None,
    artifact_names: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base = Path(root)
    manifest = json.loads((base / "identity-manifest.json").read_text(encoding="utf-8")) if (base / "identity-manifest.json").is_file() else None
    if not isinstance(manifest, Mapping):
        raise ScalePreflightError("identity manifest is missing or invalid")
    database_name, checkpoint_name = _resolve_checkpoint_artifacts(manifest, artifact_names)
    required = ("identity-manifest.json", "locator-packet-manifest.json", database_name, "PREFLIGHT-RESULT.json", checkpoint_name)
    if any(not (base / item).is_file() for item in required):
        raise ScalePreflightError("checkpoint is missing a required artifact")
    if expected_attempt_material_hash and manifest.get("attempt_material_hash") != expected_attempt_material_hash:
        raise ScalePreflightError("attempt material hash does not match the advertised binding")
    advertised = manifest.get("checkpoint_artifacts")
    if not isinstance(advertised, Mapping):
        raise ScalePreflightError("checkpoint artifact hashes are absent")
    actual = {name: _sha(base / name) for name in ("identity-manifest.json", "locator-packet-manifest.json", database_name, "PREFLIGHT-RESULT.json")}
    for name, digest in actual.items():
        if name == "identity-manifest.json":
            continue
        if advertised.get(name) != digest:
            raise ScalePreflightError(f"checkpoint hash mismatch for {name}")
    checkpoint_text = (base / checkpoint_name).read_text(encoding="utf-8")
    legacy_checkpoint = re.match(r"^# Attempt \d+ provider-free live-boundary checkpoint\n\n", checkpoint_text) is not None
    if not _checkpoint_matches_manifest(checkpoint_text, manifest):
        raise ScalePreflightError("checkpoint bytes do not match the final identity manifest")
    if manifest.get("checkpoint_sha256") and manifest["checkpoint_sha256"] != _sha(base / checkpoint_name):
        raise ScalePreflightError("checkpoint self-hash mismatch")
    if not legacy_checkpoint and advertised.get("identity-manifest-canonical-sha256") != _manifest_digest(manifest):
        raise ScalePreflightError("identity manifest canonical hash mismatch")
    return {"checkpoint_sha256": _sha(base / checkpoint_name), **actual, "manifest_material_sha256": _manifest_digest(manifest)}


def finalize_checkpoint(
    root: str | Path,
    manifest: Mapping[str, Any],
    *,
    artifact_names: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Write a self-consistent provider-free checkpoint for one durable attempt."""
    base = Path(root)
    value = json.loads(json.dumps(manifest))
    database_name, checkpoint_name = _resolve_checkpoint_artifacts(value, artifact_names)
    value.setdefault("checkpoint_artifacts", {})
    artifacts = value["checkpoint_artifacts"]
    for name in ("locator-packet-manifest.json", database_name, "PREFLIGHT-RESULT.json"):
        artifacts[name] = _sha(base / name)
    artifacts.pop("identity-manifest.json", None)
    value["checkpoint_artifacts"] = artifacts
    value["checkpoint_artifacts"]["identity-manifest-canonical-sha256"] = _manifest_digest(value)
    (base / "identity-manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint = "# Provider-free S0 checkpoint\n\n" + json.dumps(value, indent=2, sort_keys=True) + "\n"
    (base / checkpoint_name).write_text(checkpoint, encoding="utf-8")
    return verify_checkpoint(base, artifact_names={"database": database_name, "checkpoint": checkpoint_name})
