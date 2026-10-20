"""Single-authority raw-file watcher for the controlled G4-O1B cutover.

This is deliberately a small transport boundary around
``charitygraph.autonomous_loop.LocalAutonomousBridge``.  It does not inspect
legacy queue files, execute technical specifications, resume campaigns, call
providers, or interpret instruction content as shell/Python authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from charitygraph.autonomous_loop import (  # noqa: E402
    ClaimUnavailable,
    DuplicateInstruction,
    InvalidInstruction,
    LocalAutonomousBridge,
    sha256_text,
)


FENCE_NAME = "cg-g4-o1b-dormant-state-fence-20261020.json"
STATUS_NAME = "cg-g4-o1b-cutover-status.json"
INSTRUCTION_PREFIX = "cg-g4-o1b-instruction-"
INSTRUCTION_SUFFIX = ".json"
RESULT_PREFIX = "cg-g4-o1b-result-"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_bytes(_json_bytes(value))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


class CutoverWatcher:
    """One managed child with one adapter ledger and one safe ingress prefix."""

    def __init__(self, *, artifacts_root: str | Path, workspace_root: str | Path, runtime_root: str | Path, launcher_pid: int | None = None) -> None:
        self.artifacts_root = Path(artifacts_root).resolve()
        self.workspace_root = Path(workspace_root).resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.bridge_root = self.runtime_root / "bridge"
        self.adapter = LocalAutonomousBridge(self.bridge_root, workspace=self.workspace_root).open()
        self.launcher_pid = launcher_pid
        self.watcher_pid = os.getpid()
        self.instance_id = f"g4-o1b-{self.watcher_pid}-{os.urandom(6).hex()}"
        self.processed_sources: dict[str, str] = {}

    @property
    def fence_path(self) -> Path:
        candidates = sorted(self.artifacts_root.glob("cg-g4-o1b-dormant-state-fence-20261020*.json"))
        return candidates[-1] if candidates else self.artifacts_root / FENCE_NAME

    @property
    def status_path(self) -> Path:
        return self.artifacts_root / STATUS_NAME

    def _read_fence(self) -> dict[str, Any]:
        if not self.fence_path.exists():
            raise RuntimeError(f"dormant-state fence is missing: {self.fence_path}")
        fence = json.loads(self.fence_path.read_text(encoding="utf-8"))
        if fence.get("schema") != "charitygraph.g4-o1b-dormant-fence/v1" or fence.get("state") != "ACTIVE":
            raise RuntimeError("dormant-state fence is not active")
        if fence.get("workspace_path") != str(self.workspace_root):
            raise RuntimeError("fence workspace does not match watcher workspace")
        if fence.get("branch") != _git(self.workspace_root, "branch", "--show-current"):
            raise RuntimeError("fence branch does not match watcher workspace")
        if fence.get("head") != _git(self.workspace_root, "rev-parse", "HEAD"):
            raise RuntimeError("fence HEAD does not match watcher workspace")
        return fence

    def _fingerprint(self) -> str:
        files = [REPO_ROOT / "src" / "charitygraph" / "autonomous_loop.py", HERE, REPO_ROOT / "bridge" / "managed_launcher.py"]
        h = hashlib.sha256()
        for path in files:
            h.update(str(path.relative_to(REPO_ROOT)).encode("utf-8"))
            h.update(path.read_bytes())
        return h.hexdigest()

    def _write_status(self, *, state: str, last_event: str | None = None, error: str | None = None, result: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "schema": "charitygraph.g4-o1b-cutover-status/v1",
            "updated_at": utc_now(),
            "watcher_state": state,
            "managed_mode": True,
            "launcher_pid": self.launcher_pid,
            "child_watcher_pid": self.watcher_pid,
            "watcher_instance_id": self.instance_id,
            "runtime_fingerprint": self._fingerprint(),
            "workspace_path": str(self.workspace_root),
            "branch": _git(self.workspace_root, "branch", "--show-current"),
            "head": _git(self.workspace_root, "rev-parse", "HEAD"),
            "ingress": {
                "folder": str(self.artifacts_root),
                "allowlisted_filename_prefix": INSTRUCTION_PREFIX,
                "allowlisted_filename_suffix": INSTRUCTION_SUFFIX,
                "legacy_queue_and_specs_ignored": True,
            },
            "fence_path": str(self.fence_path),
            "last_event": last_event,
            "error": error,
            "last_result": result,
        }
        _atomic_write(self.status_path, payload)
        _atomic_write(self.runtime_root / "status.json", payload)

    def preflight(self) -> dict[str, Any]:
        if not self.artifacts_root.is_dir():
            raise RuntimeError(f"Drive-synced artifacts folder is missing: {self.artifacts_root}")
        fence = self._read_fence()
        observed = {"fence": fence, "branch": _git(self.workspace_root, "branch", "--show-current"), "head": _git(self.workspace_root, "rev-parse", "HEAD")}
        self._write_status(state="READY", last_event="preflight_passed")
        return observed

    def _candidate_paths(self) -> list[Path]:
        return sorted(
            (p for p in self.artifacts_root.iterdir() if p.is_file() and p.name.startswith(INSTRUCTION_PREFIX) and p.name.endswith(INSTRUCTION_SUFFIX)),
            key=lambda p: p.name,
        )

    def _mirror_result(self, instruction_id: str, result: dict[str, Any]) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in instruction_id)
        path = self.artifacts_root / f"{RESULT_PREFIX}{safe}.json"
        _atomic_write(path, result)
        return str(path)

    def _process_candidate(self, source: Path) -> dict[str, Any] | None:
        source_bytes = source.read_bytes()
        source_sha = hashlib.sha256(source_bytes).hexdigest()
        previous = self.processed_sources.get(str(source))
        if previous == source_sha:
            return None
        try:
            imported = self.adapter.import_materialized_instruction(source)
        except (InvalidInstruction, DuplicateInstruction) as exc:
            self.processed_sources[str(source)] = source_sha
            self._write_status(state="READY", last_event="rejected_input", error=f"{type(exc).__name__}: {exc}")
            return {"source_path": str(source), "source_sha256": source_sha, "state": "REJECTED", "error": str(exc)}
        instruction_id = imported["instruction_id"]
        summary = self.adapter.status_summary(instruction_id)
        if summary["status"] == "complete":
            self.processed_sources[str(source)] = source_sha
            return {"source_path": str(source), "source_sha256": source_sha, **summary, "duplicate": True}
        owner = f"{self.instance_id}:single-worker"
        try:
            envelope = self.adapter.claim(owner=owner)
            self.adapter.begin(envelope.instruction_id, owner=owner)
            if envelope.operation != "bridge_probe":
                raise InvalidInstruction("only operation bridge_probe is enabled during controlled cutover")
            result = {
                "schema": "charitygraph.g4-o1b-result/v1",
                "instruction_id": envelope.instruction_id,
                "content_sha256": envelope.content_sha256,
                "source_path": str(source),
                "source_sha256": source_sha,
                "authority": envelope.authority,
                "target": envelope.target,
                "execution_state": "TRANSPORT_PROBE_COMPLETED",
                "semantic_product_work": "NOT_PERFORMED",
                "provider_calls": 0,
                "source_acquisition": False,
                "publication": False,
                "message": "Harmless G4-O1B transport probe recorded by the one managed cutover worker.",
                "completed_at": utc_now(),
            }
            local_done = self.adapter.complete(envelope.instruction_id, owner=owner, result=result)
            result["local_result_path"] = local_done["result_path"]
            result["local_result_sha256"] = local_done["result_sha256"]
            result["drive_result_path"] = self._mirror_result(envelope.instruction_id, result)
            self.processed_sources[str(source)] = source_sha
            self._write_status(state="READY", last_event="probe_completed", result=result)
            return result
        except (ClaimUnavailable, InvalidInstruction) as exc:
            self._write_status(state="READY", last_event="candidate_not_executed", error=f"{type(exc).__name__}: {exc}")
            return {"source_path": str(source), "source_sha256": source_sha, "state": "NOT_EXECUTED", "error": str(exc)}

    def process_once(self) -> list[dict[str, Any]]:
        self.preflight()
        results: list[dict[str, Any]] = []
        for source in self._candidate_paths():
            outcome = self._process_candidate(source)
            if outcome is not None:
                results.append(outcome)
        return results

    def run_forever(self, *, poll_seconds: float = 2.0) -> None:
        self.preflight()
        self._write_status(state="RUNNING", last_event="watcher_started")
        while True:
            try:
                self.process_once()
            except Exception as exc:  # fail closed; retain a visible diagnostic
                self._write_status(state="ERROR", last_event="watcher_error", error=f"{type(exc).__name__}: {exc}")
                raise
            time.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled G4-O1B raw-file bridge watcher")
    parser.add_argument("command", choices=["watch", "poll"])
    parser.add_argument("--artifacts-root", required=True)
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--launcher-pid", type=int, default=None)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    watcher = CutoverWatcher(artifacts_root=args.artifacts_root, workspace_root=args.workspace_root, runtime_root=args.runtime_root, launcher_pid=args.launcher_pid)
    if args.command == "poll":
        print(json.dumps(watcher.process_once(), sort_keys=True, indent=2))
        return 0
    watcher.run_forever(poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
