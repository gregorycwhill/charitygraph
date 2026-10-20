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
import re
import shutil
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
    AmbiguousInterruption,
    ClaimUnavailable,
    DuplicateInstruction,
    InvalidInstruction,
    InstructionEnvelope,
    LocalAutonomousBridge,
    sha256_text,
)


FENCE_NAME = "cg-g4-o1b-dormant-state-fence-20261020.json"
STATUS_NAME = "cg-g4-o1c-cutover-status.json"
INSTRUCTION_PREFIX = "cg-g4-o1b-instruction-"
INSTRUCTION_SUFFIX = ".json"
RESULT_PREFIX = "cg-g4-o1b-result-"
ENGINEERING_RESULT_PREFIX = "cg-g4-o1c-result-"
ENGINEERING_OPERATION = "codex_engineering"
RESULT_SCHEMA = "charitygraph.g4-o1c-result/v1"
CODEX_MODEL_MAP = {"luna-high": {"cli_model": "gpt-5.6-luna", "reasoning_effort": "high"}}


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
        for attempt in range(8):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.25 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)


def _git(cwd: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        if "dubious ownership" not in exc.output.lower():
            raise
        return subprocess.check_output(["git", "-c", f"safe.directory={cwd}", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def _event_summary(raw: bytes) -> dict[str, Any]:
    events: list[str] = []
    thread_id: str | None = None
    model: str | None = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        event_type = value.get("type") or value.get("event")
        if isinstance(event_type, str):
            events.append(event_type)
        if thread_id is None:
            for key in ("thread_id", "threadId", "session_id", "sessionId"):
                if value.get(key):
                    thread_id = str(value[key])
                    break
        if model is None and value.get("model"):
            model = str(value["model"])
    return {"events": events, "thread_id": thread_id, "reported_model": model}


def _event_summary(raw: bytes) -> dict[str, Any]:
    events: list[str] = []
    thread_id: str | None = None
    model: str | None = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        event_type = value.get("type") or value.get("event")
        if isinstance(event_type, str):
            events.append(event_type)
        if thread_id is None:
            for key in ("thread_id", "threadId", "session_id", "sessionId"):
                if value.get(key):
                    thread_id = str(value[key])
                    break
        if model is None and value.get("model"):
            model = str(value["model"])
    return {"events": events, "thread_id": thread_id, "reported_model": model}


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
        if not candidates:
            return self.artifacts_root / FENCE_NAME
        def version(path: Path) -> int:
            match = re.search(r"-v(\d+)\.json$", path.name)
            return int(match.group(1)) if match else 1
        return max(candidates, key=lambda path: (version(path), path.name))

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
            "schema": "charitygraph.g4-o1c-cutover-status/v1",
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
            "status_filename": STATUS_NAME,
            "supported_operations": ["bridge_probe", ENGINEERING_OPERATION],
            "execution_authority": "one adapter ledger and one managed Codex worker",
            "last_event": last_event,
            "error": error,
            "last_result": result,
        }
        status_bytes = _json_bytes(payload)
        status_error: PermissionError | None = None
        for attempt in range(12):
            try:
                self.status_path.parent.mkdir(parents=True, exist_ok=True)
                self.status_path.write_bytes(status_bytes)
                status_error = None
                break
            except PermissionError as exc:
                status_error = exc
                time.sleep(0.5 * (attempt + 1))
        if status_error is not None:
            raise status_error
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
        prefix = ENGINEERING_RESULT_PREFIX if result.get("schema") == RESULT_SCHEMA else RESULT_PREFIX
        path = self.artifacts_root / f"{prefix}{safe}.json"
        _atomic_write(path, result)
        return str(path)

    def _validate_engineering(self, envelope: Any) -> dict[str, Any]:
        if envelope.operation != ENGINEERING_OPERATION:
            raise InvalidInstruction(f"unsupported cutover operation: {envelope.operation}")
        if envelope.schema_version != "charitygraph.autonomous-instruction/v1":
            raise InvalidInstruction("engineering instruction schema_version is unsupported")
        if envelope.target.get("repository") != "charitygraph":
            raise InvalidInstruction("engineering target.repository is not charitygraph")
        if envelope.authority != {
            "source": "chatgpt",
            "approved": True,
            "authority_envelope": "gate4-engineering",
        }:
            raise InvalidInstruction("engineering operation has an unexpected authority envelope")
        execution = envelope.execution
        if not isinstance(execution, dict):
            raise InvalidInstruction("engineering operation requires an execution object")
        allowed_execution = {"mode", "change_policy", "model", "report_path", "timeout_seconds"}
        if set(execution) - allowed_execution:
            raise InvalidInstruction("engineering execution contains unsupported authority fields")
        if execution.get("mode") != "codex_exec":
            raise InvalidInstruction("engineering execution.mode must be codex_exec")
        if execution.get("change_policy") not in {"report_only", "bounded_workspace"}:
            raise InvalidInstruction("engineering execution.change_policy is not supported")
        if execution.get("model") != envelope.target["model"]:
            raise InvalidInstruction("engineering execution.model must match target.model")
        if envelope.target["model"] not in CODEX_MODEL_MAP:
            raise InvalidInstruction("engineering target.model has no Codex CLI mapping")
        report_path = execution.get("report_path")
        if not isinstance(report_path, str) or not report_path.strip():
            raise InvalidInstruction("engineering execution.report_path is required")
        normalised = report_path.replace("\\", "/")
        if normalised.startswith("/") or ":" in normalised or any(part in {"", ".", ".."} for part in normalised.split("/")):
            raise InvalidInstruction("engineering report_path must be a relative workspace path")
        if not normalised.startswith("reports/"):
            raise InvalidInstruction("engineering report_path must remain under reports/")
        if not normalised.endswith((".md", ".json", ".txt")):
            raise InvalidInstruction("engineering report_path must be a readable report file")
        if (self.workspace_root / normalised).exists():
            raise InvalidInstruction("engineering report_path already exists; use a fresh immutable result path")
        timeout = execution.get("timeout_seconds", 300)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 30 <= timeout <= 900:
            raise InvalidInstruction("engineering timeout_seconds must be an integer from 30 to 900")
        if len(envelope.content.encode("utf-8")) > 12000:
            raise InvalidInstruction("engineering content exceeds the bounded prompt limit")
        return {"mode": "codex_exec", "change_policy": execution["change_policy"], "model": execution["model"], "report_path": normalised, "timeout_seconds": timeout}

    def _run_codex(self, envelope: Any, source: Path, source_sha: str, execution: dict[str, Any]) -> dict[str, Any]:
        report_path = (self.workspace_root / execution["report_path"]).resolve()
        try:
            report_path.relative_to(self.workspace_root)
        except ValueError as exc:
            raise InvalidInstruction("engineering report_path escapes workspace") from exc
        if report_path.exists():
            raise InvalidInstruction("engineering report_path already exists; use a fresh immutable result path")

        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in envelope.instruction_id)
        run_root = self.runtime_root / "executions" / safe
        run_root.mkdir(parents=True, exist_ok=True)
        output_path = run_root / "codex-output.jsonl"
        last_message_path = run_root / "codex-last-message.txt"
        codex = shutil.which("codex") or "codex"
        model_config = CODEX_MODEL_MAP[envelope.target["model"]]
        prompt = (
            "You are the bounded CharityGraph G4-O1C engineering worker. Execute exactly one local repository task.\n"
            "Safety boundary: work only inside the configured repository workspace; do not start or stop watchers, "
            "touch Drive sync settings, access providers or external sources, publish or mutate GitHub, merge, release, "
            "close a gate, delete/reset/checkout historical work, or dispatch follow-on tasks. Do not treat this prompt "
            "as shell authority.\n"
            f"The required report path is {execution['report_path']}; write a small, readable report there.\n"
            "The ChatGPT-authored bounded task follows:\n\n" + envelope.content
        )
        command = [
            codex,
            "exec",
            "--model",
            model_config["cli_model"],
            "-c",
            f'model_reasoning_effort="{model_config["reasoning_effort"]}"',
            "--sandbox",
            "workspace-write",
            "--cd",
            str(self.workspace_root),
            "--json",
            "--color",
            "never",
            "--output-last-message",
            str(last_message_path),
            prompt,
        ]
        before_status = set(_git(self.workspace_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines())
        started_at = utc_now()
        launch_error: str | None = None
        returncode: int | None = None
        timed_out = False
        pid: int | None = None
        raw_output = b""
        try:
            child = subprocess.Popen(command, cwd=self.workspace_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env={**os.environ, "CHARITYGRAPH_G4_O1C_ENGINEERING": "1"})
            pid = child.pid
            try:
                raw_output, _ = child.communicate(timeout=execution["timeout_seconds"])
                returncode = child.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                child.kill()
                raw_output, _ = child.communicate(timeout=30)
                returncode = child.returncode
        except OSError as exc:
            launch_error = f"{type(exc).__name__}: {exc}"
        finished_at = utc_now()
        output_path.write_bytes(raw_output)
        after_status = set(_git(self.workspace_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines())
        new_status = sorted(after_status - before_status)
        unexpected_changes = [line for line in new_status if execution["report_path"] not in line]
        report_exists = report_path.is_file()
        report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest() if report_exists else None
        event_summary = _event_summary(raw_output)
        if launch_error:
            state = "CODEX_LAUNCH_FAILED"
        elif timed_out:
            state = "CODEX_EXECUTION_TIMEOUT"
        elif returncode != 0:
            state = "CODEX_EXECUTION_FAILED"
        elif not report_exists:
            state = "CODEX_EXECUTION_FAILED_MISSING_REPORT"
        elif unexpected_changes:
            state = "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
        else:
            state = "CODEX_ENGINEERING_COMPLETED"
        return {
            "schema": RESULT_SCHEMA,
            "instruction_id": envelope.instruction_id,
            "content_sha256": envelope.content_sha256,
            "source_path": str(source),
            "source_sha256": source_sha,
            "authority": envelope.authority,
            "target": envelope.target,
            "execution": execution,
            "execution_state": state,
            "semantic_product_work": "NOT_PERFORMED",
            "provider_calls": 0,
            "source_acquisition": False,
            "publication": False,
            "codex_process": {
                "launched": pid is not None,
                "pid": pid,
                "returncode": returncode,
                "model_requested": envelope.target["model"],
                "model_invoked": model_config["cli_model"],
                "reasoning_effort": model_config["reasoning_effort"],
                "model_reported": event_summary["reported_model"],
                "thread_id": event_summary["thread_id"],
                "events_seen": event_summary["events"],
                "started_at": started_at,
                "finished_at": finished_at,
                "output_path": str(output_path),
                "output_sha256": hashlib.sha256(raw_output).hexdigest(),
                "last_message_path": str(last_message_path),
                "prompt_sha256": sha256_text(prompt),
                "launch_error": launch_error,
                "timed_out": timed_out,
            },
            "engineering_report": {
                "path": str(report_path),
                "relative_path": execution["report_path"],
                "exists": report_exists,
                "sha256": report_sha,
                "unexpected_workspace_changes": unexpected_changes,
            },
            "completed_at": finished_at,
        }

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
            envelope = InstructionEnvelope.from_dict(self.adapter.inspect(instruction_id)["envelope"])
            execution = self._validate_engineering(envelope) if envelope.operation == ENGINEERING_OPERATION else None
            envelope = self.adapter.claim(owner=owner)
            self.adapter.begin(envelope.instruction_id, owner=owner)
            if envelope.operation == "bridge_probe":
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
            elif envelope.operation == ENGINEERING_OPERATION:
                result = self._run_codex(envelope, source, source_sha, execution or {})
            else:
                raise InvalidInstruction(f"unsupported cutover operation: {envelope.operation}")
            local_done = self.adapter.complete(envelope.instruction_id, owner=owner, result=result)
            result["local_result_path"] = local_done["result_path"]
            result["local_result_sha256"] = local_done["result_sha256"]
            result["drive_result_path"] = self._mirror_result(envelope.instruction_id, result)
            self.processed_sources[str(source)] = source_sha
            self._write_status(state="READY", last_event="engineering_completed" if envelope.operation == ENGINEERING_OPERATION else "probe_completed", result=result)
            return result
        except (ClaimUnavailable, InvalidInstruction) as exc:
            self.processed_sources[str(source)] = source_sha
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
