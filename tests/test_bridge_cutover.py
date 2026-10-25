import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import bridge.bridge as bridge_module
import pytest
from bridge.managed_launcher import matching_fence_identity
from bridge.bridge import (
    CutoverWatcher,
    ENGINEERING_OPERATION,
    ENGINEERING_RESULT_PREFIX,
    FENCE_NAME,
    RESULT_PREFIX,
    STATUS_NAME,
    SUPERVISOR_LEDGER_NAME,
    SUPERVISOR_WORKSPACE_NAME,
)
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


def test_idle_polling_deduplicates_status_and_bounded_heartbeat(tmp_path, monkeypatch):
    workspace = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=workspace, text=True).strip()
    monkeypatch.setattr("bridge.bridge._git", lambda cwd, *args: branch if args == ("branch", "--show-current") else head)
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, branch)), encoding="utf-8")
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    writes = []
    real_write = bridge_module._atomic_write_bytes

    def counted_write(path, raw):
        if path == watcher.status_path:
            writes.append(raw)
        return real_write(path, raw)

    monkeypatch.setattr(bridge_module, "_atomic_write_bytes", counted_write)
    watcher.process_once()
    assert len(writes) == 1
    watcher.process_once()
    assert len(writes) == 1
    watcher._last_publication_monotonic -= watcher.heartbeat_seconds + 1
    watcher.process_once()
    assert len(writes) == 2
    assert json.loads(writes[-1].decode())["publication"]["kind"] == "heartbeat"


def test_status_publishes_drive_readable_workspace_and_claim_ledger(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, "gate4-test")), encoding="utf-8")
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    watcher.process_once()

    status = json.loads((artifacts / STATUS_NAME).read_text(encoding="utf-8"))
    workspace_surface = json.loads((artifacts / SUPERVISOR_WORKSPACE_NAME).read_text(encoding="utf-8"))
    ledger_surface = json.loads((artifacts / SUPERVISOR_LEDGER_NAME).read_text(encoding="utf-8"))
    assert status["supervision"]["workspace"]["sha256"] == hashlib.sha256((artifacts / SUPERVISOR_WORKSPACE_NAME).read_bytes()).hexdigest()
    assert status["supervision"]["ledger"]["sha256"] == hashlib.sha256((artifacts / SUPERVISOR_LEDGER_NAME).read_bytes()).hexdigest()
    assert workspace_surface["workspace_identity"]["head"] == head
    assert workspace_surface["dirty_baseline"]["clean"] is True
    assert workspace_surface["supervisable_files"][0]["path"] == "README.md"
    assert ledger_surface["dispatch_clear"] is True

    watcher.adapter.submit(_engineering_instruction(workspace, head, instruction_id="gate4:engineering:pending-ledger"))
    watcher._write_status(state="READY", force=True)
    ledger_surface = json.loads((artifacts / SUPERVISOR_LEDGER_NAME).read_text(encoding="utf-8"))
    assert ledger_surface["dispatch_clear"] is False
    assert ledger_surface["active_or_ambiguous_claims"][0]["instruction_id"] == "gate4:engineering:pending-ledger"


def test_managed_launcher_only_accepts_an_exact_latest_fence(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    first = artifacts / FENCE_NAME
    first.write_text(json.dumps(_fence(workspace, head, "gate4-test")), encoding="utf-8")
    identity = matching_fence_identity(artifacts, workspace)
    assert identity is not None
    assert identity["head"] == head

    latest = artifacts / "cg-g4-o1b-dormant-state-fence-20261020-v2.json"
    latest.write_text(json.dumps(_fence(workspace, "a" * 40, "gate4-test")), encoding="utf-8")
    assert matching_fence_identity(artifacts, workspace) is None


def test_terminal_result_is_restored_and_survives_idle_preflight(tmp_path, monkeypatch):
    workspace = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "runtime"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=workspace, text=True).strip()
    monkeypatch.setattr("bridge.bridge._git", lambda cwd, *args: branch if args == ("branch", "--show-current") else head)
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, branch)), encoding="utf-8")
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    envelope = _envelope(head, "gate4:terminal:restore", workspace_path=str(workspace.resolve()), branch=branch)
    watcher.adapter.submit(envelope)
    claimed = watcher.adapter.claim(owner="test-owner")
    watcher.adapter.begin(claimed.instruction_id, owner="test-owner")
    watcher.adapter.complete(
        claimed.instruction_id,
        owner="test-owner",
        result={"schema": "test-result/v1", "execution_state": "TEST_COMPLETED", "instruction_id": claimed.instruction_id},
    )
    restored = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    restored.process_once()
    status = json.loads((artifacts / STATUS_NAME).read_text(encoding="utf-8"))
    assert status["last_event"] == "completed"
    assert status["last_result"]["execution_state"] == "TEST_COMPLETED"
    assert status["last_result_identity"]["instruction_id"] == claimed.instruction_id


def test_production_poll_entrypoint_publishes_idle_status_once(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    artifacts = tmp_path / "watch-artifacts"
    artifacts.mkdir()
    runtime = tmp_path / "watch-runtime"
    (artifacts / FENCE_NAME).write_text(json.dumps(_fence(workspace, head, "gate4-test")), encoding="utf-8")
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "bridge" / "bridge.py"),
        "poll",
        "--artifacts-root",
        str(artifacts),
        "--workspace-root",
        str(workspace),
        "--runtime-root",
        str(runtime),
        "--poll-seconds",
        "0.05",
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(command, cwd=workspace, env=env, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    status = json.loads((artifacts / STATUS_NAME).read_text(encoding="utf-8"))
    assert status["publication"]["sequence"] == 1


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
        if command[0] == "C:/test/codex.exe":
            captured["command"] = command
            captured["kwargs"] = kwargs
            return FakeCodex()
        return real_popen(command, **kwargs)

    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: "codex-cli test")
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
    assert captured["timeout"] is None
    assert captured["command"][0:4] == ["C:/test/codex.exe", "exec", "--model", "gpt-5.6-luna"]
    assert "--sandbox" in captured["command"] and "workspace-write" in captured["command"]
    assert json.loads((artifacts / f"{ENGINEERING_RESULT_PREFIX}{envelope.instruction_id.replace(':', '_')}.json").read_text(encoding="utf-8"))["schema"] == "charitygraph.g4-o1c-result/v1"
    report_publication = outcome["report_publication"]
    assert report_publication["private"] is True
    assert report_publication["byte_length"] > 0
    assert report_publication["sha256"] == outcome["engineering_report"]["sha256"]
    assert Path(report_publication["path"]).is_file()

    second = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()
    assert second[0]["duplicate"] is True


def test_execution_status_identifies_active_run_and_writes_heartbeats(tmp_path, monkeypatch):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head, instruction_id="gate4:engineering:heartbeat")
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, envelope)
    release = threading.Event()

    class HeartbeatingCodex:
        pid = 7777
        returncode = 0

        def communicate(self, timeout=None):
            assert release.wait(timeout=5)
            report = workspace / "reports" / "g4-o1c-test-report.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("# heartbeat report\n", encoding="utf-8")
            return b'{"type":"turn.completed"}\n', None

    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: "codex-cli test")
    real_popen = bridge_module.subprocess.Popen

    def fake_popen(command, **kwargs):
        return HeartbeatingCodex() if command[0] == "C:/test/codex.exe" else real_popen(command, **kwargs)

    monkeypatch.setattr(bridge_module.subprocess, "Popen", fake_popen)
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    watcher.heartbeat_seconds = 0.01
    observed = []
    write_status = watcher._write_status

    def capture_status(**kwargs):
        written = write_status(**kwargs)
        if written:
            observed.append(json.loads((artifacts / STATUS_NAME).read_text(encoding="utf-8")))
        if kwargs.get("publication_kind") == "execution_heartbeat":
            release.set()
        return written

    monkeypatch.setattr(watcher, "_write_status", capture_status)
    outcome = watcher.process_once()[0]
    assert outcome["execution_state"] == "CODEX_ENGINEERING_COMPLETED"
    active = [item for item in observed if item["watcher_state"] == "EXECUTING"]
    assert any(item["active_execution"]["phase"] == "claimed_preparing" for item in active)
    assert any(item["active_execution"]["phase"] == "codex_running" for item in active)
    assert any(item["publication"]["kind"] == "execution_heartbeat" for item in active)
    assert observed[-1]["watcher_state"] == "READY"
    assert observed[-1]["active_execution"] is None


def test_execution_deadline_is_enforced_even_when_codex_output_reader_blocks(tmp_path, monkeypatch):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head, instruction_id="gate4:engineering:deadline")
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, envelope)
    released = threading.Event()

    class BlockingCodex:
        pid = 7878
        returncode = None

        def communicate(self, timeout=None):
            released.wait(timeout=5)
            return b"", None

        def kill(self):
            self.returncode = -9
            released.set()

    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: "codex-cli test")
    real_popen = bridge_module.subprocess.Popen
    monkeypatch.setattr(bridge_module.subprocess, "Popen", lambda command, **kwargs: BlockingCodex() if command[0] == "C:/test/codex.exe" else real_popen(command, **kwargs))
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    monkeypatch.setattr(watcher, "_write_status", lambda **kwargs: True)
    clock = iter((0.0, 31.0))
    monkeypatch.setattr(bridge_module.time, "monotonic", lambda: next(clock))

    outcome = watcher._run_codex(
        envelope,
        artifacts / "cg-g4-o1b-instruction-engineering.json",
        "d" * 64,
        {"mode": "codex_exec", "change_policy": "report_only", "model": "luna-high", "report_path": "reports/g4-o1c-test-report.md", "timeout_seconds": 30},
    )
    assert outcome["execution_state"] == "CODEX_EXECUTION_TIMEOUT"
    assert outcome["codex_process"]["timed_out"] is True
    assert outcome["codex_process"]["returncode"] == -9


def test_codex_discovery_uses_installed_location_when_path_is_missing(tmp_path, monkeypatch):
    local_app_data = tmp_path / "local-app-data"
    executable = local_app_data / "OpenAI" / "Codex" / "bin" / "build-a" / "codex.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("CHARITYGRAPH_CODEX_EXECUTABLE", raising=False)
    monkeypatch.setattr(bridge_module.shutil, "which", lambda name: None)
    assert bridge_module._resolve_codex_executable() == str(executable.resolve())


def test_engineering_fails_closed_when_codex_validation_fails(tmp_path, monkeypatch):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head, instruction_id="gate4:engineering:invalid-codex")
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, envelope)
    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: (_ for _ in ()).throw(OSError("unusable executable")))
    outcome = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()[0]
    assert outcome["execution_state"] == "CODEX_LAUNCH_FAILED"
    assert outcome["codex_process"]["launched"] is False
    assert "unusable executable" in outcome["codex_process"]["launch_error"]


def test_engineering_report_only_requires_explicit_timeout(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head, instruction_id="gate4:engineering:missing-timeout")
    raw = envelope.as_dict()
    del raw["execution"]["timeout_seconds"]
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, InstructionEnvelope.from_dict(raw))
    outcome = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime).process_once()[0]
    assert outcome["state"] == "NOT_EXECUTED"
    assert "exact" in outcome["error"]
    assert not list(artifacts.glob(f"{ENGINEERING_RESULT_PREFIX}*.json"))


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


def test_bounded_implementation_route_is_versioned_and_active(tmp_path):
    workspace, head = _engineering_workspace(tmp_path)
    envelope = _engineering_instruction(workspace, head, instruction_id="gate4:engineering:bounded-active")
    raw = envelope.as_dict()
    raw["execution"] = {
        "mode": "codex_exec",
        "change_policy": "bounded_workspace",
        "model": "luna-high",
        "report_path": "reports/g4-o1d-bounded-active.md",
        "timeout_seconds": 30,
        "authority_version": "charitygraph.g4-o1d-local-implementation/v1",
        "scope": "bounded_local_builder_code_change",
        "allowed_paths": ["bridge/bridge.py", "tests/test_bridge_cutover.py"],
        "commit_policy": "local_commit_only",
    }
    artifacts, runtime = _engineering_artifacts(tmp_path, workspace, head, InstructionEnvelope.from_dict(raw))
    watcher = CutoverWatcher(artifacts_root=artifacts, workspace_root=workspace, runtime_root=runtime)
    validated = watcher._validate_engineering(InstructionEnvelope.from_dict(raw))
    assert validated["change_policy"] == "bounded_workspace"
    assert validated["model"] == "luna-high"
    assert validated["allowed_paths"] == ["bridge/bridge.py", "tests/test_bridge_cutover.py"]
    assert validated["commit_policy"] == "local_commit_only"
    assert not list(artifacts.glob(f"{ENGINEERING_RESULT_PREFIX}*.json"))


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
