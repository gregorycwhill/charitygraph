from __future__ import annotations

import subprocess
import os
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
    DecisionNotDispatchable,
    DuplicateMissionEvent,
    MissionContract,
    MissionLedger,
    StaleMissionIdentity,
    StaleReviewCursor,
    ReviewClaimRequired,
    SupervisorClaimUnavailable,
)
from charitygraph.autonomous_loop import InstructionEnvelope, LocalAutonomousBridge
from bridge import bridge as bridge_module


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
    ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_A}, now=NOW)
    review = ledger.record_review(
        "cg-g4-double-loop-20261021-v1",
        reviewer_id="interactive",
        decision_id="decision-1",
        cursor_seq=5,
        execution_disposition="READY",
        semantic_disposition="ACCEPTED",
        decision={"reason": "offline evidence only"},
        claim_owner="interactive",
        claim_token=second["claim_token"],
        claim_version=2,
        expected_branch="gate4-test",
        expected_head=head,
        tranche_id="O1E-O1F",
        now=NOW,
    )
    assert review["duplicate"] is False
    assert ledger.record_review(
        "cg-g4-double-loop-20261021-v1", reviewer_id="interactive", decision_id="decision-1", cursor_seq=5,
        execution_disposition="READY", semantic_disposition="ACCEPTED", decision={"reason": "offline evidence only"}, now=NOW,
    )["duplicate"] is True
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="interactive", claim_token=second["claim_token"], version=2, now=NOW)
    dispatch = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="interactive", expected_version=0, now=NOW)
    with pytest.raises(SupervisorClaimUnavailable):
        ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="hourly", expected_version=1, now=NOW)
    dispatched = ledger.dispatch(
        "cg-g4-double-loop-20261021-v1", owner="interactive", claim_token=dispatch["claim_token"], version=1,
        instruction_id="gate4:engineering:successor", instruction_sha256=HASH_A, decision_id="decision-1",
        expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
    )
    assert dispatched["event_type"] == "dispatch_authorised"
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="interactive", claim_token=dispatch["claim_token"], version=1, now=NOW)
    dispatch_two = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="hourly", expected_version=1, now=NOW)
    with pytest.raises(DecisionNotDispatchable):
        ledger.dispatch(
            "cg-g4-double-loop-20261021-v1", owner="hourly", claim_token=dispatch_two["claim_token"], version=2,
            instruction_id="gate4:engineering:duplicate", instruction_sha256=HASH_B, decision_id="decision-1",
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
        )
    restarted = MissionLedger(db).open()
    status = restarted.status("cg-g4-double-loop-20261021-v1")
    assert status["review_cursors"][0]["cursor_seq"] == 5
    assert status["latest_decision"]["decision_id"] == "decision-1"
    assert status["latest_decision"]["execution_disposition"] == "READY"
    assert status["latest_decision"]["semantic_disposition"] == "ACCEPTED"
    assert "Mission cg-g4-double-loop-20261021-v1" in restarted.supervisor_brief("cg-g4-double-loop-20261021-v1")
    assert restarted.record_review(
        "cg-g4-double-loop-20261021-v1",
        reviewer_id="interactive",
        decision_id="decision-1",
        cursor_seq=5,
        execution_disposition="READY",
        semantic_disposition="ACCEPTED",
        decision={"reason": "offline evidence only"},
        now=NOW,
    )["duplicate"] is True


def test_review_requires_current_claim_exact_frontier_and_identity(tmp_path):
    repo, head = git_repo(tmp_path)
    ledger = MissionLedger(tmp_path / "bridge.sqlite3").open()
    ledger.start(contract(repo, head))
    ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_A}, now=NOW)
    with pytest.raises(ReviewClaimRequired):
        ledger.record_review(
            "cg-g4-double-loop-20261021-v1", reviewer_id="interactive", decision_id="no-claim", cursor_seq=2,
            execution_disposition="READY", semantic_disposition="ACCEPTED", decision={},
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
        )
    claim = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="hourly", expected_version=0, now=NOW)
    with pytest.raises(StaleReviewCursor):
        ledger.record_review(
            "cg-g4-double-loop-20261021-v1", reviewer_id="hourly", decision_id="short", cursor_seq=1,
            execution_disposition="READY", semantic_disposition="ACCEPTED", decision={},
            claim_owner="hourly", claim_token=claim["claim_token"], claim_version=1,
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
        )
    ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:2", event_type="evidence_seen", payload={"sha256": HASH_B}, now=NOW)
    with pytest.raises(StaleReviewCursor):
        ledger.record_review(
            "cg-g4-double-loop-20261021-v1", reviewer_id="hourly", decision_id="stale", cursor_seq=2,
            execution_disposition="READY", semantic_disposition="ACCEPTED", decision={},
            claim_owner="hourly", claim_token=claim["claim_token"], claim_version=1,
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
        )
    with pytest.raises(CompareAndSwapConflict):
        ledger.record_review(
            "cg-g4-double-loop-20261021-v1", reviewer_id="hourly", decision_id="wrong-owner", cursor_seq=3,
            execution_disposition="READY", semantic_disposition="ACCEPTED", decision={},
            claim_owner="other", claim_token=claim["claim_token"], claim_version=1,
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
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


def test_dispatch_rejects_superseded_accepted_review(tmp_path):
    repo, head = git_repo(tmp_path)
    ledger = MissionLedger(tmp_path / "bridge.sqlite3").open()
    ledger.start(contract(repo, head))
    ledger.append_event("cg-g4-double-loop-20261021-v1", event_key="evidence:1", event_type="evidence_seen", payload={"sha256": HASH_A}, now=NOW)

    first_claim = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="reviewer-one", expected_version=0, now=NOW)
    ledger.record_review(
        "cg-g4-double-loop-20261021-v1", reviewer_id="reviewer-one", decision_id="decision-old", cursor_seq=2,
        execution_disposition="READY", semantic_disposition="ACCEPTED", decision={"reason": "old acceptance"},
        claim_owner="reviewer-one", claim_token=first_claim["claim_token"], claim_version=1,
        expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
    )
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="reviewer-one", claim_token=first_claim["claim_token"], version=1, now=NOW)

    second_claim = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="reviewer-two", expected_version=1, now=NOW)
    ledger.record_review(
        "cg-g4-double-loop-20261021-v1", reviewer_id="reviewer-two", decision_id="decision-new", cursor_seq=2,
        execution_disposition="READY", semantic_disposition="ACCEPTED", decision={"reason": "new acceptance"},
        claim_owner="reviewer-two", claim_token=second_claim["claim_token"], claim_version=2,
        expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
    )
    ledger.release_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="review", owner="reviewer-two", claim_token=second_claim["claim_token"], version=2, now=NOW)

    dispatch_claim = ledger.claim_supervisor("cg-g4-double-loop-20261021-v1", claim_kind="dispatch", owner="dispatcher", expected_version=0, now=NOW)
    with pytest.raises(DecisionNotDispatchable, match="superseded"):
        ledger.dispatch(
            "cg-g4-double-loop-20261021-v1", owner="dispatcher", claim_token=dispatch_claim["claim_token"], version=1,
            instruction_id="gate4:engineering:superseded", instruction_sha256=HASH_A, decision_id="decision-old",
            expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
        )
    dispatched = ledger.dispatch(
        "cg-g4-double-loop-20261021-v1", owner="dispatcher", claim_token=dispatch_claim["claim_token"], version=1,
        instruction_id="gate4:engineering:current", instruction_sha256=HASH_B, decision_id="decision-new",
        expected_branch="gate4-test", expected_head=head, tranche_id="O1E-O1F", now=NOW,
    )
    assert dispatched["event_type"] == "dispatch_authorised"


def test_bounded_authority_accepts_when_active_and_report_only_stays_narrow(tmp_path):
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
    validated = validate_execution(execution, target=target, workspace=snapshot, authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"})
    assert validated["allowed_paths"] == ("src/example.py", "tests/test_example.py")
    with pytest.raises(InactiveImplementationRoute):
        validate_execution(execution, target=target, workspace=snapshot, authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"}, route_active=False)
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


@pytest.mark.parametrize("mutation", ["modify", "delete", "rename", "staged"])
def test_bounded_diff_guard_rejects_unauthorised_mutations(tmp_path, mutation):
    repo, _ = git_repo(tmp_path)
    before = capture_workspace(repo)
    if mutation == "modify":
        (repo / "README.md").write_text("changed\n", encoding="utf-8")
    elif mutation == "delete":
        (repo / "README.md").unlink()
    elif mutation == "rename":
        (repo / "README.md").rename(repo / "RENAMED.md")
    else:
        (repo / "staged.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "staged.py"], cwd=repo, check=True)
    with pytest.raises(DirtyBaselineViolation):
        verify_allowed_changes(before, capture_workspace(repo), allowed_paths=["reports/allowed.md"])


def test_bounded_diff_guard_rejects_symlink_escape(tmp_path):
    repo, _ = git_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    before = capture_workspace(repo)
    try:
        os.symlink(outside, repo / "escape", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(DirtyBaselineViolation, match="symlink/path escape"):
        verify_allowed_changes(before, capture_workspace(repo), allowed_paths=["escape"])


def test_real_codex_execution_quarantines_unauthorised_workspace_change(tmp_path, monkeypatch):
    repo, head = git_repo(tmp_path)
    (repo / "reports").mkdir()
    source = tmp_path / "instruction.json"
    source.write_text("{}\n", encoding="utf-8")
    target = {"repository": "charitygraph", "workspace_path": str(repo.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"}
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:engineering:workspace-quarantine",
        content="write the report only",
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"},
        target=target,
        operation="codex_engineering",
    )
    execution = {"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": "reports/quarantine.md", "timeout_seconds": 30}

    class FakeCodex:
        pid = 4242
        returncode = 0

        def communicate(self, timeout=None):
            (repo / "reports" / "quarantine.md").write_text("report\n", encoding="utf-8")
            (repo / "unauthorised.txt").write_text("must quarantine\n", encoding="utf-8")
            return b"{}\n", None

    monkeypatch.setattr(bridge_module.shutil, "which", lambda name: "codex")
    real_popen = subprocess.Popen
    def fake_popen(command, *args, **kwargs):
        return real_popen(command, *args, **kwargs) if command and command[0] == "git" else FakeCodex()
    monkeypatch.setattr(bridge_module.subprocess, "Popen", fake_popen)
    watcher = bridge_module.CutoverWatcher(artifacts_root=tmp_path / "artifacts", workspace_root=repo, runtime_root=tmp_path / "runtime")
    result = watcher._run_codex(envelope, source, "a" * 64, execution)
    assert result["execution_state"] == "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
    assert result["workspace_attestation"]["quarantined"] is True
    assert "unauthorised.txt" in result["workspace_attestation"]["unexpected_paths"]
    assert result["workspace_attestation"]["verified"] is False


def test_codex_failure_still_records_workspace_attestation(tmp_path, monkeypatch):
    repo, head = git_repo(tmp_path)
    (repo / "reports").mkdir()
    source = tmp_path / "instruction.json"
    source.write_text("{}\n", encoding="utf-8")
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:engineering:workspace-failure",
        content="fail after inspection",
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"},
        target={"repository": "charitygraph", "workspace_path": str(repo.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"},
        operation="codex_engineering",
    )
    execution = {"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": "reports/failure.md", "timeout_seconds": 30}

    class FailedCodex:
        pid = 4343
        returncode = 1

        def communicate(self, timeout=None):
            (repo / "reports" / "failure.md").write_text("failure report\n", encoding="utf-8")
            return b"failed\n", None

    monkeypatch.setattr(bridge_module.shutil, "which", lambda name: "codex")
    real_popen = subprocess.Popen
    def fake_popen(command, *args, **kwargs):
        return real_popen(command, *args, **kwargs) if command and command[0] == "git" else FailedCodex()
    monkeypatch.setattr(bridge_module.subprocess, "Popen", fake_popen)
    watcher = bridge_module.CutoverWatcher(artifacts_root=tmp_path / "artifacts", workspace_root=repo, runtime_root=tmp_path / "runtime")
    result = watcher._run_codex(envelope, source, "b" * 64, execution)
    assert result["execution_state"] == "CODEX_EXECUTION_FAILED"
    assert result["workspace_attestation"]["verified"] is True
    assert result["workspace_attestation"]["quarantined"] is False
