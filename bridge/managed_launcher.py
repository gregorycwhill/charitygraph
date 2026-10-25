"""Supported managed entrypoint for the G4-O1B cutover watcher."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator


HERE = Path(__file__).resolve()
FENCE_PREFIX = "cg-g4-o1b-dormant-state-fence-20261020"


def _git(workspace: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={workspace.resolve()}", *args],
        cwd=workspace,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _latest_fence(artifacts_root: Path) -> Path | None:
    candidates = sorted(artifacts_root.glob(f"{FENCE_PREFIX}*.json"))
    if not candidates:
        return None

    def version(path: Path) -> int:
        match = re.search(r"-v(\d+)\.json$", path.name)
        return int(match.group(1)) if match else 1

    return max(candidates, key=lambda path: (version(path), path.name))


def matching_fence_identity(artifacts_root: str | Path, workspace_root: str | Path) -> dict[str, Any] | None:
    """Return a new-launch-safe fence identity, or None when it is not exact.

    This is deliberately narrower than recovery automation: it only observes
    an immutable fence and local Git identity.  It never mutates the checkout,
    manufactures a fence, or treats an old matching fence as authority to
    retry a failed child.
    """
    artifacts = Path(artifacts_root).resolve()
    workspace = Path(workspace_root).resolve()
    fence_path = _latest_fence(artifacts)
    if fence_path is None:
        return None
    try:
        raw = fence_path.read_bytes()
        fence = json.loads(raw)
        branch = _git(workspace, "branch", "--show-current")
        head = _git(workspace, "rev-parse", "HEAD")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError):
        return None
    if fence.get("schema") != "charitygraph.g4-o1b-dormant-fence/v1" or fence.get("state") != "ACTIVE":
        return None
    if fence.get("workspace_path") != str(workspace) or fence.get("branch") != branch or fence.get("head") != head:
        return None
    return {
        "path": str(fence_path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "branch": branch,
        "head": head,
    }


@contextmanager
def managed_launcher_lock(runtime_root: str | Path) -> Iterator[None]:
    """Hold an OS-level lock for the lifetime of the managed watcher."""
    lock_path = Path(runtime_root).resolve() / "bridge" / "managed-launcher.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("another managed CharityGraph launcher is already running") from exc
    try:
        handle.seek(0)
        handle.write(f"{os.getpid()}\n".encode("ascii"))
        handle.truncate()
        handle.flush()
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Managed G4-O1B watcher launcher")
    p.add_argument("--artifacts-root", required=True)
    p.add_argument("--workspace-root", default=str(HERE.parents[1]))
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--no-sound", action="store_true")
    p.add_argument("--poll-seconds", type=float, default=2.0)
    p.add_argument("--restart-poll-seconds", type=float, default=2.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    command = [
        sys.executable,
        str(HERE.parent / "bridge.py"),
        "watch",
        "--artifacts-root",
        args.artifacts_root,
        "--workspace-root",
        args.workspace_root,
        "--runtime-root",
        args.runtime_root,
        "--launcher-pid",
        str(os.getpid()),
        "--poll-seconds",
        str(args.poll_seconds),
    ]
    if args.restart_poll_seconds <= 0:
        parser().error("--restart-poll-seconds must be positive")
    try:
        with managed_launcher_lock(args.runtime_root):
            launched_with = matching_fence_identity(args.artifacts_root, args.workspace_root)
            while True:
                child = subprocess.Popen(command, cwd=args.workspace_root)
                returncode = child.wait()
                if returncode == 0:
                    return 0
                # Fail closed after every abnormal child exit.  A new child is
                # permitted only after Drive has delivered a *different*, exact
                # active fence for the local branch and HEAD.  This lets a
                # non-Work supervisor reconcile an attested local commit via
                # Drive without granting it Windows process control.
                while True:
                    candidate = matching_fence_identity(args.artifacts_root, args.workspace_root)
                    if candidate is not None and candidate != launched_with:
                        launched_with = candidate
                        break
                    time.sleep(args.restart_poll_seconds)
    except RuntimeError as exc:
        print(f"managed launcher: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
