"""Dormant host-owned readback for the T4E clean-target recovery dry-run.

This module is deliberately a read-only seam.  A supervisor supplies an
independently fixed :class:`HostReadbackConfig`; bytes in the artifact root
can only be evidence against those pins, never a source of pins.  The module
does not import the bridge, invoke Git, start a process, write a file, or
return an actionable recovery authority object.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Iterable, Mapping


SCHEMA = "charitygraph.g4-t4e-host-readback/v1"
EXPECTED_REPOSITORY = "charitygraph"
EXPECTED_BRANCH = "gate3-cg406-remediation"
POLICY_PROVENANCE_EPOCH = "g4-t4e-recovery-policy-v1"
STRUCTURE_ONLY_UNAUTHENTICATED = "STRUCTURE_ONLY_UNAUTHENTICATED"
STRUCTURE_ONLY_REASON = "structure_only_unauthenticated"

EXPECTED_CANDIDATE_ALLOWLIST = (
    (
        "src/charitygraph/phase5_t4d_e3_factory_handoff.py",
        "e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8",
    ),
    (
        "tests/test_phase5_t4d_e3_factory_handoff.py",
        "38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7",
    ),
)
EXPECTED_TEST_COUNTS = {"focused_attestation": 32, "regression_attestation": 50}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_FENCE_VERSION = re.compile(r"^v[0-9]+$")
_JSON_ROLES = frozenset(
    {
        "instruction",
        "source_result",
        "reconciliation_result",
        "fence",
        "status",
        "ledger",
        "focused_attestation",
        "regression_attestation",
        "candidate_package",
        "manifest",
        "source_anchor",
    }
)
_REQUIRED_ROLES = frozenset(_JSON_ROLES | {"reconciliation_report"})


@dataclass(frozen=True)
class ExpectedArtifact:
    """A host-fixed artifact identity and its expected bytes hash."""

    identity: str
    relative_path: str
    sha256: str
    role: str
    kind: str = "json"


@dataclass(frozen=True)
class CandidateFilePin:
    """The exact target path/hash and its separately named local byte file."""

    path: str
    sha256: str
    artifact_identity: str


@dataclass(frozen=True)
class HostReadbackConfig:
    """Host-observed inputs for one confined private artifact root.

    These values are declarations supplied by the caller.  They are checked
    for internal consistency only; no field is an authenticated trust root.
    """

    artifact_root: Path
    workspace: str
    fence_sha256: str
    expected_artifacts: tuple[ExpectedArtifact, ...]
    candidate_files: tuple[CandidateFilePin, ...] = tuple(
        CandidateFilePin(path, sha256, f"candidate:{path}")
        for path, sha256 in EXPECTED_CANDIDATE_ALLOWLIST
    )
    repository: str = EXPECTED_REPOSITORY
    branch: str = EXPECTED_BRANCH
    head: str = ""
    fence_version: str = ""
    policy_provenance_epoch: str = POLICY_PROVENANCE_EPOCH
    pin_set_id: str = ""
    host_trust_root: str | None = None


@dataclass(frozen=True)
class HostReadbackAttestation:
    """Immutable, JSON-serialisable, private-material-redacted result."""

    status: str
    action: str
    reasons: tuple[str, ...]
    target: Mapping[str, Any]
    verified_artifacts: tuple[Mapping[str, Any], ...]
    historical_timeout: Mapping[str, Any]
    active_context: Mapping[str, Any]
    limitations: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "status": self.status,
            "action": self.action,
            "trust_scope": STRUCTURE_ONLY_UNAUTHENTICATED,
            "host_authentication_required": True,
            "adoption_grant": False,
            "reasons": list(self.reasons),
            "target": dict(self.target),
            "verified_artifacts": [dict(item) for item in self.verified_artifacts],
            "historical_timeout": dict(self.historical_timeout),
            "active_context": dict(self.active_context),
            "limitations": dict(self.limitations),
        }


class _ReadbackFailure(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or ":" in value:
        raise _ReadbackFailure("unsafe_artifact_path")
    parts = PurePosixPath(value).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _ReadbackFailure("unsafe_artifact_path")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _ReadbackFailure("duplicate_json_key")
        result[key] = value
    return result


def _load_canonical_json(raw: bytes) -> Mapping[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_no_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, _ReadbackFailure):
        raise _ReadbackFailure("json_invalid_or_noncanonical")
    if not isinstance(value, Mapping) or _canonical_json_bytes(value) != raw:
        raise _ReadbackFailure("json_invalid_or_noncanonical")
    return value


def _exact_target(value: Any, config: HostReadbackConfig, *, require_repository: bool = True) -> None:
    if not isinstance(value, Mapping):
        raise _ReadbackFailure("target_identity_inconsistent")
    if require_repository and value.get("repository") != config.repository:
        raise _ReadbackFailure("repository_mismatch")
    if not require_repository and "repository" in value and value.get("repository") != config.repository:
        raise _ReadbackFailure("repository_mismatch")
    workspace = value.get("workspace", value.get("workspace_path"))
    if workspace != config.workspace:
        raise _ReadbackFailure("workspace_mismatch")
    if value.get("branch") != config.branch or value.get("head") != config.head:
        raise _ReadbackFailure("branch_or_head_mismatch")


def _exact_active_context(value: Any, config: HostReadbackConfig, *, version_keys: tuple[str, ...]) -> None:
    _exact_target(value, config)
    if not isinstance(value, Mapping):
        raise _ReadbackFailure("target_identity_inconsistent")
    version = next((value[key] for key in version_keys if key in value), None)
    if version != config.fence_version:
        raise _ReadbackFailure("fence_version_mismatch")


def _artifact_spec_checks(config: HostReadbackConfig) -> tuple[dict[str, ExpectedArtifact], list[str]]:
    reasons: list[str] = []
    by_role: dict[str, ExpectedArtifact] = {}
    identities: set[str] = set()
    paths: set[str] = set()
    for spec in config.expected_artifacts:
        try:
            relative_path = _safe_relative(spec.relative_path)
        except _ReadbackFailure as exc:
            reasons.append(exc.reason)
            continue
        if not spec.identity or spec.identity in identities:
            reasons.append("duplicate_artifact_identity")
        if relative_path in paths:
            reasons.append("duplicate_artifact_path")
        if spec.role != "candidate_file" and spec.role in by_role:
            reasons.append("duplicate_artifact_role")
        if not _is_sha(spec.sha256) or spec.kind not in {"json", "text", "bytes"}:
            reasons.append("artifact_pin_invalid")
        identities.add(spec.identity)
        paths.add(relative_path)
        if spec.role != "candidate_file":
            by_role[spec.role] = spec
    if not _is_sha(config.fence_sha256):
        reasons.append("fence_pin_invalid")
    if config.repository != EXPECTED_REPOSITORY:
        reasons.append("repository_pin_invalid")
    if config.branch != EXPECTED_BRANCH:
        reasons.append("branch_pin_invalid")
    if _HEAD.fullmatch(config.head or "") is None:
        reasons.append("head_pin_invalid")
    if _FENCE_VERSION.fullmatch(config.fence_version or "") is None:
        reasons.append("fence_version_invalid")
    if config.policy_provenance_epoch != POLICY_PROVENANCE_EPOCH:
        reasons.append("policy_provenance_invalid")
    if not config.workspace or not config.pin_set_id or config.pin_set_id.lower() in {"candidate", "self"}:
        reasons.append("independent_pin_set_missing")
    if tuple((item.path, item.sha256) for item in config.candidate_files) != EXPECTED_CANDIDATE_ALLOWLIST:
        reasons.append("candidate_allowlist_invalid")
    expected_candidate_identities = tuple(f"candidate:{path}" for path, _ in EXPECTED_CANDIDATE_ALLOWLIST)
    if tuple(item.artifact_identity for item in config.candidate_files) != expected_candidate_identities:
        reasons.append("candidate_identity_allowlist_invalid")
    candidate_ids = {item.artifact_identity for item in config.candidate_files}
    if len(candidate_ids) != len(config.candidate_files) or len(config.candidate_files) != len(EXPECTED_CANDIDATE_ALLOWLIST):
        reasons.append("duplicate_candidate_identity")
    if any(not _is_sha(item.sha256) or not item.artifact_identity for item in config.candidate_files):
        reasons.append("candidate_pin_invalid")
    if set(by_role) != set(_REQUIRED_ROLES - {"candidate_file"}):
        reasons.append("required_artifact_missing")
    candidate_specs = [spec for spec in config.expected_artifacts if spec.role == "candidate_file"]
    if len(candidate_specs) != len(config.candidate_files):
        reasons.append("candidate_evidence_missing")
    for item in config.candidate_files:
        if not any(spec.identity == item.artifact_identity and spec.sha256 == item.sha256 for spec in candidate_specs):
            reasons.append("candidate_evidence_pin_mismatch")
    if "fence" in by_role and by_role["fence"].sha256 != config.fence_sha256:
        reasons.append("fence_pin_mismatch")
    return by_role, reasons


def _read_declared_files(config: HostReadbackConfig) -> tuple[dict[str, tuple[ExpectedArtifact, bytes]], list[str]]:
    reasons: list[str] = []
    try:
        root = Path(config.artifact_root)
    except (TypeError, ValueError):
        return {}, ["artifact_root_invalid"]
    if not root.is_absolute():
        return {}, ["artifact_root_not_absolute"]
    if root.is_symlink() or not root.is_dir():
        return {}, ["artifact_root_invalid"]
    try:
        root = root.resolve(strict=True)
    except OSError:
        return {}, ["artifact_root_invalid"]
    specs = list(config.expected_artifacts)
    expected_paths: dict[str, ExpectedArtifact] = {}
    for spec in specs:
        try:
            relative = _safe_relative(spec.relative_path)
        except _ReadbackFailure as exc:
            reasons.append(exc.reason)
            continue
        expected_paths[relative] = spec
    actual_paths: set[str] = set()
    try:
        for current, directories, files in os.walk(root, followlinks=False):
            for name in directories + files:
                path = Path(current) / name
                if path.is_symlink():
                    reasons.append("symlink_artifact")
                if path.is_file() and not path.is_symlink():
                    actual_paths.add(path.relative_to(root).as_posix())
    except OSError:
        reasons.append("artifact_root_unreadable")
    if actual_paths - set(expected_paths):
        reasons.append("extra_artifact")
    if set(expected_paths) - actual_paths:
        reasons.append("missing_artifact")
    loaded: dict[str, tuple[ExpectedArtifact, bytes]] = {}
    for relative, spec in expected_paths.items():
        path = root / Path(relative)
        try:
            if path.is_symlink() or path.resolve(strict=True).relative_to(root) is None:
                reasons.append("symlink_or_root_escape")
                continue
            raw = path.read_bytes()
        except (OSError, ValueError):
            reasons.append("missing_artifact")
            continue
        if _sha256(raw) != spec.sha256:
            reasons.append("artifact_hash_mismatch")
        loaded[spec.role + "\0" + spec.identity] = (spec, raw)
    return loaded, reasons


def _role_value(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], role: str) -> tuple[ExpectedArtifact, bytes] | None:
    for spec, raw in loaded.values():
        if spec.role == role:
            return spec, raw
    return None


def _json_role(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], role: str) -> tuple[ExpectedArtifact, Mapping[str, Any]]:
    item = _role_value(loaded, role)
    if item is None:
        raise _ReadbackFailure("required_artifact_missing")
    spec, raw = item
    if spec.kind != "json":
        raise _ReadbackFailure("artifact_kind_mismatch")
    try:
        return spec, _load_canonical_json(raw)
    except _ReadbackFailure:
        raise


def _check_source_chain(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], config: HostReadbackConfig) -> list[str]:
    reasons: list[str] = []
    try:
        instruction_spec, instruction = _json_role(loaded, "instruction")
        result_spec, result = _json_role(loaded, "source_result")
        if instruction_spec.identity == result_spec.identity:
            reasons.append("duplicate_source_identity")
        if instruction.get("instruction_id") != instruction_spec.identity:
            reasons.append("instruction_identity_mismatch")
        _exact_target(instruction.get("target"), config)
        if instruction.get("authority") != {"approved": True, "authority_envelope": "gate4-engineering", "source": "chatgpt"}:
            reasons.append("instruction_authority_mismatch")
        if result.get("instruction_id") != instruction_spec.identity:
            reasons.append("source_result_instruction_mismatch")
        if result.get("source_sha256") is not None and result.get("source_sha256") != instruction_spec.sha256:
            reasons.append("source_instruction_hash_mismatch")
        _exact_target(result.get("target"), config)
        if result.get("execution_state") != "CODEX_EXECUTION_TIMEOUT":
            reasons.append("source_timeout_status_upgraded_or_wrong")
        if result.get("terminal") is False or result.get("codex_process", {}).get("timed_out") is False:
            reasons.append("source_timeout_non_terminal")
        if result.get("provider_calls") != 0 or result.get("source_acquisition") is not False:
            reasons.append("source_provider_or_acquisition_activity")
        if result.get("publication") is not False or result.get("semantic_product_work") != "NOT_PERFORMED":
            reasons.append("source_result_scope_invalid")
        attestation = result.get("workspace_attestation")
        if isinstance(attestation, Mapping) and (attestation.get("local_commit") or attestation.get("commit")):
            reasons.append("source_result_commit_present")
    except (AttributeError, KeyError, TypeError) as exc:
        reasons.append("source_result_shape_invalid")
    except _ReadbackFailure as exc:
        reasons.append(exc.reason)
    return reasons


def _check_active_context(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], config: HostReadbackConfig) -> list[str]:
    reasons: list[str] = []
    try:
        fence_spec, fence = _json_role(loaded, "fence")
        status_spec, status = _json_role(loaded, "status")
        ledger_spec, ledger = _json_role(loaded, "ledger")
        if fence_spec.sha256 != config.fence_sha256:
            reasons.append("fence_hash_mismatch")
        if fence.get("schema") != "charitygraph.g4-o1b-dormant-fence/v1" or fence.get("state") != "ACTIVE":
            reasons.append("fence_not_active")
        if fence.get("version", fence.get("fence_version")) != config.fence_version:
            reasons.append("fence_version_mismatch")
        _exact_active_context(fence, config, version_keys=("version", "fence_version"))
        if status.get("schema") != "charitygraph.g4-o1c-cutover-status/v1":
            reasons.append("status_schema_invalid")
        _exact_active_context(status, config, version_keys=("fence_version", "version"))
        if status.get("watcher_state") != "READY" or status.get("active_execution") is not None:
            reasons.append("status_active_or_not_ready")
        last_identity = status.get("last_result_identity")
        instruction_spec, _ = _json_role(loaded, "instruction")
        if isinstance(last_identity, Mapping) and last_identity.get("instruction_id") not in {None, instruction_spec.identity}:
            reasons.append("status_result_identity_mismatch")
        last_result = status.get("last_result")
        if isinstance(last_result, Mapping) and last_result.get("execution_state") != "CODEX_EXECUTION_TIMEOUT":
            reasons.append("source_timeout_status_upgraded_or_wrong")
        if ledger.get("schema") != "charitygraph.g4-o1c-supervisory-ledger/v1":
            reasons.append("ledger_schema_invalid")
        _exact_active_context(ledger, config, version_keys=("fence_version", "version"))
        if ledger.get("dispatch_clear") is not True or ledger.get("active_or_ambiguous_claims") != []:
            reasons.append("ledger_claim_or_dispatch_blocker")
        counts = ledger.get("instruction_counts")
        if not isinstance(counts, Mapping) or any(counts.get(key) != 0 for key in ("pending", "claimed", "running", "reconciliation_required")):
            reasons.append("ledger_status_inconsistent")
        if status_spec.identity == ledger_spec.identity:
            reasons.append("duplicate_context_identity")
    except (AttributeError, KeyError, TypeError):
        reasons.append("active_context_shape_invalid")
    except _ReadbackFailure as exc:
        reasons.append(exc.reason)
    return reasons


def _check_reconciliation_and_tests(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], config: HostReadbackConfig) -> list[str]:
    reasons: list[str] = []
    try:
        source_item = _role_value(loaded, "source_result")
        if source_item is None:
            raise _ReadbackFailure("required_artifact_missing")
        source_spec, _ = source_item
        report_item = _role_value(loaded, "reconciliation_report")
        if report_item is None:
            raise _ReadbackFailure("reconciliation_evidence_missing")
        report_spec, report_raw = report_item
        if not report_raw or report_spec.kind not in {"text", "json"}:
            reasons.append("reconciliation_report_invalid")
        result_spec, result = _json_role(loaded, "reconciliation_result")
        if result_spec.identity == source_spec.identity or result_spec.sha256 == source_spec.sha256:
            reasons.append("reconciliation_result_not_separate")
        if result.get("status") != "COMPLETED" or result.get("verified") is not True or result.get("independent") is not True:
            reasons.append("reconciliation_not_independent_completed_verified")
        if result.get("source_result_id") is not None and result.get("source_result_id") != source_spec.identity:
            reasons.append("reconciliation_source_identity_mismatch")
        if result.get("source_result_sha256") is not None and result.get("source_result_sha256") != source_spec.sha256:
            reasons.append("reconciliation_source_hash_mismatch")
        for role, expected in EXPECTED_TEST_COUNTS.items():
            spec, proof = _json_role(loaded, role)
            if proof.get("identity") not in {None, spec.identity}:
                reasons.append("test_attestation_identity_mismatch")
            if proof.get("status") != "PASSED" or proof.get("passed") != expected or proof.get("expected") != expected:
                reasons.append("independent_test_evidence_invalid")
            if proof.get("terminal") is False:
                reasons.append("independent_test_evidence_non_terminal")
    except (AttributeError, KeyError, TypeError):
        reasons.append("reconciliation_or_test_shape_invalid")
    except _ReadbackFailure as exc:
        reasons.append(exc.reason)
    return reasons


def _check_candidate_package(loaded: Mapping[str, tuple[ExpectedArtifact, bytes]], config: HostReadbackConfig) -> list[str]:
    reasons: list[str] = []
    try:
        package_spec, package = _json_role(loaded, "candidate_package")
        manifest_spec, manifest = _json_role(loaded, "manifest")
        anchor_spec, anchor = _json_role(loaded, "source_anchor")
        if package.get("schema") != "charitygraph.g4-t4e-candidate-package/v1":
            reasons.append("candidate_package_schema_invalid")
        if package.get("manifest_identity") != manifest_spec.identity or package.get("source_anchor_identity") != anchor_spec.identity:
            reasons.append("candidate_package_binding_invalid")
        expected_entries = [{"path": path, "sha256": sha} for path, sha in EXPECTED_CANDIDATE_ALLOWLIST]
        if manifest != {"entries": expected_entries, "format": "candidate-manifest/v1"}:
            reasons.append("manifest_not_exact_allowlist")
        if anchor != {"entries": expected_entries, "format": "source-anchor/v1"}:
            reasons.append("source_anchor_not_exact_allowlist")
        package_files = package.get("files")
        expected_package_files = [
            {"artifact_identity": item.artifact_identity, "path": item.path, "sha256": item.sha256}
            for item in config.candidate_files
        ]
        if package_files != expected_package_files:
            reasons.append("candidate_package_files_invalid")
        candidate_specs = [spec for spec, _ in loaded.values() if spec.role == "candidate_file"]
        for item in config.candidate_files:
            matching = [spec for spec in candidate_specs if spec.identity == item.artifact_identity]
            if len(matching) != 1:
                reasons.append("candidate_file_missing_or_duplicate")
            elif matching[0].sha256 != item.sha256:
                reasons.append("candidate_file_hash_mismatch")
    except (AttributeError, KeyError, TypeError):
        reasons.append("candidate_package_shape_invalid")
    except _ReadbackFailure as exc:
        reasons.append(exc.reason)
    return reasons


def _attestation(config: HostReadbackConfig, status: str, reasons: Iterable[str], loaded: Mapping[str, tuple[ExpectedArtifact, bytes]]) -> HostReadbackAttestation:
    unique_reasons = tuple(dict.fromkeys(reasons))
    verified = tuple(
        {
            "identity": spec.identity,
            "role": spec.role,
            "sha256": spec.sha256,
            "trust_scope": STRUCTURE_ONLY_UNAUTHENTICATED,
        }
        for spec, _ in sorted(loaded.values(), key=lambda item: (item[0].role, item[0].identity))
        if spec.role != "candidate_file" or spec.identity in {item.artifact_identity for item in config.candidate_files}
    )
    source = _role_value(loaded, "source_result")
    source_identity = source[0].identity if source else None
    return HostReadbackAttestation(
        status=status,
        action="NONE",
        reasons=unique_reasons or (STRUCTURE_ONLY_REASON,),
        target=MappingProxyType({
            "repository": config.repository,
            "branch": config.branch,
            "head": config.head,
            "fence_version": config.fence_version,
            "workspace_verified": bool(config.workspace),
        }),
        verified_artifacts=tuple(MappingProxyType(dict(item)) for item in verified),
        historical_timeout=MappingProxyType({
            "result_identity": source_identity,
            "terminal": status == STRUCTURE_ONLY_UNAUTHENTICATED and not any(
                reason.startswith("source_timeout") or reason == "source_timeout_status_upgraded_or_wrong"
                for reason in unique_reasons
            ),
            "evidence_only": True,
            "authenticated": False,
            "trust_scope": STRUCTURE_ONLY_UNAUTHENTICATED,
        }),
        active_context=MappingProxyType({
            "fence_structurally_consistent": "fence_not_active" not in unique_reasons and "fence_version_mismatch" not in unique_reasons,
            "status_structurally_consistent": "status_active_or_not_ready" not in unique_reasons,
            "ledger_structurally_consistent": "ledger_claim_or_dispatch_blocker" not in unique_reasons,
            "trust_scope": STRUCTURE_ONLY_UNAUTHENTICATED,
        }),
        limitations=MappingProxyType({
            "dormant": True,
            "actionable": False,
            "host_authentication_required": True,
            "host_trust_root_present": bool(config.host_trust_root),
            "host_trust_root_authenticated": False,
            "adoption_grant": False,
            "recovery_authority": False,
            "caller_inputs_authenticated": False,
            "pin_set_authenticated": False,
            "independent_reconciliation_authenticated": False,
            "test_attestations_authenticated": False,
            "report_content_authenticated": False,
            "structural_declarations_only": True,
            "trust_scope": STRUCTURE_ONLY_UNAUTHENTICATED,
            "requires_separate_host_authentication_and_acceptance": True,
            "trusted_recovery_pins_actionable": False,
            "recovery_host_readback_actionable": False,
            "provider_calls": 0,
            "source_acquisition": False,
            "publication": False,
            "git_writes": False,
            "filesystem_writes": False,
            "raw_bytes_exposed": False,
            "private_paths_exposed": False,
        }),
    )


def verify_host_readback(config: HostReadbackConfig) -> HostReadbackAttestation:
    """Read and verify one private artifact bundle, failing closed.

    The function performs no writes and never calls a provider, Git, bridge,
    watcher, or process.  A structurally positive result remains explicitly
    non-actionable and cannot be passed as ``TrustedRecoveryPins`` or
    ``RecoveryHostReadback`` authority.
    """

    if not isinstance(config, HostReadbackConfig):
        return _attestation(
            HostReadbackConfig(Path("."), "", "0" * 64, tuple()),
            "BLOCKED",
            ["configuration_invalid"],
            {},
        )
    try:
        _, config_reasons = _artifact_spec_checks(config)
        loaded, read_reasons = _read_declared_files(config)
    except (AttributeError, KeyError, TypeError, ValueError):
        return _attestation(config, "BLOCKED", ["configuration_or_artifact_shape_invalid"], {})
    reasons = config_reasons + read_reasons
    if not config_reasons:
        reasons.extend(_check_source_chain(loaded, config))
        reasons.extend(_check_active_context(loaded, config))
        reasons.extend(_check_reconciliation_and_tests(loaded, config))
        reasons.extend(_check_candidate_package(loaded, config))
    if reasons:
        return _attestation(config, "BLOCKED", reasons, loaded)
    return _attestation(config, STRUCTURE_ONLY_UNAUTHENTICATED, (), loaded)


__all__ = [
    "CandidateFilePin",
    "EXPECTED_CANDIDATE_ALLOWLIST",
    "EXPECTED_REPOSITORY",
    "EXPECTED_BRANCH",
    "ExpectedArtifact",
    "HostReadbackAttestation",
    "HostReadbackConfig",
    "POLICY_PROVENANCE_EPOCH",
    "SCHEMA",
    "STRUCTURE_ONLY_UNAUTHENTICATED",
    "verify_host_readback",
]
