import json

import pytest

from charitygraph.s0_identity import finalize_checkpoint, verify_checkpoint
from charitygraph.scale_s0 import ScalePreflightError


def _fixture(tmp_path):
    (tmp_path / "locator-packet-manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "attempt13.sqlite3").write_bytes(b"sqlite-fixture")
    (tmp_path / "PREFLIGHT-RESULT.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


def test_finalizer_and_verifier_are_order_independent_and_detect_mutation(tmp_path):
    root = _fixture(tmp_path)
    result = finalize_checkpoint(root, {"attempt_material_hash": "a" * 64, "status": "prepared"})
    assert result["manifest_material_sha256"]
    verify_checkpoint(root, expected_attempt_material_hash="a" * 64)
    (root / "PREFLIGHT-RESULT.json").write_text('{"mutated":true}\n', encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="hash mismatch"):
        verify_checkpoint(root)


def test_wrong_attempt_material_hash_is_rejected(tmp_path):
    root = _fixture(tmp_path)
    finalize_checkpoint(root, {"attempt_material_hash": "b" * 64})
    with pytest.raises(ScalePreflightError, match="attempt material hash"):
        verify_checkpoint(root, expected_attempt_material_hash="c" * 64)
