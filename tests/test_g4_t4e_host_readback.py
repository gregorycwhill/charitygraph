from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from bridge.g4_t4e_host_readback import (
    EXPECTED_CANDIDATE_ALLOWLIST,
    EXPECTED_BRANCH,
    EXPECTED_REPOSITORY,
    CandidateFilePin,
    ExpectedArtifact,
    HostReadbackConfig,
    STRUCTURE_ONLY_UNAUTHENTICATED,
    verify_host_readback,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _write(root: Path, relative: str, raw: bytes) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)


def _fixture(
    tmp_path: Path,
    *,
    head: str = "9a0a7d60e920242e843f1d9f7be282a870022624",
    fence_version: str = "v74",
) -> tuple[HostReadbackConfig, dict[str, bytes]]:
    root = tmp_path / "private-bundle"
    root.mkdir(parents=True)
    workspace = r"C:\CharityGraph-runtime\clean-target-g4-t4e"
    instruction_id = "instruction-t4e-timeout-20261031"
    source_id = "result-t4e-timeout-20261031"
    reconciliation_id = "result-t4e-reconciliation-20261031"
    fence = {
        "branch": EXPECTED_BRANCH,
        "head": head,
        "schema": "charitygraph.g4-o1b-dormant-fence/v1",
        "state": "ACTIVE",
        "version": fence_version,
        "repository": EXPECTED_REPOSITORY,
        "workspace_path": workspace,
    }
    instruction = {
        "authority": {"approved": True, "authority_envelope": "gate4-engineering", "source": "chatgpt"},
        "instruction_id": instruction_id,
        "schema": "charitygraph.autonomous-instruction/v1",
        "target": {"branch": EXPECTED_BRANCH, "head": head, "repository": EXPECTED_REPOSITORY, "workspace": workspace},
    }
    result = {
        "codex_process": {"timed_out": True},
        "execution_state": "CODEX_EXECUTION_TIMEOUT",
        "instruction_id": instruction_id,
        "provider_calls": 0,
        "publication": False,
        "schema": "charitygraph.g4-o1c-result/v1",
        "semantic_product_work": "NOT_PERFORMED",
        "source_acquisition": False,
        "source_sha256": "INSTRUCTION_HASH_PLACEHOLDER",
        "target": {"branch": EXPECTED_BRANCH, "head": head, "repository": EXPECTED_REPOSITORY, "workspace": workspace},
        "terminal": True,
    }
    instruction_raw = _json(instruction)
    result["source_sha256"] = _sha(instruction_raw)
    result_raw = _json(result)
    report_raw = b"Independent reconciliation report: 32 focused and 50 regression tests were observed.\n"
    reconciliation = {
        "independent": True,
        "schema": "charitygraph.g4-t4e-reconciliation-result/v1",
        "source_result_id": source_id,
        "source_result_sha256": _sha(result_raw),
        "status": "COMPLETED",
        "verified": True,
    }
    status = {
        "active_execution": None,
        "branch": EXPECTED_BRANCH,
        "head": head,
        "last_result_identity": {"instruction_id": instruction_id},
        "fence_version": fence_version,
        "repository": EXPECTED_REPOSITORY,
        "schema": "charitygraph.g4-o1c-cutover-status/v1",
        "watcher_state": "READY",
        "workspace_path": workspace,
    }
    ledger = {
        "active_or_ambiguous_claims": [],
        "branch": EXPECTED_BRANCH,
        "dispatch_clear": True,
        "fence_version": fence_version,
        "head": head,
        "instruction_counts": {"complete": 1, "failed": 0, "pending": 0, "claimed": 0, "running": 0, "reconciliation_required": 0},
        "repository": EXPECTED_REPOSITORY,
        "schema": "charitygraph.g4-o1c-supervisory-ledger/v1",
        "workspace": workspace,
    }
    focused = {"expected": 32, "identity": "focused-32-20261031", "passed": 32, "schema": "charitygraph.g4-t4e-test-attestation/v1", "status": "PASSED", "terminal": True}
    regression = {"expected": 50, "identity": "regression-50-20261031", "passed": 50, "schema": "charitygraph.g4-t4e-test-attestation/v1", "status": "PASSED", "terminal": True}
    candidate_files = {path: Path(path).read_bytes() for path, _ in EXPECTED_CANDIDATE_ALLOWLIST}
    manifest_entries = [{"path": path, "sha256": _sha(candidate_files[path])} for path, _ in EXPECTED_CANDIDATE_ALLOWLIST]
    manifest = {"entries": manifest_entries, "format": "candidate-manifest/v1"}
    anchor = {"entries": manifest_entries, "format": "source-anchor/v1"}
    package = {
        "files": [
            {"artifact_identity": f"candidate:{path}", "path": path, "sha256": _sha(candidate_files[path])}
            for path, _ in EXPECTED_CANDIDATE_ALLOWLIST
        ],
        "manifest_identity": "manifest-t4e-20261031",
        "schema": "charitygraph.g4-t4e-candidate-package/v1",
        "source_anchor_identity": "anchor-t4e-20261031",
    }
    payloads: dict[str, bytes] = {
        "instruction": instruction_raw,
        "source_result": result_raw,
        "reconciliation_report": report_raw,
        "reconciliation_result": _json(reconciliation),
        "fence": _json(fence),
        "status": _json(status),
        "ledger": _json(ledger),
        "focused_attestation": _json(focused),
        "regression_attestation": _json(regression),
        "candidate_package": _json(package),
        "manifest": _json(manifest),
        "source_anchor": _json(anchor),
    }
    paths = {
        "instruction": "instruction.json",
        "source_result": "source-result.json",
        "reconciliation_report": "reconciliation-report.md",
        "reconciliation_result": "reconciliation-result.json",
        "fence": "fence.json",
        "status": "status.json",
        "ledger": "ledger.json",
        "focused_attestation": "focused.json",
        "regression_attestation": "regression.json",
        "candidate_package": "candidate-package.json",
        "manifest": "manifest.json",
        "source_anchor": "source-anchor.json",
    }
    identities = {
        "instruction": instruction_id,
        "source_result": source_id,
        "reconciliation_report": "report-reconciliation-20261031",
        "reconciliation_result": reconciliation_id,
        "fence": f"fence-{fence_version}-20261031",
        "status": f"status-{fence_version}-20261031",
        "ledger": f"ledger-{fence_version}-20261031",
        "focused_attestation": "focused-32-20261031",
        "regression_attestation": "regression-50-20261031",
        "candidate_package": "package-t4e-20261031",
        "manifest": "manifest-t4e-20261031",
        "source_anchor": "anchor-t4e-20261031",
    }
    specs = [ExpectedArtifact(identities[role], paths[role], _sha(raw), role, "text" if role == "reconciliation_report" else "json") for role, raw in payloads.items()]
    for path, raw in candidate_files.items():
        identity = f"candidate:{path}"
        specs.append(ExpectedArtifact(identity, f"candidate-bytes/{path.replace('/', '__')}", _sha(raw), "candidate_file", "bytes"))
    for role, raw in payloads.items():
        _write(root, paths[role], raw)
    for path, raw in candidate_files.items():
        _write(root, f"candidate-bytes/{path.replace('/', '__')}", raw)
    config = HostReadbackConfig(
        root,
        workspace,
        _sha(payloads["fence"]),
        tuple(specs),
        head=head,
        fence_version=fence_version,
        pin_set_id=f"caller-declared-t4e-{fence_version}",
    )
    return config, payloads


def test_positive_readback_is_immutable_redacted_and_nonactionable(tmp_path):
    config, _ = _fixture(tmp_path)
    before = sorted((p.relative_to(config.artifact_root).as_posix(), p.read_bytes()) for p in config.artifact_root.rglob("*") if p.is_file())
    attestation = verify_host_readback(config)
    after = sorted((p.relative_to(config.artifact_root).as_posix(), p.read_bytes()) for p in config.artifact_root.rglob("*") if p.is_file())
    assert attestation.status == STRUCTURE_ONLY_UNAUTHENTICATED
    assert attestation.action == "NONE"
    assert attestation.reasons == ("structure_only_unauthenticated",)
    assert attestation.limitations["host_authentication_required"] is True
    assert attestation.limitations["structural_declarations_only"] is True
    assert attestation.limitations["adoption_grant"] is False
    assert attestation.limitations["caller_inputs_authenticated"] is False
    assert attestation.limitations["trusted_recovery_pins_actionable"] is False
    assert attestation.limitations["recovery_host_readback_actionable"] is False
    serialised = json.dumps(attestation.as_dict(), sort_keys=True)
    assert "candidate bytes" not in serialised
    assert str(config.artifact_root) not in serialised
    assert before == after
    with pytest.raises((AttributeError, TypeError)):
        attestation.reasons += ("mutated",)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("role", "replacement"),
    [
        ("candidate_package", (b"candidate:", b"forged:")),
        ("manifest", (b"candidate-manifest/v1", b"candidate-manifest/v2")),
        ("source_result", (b"CODEX_EXECUTION_TIMEOUT", b"CODEX_ENGINEERING_COMPLETED")),
        ("ledger", (b'"dispatch_clear":true', b'"dispatch_clear":false')),
    ],
)
def test_byte_tamper_is_blocked_without_trusting_candidate_claims(tmp_path, role, replacement):
    config, payloads = _fixture(tmp_path)
    spec = next(item for item in config.expected_artifacts if item.role == role)
    (config.artifact_root / spec.relative_path).write_bytes(payloads[role].replace(*replacement))
    result = verify_host_readback(config)
    assert result.status == "BLOCKED"
    assert "artifact_hash_mismatch" in result.reasons


def test_missing_and_extra_files_are_blocked(tmp_path):
    config, _ = _fixture(tmp_path)
    (config.artifact_root / "ledger.json").unlink()
    (config.artifact_root / "unexpected.bin").write_bytes(b"extra")
    result = verify_host_readback(config)
    assert result.status == "BLOCKED"
    assert "missing_artifact" in result.reasons
    assert "extra_artifact" in result.reasons


def test_path_traversal_and_symlink_are_blocked(tmp_path, monkeypatch):
    config, _ = _fixture(tmp_path)
    specs = list(config.expected_artifacts)
    specs[0] = ExpectedArtifact(specs[0].identity, "../outside.json", specs[0].sha256, specs[0].role, specs[0].kind)
    altered = replace(config, expected_artifacts=tuple(specs))
    result = verify_host_readback(altered)
    assert result.status == "BLOCKED"
    assert "unsafe_artifact_path" in result.reasons
    link = config.artifact_root / "symlink.json"
    try:
        os.symlink(config.artifact_root / "fence.json", link)
    except (OSError, NotImplementedError):
        link.write_bytes(b"symlink sentinel")
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original_is_symlink(path))
    assert "symlink_artifact" in verify_host_readback(config).reasons
    assert "artifact_root_not_absolute" in verify_host_readback(replace(config, artifact_root=Path("relative-root"))).reasons


def test_stale_dynamic_context_and_inconsistent_ledger_are_blocked(tmp_path):
    config, _ = _fixture(tmp_path)
    fence = config.artifact_root / "fence.json"
    value = json.loads(fence.read_bytes())
    value["head"] = "0" * 40
    raw = _json(value)
    fence.write_bytes(raw)
    specs = [replace(spec, sha256=_sha(raw)) if spec.role == "fence" else spec for spec in config.expected_artifacts]
    altered = replace(config, expected_artifacts=tuple(specs), fence_sha256=_sha(raw))
    result = verify_host_readback(altered)
    assert result.status == "BLOCKED"
    assert "branch_or_head_mismatch" in result.reasons


@pytest.mark.parametrize("fence_version", ["v74", "v75", "v120"])
def test_dynamic_active_context_versions_are_structural_only(tmp_path, fence_version):
    config, _ = _fixture(tmp_path, fence_version=fence_version, head="b" * 40)
    result = verify_host_readback(config)
    assert result.status == STRUCTURE_ONLY_UNAUTHENTICATED
    assert result.action == "NONE"
    assert result.limitations["host_authentication_required"] is True
    assert result.limitations["recovery_authority"] is False


@pytest.mark.parametrize(
    ("role", "field", "replacement", "reason"),
    [
        ("status", "head", "c" * 40, "branch_or_head_mismatch"),
        ("ledger", "workspace", r"C:\\other-workspace", "workspace_mismatch"),
        ("ledger", "fence_version", "v75", "fence_version_mismatch"),
    ],
)
def test_raw_context_records_must_match_observed_context(tmp_path, role, field, replacement, reason):
    config, _ = _fixture(tmp_path)
    spec = next(item for item in config.expected_artifacts if item.role == role)
    value = json.loads((config.artifact_root / spec.relative_path).read_bytes())
    value[field] = replacement
    raw = _json(value)
    (config.artifact_root / spec.relative_path).write_bytes(raw)
    specs = [replace(item, sha256=_sha(raw)) if item.role == role else item for item in config.expected_artifacts]
    result = verify_host_readback(replace(config, expected_artifacts=tuple(specs)))
    assert result.status == "BLOCKED"
    assert reason in result.reasons


def test_caller_pins_and_synthetic_independent_evidence_are_not_authenticated(tmp_path):
    config, _ = _fixture(tmp_path)
    result = verify_host_readback(replace(config, pin_set_id="fake-caller-pin", host_trust_root="fake-root"))
    assert result.status == STRUCTURE_ONLY_UNAUTHENTICATED
    assert result.limitations["pin_set_authenticated"] is False
    assert result.limitations["independent_reconciliation_authenticated"] is False
    assert result.limitations["test_attestations_authenticated"] is False
    assert result.limitations["report_content_authenticated"] is False
    assert result.limitations["host_trust_root_authenticated"] is False


def test_missing_host_trust_root_cannot_promote_authority(tmp_path):
    config, _ = _fixture(tmp_path)
    result = verify_host_readback(config)
    assert result.status == STRUCTURE_ONLY_UNAUTHENTICATED
    assert result.limitations["host_trust_root_present"] is False
    assert result.limitations["host_authentication_required"] is True
    assert result.limitations["adoption_grant"] is False


def test_noncanonical_json_is_blocked_even_when_its_declared_hash_is_updated(tmp_path):
    config, _ = _fixture(tmp_path)
    status_spec = next(spec for spec in config.expected_artifacts if spec.role == "status")
    raw = b'{"watcher_state": "READY", "active_execution": null}\n'
    (config.artifact_root / status_spec.relative_path).write_bytes(raw)
    specs = [replace(spec, sha256=_sha(raw)) if spec.role == "status" else spec for spec in config.expected_artifacts]
    result = verify_host_readback(replace(config, expected_artifacts=tuple(specs)))
    assert result.status == "BLOCKED"
    assert "json_invalid_or_noncanonical" in result.reasons


def test_missing_independent_test_evidence_and_wrong_allowlist_fail_closed(tmp_path):
    config, _ = _fixture(tmp_path)
    (config.artifact_root / "focused.json").unlink()
    result = verify_host_readback(config)
    assert result.status == "BLOCKED"
    assert "missing_artifact" in result.reasons
    assert "independent_test_evidence_invalid" in result.reasons or "required_artifact_missing" in result.reasons
    wrong = replace(config, candidate_files=(CandidateFilePin(EXPECTED_CANDIDATE_ALLOWLIST[0][0], "0" * 64, "candidate:wrong"),) + config.candidate_files[1:])
    assert "candidate_allowlist_invalid" in verify_host_readback(wrong).reasons
    fake_identity = replace(
        config,
        candidate_files=(
            CandidateFilePin(config.candidate_files[0].path, config.candidate_files[0].sha256, "candidate:fake"),
        ) + config.candidate_files[1:],
    )
    assert "candidate_identity_allowlist_invalid" in verify_host_readback(fake_identity).reasons


def test_exact_candidate_hash_allowlist_remains_unchanged(tmp_path):
    config, _ = _fixture(tmp_path)
    assert tuple((item.path, item.sha256) for item in config.candidate_files) == EXPECTED_CANDIDATE_ALLOWLIST
    result = verify_host_readback(config)
    assert result.status == STRUCTURE_ONLY_UNAUTHENTICATED
    assert all(item["trust_scope"] == STRUCTURE_ONLY_UNAUTHENTICATED for item in result.verified_artifacts)


def test_duplicate_source_identity_and_timeout_semantics_are_rejected(tmp_path):
    config, _ = _fixture(tmp_path)
    specs = list(config.expected_artifacts)
    source_index = next(i for i, spec in enumerate(specs) if spec.role == "source_result")
    instruction = specs[next(i for i, spec in enumerate(specs) if spec.role == "instruction")]
    specs[source_index] = ExpectedArtifact(instruction.identity, specs[source_index].relative_path, specs[source_index].sha256, "source_result")
    altered = replace(config, expected_artifacts=tuple(specs))
    result = verify_host_readback(altered)
    assert result.status == "BLOCKED"
    assert "duplicate_artifact_identity" in result.reasons

    config, _ = _fixture(tmp_path / "timeout")
    source_spec = next(spec for spec in config.expected_artifacts if spec.role == "source_result")
    source = json.loads((config.artifact_root / source_spec.relative_path).read_bytes())
    source["execution_state"] = "CODEX_ENGINEERING_COMPLETED"
    raw = _json(source)
    (config.artifact_root / source_spec.relative_path).write_bytes(raw)
    specs = [replace(spec, sha256=_sha(raw)) if spec.role == "source_result" else spec for spec in config.expected_artifacts]
    timeout_result = verify_host_readback(replace(config, expected_artifacts=tuple(specs)))
    assert "source_timeout_status_upgraded_or_wrong" in timeout_result.reasons


def test_zero_writes_and_no_authorisation_promotion(tmp_path):
    config, _ = _fixture(tmp_path)
    unrelated = config.artifact_root.parent / "unrelated-dirty.txt"
    unrelated.write_bytes(b"preserve me")
    index_sentinel = config.artifact_root.parent / "unrelated-index-sentinel"
    index_sentinel.write_bytes(b"staged-state-sentinel")
    before = {p: p.stat().st_mtime_ns for p in config.artifact_root.rglob("*") if p.is_file()}
    result = verify_host_readback(config)
    after = {p: p.stat().st_mtime_ns for p in config.artifact_root.rglob("*") if p.is_file()}
    assert result.limitations["git_writes"] is False
    assert result.limitations["filesystem_writes"] is False
    assert before == after
    assert unrelated.read_bytes() == b"preserve me"
    assert index_sentinel.read_bytes() == b"staged-state-sentinel"
    assert result.as_dict()["action"] == "NONE"
