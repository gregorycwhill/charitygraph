from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from charitygraph import g4_clean_target_recovery_authority as authority


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _pins() -> authority.TrustedRecoveryPins:
    return authority.TrustedRecoveryPins(
        repository="charitygraph",
        workspace=r"C:\CharityGraph-runtime\clean-target",
        branch=authority.EXPECTED_BRANCH,
        head=authority.EXPECTED_HEAD,
        fence_version=authority.EXPECTED_FENCE_VERSION,
        fence_sha256=authority.EXPECTED_FENCE_SHA256,
        source_instruction_id="instruction-t4e-timeout-20261031",
        source_instruction_sha256=_sha("instruction"),
        source_result_id="result-t4e-timeout-20261031",
        source_result_sha256=_sha("source-result"),
        reconciliation_report_id="report-reconciliation-20261031",
        reconciliation_report_sha256=_sha("reconciliation-report"),
        reconciliation_result_id="result-reconciliation-20261031",
        reconciliation_result_sha256=_sha("reconciliation-result"),
        manifest_sha256=_sha("manifest"),
        source_anchor_sha256=_sha("source-anchor"),
        focused_attestation_id="focused-32-20261031",
        focused_attestation_sha256=_sha("focused-attestation"),
        regression_attestation_id="regression-50-20261031",
        regression_attestation_sha256=_sha("regression-attestation"),
    )


def _envelope(pins: authority.TrustedRecoveryPins) -> dict[str, Any]:
    return {
        "schema": "charitygraph.recovery-authority-v1",
        "target": {
            "repository": pins.repository,
            "workspace": pins.workspace,
            "branch": pins.branch,
            "head": pins.head,
            "fence": {"version": pins.fence_version, "sha256": pins.fence_sha256},
        },
        "source": {
            "instruction": {"id": pins.source_instruction_id, "sha256": pins.source_instruction_sha256},
            "result": {
                "id": pins.source_result_id,
                "sha256": pins.source_result_sha256,
                "execution_state": "CODEX_EXECUTION_TIMEOUT",
                "terminal": True,
                "provider_calls": 0,
                "source_acquisition": False,
                "publication": False,
                "semantic_product_work": "NOT_PERFORMED",
            },
        },
        "candidate": {
            "manifest_sha256": pins.manifest_sha256,
            "source_anchor_sha256": pins.source_anchor_sha256,
            "files": [
                {"path": path, "sha256": sha256} for path, sha256 in pins.artifact_hashes
            ],
        },
        "reconciliation": {
            "report": {"id": pins.reconciliation_report_id, "sha256": pins.reconciliation_report_sha256},
            "result": {"id": pins.reconciliation_result_id, "sha256": pins.reconciliation_result_sha256},
            "status": "COMPLETED",
            "verified": True,
            "independent": True,
        },
        "tests": {
            "focused": {
                "passed": 32,
                "expected": 32,
                "attestation": {"id": pins.focused_attestation_id, "sha256": pins.focused_attestation_sha256},
            },
            "regression": {
                "passed": 50,
                "expected": 50,
                "attestation": {"id": pins.regression_attestation_id, "sha256": pins.regression_attestation_sha256},
            },
        },
        "target_state": {
            "clean": True,
            "tracked_dirty_paths": [],
            "staged_paths": [],
            "untracked_paths": [],
            "ignored_paths": [],
        },
        "scope": {
            "mode": "DORMANT_ONLY",
            "bridge_ingress": False,
            "t3_rights": "BLOCKED",
            "provider_promotion": False,
            "rights_promotion": False,
            "ordinary_tracked_dirty_adoption": False,
        },
    }


def _assert_blocked(envelope: dict[str, Any], pins: authority.TrustedRecoveryPins, reason: str) -> None:
    plan = authority.validate_recovery_authority(envelope, pins)
    assert plan["status"] == "BLOCKED"
    assert reason in plan["reasons"]
    assert plan["action"] == "NONE"


def test_positive_shape_returns_serialisable_dry_run_plan_without_bytes():
    pins = _pins()
    envelope = _envelope(pins)
    plan = authority.validate_recovery_authority(envelope, pins)
    assert plan["status"] == "DRY_RUN_ELIGIBLE"
    assert plan["action"] == "DRY_RUN_ONLY"
    assert plan["source"]["terminal_state"] == "CODEX_EXECUTION_TIMEOUT"
    assert plan["candidate"]["files"] == list(envelope["candidate"]["files"])
    assert plan["tests"]["focused_passed"] == 32
    assert plan["tests"]["regression_passed"] == 50
    json.dumps(plan)
    assert "bytes" not in json.dumps(plan).lower()


def test_canonical_envelope_bytes_are_stable_and_json_serialisable():
    envelope = _envelope(_pins())
    first = authority.canonical_envelope_bytes(envelope)
    reordered = {key: envelope[key] for key in reversed(list(envelope))}
    assert first == authority.canonical_envelope_bytes(reordered)
    assert first.endswith(b"\n")


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda e: e.pop("source"), "envelope_keys_invalid"),
        (lambda e: e.__setitem__("target", {**e["target"], "head": "0" * 40}), "target_identity_mismatch"),
        (lambda e: e["target"]["fence"].__setitem__("sha256", "1" * 64), "fence_mismatch"),
        (lambda e: e["source"]["instruction"].__setitem__("sha256", "1" * 64), "source_instruction_mismatch"),
        (lambda e: e["source"]["result"].__setitem__("execution_state", "CODEX_ENGINEERING_COMPLETED"), "source_result_not_timeout_evidence"),
        (lambda e: e["reconciliation"].__setitem__("verified", False), "reconciliation_not_independently_completed_verified"),
        (lambda e: e["candidate"]["files"].append({"path": "extra", "sha256": "2" * 64}), "candidate_allowlist_invalid"),
        (lambda e: e["candidate"]["files"].__setitem__(0, {"path": e["candidate"]["files"][1]["path"], "sha256": e["candidate"]["files"][0]["sha256"]}), "duplicate_candidate_path"),
        (lambda e: e["tests"]["focused"].__setitem__("passed", 31), "focused_test_proof_invalid"),
        (lambda e: e["tests"]["regression"]["attestation"].__setitem__("sha256", "3" * 64), "regression_attestation_mismatch"),
        (lambda e: e["target_state"].__setitem__("tracked_dirty_paths", ["tracked.py"]), "target_dirty"),
        (lambda e: e["scope"].__setitem__("ordinary_tracked_dirty_adoption", True), "scope_or_rights_limit_invalid"),
        (lambda e: e.__setitem__("candidate", {**e["candidate"], "candidate_signature": "self-asserted"}), "candidate_shape_invalid"),
    ],
)
def test_primary_negative_shapes_fail_closed(mutation, reason):
    pins = _pins()
    envelope = copy.deepcopy(_envelope(pins))
    mutation(envelope)
    _assert_blocked(envelope, pins, reason)


def test_missing_independent_pins_never_becomes_authority():
    plan = authority.validate_recovery_authority(_envelope(_pins()), None)
    assert plan["status"] == "BLOCKED"
    assert plan["reasons"] == ["independent_provenance_missing"]


def test_candidate_self_hash_cannot_replace_independent_pins():
    pins = _pins()
    altered = copy.deepcopy(_envelope(pins))
    altered["candidate"]["manifest_sha256"] = _sha("candidate-self-hash")
    _assert_blocked(altered, pins, "manifest_mismatch")


def test_trusted_pin_allowlist_is_bound_to_the_two_exact_files():
    pins = _pins()
    altered = authority.TrustedRecoveryPins(**{**pins.__dict__, "artifact_hashes": (("other", "4" * 64),)})
    plan = authority.validate_recovery_authority(_envelope(pins), altered)
    assert plan["status"] == "BLOCKED"
    assert "trusted_artifact_allowlist_invalid" in plan["reasons"]


def test_trusted_pins_cannot_retarget_the_validator_to_another_branch():
    pins = _pins()
    altered = authority.TrustedRecoveryPins(**{**pins.__dict__, "branch": "other-branch"})
    plan = authority.validate_recovery_authority(_envelope(pins), altered)
    assert plan["status"] == "BLOCKED"
    assert "trusted_branch_invalid" in plan["reasons"]


def test_fake_success_result_and_same_result_reconciliation_are_blocked():
    pins = _pins()
    envelope = copy.deepcopy(_envelope(pins))
    envelope["reconciliation"]["result"]["id"] = pins.source_result_id
    envelope["reconciliation"]["result"]["sha256"] = pins.source_result_sha256
    _assert_blocked(envelope, pins, "reconciliation_result_not_separate")


def test_dirty_staged_untracked_and_ignored_target_is_blocked():
    pins = _pins()
    envelope = _envelope(pins)
    envelope["target_state"]["staged_paths"] = ["staged"]
    envelope["target_state"]["untracked_paths"] = ["untracked"]
    envelope["target_state"]["ignored_paths"] = ["ignored"]
    _assert_blocked(envelope, pins, "target_dirty")

