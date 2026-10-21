"""Fail-closed O1F bounded local implementation authority.

The policy is certification machinery only.  The route is deliberately
inactive until a separate ChatGPT supervisory acceptance changes that state.
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMPLEMENTATION_AUTHORITY_VERSION = "charitygraph.g4-o1d-local-implementation/v1"
IMPLEMENTATION_SCOPE = "bounded_local_builder_code_change"
CODE_CHANGE_ROUTE_ACTIVE = False
ALLOWED_AUTHORITY = {"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"}


class BoundedAuthorityError(ValueError):
    pass


class InactiveImplementationRoute(BoundedAuthorityError):
    pass


class DirtyBaselineViolation(BoundedAuthorityError):
    pass


@dataclass(frozen=True)
class WorkspaceSnapshot:
    workspace_path: str
    branch: str
    head: str
    entries: dict[str, tuple[str, str, str]]


def _git(repo: Path, *args: str, raw: bool = False) -> str | bytes:
    command = ["git", "-c", f"safe.directory={repo}", *args]
    if raw:
        return subprocess.check_output(command, cwd=repo, stderr=subprocess.STDOUT)
    return subprocess.check_output(command, cwd=repo, text=True, stderr=subprocess.STDOUT).strip()


def _status_paths(status: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in status.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths[value] = line[:2]
    return paths


def _file_sha(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_workspace(repo: str | Path) -> WorkspaceSnapshot:
    root = Path(repo).resolve()
    status = str(_git(root, "status", "--porcelain=v1", "--untracked-files=all"))
    paths = _status_paths(status)
    entries: dict[str, tuple[str, str, str]] = {}
    for relative, status_code in paths.items():
        path = root / relative
        try:
            diff = bytes(_git(root, "diff", "--binary", "HEAD", "--", relative, raw=True))
        except subprocess.CalledProcessError:
            diff = b""
        entries[relative] = (
            status_code,
            _file_sha(path),
            hashlib.sha256(diff).hexdigest(),
        )
    return WorkspaceSnapshot(
        workspace_path=str(root),
        branch=str(_git(root, "branch", "--show-current")),
        head=str(_git(root, "rev-parse", "HEAD")),
        entries=entries,
    )


def validate_target(*, target: dict[str, Any], workspace: WorkspaceSnapshot, authority: dict[str, Any]) -> None:
    if authority != ALLOWED_AUTHORITY:
        raise BoundedAuthorityError("bounded implementation authority envelope is not approved")
    for key in ("repository", "workspace_path", "branch", "head", "model"):
        if not target.get(key):
            raise BoundedAuthorityError(f"target.{key} is required")
    if target["repository"] != "charitygraph":
        raise BoundedAuthorityError("bounded implementation repository is not charitygraph")
    if not Path(target["workspace_path"]).is_absolute():
        raise BoundedAuthorityError("bounded implementation workspace_path must be absolute")
    if Path(target["workspace_path"]).resolve() != Path(workspace.workspace_path).resolve():
        raise BoundedAuthorityError("bounded implementation workspace_path does not match the inspected workspace")
    if target["branch"] != workspace.branch or target["head"] != workspace.head:
        raise BoundedAuthorityError(f"stale target identity: observed {workspace.branch}@{workspace.head}")
    if target["model"] != "luna-high":
        raise BoundedAuthorityError("bounded implementation model is unsupported")


def validate_execution(execution: dict[str, Any], *, target: dict[str, Any], workspace: WorkspaceSnapshot, authority: dict[str, Any], route_active: bool = CODE_CHANGE_ROUTE_ACTIVE) -> dict[str, Any]:
    expected = {"mode", "change_policy", "model", "report_path", "timeout_seconds", "authority_version", "scope", "allowed_paths", "commit_policy"}
    if set(execution) != expected:
        raise BoundedAuthorityError("bounded implementation execution fields are not exact")
    if execution.get("mode") != "codex_exec" or execution.get("change_policy") != "bounded_workspace":
        raise BoundedAuthorityError("bounded implementation must use codex_exec/bounded_workspace")
    if execution.get("authority_version") != IMPLEMENTATION_AUTHORITY_VERSION:
        raise BoundedAuthorityError("bounded implementation authority_version is unsupported")
    if execution.get("scope") != IMPLEMENTATION_SCOPE:
        raise BoundedAuthorityError("bounded implementation scope is unsupported")
    if execution.get("commit_policy") != "local_commit_only":
        raise BoundedAuthorityError("bounded implementation commit_policy is unsupported")
    allowed = execution.get("allowed_paths")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(item, str) and item for item in allowed):
        raise BoundedAuthorityError("bounded implementation allowed_paths must be a non-empty list")
    for item in allowed:
        normalised = item.replace("\\", "/")
        if normalised.startswith("/") or ":" in normalised or any(part in {"", ".", ".."} for part in normalised.split("/")):
            raise BoundedAuthorityError("bounded implementation allowed_paths must be relative")
    if execution.get("model") != target.get("model"):
        raise BoundedAuthorityError("bounded implementation model does not match target")
    validate_target(target=target, workspace=workspace, authority=authority)
    if not route_active:
        raise InactiveImplementationRoute("bounded implementation route is inactive pending supervisory acceptance")
    return {"allowed_paths": tuple(allowed), "authority_version": IMPLEMENTATION_AUTHORITY_VERSION, "scope": IMPLEMENTATION_SCOPE}


def verify_allowed_changes(before: WorkspaceSnapshot, after: WorkspaceSnapshot, *, allowed_paths: list[str] | tuple[str, ...]) -> dict[str, Any]:
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    changed = sorted(path for path in set(before.entries) | set(after.entries) if before.entries.get(path) != after.entries.get(path))
    unexpected = sorted(path for path in changed if path not in allowed)
    if unexpected:
        raise DirtyBaselineViolation(f"unexpected bounded workspace changes: {', '.join(unexpected)}")
    baseline_changed = sorted(path for path in changed if path in before.entries)
    if baseline_changed:
        raise DirtyBaselineViolation(f"pre-existing dirty baseline was changed: {', '.join(baseline_changed)}")
    return {"changed_paths": changed, "unexpected_paths": unexpected, "baseline_preserved": not baseline_changed}


def report_only_execution(execution: dict[str, Any]) -> dict[str, Any]:
    allowed = {"mode", "change_policy", "model", "report_path", "timeout_seconds"}
    if set(execution) != allowed or execution.get("change_policy") != "report_only":
        raise BoundedAuthorityError("report_only execution contains bounded implementation authority fields")
    return dict(execution)


__all__ = [
    "ALLOWED_AUTHORITY",
    "BoundedAuthorityError",
    "CODE_CHANGE_ROUTE_ACTIVE",
    "DirtyBaselineViolation",
    "IMPLEMENTATION_AUTHORITY_VERSION",
    "IMPLEMENTATION_SCOPE",
    "InactiveImplementationRoute",
    "WorkspaceSnapshot",
    "capture_workspace",
    "report_only_execution",
    "validate_execution",
    "validate_target",
    "verify_allowed_changes",
]
