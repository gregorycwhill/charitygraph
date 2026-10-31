import os
import subprocess
from pathlib import Path

import bridge.bridge as bridge_module
import bridge.managed_launcher as launcher_module
from charitygraph import bounded_authority
from charitygraph.windows_process import quiet_subprocess_kwargs


def _expected_windows_kwargs():
    if os.name != "nt":
        return {}
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": flag} if flag else {}


def test_bridge_children_use_no_window_flag_on_windows():
    assert bridge_module._quiet_subprocess_kwargs() == _expected_windows_kwargs()


def test_launcher_children_use_no_window_flag_on_windows():
    assert launcher_module._quiet_subprocess_kwargs() == _expected_windows_kwargs()


def test_git_safety_check_uses_quiet_subprocess_options(monkeypatch):
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)
    assert bridge_module._git_bytes(Path("C:/unused"), "status", "--short") == b""
    assert observed["creationflags"] == _expected_windows_kwargs()["creationflags"]


def test_bounded_authority_uses_one_index_read_not_one_diff_per_dirty_path(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    for index in range(12):
        (repo / f"dirty-{index}.txt").write_text(f"before {index}\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    for index in range(12):
        (repo / f"dirty-{index}.txt").write_text(f"after {index}\n", encoding="utf-8")

    real_git = bounded_authority._git
    calls = []

    def observed_git(root, *args, **kwargs):
        calls.append(args)
        return real_git(root, *args, **kwargs)

    monkeypatch.setattr(bounded_authority, "_git", observed_git)
    snapshot = bounded_authority.capture_workspace(repo)

    assert len(snapshot.entries) == 12
    assert ("ls-files", "-s", "-z") in calls
    assert not any(args[:2] == ("diff", "--binary") for args in calls)


def test_shared_quiet_process_policy_matches_windows_contract():
    assert quiet_subprocess_kwargs() == _expected_windows_kwargs()
