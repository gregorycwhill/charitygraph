import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import bridge.bridge as bridge_module
import pytest
from bridge.bridge import CutoverWatcher, ENGINEERING_OPERATION, ENGINEERING_RESULT_PREFIX, FENCE_NAME, RESULT_PREFIX, STATUS_NAME
from charitygraph.autonomous_loop import InstructionEnvelope, canonical_json


def _fence(workspace, head, branch="test-branch"):
    return {
        "schema": "charitygraph.g4-o1b-dormant-fence/v1",
        "state": "ACTIVE",
        "workspace_path": str(workspace.resolve()),
        "branch": branch,
        "head": head,
        "legacy_execution": "FENCED",
    }


def _envelope(head, instruction_id="gate4:probe:1", workspace_path="C:/unused", branch="test-branch"):
    return InstructionEnvelope.create(
        instruction_id=instruction_id,
        content="Record a harmless transport probe only.",
        target={"repository": "charitygraph", "workspace_path": workspace_path, "branch": branch, "head": head, "model": "luna-high"},
        operation="bridge_probe",
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-local"},
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def test_cutover_ignores_legacy_files_and_writes_one_result(tmp_path, monkeypatch):
    workspace = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=workspace, text=True).strip()
    monkeypatch.setattr("bridge.bridge._git", lambda cwd, *args: branch if args == ("branch", "--show-current") else head)
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, branch)), encoding="utf-8")
    (artifacts / "cg-spec--g2-403-dormant-campaign-resume-repair-007.md").write_text("legacy", encoding="utf-8")
    (artifacts / "cg-g4-o1b-instruction-probe.json").write_text(canonical_json(_envelope(head, workspace_path=str(workspace.resolve()), branch=branch).as_dict()) + "\n", encoding="utf-8", newline="\n")
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    outcomes = watcher.process_once()
    assert outcomes[0].get("execution_state") == "TRANSPORT_PROBE_COMPLETED", outcomes
    assert len(list(artifacts.glob("cg-g4-o1b-result-*.json"))) == 1
    assert not (artifacts / "cg-spec--g2-403-dormant-campaign-resume-repair-007.md").with_suffix(".json").exists()
    assert json.loads((artifacts / STATUS_NAME).read_text(encoding="utf-8"))["watcher_state"] == "READY"


def test_cutover_rejects_bom_and_pretty_input(tmp_path, monkeypatch):
    workspace = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=workspace, text=True).strip()
    monkeypatch.setattr("bridge.bridge._git", lambda cwd, *args: branch if args == ("branch", "--show-current") else head)
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, branch)), encoding="utf-8")
    raw = canonical_json(_envelope(head, "gate4:probe:2", workspace_path=str(workspace.resolve()), branch=branch).as_dict()) + "\n"
    (artifacts / "cg-g4-o1b-instruction-bom.json").write_bytes(b"\xef\xbb\xbf" + raw.encode())
    (artifacts / "cg-g4-o1b-instruction-pretty.json").write_text(json.dumps(_envelope(head, "gate4:probe:3", workspace_path=str(workspace.resolve()), branch=branch).as_dict(), indent=2) + "\n", encoding="utf-8")
    outcomes = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()
    assert len(outcomes) == 2
    assert all(item["state"] == "REJECTED" for item in outcomes)
    assert not list(artifacts.glob("cg-g4-o1b-result-*.json"))


def _engineering_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-b", "gate4-test"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "G4 test"], cwd=workspace, check=True)
    (workspace / "README.md").write_text("bounded test workspace\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=workspace, check=True, capture_output=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    return workspace, head


def _engineering_instruction(workspace, head, instruction_id="gate4:engineering:1", report_path="reports/g4-o1c-test-report.md"):
    return InstructionEnvelope.create(
        instruction_id=instruction_id,
        content="Inspect the repository identity and write a short report containing the observed HEAD.",
        target={"repository": "charitygraph", "workspace_path": str(workspace.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"},
        operation=ENGINEERING_OPERATION,
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"},
        execution={"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": report_path, "timeout_seconds": 30},
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def _engineering_artifacts(tmp_path, workspace, head, envelope):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    fence = _fence(workspace, head, "gate4-test")
    (artifacts / FENCE_NAME).write_text(json.dumps(fence), encoding="utf-8")
    source = artifacts / "cg-g4-o1b-instruction-engineering.json"
    source.write_text(canonical_json(envelope.as_dict()) + "\n", encoding="utf-8", newline="\n")
    return artifacts, runtime


def test_engineering_operation_launches_codex_and_is_single_use(tmp_path, monkeypatch):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head)
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, envelope)
    captured = {}

    class FakeCodex:
        pid = 4242
        returncode = 0

        def communicate(self, timeout):
            captured["timeout"] = timeout
            report = workspace / "reports" / "g4-o1c-test-report.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("# bounded report\n\nHEAD verified by Codex.\n", encoding="utf-8")
            return b'{"type":"thread.started","thread_id":"thread-g4-o1c-test"}\n{"type":"turn.completed","model":"luna-high"}\n', None

    def fake_popen(command, **kwargs):
        if command[0] == "codex":
            captured["command"] = command
            captured["kwargs"] = kwargs
            return FakeCodex()
        return real_popen(command, **kwargs)

    monkeypatch.setattr(bridge_module.shutil, "which", lambda name: "codex")
    real_popen = bridge_module.subprocess.Popen
    monkeypatch.setattr(bridge_module.subprocess, "Popen", fake_popen)
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    outcome = watcher.process_once()[0]
    assert outcome["execution_state"] == "CODEX_ENGINEERING_COMPLETED"
    assert outcome["codex_process"]["launched"] is True
    assert outcome["codex_process"]["pid"] == 4242
    assert outcome["codex_process"]["thread_id"] == "thread-g4-o1c-test"
    assert outcome["codex_process"]["model_reported"] == "luna-high"
    assert outcome["engineering_report"]["exists"] is True
    assert captured["timeout"] == 30
    assert captured["command"][0:4] == ["codex", "exec", "--model", "gpt-5.6-luna"]
    assert "--sandbox" in captured["command"] and "workspace-write" in captured["command"]
    assert json.loads((artifacts / f"{ENGINEERING_RESULT_PREFIX}{envelope.instruction_id.replace(':', '_')}.json").read_text(encoding="utf-8"))["schema"] == "charitygraph.g4-o1c-result/v1"

    second = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()
    assert second[0]["duplicate"] is True


def test_engineering_operation_rejects_authority_expansion_before_claim(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head)
    raw = envelope.as_dict()
    raw["authority"]["scope"] = "all-host-actions"
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, InstructionEnvelope.from_dict(raw))
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    outcome = watcher.process_once()[0]
    assert outcome["state"] == "NOT_EXECUTED"
    assert "unexpected authority envelope" in outcome["error"]


def test_engineering_operation_real_codex_cli_rehearsal(tmp_path):
    if os.environ.get("CG_RUN_REAL_CODEX") != "1":
        pytest.skip("explicit real Codex CLI rehearsal opt-in")
    if shutil.which("codex") is None:
        pytest.fail("codex CLI is required for the explicit real rehearsal")
    workspace, head = _engineering_workspace(tmp_path)
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:engineering:real-cli",
        content=(
            "Read only README.md and the current git HEAD. Write exactly one small Markdown report at "
            "reports/g4-o1c-real-cli-report.md containing the observed branch, full HEAD and a statement that "
            "this was a provider-free repository inspection. Do not edit any other file and do not use network, "
            "providers, source acquisition, GitHub, publication, merge, release, deletion or reset."
        ),
        target={"repository": "charitygraph", "workspace_path": str(workspace.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"},
        operation=ENGINEERING_OPERATION,
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"},
        execution={"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": "reports/g4-o1c-real-cli-report.md", "timeout_seconds": 300},
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, envelope)
    outcome = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()[0]
    assert outcome["execution_state"] == "CODEX_ENGINEERING_COMPLETED", outcome
    assert outcome["codex_process"]["launched"] is True
    assert outcome["codex_process"]["returncode"] == 0
    assert outcome["codex_process"]["thread_id"]
    assert outcome["codex_process"]["model_requested"] == "luna-high"
    assert outcome["engineering_report"]["exists"] is True
