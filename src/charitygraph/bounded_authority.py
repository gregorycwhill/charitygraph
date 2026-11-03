"""Fail-closed O1F bounded local implementation authority.

The policy is certification machinery for the separately authorised bounded
local implementation route.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from charitygraph.windows_process import quiet_subprocess_kwargs


IMPLEMENTATION_AUTHORITY_VERSION = "charitygraph.g4-o1d-local-implementation/v1"
IMPLEMENTATION_SCOPE = "bounded_local_builder_code_change"
CODE_CHANGE_ROUTE_ACTIVE = True
ALLOWED_AUTHORITY = {"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"}


class BoundedAuthorityError(ValueError):
    pass


class InactiveImplementationRoute(BoundedAuthorityError):
    pass


class DirtyBaselineViolation(BoundedAuthorityError):
    pass


@dataclass(frozen=True)
class DirtyFileBaseline:
    """Private pre-execution bytes for an explicitly editable dirty file.

    These bytes never leave the local attestation process.  They allow a
    three-way reconciliation against HEAD rather than treating an allowlisted
    pre-existing edit as either invisible or categorically forbidden.
    """

    base_bytes: bytes
    dirty_bytes: bytes


@dataclass(frozen=True)
class WorkspaceSnapshot:
    workspace_path: str
    branch: str
    head: str
    entries: dict[str, tuple[str, str, str]]
    dirty_file_baselines: dict[str, DirtyFileBaseline] = field(default_factory=dict, repr=False)
    adopted_file_baselines: dict[str, str] = field(default_factory=dict, repr=False)


def _git(repo: Path, *args: str, raw: bool = False) -> str | bytes:
    command = ["git", "-c", f"safe.directory={repo}", *args]
    if raw:
        return subprocess.check_output(command, cwd=repo, stderr=subprocess.STDOUT, **quiet_subprocess_kwargs())
    return subprocess.check_output(command, cwd=repo, text=True, stderr=subprocess.STDOUT, **quiet_subprocess_kwargs()).strip()


def _index_fingerprints(repo: Path) -> dict[str, str]:
    """Return staged-object identities using one Git invocation for all paths.

    A workspace snapshot needs to detect index-only changes as well as
    worktree-byte changes.  Calling ``git diff`` once per dirty path made a
    large dirty baseline expensive and, on Windows, created a burst of console
    child processes.  The index already provides a per-path identity, so one
    ``ls-files -s -z`` read supplies the same staged-change protection.
    """
    raw = bytes(_git(repo, "ls-files", "-s", "-z", raw=True))
    by_path: dict[str, list[str]] = {}
    for record in raw.split(b"\0"):
        if not record or b"\t" not in record:
            continue
        metadata, path_raw = record.split(b"\t", 1)
        parts = metadata.decode("ascii", errors="strict").split()
        if len(parts) != 3:
            raise OSError("Git index entry has an unexpected format")
        path = path_raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        by_path.setdefault(path, []).append(":".join(parts))
    return {
        path: hashlib.sha256("\0".join(sorted(entries)).encode("ascii")).hexdigest()
        for path, entries in by_path.items()
    }


def _status_paths(status: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in status.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            old, new = value.split(" -> ", 1)
            # Keep both sides of a rename.  A post-execution comparison that
            # observes only the destination can otherwise miss deletion of a
            # pre-existing path.
            paths[old] = line[:2]
            paths[new] = line[:2]
        else:
            paths[value] = line[:2]
    return paths


def _file_sha(path: Path) -> str:
    if path.is_symlink():
        return "symlink:" + str(path.readlink())
    if not path.exists():
        return "<missing>"
    if path.is_dir():
        # Git represents an embedded repository as one untracked directory
        # entry. Hash its contents deterministically rather than attempting
        # to open the directory itself as a regular file.
        digest = hashlib.sha256()
        digest.update(b"directory\\0")
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            digest.update(child.name.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\\0")
            digest.update(_file_sha(child).encode("utf-8", errors="surrogateescape"))
            digest.update(b"\\0")
        return "directory:" + digest.hexdigest()
    if not path.is_file():
        raise OSError(f"unsupported workspace entry type: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_workspace(
    repo: str | Path,
    *,
    preserve_dirty_paths: set[str] | None = None,
    adopted_untracked_paths: set[str] | None = None,
) -> WorkspaceSnapshot:
    root = Path(repo).resolve()
    preserved = {item.replace("\\", "/") for item in (preserve_dirty_paths or set())}
    adopted = {item.replace("\\", "/") for item in (adopted_untracked_paths or set())}
    if preserved & adopted:
        raise DirtyBaselineViolation("an adopted path cannot also use dirty-file reconciliation")
    # Porcelain status deliberately uses a leading space for an unstaged-only
    # modification.  Do not route it through the text helper, whose normal
    # ``strip`` behaviour would remove that safety-significant byte from the
    # first record and corrupt its path.
    status = bytes(_git(root, "status", "--porcelain=v1", "--untracked-files=all", raw=True)).decode(
        "utf-8", errors="surrogateescape"
    ).rstrip("\r\n")
    paths = _status_paths(status)
    index_fingerprints = _index_fingerprints(root)
    entries: dict[str, tuple[str, str, str]] = {}
    dirty_file_baselines: dict[str, DirtyFileBaseline] = {}
    adopted_file_baselines: dict[str, str] = {}
    for relative, status_code in paths.items():
        path = root / relative
        entries[relative] = (
            status_code,
            _file_sha(path),
            index_fingerprints.get(relative, "<not-indexed>"),
        )
        if relative in adopted:
            # Adoption is deliberately narrower than dirty-file reconciliation:
            # an independently attested artifact may start as an untracked,
            # regular file, but only its exact pre-launch hash is preserved.
            if status_code != "??" or path.is_symlink() or not path.is_file():
                raise DirtyBaselineViolation(f"adopted path must be an untracked regular file: {relative}")
            adopted_file_baselines[relative] = entries[relative][1]
        if relative in preserved:
            # An untracked, deleted, symlinked, or non-regular file has no
            # stable Git ancestor for three-way reconciliation.  Refuse to
            # make it writable rather than silently weakening the dirty-state
            # boundary.
            if status_code == "??" or path.is_symlink() or not path.is_file():
                raise DirtyBaselineViolation(f"allowlisted dirty path cannot be reconciled safely: {relative}")
            try:
                base_bytes = bytes(_git(root, "show", f"HEAD:{relative}", raw=True))
            except subprocess.CalledProcessError as exc:
                raise DirtyBaselineViolation(f"allowlisted dirty path has no HEAD baseline: {relative}") from exc
            dirty_file_baselines[relative] = DirtyFileBaseline(base_bytes=base_bytes, dirty_bytes=path.read_bytes())
    return WorkspaceSnapshot(
        workspace_path=str(root),
        branch=str(_git(root, "branch", "--show-current")),
        head=str(_git(root, "rev-parse", "HEAD")),
        entries=entries,
        dirty_file_baselines=dirty_file_baselines,
        adopted_file_baselines=adopted_file_baselines,
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
    adoption = execution.get("change_policy") == "provenance_bound_adoption"
    if adoption:
        expected = expected | {"adopted_artifacts"}
    if set(execution) != expected:
        raise BoundedAuthorityError("bounded implementation execution fields are not exact")
    if execution.get("mode") != "codex_exec" or execution.get("change_policy") not in {"bounded_workspace", "provenance_bound_adoption"}:
        raise BoundedAuthorityError("bounded implementation must use codex_exec with a supported bounded change policy")
    if execution.get("authority_version") != IMPLEMENTATION_AUTHORITY_VERSION:
        raise BoundedAuthorityError("bounded implementation authority_version is unsupported")
    if execution.get("scope") != IMPLEMENTATION_SCOPE:
        raise BoundedAuthorityError("bounded implementation scope is unsupported")
    if execution.get("commit_policy") != "local_commit_only":
        raise BoundedAuthorityError("bounded implementation commit_policy is unsupported")
    allowed = execution.get("allowed_paths")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(item, str) and item for item in allowed):
        raise BoundedAuthorityError("bounded implementation allowed_paths must be a non-empty list")
    normalised_allowed = [item.replace("\\", "/") for item in allowed]
    if len(set(normalised_allowed)) != len(normalised_allowed):
        raise BoundedAuthorityError("bounded implementation allowed_paths must be unique")
    for item in allowed:
        normalised = item.replace("\\", "/")
        if normalised.startswith("/") or ":" in normalised or any(part in {"", ".", ".."} for part in normalised.split("/")):
            raise BoundedAuthorityError("bounded implementation allowed_paths must be relative")
    adopted_artifacts: tuple[dict[str, str], ...] = ()
    if adoption:
        raw_adopted = execution.get("adopted_artifacts")
        if not isinstance(raw_adopted, list) or not raw_adopted:
            raise BoundedAuthorityError("provenance-bound adoption requires adopted_artifacts")
        expected_adoption_fields = {"path", "sha256", "source_instruction_id", "source_result_file", "source_result_sha256"}
        parsed: list[dict[str, str]] = []
        for item in raw_adopted:
            if not isinstance(item, dict) or set(item) != expected_adoption_fields or not all(isinstance(item.get(key), str) and item[key] for key in expected_adoption_fields):
                raise BoundedAuthorityError("each adopted artifact must use the exact provenance schema")
            path = item["path"].replace("\\", "/")
            if path not in allowed or path.startswith("/") or ":" in path or any(part in {"", ".", ".."} for part in path.split("/")):
                raise BoundedAuthorityError("adopted artifact path must be an allowlisted relative path")
            if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or not re.fullmatch(r"[0-9a-f]{64}", item["source_result_sha256"]):
                raise BoundedAuthorityError("adopted artifact hashes must be lowercase SHA-256")
            if not item["source_result_file"].startswith("cg-g4-o1c-result-") or not item["source_result_file"].endswith(".json") or "/" in item["source_result_file"] or "\\" in item["source_result_file"]:
                raise BoundedAuthorityError("adopted artifact source result must be a bridge result file")
            parsed.append({**item, "path": path})
        if len({item["path"] for item in parsed}) != len(parsed):
            raise BoundedAuthorityError("adopted artifact paths must be unique")
        adopted_artifacts = tuple(parsed)
    if execution.get("model") != target.get("model"):
        raise BoundedAuthorityError("bounded implementation model does not match target")
    validate_target(target=target, workspace=workspace, authority=authority)
    if not route_active:
        raise InactiveImplementationRoute("bounded implementation route is inactive pending supervisory acceptance")
    return {"allowed_paths": tuple(normalised_allowed), "authority_version": IMPLEMENTATION_AUTHORITY_VERSION, "scope": IMPLEMENTATION_SCOPE, "adopted_artifacts": adopted_artifacts}


def _path_has_symlink_component(root: Path, relative: str) -> bool:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def validate_clean_commit_paths(workspace: WorkspaceSnapshot, *, allowed_paths: list[str] | tuple[str, ...]) -> None:
    """Require ordinary bridge-owned commit paths to be safe at launch.

    An explicitly allowlisted tracked regular file may already have an
    ordinary worktree or index modification.  The execution baseline captures
    those bytes for post-worker reconciliation.  Additions, deletions,
    renames, copies, type changes, ignored/untracked, symlinked and directory
    paths remain unsafe ordinary-commit inputs.  Adoption is intentionally
    excluded: it has its own provenance and untracked-file rules.
    """
    root = Path(workspace.workspace_path)
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    for relative in sorted(allowed):
        candidate = root / relative
        entry = workspace.entries.get(relative)
        if entry is not None:
            status_code = entry[0]
            # Only ordinary tracked modifications can use the dirty-file
            # reconciliation captured by the execution baseline.  This keeps
            # staged additions/deletions, renames/copies, type changes and
            # conflict states fail-closed while admitting dirty product files.
            if any(character not in {" ", "M"} for character in status_code) or not candidate.exists():
                raise DirtyBaselineViolation(f"ordinary commit path is not an existing tracked regular file: {relative}")
        if _path_has_symlink_component(root, relative):
            raise DirtyBaselineViolation(f"ordinary commit path has a symlink component: {relative}")
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise DirtyBaselineViolation(f"ordinary commit path must be a regular file: {relative}")
        tracked = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "ls-files", "--error-unmatch", "--", relative],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            **quiet_subprocess_kwargs(),
        )
        if tracked.returncode != 0:
            raise DirtyBaselineViolation(f"ordinary commit path is an existing non-tracked file: {relative}")


def verify_clean_commit_changes(
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
    *,
    allowed_paths: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Attest worker output that is eligible for a bridge-owned commit."""
    verified = verify_allowed_changes(before, after, allowed_paths=allowed_paths)
    root = Path(after.workspace_path)
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    changed = verified["changed_paths"]
    if not changed:
        raise DirtyBaselineViolation("bridge-owned commit requires at least one changed path")
    for relative in changed:
        if relative not in allowed:
            raise DirtyBaselineViolation(f"changed path is not in the exact commit allowlist: {relative}")
        status = after.entries.get(relative, ("", "", ""))[0]
        if status[:1] in {"D", "R", "C"} or status[1:2] in {"D", "R", "C"}:
            raise DirtyBaselineViolation(f"deletion, rename or copy is not permitted for bridge-owned commits: {relative}")
        if _path_has_symlink_component(root, relative):
            raise DirtyBaselineViolation(f"bridge-owned commit path has a symlink component: {relative}")
        candidate = root / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise DirtyBaselineViolation(f"bridge-owned commit path must be a regular file: {relative}")
    return verified


def verify_allowed_changes(before: WorkspaceSnapshot, after: WorkspaceSnapshot, *, allowed_paths: list[str] | tuple[str, ...], reconciliation_evidence_dir: str | Path | None = None) -> dict[str, Any]:
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    if before.workspace_path != after.workspace_path:
        raise DirtyBaselineViolation("workspace path changed during execution")
    if before.branch != after.branch or before.head != after.head:
        raise DirtyBaselineViolation(
            f"repository identity changed during execution: {before.branch}@{before.head} -> {after.branch}@{after.head}"
        )
    changed = sorted(path for path in set(before.entries) | set(after.entries) if before.entries.get(path) != after.entries.get(path))
    unexpected = sorted(path for path in changed if path not in allowed)
    root = Path(after.workspace_path)
    escaped = []
    for relative in changed:
        candidate = root / relative
        try:
            candidate.relative_to(root)
        except ValueError:
            escaped.append(relative)
            continue
        current = root
        parts = Path(relative).parts
        for part in parts:
            current = current / part
            if current.is_symlink():
                escaped.append(relative)
                break
    if escaped:
        unexpected = sorted(set(unexpected) | set(escaped))
    if unexpected:
        reason = "unexpected bounded workspace changes: " + ", ".join(unexpected)
        if escaped:
            reason += "; symlink/path escape detected"
        raise DirtyBaselineViolation(reason)
    baseline_changed = sorted(path for path in changed if path in before.entries)
    protected_baseline_changes = sorted(path for path in baseline_changed if path not in allowed)
    if protected_baseline_changes:
        raise DirtyBaselineViolation(f"pre-existing dirty baseline was changed outside the allowlist: {', '.join(protected_baseline_changes)}")

    reconciled: dict[str, dict[str, str]] = {}
    adopted: dict[str, dict[str, str]] = {}
    for relative in sorted(path for path in baseline_changed if path in allowed):
        adopted_baseline = before.adopted_file_baselines.get(relative)
        if adopted_baseline is not None:
            current_path = root / relative
            after_entry = after.entries.get(relative)
            if current_path.is_symlink() or not current_path.is_file() or after_entry is None or after_entry[0] != "??":
                raise DirtyBaselineViolation(f"adopted path is no longer an untracked regular file: {relative}")
            adopted[relative] = {
                "preexisting_sha256": adopted_baseline,
                "after_sha256": after_entry[1],
                "method": "provenance-bound-adoption",
            }
            continue
        baseline = before.dirty_file_baselines.get(relative)
        if baseline is None:
            raise DirtyBaselineViolation(f"allowlisted dirty path was changed without a pre-execution preservation snapshot: {relative}")
        current_path = root / relative
        if current_path.is_symlink() or not current_path.is_file():
            raise DirtyBaselineViolation(f"allowlisted dirty path is no longer a regular file: {relative}")
        after_bytes = current_path.read_bytes()
        # Git's three-way merge is used as a strict preservation proof:
        #   base   = HEAD before execution
        #   local  = the user's pre-existing dirty file
        #   remote = the post-worker file
        # A clean merge that produces exactly the post-worker bytes proves the
        # worker's edits are disjoint from, and retain, the existing edits.
        # Git objects are conventionally LF while a Windows worktree may use
        # CRLF for both the pre-existing edit and the post-worker file.  Align
        # only the base's line endings in that narrow, consistent case; any
        # worker-induced line-ending conversion remains a reconciliation
        # failure rather than becoming invisible.
        merge_base_bytes = baseline.base_bytes
        if (
            b"\r" not in merge_base_bytes
            and b"\r\n" in baseline.dirty_bytes
            and b"\r\n" in after_bytes
            and b"\r" not in baseline.dirty_bytes.replace(b"\r\n", b"")
            and b"\r" not in after_bytes.replace(b"\r\n", b"")
        ):
            merge_base_bytes = merge_base_bytes.replace(b"\n", b"\r\n")
        with tempfile.TemporaryDirectory(prefix="charitygraph-dirty-baseline-") as temporary:
            temporary_root = Path(temporary)
            local_path = temporary_root / "local"
            base_path = temporary_root / "base"
            remote_path = temporary_root / "remote"
            local_path.write_bytes(baseline.dirty_bytes)
            base_path.write_bytes(merge_base_bytes)
            remote_path.write_bytes(after_bytes)
            merged = subprocess.run(
                ["git", "merge-file", "-p", str(local_path), str(base_path), str(remote_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                **quiet_subprocess_kwargs(),
            )
        if merged.returncode != 0 or merged.stdout != after_bytes:
            if reconciliation_evidence_dir is not None:
                evidence = Path(reconciliation_evidence_dir) / hashlib.sha256(relative.encode("utf-8")).hexdigest()
                evidence.mkdir(parents=True, exist_ok=True)
                (evidence / "base.bin").write_bytes(merge_base_bytes)
                (evidence / "preexisting.bin").write_bytes(baseline.dirty_bytes)
                (evidence / "post_worker.bin").write_bytes(after_bytes)
                (evidence / "merge.stdout").write_bytes(merged.stdout)
                (evidence / "merge.stderr").write_bytes(merged.stderr)
                (evidence / "manifest.json").write_text(json.dumps({"path": relative, "returncode": merged.returncode, "base_sha256": hashlib.sha256(merge_base_bytes).hexdigest(), "preexisting_sha256": hashlib.sha256(baseline.dirty_bytes).hexdigest(), "post_worker_sha256": hashlib.sha256(after_bytes).hexdigest(), "merge_stdout_sha256": hashlib.sha256(merged.stdout).hexdigest(), "merge_stderr_sha256": hashlib.sha256(merged.stderr).hexdigest()}, sort_keys=True) + "\n", encoding="utf-8")
            raise DirtyBaselineViolation(
                f"allowlisted dirty baseline was not preserved by a clean three-way reconciliation: {relative}"
            )
        reconciled[relative] = {
            "base_sha256": hashlib.sha256(baseline.base_bytes).hexdigest(),
            "preexisting_sha256": hashlib.sha256(baseline.dirty_bytes).hexdigest(),
            "after_sha256": hashlib.sha256(after_bytes).hexdigest(),
            "method": "git-merge-file-clean-exact",
        }
    return {
        "changed_paths": changed,
        "unexpected_paths": unexpected,
        "baseline_preserved": True,
        "dirty_allowlisted_reconciliation": reconciled,
        "provenance_bound_adoption": adopted,
    }


def verify_local_commit(before: WorkspaceSnapshot, after: WorkspaceSnapshot, *, allowed_paths: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Accept one allowlisted direct-child local commit without masking baseline drift."""
    if before.workspace_path != after.workspace_path or before.branch != after.branch:
        raise DirtyBaselineViolation("repository workspace or branch changed during local commit")
    if before.head == after.head:
        raise DirtyBaselineViolation("local commit attestation requires a new commit")
    root = Path(after.workspace_path)
    parents = str(_git(root, "rev-list", "--parents", "-n", "1", after.head)).split()
    if len(parents) != 2 or parents[1] != before.head:
        raise DirtyBaselineViolation("local commit must be one non-merge direct child of the starting HEAD")
    if _git(root, "rev-list", "--count", f"{before.head}..{after.head}") != "1":
        raise DirtyBaselineViolation("local commit attestation permits exactly one commit")
    committed_paths = sorted(filter(None, str(_git(root, "diff", "--name-only", "--no-renames", before.head, after.head)).splitlines()))
    allowed = {path.replace("\\", "/") for path in allowed_paths}
    unexpected = sorted(path for path in committed_paths if path not in allowed)
    adopted_paths = set(before.adopted_file_baselines)
    baseline_committed = sorted(path for path in committed_paths if path in before.entries and path not in adopted_paths)
    symlinks = [path for path in committed_paths if (root / path).is_symlink()]
    if unexpected or baseline_committed or symlinks:
        parts: list[str] = []
        if unexpected:
            parts.append("unexpected committed paths: " + ", ".join(unexpected))
        if baseline_committed:
            parts.append("pre-existing dirty paths were committed: " + ", ".join(baseline_committed))
        if symlinks:
            parts.append("committed symlink paths are not permitted: " + ", ".join(symlinks))
        raise DirtyBaselineViolation("; ".join(parts))
    missing_adoptions = sorted(adopted_paths - set(committed_paths))
    if missing_adoptions:
        raise DirtyBaselineViolation("provenance-bound adopted paths were not committed: " + ", ".join(missing_adoptions))
    worktree_entries = dict(after.entries)
    for path in adopted_paths:
        # The commit has made the file clean, but for preservation proof it is
        # still the post-worker form of the original untracked artifact.
        worktree_entries[path] = ("??", _file_sha(root / path), "<committed-adoption>")
    worktree_after = WorkspaceSnapshot(
        workspace_path=after.workspace_path,
        branch=after.branch,
        head=before.head,
        entries=worktree_entries,
        adopted_file_baselines=before.adopted_file_baselines,
    )
    worktree = verify_allowed_changes(before, worktree_after, allowed_paths=allowed_paths)
    return {
        "commit_head": after.head,
        "commit_paths": committed_paths,
        "changed_paths": sorted(set(worktree["changed_paths"]) | set(committed_paths)),
        "unexpected_paths": worktree["unexpected_paths"],
        "baseline_preserved": worktree["baseline_preserved"],
        "provenance_bound_adoption": worktree["provenance_bound_adoption"],
    }


def report_only_execution(execution: dict[str, Any]) -> dict[str, Any]:
    allowed = {"mode", "change_policy", "model", "report_path", "timeout_seconds"}
    if set(execution) != allowed:
        raise BoundedAuthorityError("report_only execution must contain exactly mode, change_policy, model, report_path, timeout_seconds")
    if execution.get("change_policy") != "report_only":
        raise BoundedAuthorityError("report_only execution must use change_policy=report_only")
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
    "validate_clean_commit_paths",
    "validate_execution",
    "validate_target",
    "verify_clean_commit_changes",
    "verify_local_commit",
    "verify_allowed_changes",
]
