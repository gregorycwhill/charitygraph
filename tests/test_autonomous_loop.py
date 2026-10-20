from datetime import datetime, timedelta, timezone

import pytest

from charitygraph.autonomous_loop import (
    AmbiguousInterruption,
    ClaimUnavailable,
    DuplicateInstruction,
    InstructionEnvelope,
    InvalidInstruction,
    LocalAutonomousBridge,
    StaleOwnership,
)


HEAD = "a" * 40


def envelope(*, instruction_id="gate4:test", content="run the private rehearsal"):
    return InstructionEnvelope.create(
        instruction_id=instruction_id,
        content=content,
        target={
            "repository": "charitygraph",
            "workspace_path": "C:/workspace/charitygraph",
            "branch": "gate4-test",
            "head": HEAD,
            "model": "luna-high",
        },
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def test_submit_is_immutable_and_duplicate_delivery_is_idempotent(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path).open()
    first = bridge.submit(envelope())
    duplicate = bridge.submit(envelope())
    assert first["accepted"] is True
    assert duplicate == {"accepted": False, "duplicate": True, "status": "pending", "instruction_id": "gate4:test"}
    with pytest.raises(DuplicateInstruction):
        bridge.submit(envelope(content="changed body"))


def test_claim_and_result_are_durable_and_single_owner(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path).open()
    bridge.submit(envelope())
    claimed = bridge.claim(owner="watcher-a", now=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert claimed.instruction_id == "gate4:test"
    bridge.begin("gate4:test", owner="watcher-a")
    with pytest.raises(StaleOwnership):
        bridge.complete("gate4:test", owner="watcher-b", result={"ok": False})
    done = bridge.complete("gate4:test", owner="watcher-a", result={"ok": True, "attempts": 1})
    assert done["status"] == "complete"
    assert bridge.inspect("gate4:test")["status"] == "complete"
    assert bridge.complete("gate4:test", owner="watcher-a", result={"different": True})["result_sha256"] == done["result_sha256"]


def test_stale_lease_requires_explicit_reconciliation(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path).open()
    bridge.submit(envelope())
    at = datetime(2026, 10, 20, tzinfo=timezone.utc)
    bridge.claim(owner="watcher-a", now=at, lease_seconds=1)
    with pytest.raises(AmbiguousInterruption):
        bridge.claim(owner="watcher-b", now=at + timedelta(seconds=2))
    with pytest.raises(AmbiguousInterruption):
        bridge.claim(owner="watcher-b", now=at + timedelta(seconds=2))
    bridge.reconcile("gate4:test", actor="host-bootstrap", rationale="verified no provider crossing and no child process remains", now=at + timedelta(seconds=3))
    assert bridge.claim(owner="watcher-b", now=at + timedelta(seconds=4)).instruction_id == "gate4:test"


def test_invalid_authority_and_forbidden_operation_fail_closed(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path).open()
    bad = envelope().as_dict()
    bad["authority"] = {"source": "manual", "approved": True}
    with pytest.raises(InvalidInstruction):
        bridge.submit(InstructionEnvelope.from_dict(bad))
    bad = envelope().as_dict()
    bad["operation"] = "publish"
    with pytest.raises(InvalidInstruction):
        bridge.submit(InstructionEnvelope.from_dict(bad))
    bad = envelope().as_dict()
    bad["target"]["model"] = "terra-high"
    with pytest.raises(InvalidInstruction, match="unsupported target model"):
        bridge.submit(InstructionEnvelope.from_dict(bad))


def test_claim_requires_an_available_instruction(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path).open()
    with pytest.raises(ClaimUnavailable):
        bridge.claim(owner="watcher-a")


def test_materialized_import_requires_exact_utf8_canonical_bytes(tmp_path):
    bridge = LocalAutonomousBridge(tmp_path / "bridge").open()
    source = tmp_path / "instruction.json"
    source.write_text(__import__("json").dumps(envelope().as_dict(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    imported = bridge.import_materialized_instruction(source)
    assert imported["accepted"] is True
    assert len(imported["materialized_sha256"]) == 64
    source.write_bytes(b"\xef\xbb\xbf" + source.read_bytes())
    with pytest.raises(InvalidInstruction, match="BOM"):
        LocalAutonomousBridge(tmp_path / "other").open().import_materialized_instruction(source)


def test_materialized_import_rejects_pretty_or_multi_line_json(tmp_path):
    source = tmp_path / "pretty.json"
    source.write_text(__import__("json").dumps(envelope().as_dict(), indent=2) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(InvalidInstruction, match="canonical JSON line"):
        LocalAutonomousBridge(tmp_path / "bridge").open().import_materialized_instruction(source)
