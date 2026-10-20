"""Supported managed entrypoint for the G4-O1B cutover watcher."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve()


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
    child = subprocess.Popen(command, cwd=args.workspace_root)
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
