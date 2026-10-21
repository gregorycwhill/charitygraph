from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from charitygraph.bounded_authority import (
    BoundedAuthorityError,
    DirtyBaselineViolation,
    InactiveImplementationRoute,
    capture_workspace,
    report_only_execution,
    validate_execution,
    verify_allowed_changes,
)
from charitygraph.mission_ledger import (
    CompareAndSwapConflict,
    DuplicateMissionEvent,
    MissionContract,
    MissionLedger,
    StaleMissionIdentity,
    StaleReviewCursor,
    SupervisorClaimUnavailable,
)
from charitygraph.autonomous_loop import InstructionEnvelope, LocalAutonomousBridge


NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def contract(repo: Path, head: str) -> MissionContract:
    return MissionContract.create(
        mission_id="cg-g4-double-loop-20261021-v1",
        tranche_id="O1E-O1F",
        instruction_id="gate4:engineering:o1e-o1f-bootstrap",
        run_id="run-o1e-o1f-1",
        supervisor_review_id="review-hourly-1",
        repository="charitygraph",
        workspace_path=str(repo.resolve()),
        branch="gate4-test",
        head=head,
        created_at=NOW.isoformat(),
    )


def git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "gate4-test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "G4 test"], cwd=repo, check=True)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return repo, head


def test_mission_start_and_duplicate_event_ingestion_are_idempotent(tmp_path):
    repo, head = git_repo(tmp_path)
    ledger = MissionLedger(tmp_path / "bridge.sqlite3").open()
    first = ledger.start(contract(repo, head))
    duplicate_start = ledger.start(contract(repo, head))
    assert first["duplicate"] is False
    assert duplicate_start["duplicate"] is True
    event = ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_A}, now=NOW)
    assert event["event_seq"] == 2
    assert ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_A}, now=NOW)["duplicate"] is True
    with pytest.raises(DuplicateMissionEvent):
        ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_B}, now=NOW)


def test_supervisor_claims_are_compare_and_swap_and_review_cursor_survives_restart(tmp_path):
    repo, head = git_repo(tmp_path)
    db = tmp_path / "bridge.sqlite3"
    ledger = MissionLedger(db).open()
    ledger.start(contract(repo, head))
    first = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="hourly", expected_version=0, now=NOW)
    with pytest.raises(SupervisorClaimUnavailable):
        ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="interactive", expected_version=1, now=NOW)
    with pytest.raises(CompareAndSwapConflict):
        ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="interactive", expected_version=0, now=NOW)
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="hourly", claim_token=first["claim_token"], version=1, now=NOW)
    second = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="interactive", expected_version=1, now=NOW)
    assert second["version"] == 2
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="interactive", claim_token=second["claim_token"], version=2, now=NOW)
    dispatch = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="interactive", expected_version=0, now=NOW)
    with pytest.raises(SupervisorClaimUnavailable):
        ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="hourly", expected_version=1, now=NOW)
    dispatched = ledger.dispatch("cg-g4-double-loop-20261021-v1", owner="interactive", claim_token=dispatch["claim_token"], version=1, instruction_id="gate4:engineering:successor", instruction_sha256=HASH_A, now=NOW)
    assert dispatched["event_type"] == "dispatch_authorised"
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="interactive", claim_token=dispatch["claim_token"], version=1, now=NOW)
    ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:2", event_type="evidence_seen", payload={"sha256": HASH_B}, now=NOW)
    review = ledger.record_review(
        "cg-g4-double-loop-20261021-v1",
        reviewer_id="interactive",
        decision_id="decision-1",
        cursor_seq=5,
        execution_disposition="READY",
        semantic_disposition="HOLD_FOR_PRODUCT_REVIEW",
        decision={"reason": "offline evidence only"},
        now=NOW,
    )
    assert review["duplicate"] is False
    restarted = MissionLedger(db).open()
    status = restarted.status("cg-g4-double-loop-20261021-v1")
    assert status["review_cursors"][0]["cursor_seq"] == 5
    assert status["latest_decision"]["decision_id"] == "decision-1"
    assert status["latest_decision"]["execution_disposition"] == "READY"
    assert status["latest_decision"]["semantic_disposition"] == "HOLD_FOR_PRODUCT_REVIEW"
    assert "Mission cg-g4-double-loop-20261021-v1" in restarted.supervisor_brief("cg-g4-double-loop-20261021-v1")
    assert restarted.record_review(
        "cg-g4-double-loop-20261021-v1",
        reviewer_id="interactive",
        decision_id="decision-1",
        cursor_seq=5,
        execution_disposition="READY",
        semantic_disposition="HOLD_FOR_PRODUCT_REVIEW",
        decision={"reason": "offline evidence only"},
        now=NOW,
    )["duplicate"] is True
    with pytest.raises(StaleReviewCursor):
        restarted.record_review(
            "cg-g4-double-loop-20261021-v1",
            reviewer_id="interactive",
            decision_id="decision-2",
            cursor_seq=1,
            execution_disposition="READY",
            semantic_disposition="HOLD_FOR_PRODUCT_REVIEW",
            decision={},
            now=NOW,
        )


def test_mission_records_execution_identity_and_rejects_stale_head(tmp_path):
    repo, head = git_repo(tmp_path)
    ledger = MissionLedger(tmp_path / "bridge.sqlite3").open()
    ledger.start(contract(repo, head))
    recorded = ledger.record_execution(
        "cg-g4-double-loop-20261021-v1",
        run_id="run-o1e-o1f-1",
        instruction_sha256=HASH_A,
        result_sha256=HASH_B,
        branch="gate4-test",
        head=head,
        execution_disposition="CODEX_ENGINEERING_COMPLETED",
        report_ref={"path": "reports/o1e.md", "sha256": HASH_B, "private": True},
        now=NOW,
    )
    assert recorded["payload"]["repository"]["head"] == head
    with pytest.raises(StaleMissionIdentity):
        ledger.verify_identity("cg-g4-double-loop-20261021-v1", branch="gate4-test", head="c" * 40, now=NOW)
    assert ledger.status("cg-g4-double-loop-20261021-v1")["latest_event"]["event_type"] == "stale_head_detected"


def test_mission_stop_and_escalation_are_explicit_terminal_states(tmp_path):
    repo, head = git_repo(tmp_path)
    stopped = MissionLedger(tmp_path / "stopped.sqlite3").open()
    stopped.start(contract(repo, head))
    stopped.stop("cg-g4-double-loop-20261021-v1", actor="supervisor", reason="acceptance boundary reached", now=NOW)
    assert stopped.status("cg-g4-double-loop-20261021-v1")["state"] == "stopped"
    escalated = MissionLedger(tmp_path / "escalated.sqlite3").open()
    escalated.start(contract(repo, head))
    escalated.escalate("cg-g4-double-loop-20261021-v1", actor="supervisor", reason="material policy decision required", now=NOW)
    assert escalated.status("cg-g4-double-loop-20261021-v1")["state"] == "escalated"


def test_bounded_authority_rejects_when_inactive_and_report_only_stays_narrow(tmp_path):
    repo, head = git_repo(tmp_path)
    snapshot = capture_workspace(repo)
    target = {"repository": "charitygraph", "workspace_path": str(repo.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"}
    execution = {
        "mode": "codex_exec",
        "change_policy": "bounded_workspace",
        "model": "luna-high",
        "report_path": "reports/o1f.md",
        "timeout_seconds": 60,
        "authority_version": "charitygraph.g4-o1d-local-implementation/v1",
        "scope": "bounded_local_builder_code_change",
        "allowed_paths": ["src/example.py", "tests/test_example.py"],
        "commit_policy": "local_commit_only",
    }
    with pytest.raises(InactiveImplementationRoute):
        validate_execution(execution, target=target, workspace=snapshot, authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"})
    assert report_only_execution({"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": "reports/read-only.md", "timeout_seconds": 60})["change_policy"] == "report_only"
    with pytest.raises(BoundedAuthorityError):
        report_only_execution(execution)


def test_completed_duplicate_is_reconciled_before_stale_head_verification(tmp_path):
    repo, head = git_repo(tmp_path)
    bridge = LocalAutonomousBridge(tmp_path / "bridge", workspace=repo).open()
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:historical:duplicate",
        content="historical terminal instruction",
        target={"repository": "charitygraph", "workspace_path": str(repo.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"},
        created_at=NOW,
    )
    assert bridge.submit(envelope)["accepted"] is True
    (repo / "README.md").write_text("new local commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "later"], cwd=repo, check=True, capture_output=True)
    duplicate = bridge.submit(envelope)
    assert duplicate["duplicate"] is True
    assert duplicate["status"] == "pending"


def test_bounded_diff_guard_preserves_dirty_baseline_and_limits_paths(tmp_path):
    repo, _ = git_repo(tmp_path)
    (repo / "notes.txt").write_text("pre-existing\n", encoding="utf-8")
    before = capture_workspace(repo)
    (repo / "src").mkdir()
    (repo / "src" / "allowed.py").write_text("x = 1\n", encoding="utf-8")
    after = capture_workspace(repo)
    verified = verify_allowed_changes(before, after, allowed_paths=["src/allowed.py"])
    assert verified["changed_paths"] == ["src/allowed.py"]
    (repo / "other.py").write_text("unexpected\n", encoding="utf-8")
    with pytest.raises(DirtyBaselineViolation):
        verify_allowed_changes(before, capture_workspace(repo), allowed_paths=["src/allowed.py"])
    (repo / "other.py").unlink()
    (repo / "notes.txt").write_text("changed baseline\n", encoding="utf-8")
    with pytest.raises(DirtyBaselineViolation, match="pre-existing"):
        verify_allowed_changes(before, capture_workspace(repo), allowed_paths=["src/allowed.py", "notes.txt"])
