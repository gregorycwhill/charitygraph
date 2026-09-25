import json

import pytest

from charitygraph.s0_identity import finalize_checkpoint, verify_checkpoint
from charitygraph.scale_s0 import ScalePreflightError


def _fixture(tmp_path, attempt_number=14):
    (tmp_path / "locator-packet-manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / f"attempt{attempt_number}.sqlite3").write_bytes(b"sqlite-fixture")
    (tmp_path / "PREFLIGHT-RESULT.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


def test_finalizer_and_verifier_are_order_independent_and_detect_mutation(tmp_path):
    root = _fixture(tmp_path)
    result = finalize_checkpoint(root, {"attempt_id": "attempt:s0:14", "run_id": "run:s0:attempt-14", "attempt_material_hash": "a" * 64, "status": "prepared"})
    assert result["manifest_material_sha256"]
    verify_checkpoint(root, expected_attempt_material_hash="a" * 64)
    (root / "PREFLIGHT-RESULT.json").write_text('{"mutated":true}\n', encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="hash mismatch"):
        verify_checkpoint(root)


def test_wrong_attempt_material_hash_is_rejected(tmp_path):
    root = _fixture(tmp_path)
    finalize_checkpoint(root, {"attempt_id": "attempt:s0:14", "run_id": "run:s0:attempt-14", "attempt_material_hash": "b" * 64})
    with pytest.raises(ScalePreflightError, match="attempt material hash"):
        verify_checkpoint(root, expected_attempt_material_hash="c" * 64)


def test_attempt13_checkpoint_format_remains_compatible(tmp_path):
    root = _fixture(tmp_path, attempt_number=13)
    finalize_checkpoint(root, {"attempt_id": "attempt:s0:13", "run_id": "run:s0:attempt-13", "attempt_material_hash": "d" * 64})
    assert (root / "CHECKPOINT-ATTEMPT13.md").is_file()
    verify_checkpoint(root, expected_attempt_material_hash="d" * 64)


def test_wrong_names_and_mismatched_identity_fail_closed(tmp_path):
    root = _fixture(tmp_path)
    with pytest.raises(ScalePreflightError, match="database name"):
        finalize_checkpoint(root, {"attempt_id": "attempt:s0:14", "run_id": "run:s0:attempt-14", "checkpoint_artifacts": {"attempt13.sqlite3": "wrong"}})
    with pytest.raises(ScalePreflightError, match="identities"):
        finalize_checkpoint(root, {"attempt_id": "attempt:s0:14", "run_id": "run:s0:attempt-13"})


def test_explicit_names_are_supported_without_loose_directory_scanning(tmp_path):
    root = _fixture(tmp_path)
    finalize_checkpoint(root, {"attempt_material_hash": "e" * 64}, artifact_names={"database": "attempt14.sqlite3", "checkpoint": "CHECKPOINT-ATTEMPT14.md"})
    verify_checkpoint(root, expected_attempt_material_hash="e" * 64, artifact_names={"database": "attempt14.sqlite3", "checkpoint": "CHECKPOINT-ATTEMPT14.md"})


def test_reusable_checkpoint_code_has_no_attempt13_filename_literal():
    source = __import__("charitygraph.s0_identity", fromlist=["__file__"]).__file__
    text = open(source, encoding="utf-8").read()
    assert "attempt13" not in text.lower()
