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
import threading
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
from charitygraph.bounded_authority import (  # noqa: E402
    BoundedAuthorityError,
    DirtyBaselineViolation,
    capture_workspace,
    report_only_execution,
    validate_execution as validate_bounded_execution,
    verify_local_commit,
    verify_allowed_changes,
)


FENCE_NAME = "cg-g4-o1b-dormant-state-fence-20261020.json"
STATUS_NAME = "cg-g4-o1c-cutover-status.json"
SUPERVISOR_WORKSPACE_NAME = "cg-g4-o1c-supervisor-workspace.json"
SUPERVISOR_LEDGER_NAME = "cg-g4-o1c-supervisor-ledger.json"
INSTRUCTION_PREFIX = "cg-g4-o1b-instruction-"
INSTRUCTION_SUFFIX = ".json"
RESULT_PREFIX = "cg-g4-o1b-result-"
ENGINEERING_RESULT_PREFIX = "cg-g4-o1c-result-"
ENGINEERING_OPERATION = "codex_engineering"
RESULT_SCHEMA = "charitygraph.g4-o1c-result/v1"
CODEX_MODEL_MAP = {"luna-high": {"cli_model": "gpt-5.6-luna", "reasoning_effort": "high"}}
HEARTBEAT_SECONDS = 120.0
RESULT_PUBLICATION_GRACE_SECONDS = 180
IMPLEMENTATION_AUTHORITY_VERSION = "charitygraph.g4-o1d-local-implementation/v1"
IMPLEMENTATION_SCOPE = "bounded_local_builder_code_change"
CODE_CHANGE_ROUTE_ACTIVE = True


def _resolve_codex_executable() -> str:
    """Resolve an installed Codex CLI without relying on the launcher PATH."""
    configured = os.environ.get("CHARITYGRAPH_CODEX_EXECUTABLE")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        raise FileNotFoundError("CHARITYGRAPH_CODEX_EXECUTABLE does not identify a regular file")

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(Path(local_app_data).glob("OpenAI/Codex/bin/*/codex.exe"))
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.extend(Path(user_profile).glob(".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe"))
    path_candidate = shutil.which("codex")
    if path_candidate:
        candidates.append(Path(path_candidate))

    seen: set[Path] = set()
    for candidate in sorted(candidates, key=lambda item: item.stat().st_mtime if item.is_file() else -1, reverse=True):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return str(resolved)
    raise FileNotFoundError("no installed Codex executable was found")


def _validate_codex_executable(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
        check=False,
    )
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        raise OSError(f"Codex executable validation failed with exit code {completed.returncode}")
    return version


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_bytes(raw)
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


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_bytes(path, _json_bytes(value))


def _git(cwd: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        if "dubious ownership" not in exc.output.lower():
            raise
        return subprocess.check_output(["git", "-c", f"safe.directory={cwd}", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def _git_bytes(cwd: Path, *args: str) -> bytes:
    """Read Git-owned bytes without trusting the worktree's file contents."""
    command = ["git", *args]
    completed = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode == 0:
        return completed.stdout
    diagnostics = completed.stdout + completed.stderr
    if "dubious ownership" not in diagnostics.decode("utf-8", errors="replace").lower():
        raise subprocess.CalledProcessError(completed.returncode, command, output=diagnostics)
    return subprocess.check_output(["git", "-c", f"safe.directory={cwd}", *args], cwd=cwd, stderr=subprocess.PIPE)


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
        self.heartbeat_seconds = HEARTBEAT_SECONDS
        self._status_initialised = False
        self._status_sequence = 0
        self._last_publication_monotonic: float | None = None
        self._last_status_substantive: dict[str, Any] | None = None
        self._last_event: str | None = None
        self._last_event_at: str | None = None
        self._last_result: dict[str, Any] | None = None
        self._last_result_identity: dict[str, Any] | None = None
        self._active_execution: dict[str, Any] | None = None
        self._supervision_key: str | None = None
        self._supervision_refs: dict[str, Any] | None = None
        terminal = self.adapter.latest_terminal()
        if terminal:
            self._last_event = terminal["last_event"]
            self._last_event_at = terminal["last_event_at"]
            self._last_result = terminal["result"]
            self._last_result_identity = self._result_identity(terminal)

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

    @staticmethod
    def _result_identity(terminal: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
        value = result if result is not None else terminal.get("result")
        disposition = (value or {}).get("execution_state") or terminal.get("status")
        return {
            "instruction_id": terminal.get("instruction_id"),
            "status": terminal.get("status"),
            "disposition": disposition,
            "result_path": terminal.get("result_path"),
            "result_sha256": terminal.get("result_sha256"),
            "completed_at": terminal.get("updated_at"),
        }

    def _substantive_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key not in {"updated_at", "publication"}}

    def _set_event(
        self,
        *,
        event: str | None,
        event_at: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        if event is None:
            return
        if event in {"preflight_passed", "watcher_started"} and self._last_result is not None:
            return
        self._last_event = event
        self._last_event_at = event_at or utc_now()
        if result is not None:
            self._last_result = result
            self._last_result_identity = {
                "instruction_id": result.get("instruction_id"),
                "status": "complete" if result.get("execution_state", "").endswith("COMPLETED") else "terminal",
                "disposition": result.get("execution_state"),
                "result_path": result.get("local_result_path"),
                "result_sha256": result.get("local_result_sha256"),
                "completed_at": result.get("completed_at"),
            }

    def _status_payload(self, *, state: str, error: str | None = None, publication_kind: str = "state_transition") -> dict[str, Any]:
        payload = {
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
                "code_change_route": {
                    "version": IMPLEMENTATION_AUTHORITY_VERSION,
                    "active": CODE_CHANGE_ROUTE_ACTIVE,
                    "policy": "bounded_workspace",
                    "scope": IMPLEMENTATION_SCOPE,
                    "acceptance_required": "separate ChatGPT-originated supervisory acceptance test",
                },
            },
            "fence_path": str(self.fence_path),
            "status_filename": STATUS_NAME,
            "supported_operations": ["bridge_probe", ENGINEERING_OPERATION],
            "execution_authority": "one adapter ledger and one managed Codex worker",
            "active_execution": self._active_execution,
            "telemetry_contract": {
                "local_status_generated_at": "updated_at",
                "heartbeat_seconds": self.heartbeat_seconds,
                "stale_after_seconds": int(self.heartbeat_seconds * 2),
                "result_publication_grace_seconds": RESULT_PUBLICATION_GRACE_SECONDS,
                "drive_delivery": "The watcher confirms atomic local writes only; compare Drive modified time with updated_at to observe sync delay.",
            },
            "supervision": self._publish_supervisory_surface(),
            "last_event": self._last_event,
            "last_event_at": self._last_event_at,
            "last_result": self._last_result,
            "last_result_identity": self._last_result_identity,
            "error": error,
        }
        return payload

    @staticmethod
    def _supervisable_path(path: str) -> bool:
        """Keep the catalogue useful without exporting runtime or credential files."""
        normalised = path.replace("\\", "/")
        if normalised.startswith((".git/", "runtime/", ".venv/", "venv/", "__pycache__/")):
            return False
        if normalised.lower().endswith((".env", ".pem", ".key", ".p12", ".pfx")):
            return False
        if normalised in {"AGENTS.md", "ARCHITECTURE.md", "BUILDER_MACHINERY.md", "README.md"}:
            return True
        return normalised.startswith(("src/", "tests/", "bridge/", "docs/", "config/")) and normalised.lower().endswith((".py", ".md", ".json", ".toml", ".yaml", ".yml"))

    def _dirty_paths(self) -> list[dict[str, str]]:
        raw = _git_bytes(self.workspace_root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        fields = raw.split(b"\0")
        entries: list[dict[str, str]] = []
        index = 0
        while index < len(fields):
            field = fields[index]
            index += 1
            if not field:
                continue
            if len(field) < 4:
                continue
            status = field[:2].decode("ascii", errors="replace")
            path = field[3:].decode("utf-8", errors="replace").replace("\\", "/")
            entries.append({"path": path, "status": status})
            # Porcelain v1 -z encodes the source path of a rename/copy as the
            # next NUL field.  It is still a dirty baseline path and must be
            # visible to the supervisor.
            if status[0] in {"R", "C"} and index < len(fields) and fields[index]:
                entries.append({"path": fields[index].decode("utf-8", errors="replace").replace("\\", "/"), "status": status})
                index += 1
        return sorted(entries, key=lambda item: (item["path"], item["status"]))

    def _workspace_catalogue(self) -> list[dict[str, Any]]:
        raw = _git_bytes(self.workspace_root, "ls-tree", "-r", "-z", "HEAD")
        files: list[dict[str, Any]] = []
        for entry in raw.split(b"\0"):
            if not entry or b"\t" not in entry:
                continue
            metadata, path_raw = entry.split(b"\t", 1)
            parts = metadata.decode("ascii", errors="replace").split()
            if len(parts) != 3 or parts[1] != "blob":
                continue
            path = path_raw.decode("utf-8", errors="replace").replace("\\", "/")
            if not self._supervisable_path(path):
                continue
            files.append(
                {
                    "path": path,
                    "git_blob_id": parts[2],
                    "hash_algorithm": "git-object-id",
                }
            )
        return sorted(files, key=lambda item: item["path"])

    def _write_supervisory_artifact(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = _json_bytes(payload)
        destination = self.artifacts_root / name
        if not destination.exists() or destination.read_bytes() != raw:
            _atomic_write_bytes(destination, raw)
        return {"file_name": name, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw)}

    def _publish_supervisory_surface(self) -> dict[str, Any]:
        """Publish a Drive-readable observation surface without exposing the host.

        The exported workspace catalogue is derived from Git objects, not from
        arbitrary local files.  The ledger summary contains no task body or
        claim token.  Either artifact may be read by a non-Work ChatGPT
        supervisor; neither grants it filesystem, process, or dispatch power.
        """
        fence_raw = self.fence_path.read_bytes() if self.fence_path.exists() else b""
        branch = _git(self.workspace_root, "branch", "--show-current")
        head = _git(self.workspace_root, "rev-parse", "HEAD")
        dirty_paths = self._dirty_paths()
        ledger = self.adapter.supervisory_ledger_summary()
        key_material = {
            "branch": branch,
            "head": head,
            "fence_sha256": hashlib.sha256(fence_raw).hexdigest(),
            "dirty_paths": dirty_paths,
            "ledger": ledger,
        }
        key = hashlib.sha256(_json_bytes(key_material)).hexdigest()
        if self._supervision_key == key and self._supervision_refs is not None:
            return self._supervision_refs
        workspace = {
            "schema": "charitygraph.g4-o1c-supervisor-workspace/v1",
            "workspace_identity": {
                "repository": "charitygraph",
                "workspace_path": str(self.workspace_root),
                "branch": branch,
                "head": head,
                "tree": _git(self.workspace_root, "rev-parse", "HEAD^{tree}"),
            },
            "fence": {
                "file_name": self.fence_path.name,
                "sha256": hashlib.sha256(fence_raw).hexdigest(),
            },
            "dirty_baseline": {"clean": not dirty_paths, "paths": dirty_paths},
            "supervisable_files": self._workspace_catalogue(),
        }
        refs = {
            "workspace": self._write_supervisory_artifact(SUPERVISOR_WORKSPACE_NAME, workspace),
            "ledger": self._write_supervisory_artifact(SUPERVISOR_LEDGER_NAME, ledger),
            "read_contract": "Read both artifacts and require ledger.dispatch_clear=true before creating an instruction.",
        }
        self._supervision_key = key
        self._supervision_refs = refs
        return refs

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
        files = [
            REPO_ROOT / "src" / "charitygraph" / "autonomous_loop.py",
            REPO_ROOT / "src" / "charitygraph" / "bounded_authority.py",
            HERE,
            REPO_ROOT / "bridge" / "managed_launcher.py",
        ]
        h = hashlib.sha256()
        for path in files:
            h.update(str(path.relative_to(REPO_ROOT)).encode("utf-8"))
            h.update(path.read_bytes())
        return h.hexdigest()

    def _write_status(
        self,
        *,
        state: str,
        last_event: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
        force: bool = False,
        publication_kind: str = "state_transition",
    ) -> bool:
        self._set_event(event=last_event, result=result)
        payload = self._status_payload(state=state, error=error, publication_kind=publication_kind)
        substantive = self._substantive_status(payload)
        now_monotonic = time.monotonic()
        unchanged = substantive == self._last_status_substantive
        heartbeat_due = (
            self._last_publication_monotonic is not None
            and now_monotonic - self._last_publication_monotonic >= self.heartbeat_seconds
        )
        if not force and unchanged and not heartbeat_due:
            return False
        if unchanged and heartbeat_due:
            publication_kind = "heartbeat"
        self._status_sequence += 1
        payload["publication"] = {
            "kind": publication_kind,
            "sequence": self._status_sequence,
            "heartbeat_seconds": self.heartbeat_seconds,
        }
        status_bytes = _json_bytes(payload)
        status_error: PermissionError | None = None
        for attempt in range(12):
            try:
                _atomic_write_bytes(self.status_path, status_bytes)
                status_error = None
                break
            except PermissionError as exc:
                status_error = exc
                time.sleep(0.5 * (attempt + 1))
        if status_error is not None:
            raise status_error
        _atomic_write(self.runtime_root / "status.json", payload)
        self._last_status_substantive = substantive
        self._last_publication_monotonic = now_monotonic
        self._status_initialised = True
        return True

    def preflight(self) -> dict[str, Any]:
        if not self.artifacts_root.is_dir():
            raise RuntimeError(f"Drive-synced artifacts folder is missing: {self.artifacts_root}")
        fence = self._read_fence()
        observed = {"fence": fence, "branch": _git(self.workspace_root, "branch", "--show-current"), "head": _git(self.workspace_root, "rev-parse", "HEAD")}
        self._write_status(
            state="READY",
            last_event=None if self._status_initialised else (self._last_event or "preflight_passed"),
            force=not self._status_initialised,
        )
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

    def _publish_report(self, instruction_id: str, report_path: Path, report_sha256: str) -> dict[str, Any]:
        raw = report_path.read_bytes()
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in instruction_id)
        suffix = report_path.suffix.lower() or ".txt"
        filename = f"cg-g4-o1c-report-{safe}-{report_sha256[:16]}{suffix}"
        destination = self.artifacts_root / filename
        if destination.exists():
            existing = destination.read_bytes()
            if hashlib.sha256(existing).hexdigest() != report_sha256 or len(existing) != len(raw):
                raise DuplicateInstruction("immutable private report path contains different bytes")
        else:
            _atomic_write_bytes(destination, raw)
        return {
            "private": True,
            "folder": str(self.artifacts_root),
            "file_name": filename,
            "file_identity": f"{filename}:{report_sha256}",
            "path": str(destination),
            "sha256": report_sha256,
            "byte_length": len(raw),
        }

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
        base_execution = {"mode", "change_policy", "model", "report_path", "timeout_seconds"}
        implementation_execution = {"authority_version", "scope", "allowed_paths", "commit_policy"}
        allowed_execution = base_execution | implementation_execution if execution.get("change_policy") == "bounded_workspace" else base_execution
        if set(execution) - allowed_execution:
            raise InvalidInstruction("engineering execution contains unsupported authority fields")
        if execution.get("mode") != "codex_exec":
            raise InvalidInstruction("engineering execution.mode must be codex_exec")
        change_policy = execution.get("change_policy")
        if change_policy not in {"report_only", "bounded_workspace"}:
            raise InvalidInstruction("engineering execution.change_policy is not supported")
        if change_policy == "report_only":
            try:
                report_only_execution(execution)
            except BoundedAuthorityError as exc:
                raise InvalidInstruction(str(exc)) from exc
        bounded_authority: dict[str, Any] | None = None
        if change_policy == "bounded_workspace":
            try:
                bounded_authority = validate_bounded_execution(
                    execution,
                    target=envelope.target,
                    workspace=capture_workspace(self.workspace_root),
                    authority=envelope.authority,
                    route_active=CODE_CHANGE_ROUTE_ACTIVE,
                )
            except BoundedAuthorityError as exc:
                raise InvalidInstruction(str(exc)) from exc
        if change_policy == "bounded_workspace":
            if execution.get("authority_version") != IMPLEMENTATION_AUTHORITY_VERSION:
                raise InvalidInstruction("bounded implementation authority_version is unsupported")
            if execution.get("scope") != IMPLEMENTATION_SCOPE:
                raise InvalidInstruction("bounded implementation scope is unsupported")
            allowed_paths = execution.get("allowed_paths")
            if not isinstance(allowed_paths, list) or not allowed_paths or not all(isinstance(item, str) for item in allowed_paths):
                raise InvalidInstruction("bounded implementation allowed_paths must be a non-empty list")
            for allowed_path in allowed_paths:
                normalised_path = allowed_path.replace("\\", "/")
                if normalised_path.startswith("/") or ":" in normalised_path or any(part in {"", ".", ".."} for part in normalised_path.split("/")):
                    raise InvalidInstruction("bounded implementation allowed_paths must remain relative")
            if execution.get("commit_policy") != "local_commit_only":
                raise InvalidInstruction("bounded implementation commit_policy is unsupported")
            if not CODE_CHANGE_ROUTE_ACTIVE:
                raise InvalidInstruction("bounded implementation route is inactive pending supervisory acceptance")
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
        validated = {
            "mode": "codex_exec",
            "change_policy": execution["change_policy"],
            "model": execution["model"],
            "report_path": normalised,
            "timeout_seconds": timeout,
        }
        if bounded_authority is not None:
            # The execution worker needs the validated allowlist for its
            # post-run workspace attestation.  Dropping it here would make a
            # valid bounded implementation appear to change unauthorized paths.
            validated.update(
                authority_version=bounded_authority["authority_version"],
                scope=bounded_authority["scope"],
                allowed_paths=list(bounded_authority["allowed_paths"]),
                commit_policy=execution["commit_policy"],
            )
        return validated

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
        codex: str | None = None
        codex_version: str | None = None
        codex_validation_error: str | None = None
        try:
            codex = _resolve_codex_executable()
            codex_version = _validate_codex_executable(codex)
        except (OSError, subprocess.SubprocessError) as exc:
            codex_validation_error = f"{type(exc).__name__}: {exc}"
        command = [] if codex is None else [
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
        allowed_paths = {execution["report_path"]}
        if execution.get("change_policy") == "bounded_workspace":
            allowed_paths.update(execution.get("allowed_paths", []))
        before_workspace = None
        baseline_error: str | None = None
        try:
            # This is the authoritative pre-launch baseline.  It includes
            # tracked, modified, staged, deleted, renamed and untracked paths;
            # status-line deltas are not sufficient for a safety boundary.
            before_workspace = capture_workspace(self.workspace_root, preserve_dirty_paths=allowed_paths)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            baseline_error = f"{type(exc).__name__}: {exc}"
        started_at = utc_now()
        launch_error: str | None = None
        returncode: int | None = None
        timed_out = False
        pid: int | None = None
        raw_output = b""
        if baseline_error is None:
            if codex_validation_error is not None:
                launch_error = codex_validation_error
            else:
                assert codex is not None
                try:
                    child = subprocess.Popen(command, cwd=self.workspace_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env={**os.environ, "CHARITYGRAPH_G4_O1C_ENGINEERING": "1"})
                    pid = child.pid
                    if self._active_execution is not None:
                        self._active_execution.update(
                            phase="codex_running",
                            codex_pid=pid,
                            codex_started_at=started_at,
                            last_local_heartbeat_at=started_at,
                        )
                    self._write_status(
                        state="EXECUTING",
                        last_event="codex_started",
                        force=True,
                        publication_kind="execution_transition",
                    )
                    # ``Popen.communicate(timeout=...)`` has not proved a
                    # reliable watchdog for the real Codex CLI on Windows:
                    # its output pipe can remain open while the timeout call
                    # does not return.  Drain output on a daemon reader and
                    # enforce the deadline from this watcher thread instead.
                    collected: dict[str, Any] = {}
                    output_complete = threading.Event()

                    def collect_output() -> None:
                        try:
                            collected["raw"], _ = child.communicate(timeout=None)
                        except OSError as exc:
                            collected["error"] = f"{type(exc).__name__}: {exc}"
                        finally:
                            output_complete.set()

                    threading.Thread(target=collect_output, name="charitygraph-codex-output", daemon=True).start()
                    deadline = time.monotonic() + execution["timeout_seconds"]
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            timed_out = True
                            child.kill()
                            if not output_complete.wait(timeout=30):
                                launch_error = "Codex child did not terminate within 30 seconds of the enforced deadline"
                            raw_output = collected.get("raw", b"")
                            if collected.get("error"):
                                launch_error = collected["error"]
                            returncode = child.returncode
                            break
                        if output_complete.wait(timeout=min(self.heartbeat_seconds, remaining)):
                            raw_output = collected.get("raw", b"")
                            if collected.get("error"):
                                launch_error = collected["error"]
                            returncode = child.returncode
                            break
                        if time.monotonic() >= deadline:
                            timed_out = True
                            child.kill()
                            if not output_complete.wait(timeout=30):
                                launch_error = "Codex child did not terminate within 30 seconds of the enforced deadline"
                            raw_output = collected.get("raw", b"")
                            if collected.get("error"):
                                launch_error = collected["error"]
                            returncode = child.returncode
                            break
                        if self._active_execution is not None:
                            self._active_execution["last_local_heartbeat_at"] = utc_now()
                        self._write_status(
                            state="EXECUTING",
                            last_event="execution_heartbeat",
                            force=True,
                            publication_kind="execution_heartbeat",
                        )
                except OSError as exc:
                    launch_error = f"{type(exc).__name__}: {exc}"
        finished_at = utc_now()
        output_path.write_bytes(raw_output)
        after_workspace = None
        attestation_error = baseline_error
        if before_workspace is not None:
            try:
                after_workspace = capture_workspace(self.workspace_root)
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                attestation_error = f"{type(exc).__name__}: {exc}"
        changed_paths: list[str] = []
        unexpected_changes: list[str] = []
        workspace_verification: dict[str, Any] | None = None
        commit_attestation: dict[str, Any] | None = None
        if before_workspace is not None and after_workspace is not None:
            try:
                if execution.get("change_policy") == "bounded_workspace" and before_workspace.head != after_workspace.head:
                    commit_attestation = verify_local_commit(
                        before_workspace,
                        after_workspace,
                        allowed_paths=sorted(allowed_paths),
                    )
                    workspace_verification = commit_attestation
                    changed_paths = commit_attestation["changed_paths"]
                    unexpected_changes = commit_attestation["unexpected_paths"]
                else:
                    workspace_verification = verify_allowed_changes(before_workspace, after_workspace, allowed_paths=sorted(allowed_paths), reconciliation_evidence_dir=run_root / "dirty-reconciliation")
                    changed_paths = workspace_verification["changed_paths"]
                    unexpected_changes = workspace_verification["unexpected_paths"]
            except DirtyBaselineViolation as exc:
                attestation_error = str(exc)
                changed_paths = sorted(path for path in set(before_workspace.entries) | set(after_workspace.entries) if before_workspace.entries.get(path) != after_workspace.entries.get(path))
                unexpected_changes = sorted(path for path in changed_paths if path not in allowed_paths)
        workspace_attestation = {
            "verified": workspace_verification is not None and attestation_error is None,
            "quarantined": bool(attestation_error or unexpected_changes),
            "allowed_paths": sorted(allowed_paths),
            "changed_paths": changed_paths,
            "unexpected_paths": unexpected_changes,
            "baseline_error": attestation_error,
            "dirty_reconciliation_evidence_dir": str(run_root / "dirty-reconciliation"),
            "local_commit": commit_attestation,
            "before": None if before_workspace is None else {
                "workspace_path": before_workspace.workspace_path,
                "branch": before_workspace.branch,
                "head": before_workspace.head,
                "entries": {path: list(value) for path, value in before_workspace.entries.items()},
            },
            "after": None if after_workspace is None else {
                "workspace_path": after_workspace.workspace_path,
                "branch": after_workspace.branch,
                "head": after_workspace.head,
                "entries": {path: list(value) for path, value in after_workspace.entries.items()},
            },
        }
        report_exists = report_path.is_file()
        report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest() if report_exists else None
        event_summary = _event_summary(raw_output)
        if launch_error:
            state = "CODEX_LAUNCH_FAILED"
        elif attestation_error or unexpected_changes:
            # A safety-boundary failure takes precedence over the worker's
            # exit code.  The adapter will durably complete this as a
            # non-success result, so it cannot be silently retried.
            state = "CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES"
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
        result = {
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
                "executable": codex,
                "executable_version": codex_version,
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
            "workspace_attestation": workspace_attestation,
            "engineering_report": {
                "path": str(report_path),
                "relative_path": execution["report_path"],
                "exists": report_exists,
                "sha256": report_sha,
                "unexpected_workspace_changes": unexpected_changes,
            },
            "completed_at": finished_at,
        }
        # A report is diagnostic evidence, not an acceptance signal.  Publish
        # it whenever a worker produced it, including quarantined or failed
        # runs, so the independent supervisor can diagnose without replaying.
        if report_exists:
            result["report_publication"] = self._publish_report(envelope.instruction_id, report_path, report_sha or "")
            result["report_publication"]["terminal_state"] = state
            result["report_publication"]["product_accepted"] = False
        return result

    def _process_candidate(self, source: Path) -> dict[str, Any] | None:
        source_bytes = source.read_bytes()
        source_sha = hashlib.sha256(source_bytes).hexdigest()
        previous = self.processed_sources.get(str(source))
        if previous == source_sha:
            return None
        try:
            preview, _ = self.adapter.read_materialized_instruction(source)
            imported = self.adapter.import_materialized_instruction(source)
            instruction_id = imported["instruction_id"]
            summary = self.adapter.status_summary(instruction_id)
            if imported.get("duplicate") and summary["status"] == "complete":
                self.processed_sources[str(source)] = source_sha
                return {"source_path": str(source), "source_sha256": source_sha, **summary, "duplicate": True}
            if (
                preview.operation == ENGINEERING_OPERATION
                and isinstance(preview.execution, dict)
                and preview.execution.get("change_policy") == "bounded_workspace"
            ):
                self._validate_engineering(preview)
        except (InvalidInstruction, DuplicateInstruction) as exc:
            self.processed_sources[str(source)] = source_sha
            # Invalid materialized files are terminally rejected input, not a
            # live bridge fault or claim.  Preserve the outcome for callers
            # but do not leave a stale error on READY after a watcher restart
            # re-observes a historical malformed file.
            error = None if isinstance(exc, InvalidInstruction) else f"{type(exc).__name__}: {exc}"
            self._write_status(state="READY", last_event="rejected_input", error=error)
            return {"source_path": str(source), "source_sha256": source_sha, "state": "REJECTED", "error": str(exc)}
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
            if envelope.operation == ENGINEERING_OPERATION:
                assert execution is not None
                self._active_execution = {
                    "instruction_id": envelope.instruction_id,
                    "content_sha256": envelope.content_sha256,
                    "phase": "claimed_preparing",
                    "claimed_at": utc_now(),
                    "timeout_seconds": execution["timeout_seconds"],
                }
                self._write_status(
                    state="EXECUTING",
                    last_event="engineering_claimed",
                    force=True,
                    publication_kind="execution_transition",
                )
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
            if envelope.operation == ENGINEERING_OPERATION and self._active_execution is not None:
                self._active_execution.update(
                    phase="terminal_recording",
                    codex_finished_at=result["codex_process"]["finished_at"],
                )
                self._write_status(
                    state="FINALIZING",
                    last_event="codex_finished",
                    force=True,
                    publication_kind="execution_transition",
                )
            local_done = self.adapter.complete(envelope.instruction_id, owner=owner, result=result)
            result["local_result_path"] = local_done["result_path"]
            result["local_result_sha256"] = local_done["result_sha256"]
            result["drive_result_path"] = self._mirror_result(envelope.instruction_id, result)
            self.processed_sources[str(source)] = source_sha
            self._active_execution = None
            self._write_status(state="READY", last_event="engineering_completed" if envelope.operation == ENGINEERING_OPERATION else "probe_completed", result=result)
            return result
        except (ClaimUnavailable, InvalidInstruction) as exc:
            self.processed_sources[str(source)] = source_sha
            self._active_execution = None
            self._write_status(state="READY", last_event="candidate_not_executed", error=f"{type(exc).__name__}: {exc}")
            return {"source_path": str(source), "source_sha256": source_sha, "state": "NOT_EXECUTED", "error": str(exc)}

    def process_once(self) -> list[dict[str, Any]]:
        self.preflight()
        results: list[dict[str, Any]] = []
        for source in self._candidate_paths():
            outcome = self._process_candidate(source)
            if outcome is not None:
                results.append(outcome)
        self._write_status(state="READY", publication_kind="heartbeat")
        return results

    def run_forever(self, *, poll_seconds: float = 2.0) -> None:
        self.preflight()
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
