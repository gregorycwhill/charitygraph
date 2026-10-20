import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bridge.bridge import CutoverWatcher, FENCE_NAME, STATUS_NAME
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
