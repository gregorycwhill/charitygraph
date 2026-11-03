import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from charitygraph.autonomous_loop import InstructionEnvelope
from bridge import bridge as bridge_module


AUTHORITY = {"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"}


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "gate4-test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "G4 test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "reports").mkdir()
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    (repo / "src" / "product.py").write_text('value = "HEAD product"\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    return repo, _git(repo, "rev-parse", "HEAD")


def _execution() -> dict[str, object]:
    return {
        "mode": "codex_exec",
        "change_policy": "bounded_workspace",
        "model": "luna-high",
        "report_path": "reports/result.md",
        "timeout_seconds": 30,
        "authority_version": "charitygraph.g4-o1d-local-implementation/v1",
        "scope": "bounded_local_builder_code_change",
        "allowed_paths": ["reports/result.md", "src/product.py"],
        "commit_policy": "local_commit_only",
    }


def _run_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation) -> tuple[Path, str, dict[str, object]]:
    repo, head = _repo(tmp_path)
    (repo / "src" / "product.py").write_text('value = "pre-existing product edit"\n', encoding="utf-8")
    source = tmp_path / "instruction.json"
    source.write_text("{}\n", encoding="utf-8")
    target = {
        "repository": "charitygraph",
        "workspace_path": str(repo.resolve()),
        "branch": "gate4-test",
        "head": head,
        "model": "luna-high",
    }
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:engineering:dirty-product-adoption",
        content="write only the explicitly allowlisted product file and report",
        authority=AUTHORITY,
        target=target,
        operation="codex_engineering",
    )

    class FakeCodex:
        pid = 4248
        returncode = 0

        def communicate(self, timeout=None):
            (repo / "reports" / "result.md").write_text("worker report\n", encoding="utf-8")
            mutation(repo)
            return b"{}\n", None

    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: "codex-cli test")
    real_popen = subprocess.Popen

    def fake_popen(command, *args, **kwargs):
        return real_popen(command, *args, **kwargs) if command and command[0] == "git" else FakeCodex()

    monkeypatch.setattr(bridge_module.subprocess, "Popen", fake_popen)
    watcher = bridge_module.CutoverWatcher(
        artifacts_root=tmp_path / "artifacts",
        workspace_root=repo,
        runtime_root=tmp_path / "runtime",
    )
    return repo, head, watcher._run_codex(envelope, source, hashlib.sha256(b"{}").hexdigest(), _execution())


def test_same_hunk_allowlisted_dirty_product_uses_current_worker_bytes(tmp_path, monkeypatch):
    repo, head, result = _run_worker(
        tmp_path,
        monkeypatch,
        lambda root: (root / "src" / "product.py").write_text('value = "worker product outcome"\n', encoding="utf-8"),
    )

    assert result["execution_state"] == "CODEX_ENGINEERING_COMPLETED"
    attestation = result["workspace_attestation"]
    assert attestation["verified"] is True
    reconciliation = attestation["dirty_allowlisted_reconciliation"]["src/product.py"]
    assert reconciliation["method"] == "allowlisted-current-worktree-product"
    assert reconciliation["preexisting_sha256"] in {
        hashlib.sha256(b'value = "pre-existing product edit"\n').hexdigest(),
        hashlib.sha256(b'value = "pre-existing product edit"\r\n').hexdigest(),
    }
    assert reconciliation["after_sha256"] in {
        hashlib.sha256(b'value = "worker product outcome"\n').hexdigest(),
        hashlib.sha256(b'value = "worker product outcome"\r\n').hexdigest(),
    }
    assert _git(repo, "show", "HEAD:src/product.py") == 'value = "worker product outcome"'
    assert attestation["local_commit"]["commit_paths"] == ["reports/result.md", "src/product.py"]
    assert attestation["local_commit"]["bridge_owned_commit"]["parent_head"] == head
    assert _git(repo, "rev-parse", "HEAD^") == head


def test_dirty_product_commit_preserves_unrelated_dirty_path_and_is_one_direct_child(tmp_path, monkeypatch):
    repo, head = _repo(tmp_path)
    (repo / "src" / "product.py").write_text('value = "pre-existing product edit"\n', encoding="utf-8")
    (repo / "unrelated.txt").write_text("keep dirty\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True)

    source = tmp_path / "instruction.json"
    source.write_text("{}\n", encoding="utf-8")
    target = {"repository": "charitygraph", "workspace_path": str(repo.resolve()), "branch": "gate4-test", "head": head, "model": "luna-high"}
    envelope = InstructionEnvelope.create(
        instruction_id="gate4:engineering:dirty-product-commit-only",
        content="write the approved product and report only",
        authority=AUTHORITY,
        target=target,
        operation="codex_engineering",
    )

    class FakeCodex:
        pid = 4249
        returncode = 0

        def communicate(self, timeout=None):
            (repo / "reports" / "result.md").write_text("worker report\n", encoding="utf-8")
            (repo / "src" / "product.py").write_text('value = "worker product outcome"\n', encoding="utf-8")
            return b"{}\n", None

    monkeypatch.setattr(bridge_module, "_resolve_codex_executable", lambda: "C:/test/codex.exe")
    monkeypatch.setattr(bridge_module, "_validate_codex_executable", lambda executable: "codex-cli test")
    real_popen = subprocess.Popen
    monkeypatch.setattr(
        bridge_module.subprocess,
        "Popen",
        lambda command, *args, **kwargs: real_popen(command, *args, **kwargs) if command and command[0] == "git" else FakeCodex(),
    )
    watcher = bridge_module.CutoverWatcher(artifacts_root=tmp_path / "artifacts", workspace_root=repo, runtime_root=tmp_path / "runtime")
    result = watcher._run_codex(envelope, source, hashlib.sha256(b"{}").hexdigest(), _execution())

    assert result["execution_state"] == "CODEX_ENGINEERING_COMPLETED"
    assert result["workspace_attestation"]["local_commit"]["commit_paths"] == ["reports/result.md", "src/product.py"]
    assert _git(repo, "rev-parse", "HEAD^") == head
    assert _git(repo, "show", "--format=", "--name-only", "HEAD") == "reports/result.md\nsrc/product.py"
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.txt"
    assert (repo / "unrelated.txt").read_text(encoding="utf-8") == "keep dirty\n"


def test_unrelated_worker_path_remains_blocked(tmp_path, monkeypatch):
    repo, head, result = _run_worker(
        tmp_path,
        monkeypatch,
        lambda root: (root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8"),
    )

    assert result["execution_state"] == "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
    assert result["workspace_attestation"]["verified"] is False
    assert "unexpected.txt" in result["workspace_attestation"]["unexpected_paths"]
    assert _git(repo, "rev-parse", "HEAD") == head


def test_dirty_product_type_change_remains_blocked(tmp_path, monkeypatch):
    def change_type(root: Path) -> None:
        product = root / "src" / "product.py"
        product.unlink()
        product.mkdir()

    repo, head, result = _run_worker(tmp_path, monkeypatch, change_type)

    assert result["execution_state"] == "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
    assert result["workspace_attestation"]["verified"] is False
    assert _git(repo, "rev-parse", "HEAD") == head


def test_dirty_product_symlink_remains_blocked(tmp_path, monkeypatch):
    outside = tmp_path / "outside.py"
    outside.write_text("outside\n", encoding="utf-8")
    probe = tmp_path / "symlink-probe"
    try:
        os.symlink(outside, probe)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    probe.unlink()

    def replace_with_symlink(root: Path) -> None:
        product = root / "src" / "product.py"
        product.unlink()
        os.symlink(outside, product)

    repo, head, result = _run_worker(tmp_path, monkeypatch, replace_with_symlink)

    assert result["execution_state"] == "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
    assert result["workspace_attestation"]["verified"] is False
    assert _git(repo, "rev-parse", "HEAD") == head
