"""Mechanical identity binding for production-shaped semantic calls.

This module hashes executable bytes and selection inputs; it never interprets
the retained evidence.  A caller must validate the bound identity immediately
before handing a request to a provider.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


class ExecutionIdentityMismatch(RuntimeError):
    """The requested identity is not the identity of executable artifacts."""


@dataclass(frozen=True)
class ExecutionIdentity:
    prompt_sha256: str
    schema_sha256: str
    packet_selection_contract: str
    packet_selection_version: str
    packet_selection_sha256: str
    retained_source_manifest_sha256: str
    provider: str
    model: str
    experiment_arm: str

    @property
    def identity_sha256(self) -> str:
        return sha256_json(asdict(self))

    def as_dict(self) -> dict[str, str]:
        result = asdict(self)
        result["identity_sha256"] = self.identity_sha256
        return result


def bind_execution_identity(*, prompt: str | bytes, schema: Any,
                            packet_selection_contract: str,
                            packet_selection_version: str,
                            packet_selection: Any,
                            retained_source_manifest: Any,
                            provider: str, model: str,
                            experiment_arm: str) -> ExecutionIdentity:
    prompt_bytes = prompt if isinstance(prompt, bytes) else prompt.encode("utf-8")
    return ExecutionIdentity(
        prompt_sha256=sha256_bytes(prompt_bytes),
        schema_sha256=sha256_json(schema),
        packet_selection_contract=packet_selection_contract,
        packet_selection_version=packet_selection_version,
        packet_selection_sha256=sha256_json(packet_selection),
        retained_source_manifest_sha256=sha256_json(retained_source_manifest),
        provider=provider, model=model, experiment_arm=experiment_arm,
    )


def assert_execution_identity(requested: Mapping[str, Any] | ExecutionIdentity,
                              actual: ExecutionIdentity) -> None:
    expected = requested.as_dict() if isinstance(requested, ExecutionIdentity) else dict(requested)
    expected.pop("identity_sha256", None)
    actual_fields = asdict(actual)
    mismatches = sorted(k for k in actual_fields if expected.get(k) != actual_fields[k])
    if mismatches:
        raise ExecutionIdentityMismatch("execution identity mismatch: " + ", ".join(mismatches))
    if "identity_sha256" in expected and expected["identity_sha256"] != actual.identity_sha256:
        raise ExecutionIdentityMismatch("execution identity digest mismatch")


def write_identity_manifest(path: str | Path, *, requested: Mapping[str, Any], executed: ExecutionIdentity) -> None:
    payload = {"requested": dict(requested), "executed": executed.as_dict()}
    Path(path).write_bytes(canonical_bytes(payload) + b"\n")


__all__ = ["ExecutionIdentity", "ExecutionIdentityMismatch", "bind_execution_identity", "assert_execution_identity", "write_identity_manifest", "sha256_json"]
