"""Supported managed entrypoint for the G4-O1B cutover watcher."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator


HERE = Path(__file__).resolve()


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
    with managed_launcher_lock(args.runtime_root):
        child = subprocess.Popen(command, cwd=args.workspace_root)
        return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
