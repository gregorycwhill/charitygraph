import os
import subprocess
from pathlib import Path

import bridge.bridge as bridge_module
import bridge.managed_launcher as launcher_module


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
