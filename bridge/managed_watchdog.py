"""Fail-closed liveness helper for the managed G4 bridge launcher."""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from bridge.managed_launcher import matching_fence_identity


def _recorded_launcher_is_alive(runtime_root: str | Path) -> bool:
    lock_path = Path(runtime_root).resolve() / "bridge" / "managed-launcher.lock"
    try:
        pid = int(lock_path.read_text(encoding="ascii").strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def _active_claim_count(runtime_root: str | Path) -> int | None:
    db = Path(runtime_root).resolve() / "bridge" / "bridge.sqlite3"
    if not db.exists():
        return None
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM instructions WHERE status IN ('claimed', 'running')").fetchone()[0])
    except sqlite3.Error:
        return None


def ensure_launcher(*, artifacts_root: str | Path, workspace_root: str | Path, runtime_root: str | Path) -> str:
    """Start one launcher only when recovery cannot duplicate live work."""
    if matching_fence_identity(artifacts_root, workspace_root) is None:
        return "fence_not_exact"
    claims = _active_claim_count(runtime_root)
    if claims is None:
        return "ledger_unavailable"
    if claims:
        return "active_claim_present"
    if _recorded_launcher_is_alive(runtime_root):
        return "launcher_already_alive"
    command = [sys.executable, str(Path(__file__).with_name("managed_launcher.py")), "--artifacts-root", str(Path(artifacts_root).resolve()), "--workspace-root", str(Path(workspace_root).resolve()), "--runtime-root", str(Path(runtime_root).resolve()), "--no-sound"]
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(command, cwd=workspace_root, creationflags=flags, close_fds=True)
    return "launcher_started"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed managed bridge liveness watchdog")
    parser.add_argument("--artifacts-root", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    args = parser.parse_args(argv)
    print(ensure_launcher(**vars(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
