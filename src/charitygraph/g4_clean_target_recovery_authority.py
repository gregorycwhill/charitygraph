"""Pure, dormant structural validation for clean-target T4E recovery.

The candidate envelope and pin record are deliberately not authority.  A
future bridge may supply an active execution context and host-readback
implementation, but this pure module has no way to authenticate either one.
It therefore only returns a non-actionable structural result and never grants
execution eligibility.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


RECOVERY_AUTHORITY_VERSION = "recovery-authority-v1"
PLAN_SCHEMA = "charitygraph.recovery-plan/v1"
STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED = (
    "STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED"
)
EXPECTED_REPOSITORY = "charitygraph"
EXPECTED_BRANCH = "gate3-cg406-remediation"
POLICY_PROVENANCE_EPOCH = "g4-t4e-recovery-policy-v1"
RECOVERY_POLICY_PROVENANCE_EPOCH = POLICY_PROVENANCE_EPOCH

EXPECTED_ARTIFACTS = (
    (
        "src/charitygraph/phase5_t4d_e3_factory_handoff.py",
        "e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8",
    ),
    (
        "tests/test_phase5_t4d_e3_factory_handoff.py",
        "38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7",
    ),
)
EXPECTED_TEST_COUNTS = {"focused": 32, "regression": 50}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_PIN_FIELDS = frozenset(
    {
        "repository",
        "workspace",
        "branch",
        "head",
        "fence_version",
        "fence_sha256",
        "policy_provenance_epoch",
        "source_instruction_id",
        "source_instruction_sha256",
        "source_result_id",
        "source_result_sha256",
        "reconciliation_report_id",
        "reconciliation_report_sha256",
        "reconciliation_result_id",
        "reconciliation_result_sha256",
        "manifest_sha256",
        "source_anchor_sha256",
        "focused_attestation_id",
        "focused_attestation_sha256",
        "regression_attestation_id",
        "regression_attestation_sha256",
        "artifact_hashes",
    }
)
_ACTIVE_CONTEXT_FIELDS = frozenset(
    {
        "repository",
        "workspace",
        "branch",
        "head",
        "fence_version",
        "fence_sha256",
        "policy_provenance_epoch",
    }
)


@dataclass(frozen=True)
class TrustedRecoveryPins:
    """Evidence pins supplied by a later host integration.

    These values are inputs to structural validation only.  Constructing this
    object does not establish independent origin, even though the dataclass is
    immutable.  ``artifact_hashes`` is a tuple so the object is straightforward
    to transport.
    """

    repository: str
    workspace: str
    branch: str
    head: str
    fence_version: str
    fence_sha256: str
    policy_provenance_epoch: str
    source_instruction_id: str
    source_instruction_sha256: str
    source_result_id: str
    source_result_sha256: str
    reconciliation_report_id: str
    reconciliation_report_sha256: str
    reconciliation_result_id: str
    reconciliation_result_sha256: str
    manifest_sha256: str
    source_anchor_sha256: str
    focused_attestation_id: str
    focused_attestation_sha256: str
    regression_attestation_id: str
    regression_attestation_sha256: str
    artifact_hashes: tuple[tuple[str, str], ...] = EXPECTED_ARTIFACTS

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrustedRecoveryPins":
        """Construct pins from a bridge-friendly JSON-shaped mapping."""

        if not isinstance(value, Mapping) or set(value) != _PIN_FIELDS:
            raise ValueError("trusted pins must contain exactly the independent pin fields")
        raw_artifacts = value["artifact_hashes"]
        if not isinstance(raw_artifacts, (list, tuple)):
            raise ValueError("trusted artifact pins must be a list")
        artifacts: list[tuple[str, str]] = []
        for item in raw_artifacts:
            if isinstance(item, Mapping) and set(item) == {"path", "sha256"}:
                artifacts.append((item["path"], item["sha256"]))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                artifacts.append((item[0], item[1]))
            else:
                raise ValueError("trusted artifact pin has invalid shape")
        fields = {key: value[key] for key in _PIN_FIELDS if key != "artifact_hashes"}
        fields["artifact_hashes"] = tuple(artifacts)
        return cls(**fields)


# A descriptive alias keeps the later bridge call-site readable.
IndependentRecoveryPins = TrustedRecoveryPins


@dataclass(frozen=True)
class ActiveBridgeExecutionContext:
    """The exact active target read back by a future authenticated host.

    This is intentionally separate from the immutable policy/evidence pins.
    The dataclass carries shape for the future bridge boundary; it is not an
    authentication credential and cannot make this pure validator actionable.
    """

    repository: str
    workspace: str
    branch: str
    head: str
    fence_version: str
    fence_sha256: str
    policy_provenance_epoch: str = POLICY_PROVENANCE_EPOCH

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ActiveBridgeExecutionContext":
        """Construct an active-context value from a bridge-shaped mapping."""

        if not isinstance(value, Mapping) or set(value) != _ACTIVE_CONTEXT_FIELDS:
            raise ValueError("active bridge context must contain exactly its context fields")
        return cls(**{key: value[key] for key in _ACTIVE_CONTEXT_FIELDS})


class RecoveryHostReadback(Protocol):
    """Narrow future bridge seam; implementation and authentication are later work.

    A host implementation must read the current status, fence, result and
    report bytes, and obtain their independently trusted SHA pins.  Merely
    implementing this protocol or returning caller-supplied values is not
    accepted by this module.
    """

    def active_execution_context(self) -> ActiveBridgeExecutionContext: ...

    def status_bytes(self) -> bytes: ...

    def fence_bytes(self) -> bytes: ...

    def result_bytes(self) -> bytes: ...

    def report_bytes(self) -> bytes: ...

    def independently_trusted_sha256(self, name: str) -> str: ...


def canonical_envelope_bytes(envelope: Mapping[str, Any]) -> bytes:
    """Return the deterministic transport representation of an envelope."""

    if not isinstance(envelope, Mapping):
        raise TypeError("recovery envelope must be a mapping")
    return (
        json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _exact(value: Any, keys: set[str], label: str, reasons: list[str]) -> bool:
    if not isinstance(value, Mapping) or set(value) != keys:
        reasons.append(f"{label}_shape_invalid")
        return False
    return True


def _pins(value: TrustedRecoveryPins | Mapping[str, Any]) -> TrustedRecoveryPins:
    if isinstance(value, TrustedRecoveryPins):
        return value
    return TrustedRecoveryPins.from_mapping(value)


def _valid_pin_values(pins: TrustedRecoveryPins, reasons: list[str]) -> None:
    if not all(isinstance(getattr(pins, field), str) and getattr(pins, field) for field in (
        "repository", "workspace", "branch", "head", "fence_version",
        "source_instruction_id", "source_result_id", "reconciliation_report_id",
        "reconciliation_result_id", "focused_attestation_id", "regression_attestation_id",
    )):
        reasons.append("independent_provenance_missing")
    if not isinstance(pins.head, str) or _HEAD.fullmatch(pins.head) is None:
        reasons.append("trusted_head_invalid")
    if pins.repository != EXPECTED_REPOSITORY:
        reasons.append("trusted_repository_invalid")
    if pins.branch != EXPECTED_BRANCH:
        reasons.append("trusted_branch_invalid")
    if (
        not isinstance(pins.fence_version, str)
        or not pins.fence_version.startswith("v")
        or not pins.fence_version[1:].isdigit()
    ):
        reasons.append("trusted_fence_version_invalid")
    if pins.policy_provenance_epoch != POLICY_PROVENANCE_EPOCH:
        reasons.append("trusted_policy_provenance_invalid")
    for field in (
        "fence_sha256", "source_instruction_sha256", "source_result_sha256",
        "reconciliation_report_sha256", "reconciliation_result_sha256", "manifest_sha256",
        "source_anchor_sha256", "focused_attestation_sha256", "regression_attestation_sha256",
    ):
        if not _is_sha(getattr(pins, field)):
            reasons.append(f"trusted_{field}_invalid")
    if pins.artifact_hashes != EXPECTED_ARTIFACTS:
        reasons.append("trusted_artifact_allowlist_invalid")


def _blocked(reasons: list[str]) -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        "status": "BLOCKED",
        "action": "NONE",
        "reasons": list(dict.fromkeys(reasons)) or ["validation_failed"],
        "limitations": {
            "dormant": True,
            "t3_rights": "BLOCKED",
            "provider_promotion": False,
            "rights_promotion": False,
            "ordinary_tracked_dirty_adoption": False,
        },
    }


def _structure_verified_plan(
    envelope: Mapping[str, Any],
    pins: TrustedRecoveryPins,
    context: ActiveBridgeExecutionContext,
) -> dict[str, Any]:
    candidate = envelope["candidate"]
    source = envelope["source"]
    reconciliation = envelope["reconciliation"]
    tests = envelope["tests"]
    return {
        "schema": PLAN_SCHEMA,
        "status": STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED,
        "action": "NONE",
        "authority_version": RECOVERY_AUTHORITY_VERSION,
        "policy_provenance_epoch": pins.policy_provenance_epoch,
        "target": {
            "repository": context.repository,
            "workspace": context.workspace,
            "branch": context.branch,
            "head": context.head,
            "fence_version": context.fence_version,
            "fence_sha256": context.fence_sha256,
        },
        "source": {
            "instruction_id": source["instruction"]["id"],
            "instruction_sha256": source["instruction"]["sha256"],
            "result_id": source["result"]["id"],
            "result_sha256": source["result"]["sha256"],
            "terminal_state": "CODEX_EXECUTION_TIMEOUT",
        },
        "candidate": {
            "manifest_sha256": candidate["manifest_sha256"],
            "source_anchor_sha256": candidate["source_anchor_sha256"],
            "files": list(candidate["files"]),
        },
        "reconciliation": {
            "report_id": reconciliation["report"]["id"],
            "report_sha256": reconciliation["report"]["sha256"],
            "result_id": reconciliation["result"]["id"],
            "result_sha256": reconciliation["result"]["sha256"],
            "status": "COMPLETED",
            "verified": True,
        },
        "tests": {
            "focused_passed": tests["focused"]["passed"],
            "focused_attestation_sha256": tests["focused"]["attestation"]["sha256"],
            "regression_passed": tests["regression"]["passed"],
            "regression_attestation_sha256": tests["regression"]["attestation"]["sha256"],
        },
        "limitations": {
            "dormant": True,
            "host_authentication_required": True,
            "t3_rights": "BLOCKED",
            "provider_promotion": False,
            "rights_promotion": False,
            "ordinary_tracked_dirty_adoption": False,
            "timeout_is_evidence_only": True,
        },
    }


def validate_recovery_authority(
    envelope: Mapping[str, Any],
    trusted_pins: TrustedRecoveryPins | Mapping[str, Any] | None,
    active_context: ActiveBridgeExecutionContext | Mapping[str, Any] | None = None,
    host_readback: RecoveryHostReadback | None = None,
) -> dict[str, Any]:
    """Validate structure against pins and an active context, never authority.

    Every failure is represented as ``{"status": "BLOCKED", ...}`` rather
    than raising or partially authorising a transaction.  No field in the
    candidate, pin object, context object, or host protocol implementation can
    establish provenance on its own.  ``host_readback`` is reserved for the
    separately reviewed bridge integration and is rejected here if supplied.
    """

    reasons: list[str] = []
    if trusted_pins is None:
        return _blocked(["independent_provenance_missing"])
    try:
        pins = _pins(trusted_pins)
    except (TypeError, ValueError):
        return _blocked(["independent_provenance_invalid"])
    _valid_pin_values(pins, reasons)
    if reasons:
        return _blocked(reasons)
    if active_context is None:
        return _blocked(["active_execution_context_missing"])
    try:
        context = (
            active_context
            if isinstance(active_context, ActiveBridgeExecutionContext)
            else ActiveBridgeExecutionContext.from_mapping(active_context)
        )
    except (TypeError, ValueError):
        return _blocked(["active_execution_context_invalid"])
    if host_readback is not None:
        return _blocked(["host_authentication_integration_unavailable"])
    if not isinstance(envelope, Mapping):
        return _blocked(["envelope_shape_invalid"])

    top_keys = {
        "schema", "policy_provenance_epoch", "target", "source", "candidate",
        "reconciliation", "tests", "target_state", "scope"
    }
    if set(envelope) != top_keys:
        reasons.append("envelope_keys_invalid")
        return _blocked(reasons)
    if envelope["schema"] != f"charitygraph.{RECOVERY_AUTHORITY_VERSION}":
        reasons.append("envelope_version_invalid")
    if envelope["policy_provenance_epoch"] != pins.policy_provenance_epoch:
        reasons.append("policy_provenance_mismatch")

    target_keys = {"repository", "workspace", "branch", "head", "fence"}
    if _exact(envelope["target"], target_keys, "target", reasons):
        target = envelope["target"]
        if any(
            target[field] != getattr(context, field)
            or target[field] != getattr(pins, field)
            for field in ("repository", "workspace", "branch", "head")
        ):
            reasons.append("target_identity_mismatch")
        if not _exact(target["fence"], {"version", "sha256"}, "fence", reasons):
            pass
        elif any(
            target["fence"][field] != getattr(context, context_field)
            or target["fence"][field] != getattr(pins, context_field)
            for field, context_field in (("version", "fence_version"), ("sha256", "fence_sha256"))
        ):
            reasons.append("fence_mismatch")

    if any(
        getattr(context, field) != getattr(pins, field)
        for field in ("repository", "workspace", "branch", "head", "fence_version", "fence_sha256")
    ):
        reasons.append("active_context_mismatch")
    if context.policy_provenance_epoch != pins.policy_provenance_epoch:
        reasons.append("active_policy_provenance_mismatch")

    source_keys = {"instruction", "result"}
    if _exact(envelope["source"], source_keys, "source", reasons):
        source = envelope["source"]
        if _exact(source["instruction"], {"id", "sha256"}, "source_instruction", reasons):
            if (source["instruction"]["id"], source["instruction"]["sha256"]) != (
                pins.source_instruction_id, pins.source_instruction_sha256
            ):
                reasons.append("source_instruction_mismatch")
        result_keys = {
            "id", "sha256", "execution_state", "terminal", "provider_calls",
            "source_acquisition", "publication", "semantic_product_work",
        }
        if _exact(source["result"], result_keys, "source_result", reasons):
            result = source["result"]
            if (result["id"], result["sha256"]) != (pins.source_result_id, pins.source_result_sha256):
                reasons.append("source_result_mismatch")
            if (
                result["execution_state"] != "CODEX_EXECUTION_TIMEOUT"
                or result["terminal"] is not True
                or result["provider_calls"] != 0
                or result["source_acquisition"] is not False
                or result["publication"] is not False
                or result["semantic_product_work"] != "NOT_PERFORMED"
            ):
                reasons.append("source_result_not_timeout_evidence")

    candidate_keys = {"manifest_sha256", "source_anchor_sha256", "files"}
    if _exact(envelope["candidate"], candidate_keys, "candidate", reasons):
        candidate = envelope["candidate"]
        if candidate["manifest_sha256"] != pins.manifest_sha256:
            reasons.append("manifest_mismatch")
        if candidate["source_anchor_sha256"] != pins.source_anchor_sha256:
            reasons.append("source_anchor_mismatch")
        files = candidate["files"]
        if not isinstance(files, list) or len(files) != len(EXPECTED_ARTIFACTS):
            reasons.append("candidate_allowlist_invalid")
        else:
            parsed: list[tuple[Any, Any]] = []
            for item in files:
                if not _exact(item, {"path", "sha256"}, "candidate_file", reasons):
                    continue
                if not isinstance(item["path"], str) or not isinstance(item["sha256"], str):
                    reasons.append("candidate_file_invalid")
                    continue
                parsed.append((item["path"], item["sha256"]))
            if len(set(path for path, _ in parsed)) != len(parsed):
                reasons.append("duplicate_candidate_path")
            if tuple(parsed) != EXPECTED_ARTIFACTS or tuple(parsed) != pins.artifact_hashes:
                reasons.append("candidate_allowlist_mismatch")

    reconciliation_keys = {"report", "result", "status", "verified", "independent"}
    if _exact(envelope["reconciliation"], reconciliation_keys, "reconciliation", reasons):
        reconciliation = envelope["reconciliation"]
        for name, expected in (
            ("report", (pins.reconciliation_report_id, pins.reconciliation_report_sha256)),
            ("result", (pins.reconciliation_result_id, pins.reconciliation_result_sha256)),
        ):
            if _exact(reconciliation[name], {"id", "sha256"}, f"reconciliation_{name}", reasons):
                if (reconciliation[name]["id"], reconciliation[name]["sha256"]) != expected:
                    reasons.append(f"reconciliation_{name}_mismatch")
        if reconciliation["status"] != "COMPLETED" or reconciliation["verified"] is not True or reconciliation["independent"] is not True:
            reasons.append("reconciliation_not_independently_completed_verified")
        if (
            isinstance(reconciliation.get("result"), Mapping)
            and reconciliation["result"].get("id") == pins.source_result_id
        ):
            reasons.append("reconciliation_result_not_separate")

    tests_keys = {"focused", "regression"}
    if _exact(envelope["tests"], tests_keys, "tests", reasons):
        tests = envelope["tests"]
        for name, expected_count, expected_id, expected_sha in (
            ("focused", 32, pins.focused_attestation_id, pins.focused_attestation_sha256),
            ("regression", 50, pins.regression_attestation_id, pins.regression_attestation_sha256),
        ):
            if _exact(tests[name], {"passed", "expected", "attestation"}, f"{name}_tests", reasons):
                proof = tests[name]
                if proof["passed"] != expected_count or proof["expected"] != expected_count:
                    reasons.append(f"{name}_test_proof_invalid")
                if _exact(proof["attestation"], {"id", "sha256"}, f"{name}_attestation", reasons):
                    if (proof["attestation"]["id"], proof["attestation"]["sha256"]) != (expected_id, expected_sha):
                        reasons.append(f"{name}_attestation_mismatch")

    state_keys = {"clean", "tracked_dirty_paths", "staged_paths", "untracked_paths", "ignored_paths"}
    if _exact(envelope["target_state"], state_keys, "target_state", reasons):
        state = envelope["target_state"]
        if state["clean"] is not True or any(state[name] != [] for name in state_keys if name != "clean"):
            reasons.append("target_dirty")

    scope_keys = {
        "mode", "bridge_ingress", "t3_rights", "provider_promotion",
        "rights_promotion", "ordinary_tracked_dirty_adoption",
    }
    if _exact(envelope["scope"], scope_keys, "scope", reasons):
        scope = envelope["scope"]
        if scope != {
            "mode": "DORMANT_ONLY",
            "bridge_ingress": False,
            "t3_rights": "BLOCKED",
            "provider_promotion": False,
            "rights_promotion": False,
            "ordinary_tracked_dirty_adoption": False,
        }:
            reasons.append("scope_or_rights_limit_invalid")

    if reasons:
        return _blocked(reasons)
    return _structure_verified_plan(envelope, pins, context)


# Short integration spelling for a later bridge caller.
validate = validate_recovery_authority


__all__ = [
    "ActiveBridgeExecutionContext",
    "EXPECTED_ARTIFACTS",
    "EXPECTED_TEST_COUNTS",
    "IndependentRecoveryPins",
    "POLICY_PROVENANCE_EPOCH",
    "RECOVERY_AUTHORITY_VERSION",
    "RECOVERY_POLICY_PROVENANCE_EPOCH",
    "RecoveryHostReadback",
    "STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED",
    "TrustedRecoveryPins",
    "canonical_envelope_bytes",
    "validate",
    "validate_recovery_authority",
]
