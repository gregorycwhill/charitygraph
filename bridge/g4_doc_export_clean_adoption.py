"""Read-only attestation for a future clean-target CGDOC1 overlay adoption.

This module is deliberately narrower than the bridge commit mechanism.  It
never stages bytes, writes an index or ref, launches a process, reads a Doc, or
activates a scanner.  It proves only that a trusted host could re-check the
four supplied worktree blobs in a disposable clean target immediately before
using the existing bridge-owned exact-path commit seam.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from bridge.g4_doc_export_ingress import (
    DocExportError,
    FENCE_SCHEMA,
    _has_reparse_attribute,
    _read_regular_file_no_follow,
)


SCHEMA = "charitygraph.g4-o1c-clean-target-adoption-attestation/v1"
NOT_ADOPTED = "NOT_ADOPTED"
NOT_ACTIVATED = "NOT_ACTIVATED"
PARTIAL = "PARTIAL"
EXPECTED_REPOSITORY = "charitygraph"
_HEX_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CleanAdoptionError(ValueError):
    """A stale, ambiguous, unsafe, or otherwise unverifiable overlay."""


@dataclass(frozen=True)
class OverlayIdentity:
    """One exact tracked path and its expected HEAD/worktree Git blobs."""

    path: str
    head_blob: str
    worktree_blob: str


@dataclass(frozen=True)
class CleanAdoptionRequest:
    """All identities a trusted host must bind before a future adoption.

    The fence bytes and identity are supplied by the caller and checked as a
    single exact value.  Matching a caller-supplied digest is an attestation
    input, not proof that this read-only helper authenticated the host.
    """

    repository: str
    root_workspace: str
    clean_target: str
    expected_branch: str
    expected_head: str
    fence_sha256: str
    fence_id: str
    fence_version: int
    fence_bytes: bytes
    allowlist: tuple[str, ...]
    overlay_identities: tuple[OverlayIdentity, ...]
    root_dirty_baseline: tuple[tuple[str, str, str], ...]
    root_dirty_baseline_sha256: str


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def dirty_baseline_fingerprint(entries: Iterable[tuple[str, str, str]]) -> str:
    """Hash the complete sorted porcelain path/status/blob baseline."""
    normalised = sorted([[path.replace("\\", "/"), status, identity] for path, status, identity in entries])
    return hashlib.sha256(_canonical_bytes(normalised)).hexdigest()


def _git(cwd: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "output", "") or str(exc)
        raise CleanAdoptionError(f"read-only git identity check failed: {detail.strip()}") from exc


def _git_bytes(cwd: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "output", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        raise CleanAdoptionError(f"read-only git identity check failed: {detail.strip()}") from exc


def _validate_relative_path(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CleanAdoptionError(f"{field} must be a non-empty relative path")
    path = value.replace("\\", "/")
    if path.startswith("/") or ":" in path:
        raise CleanAdoptionError(f"{field} must be relative")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CleanAdoptionError(f"{field} contains traversal or ambiguous components")
    return path


def _validate_sha(value: Any, pattern: re.Pattern[str], *, field: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise CleanAdoptionError(f"{field} is not an exact lowercase digest")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CleanAdoptionError(f"fence contains duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_json_constant(value: str) -> None:
    raise CleanAdoptionError(f"fence contains non-standard JSON constant: {value}")


def _validate_fence(request: CleanAdoptionRequest) -> dict[str, Any]:
    """Validate the exact caller-supplied fence, without authenticating origin."""
    _validate_sha(request.fence_sha256, _HEX_SHA256, field="fence_sha256")
    if not isinstance(request.fence_id, str) or not request.fence_id.strip():
        raise CleanAdoptionError("fence_id must be a non-empty identity")
    if isinstance(request.fence_version, bool) or not isinstance(request.fence_version, int) or request.fence_version < 1:
        raise CleanAdoptionError("fence_version must be a positive integer")
    if not isinstance(request.fence_bytes, bytes) or not request.fence_bytes:
        raise CleanAdoptionError("trusted fence bytes are required")
    actual_sha256 = hashlib.sha256(request.fence_bytes).hexdigest()
    if actual_sha256 != request.fence_sha256:
        raise CleanAdoptionError("fence SHA does not match the supplied fence bytes")
    try:
        fence = json.loads(
            request.fence_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CleanAdoptionError("fence bytes are not valid UTF-8 JSON") from exc
    if not isinstance(fence, dict):
        raise CleanAdoptionError("fence must be a JSON object")
    try:
        canonical = _canonical_bytes(fence)
    except UnicodeEncodeError as exc:
        raise CleanAdoptionError("fence contains non-UTF-8 JSON text") from exc
    if canonical != request.fence_bytes:
        raise CleanAdoptionError("fence bytes are not exact canonical UTF-8 JSON")
    if fence.get("schema") != FENCE_SCHEMA or fence.get("state") != "ACTIVE":
        raise CleanAdoptionError("fence schema or state is not active")
    if fence.get("fence_id") != request.fence_id or fence.get("fence_version") != request.fence_version:
        raise CleanAdoptionError("fence ID or version conflicts with the supplied identity")
    if not isinstance(fence.get("workspace_path"), str) or not fence["workspace_path"]:
        raise CleanAdoptionError("fence workspace identity is missing")
    if not isinstance(fence.get("branch"), str) or not fence["branch"]:
        raise CleanAdoptionError("fence branch identity is missing")
    if not isinstance(fence.get("head"), str) or not _HEX_SHA1.fullmatch(fence["head"]):
        raise CleanAdoptionError("fence HEAD identity is invalid")
    return fence


def _validate_request(
    request: CleanAdoptionRequest,
) -> tuple[tuple[str, ...], tuple[OverlayIdentity, ...], dict[str, Any]]:
    if request.repository != EXPECTED_REPOSITORY:
        raise CleanAdoptionError("repository identity is not charitygraph")
    if not request.expected_branch or request.expected_branch == "(HEAD)":
        raise CleanAdoptionError("an attached expected branch is required")
    _validate_sha(request.expected_head, _HEX_SHA1, field="expected_head")
    fence = _validate_fence(request)
    raw_allowlist = tuple(_validate_relative_path(item, field="allowlist") for item in request.allowlist)
    if not raw_allowlist or len(set(raw_allowlist)) != len(raw_allowlist):
        raise CleanAdoptionError("allowlist must be an exact set without duplicates")
    allowlist = tuple(sorted(raw_allowlist))
    if len(request.overlay_identities) != len(allowlist):
        raise CleanAdoptionError("overlay identities must cover the allowlist exactly once")
    identities: list[OverlayIdentity] = []
    seen: set[str] = set()
    for identity in request.overlay_identities:
        path = _validate_relative_path(identity.path, field="overlay identity path")
        if path in seen:
            raise CleanAdoptionError("duplicate or conflicting overlay identity")
        seen.add(path)
        _validate_sha(identity.head_blob, _HEX_SHA1, field=f"{path}.head_blob")
        _validate_sha(identity.worktree_blob, _HEX_SHA1, field=f"{path}.worktree_blob")
        identities.append(OverlayIdentity(path, identity.head_blob, identity.worktree_blob))
    if tuple(sorted(seen)) != allowlist:
        raise CleanAdoptionError("overlay identities do not match the exact allowlist")
    baseline = tuple(
        sorted(
            (str(path).replace("\\", "/"), str(status), str(identity))
            for path, status, identity in request.root_dirty_baseline
        )
    )
    if any(_validate_relative_path(path, field="root dirty baseline path") != path for path, _, _ in baseline):
        raise CleanAdoptionError("root dirty baseline contains an unsafe path")
    expected_baseline_sha = dirty_baseline_fingerprint(baseline)
    if request.root_dirty_baseline_sha256 != expected_baseline_sha:
        raise CleanAdoptionError("root dirty baseline fingerprint does not bind its entries")
    return allowlist, tuple(sorted(identities, key=lambda item: item.path)), fence


def read_dirty_baseline(repository: str | Path) -> tuple[tuple[str, str, str], ...]:
    """Read Git's complete porcelain baseline without changing repository state."""
    raw = _git_bytes(Path(repository), "status", "--porcelain=v1", "-z", "--untracked-files=all")
    fields = raw.split(b"\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        if len(field) < 4:
            raise CleanAdoptionError("Git returned an ambiguous dirty-baseline record")
        status = field[:2].decode("ascii", errors="strict")
        path = field[3:].decode("utf-8", errors="strict").replace("\\", "/")
        _validate_relative_path(path, field="Git dirty baseline path")
        entries.append((path, status))
        if status[0] in {"R", "C"}:
            if index >= len(fields) or not fields[index]:
                raise CleanAdoptionError("Git rename/copy baseline is missing its source identity")
            source = fields[index].decode("utf-8", errors="strict").replace("\\", "/")
            _validate_relative_path(source, field="Git rename/copy source path")
            entries.append((source, status))
            index += 1
    root = _assert_regular_directory(Path(repository), label="Git repository")
    identified: list[tuple[str, str, str]] = []
    for path, status in entries:
        try:
            (root / path).lstat()
        except OSError:
            identity = "MISSING"
        else:
            identity = _stable_worktree_blob(root, path, label=f"dirty baseline {path}")
        identified.append((path, status, identity))
    return tuple(sorted(identified))


def _assert_regular_directory(path: Path, *, label: str) -> Path:
    try:
        value = path.lstat()
    except OSError as exc:
        raise CleanAdoptionError(f"{label} is missing") from exc
    if path.is_symlink() or _has_reparse_attribute(value) or not stat.S_ISDIR(value.st_mode):
        raise CleanAdoptionError(f"{label} must be a non-link regular directory")
    resolved = path.resolve()
    try:
        resolved_value = resolved.lstat()
    except OSError as exc:
        raise CleanAdoptionError(f"{label} cannot be resolved safely") from exc
    if _has_reparse_attribute(resolved_value) or not resolved.is_dir():
        raise CleanAdoptionError(f"{label} is not a trusted directory")
    return resolved


def _assert_safe_parent_chain(root: Path, relative: str, *, label: str) -> Path:
    current = root
    for component in relative.split("/"):
        current = current / component
        try:
            value = current.lstat()
        except OSError as exc:
            raise CleanAdoptionError(f"{label} is missing") from exc
        if current.is_symlink() or _has_reparse_attribute(value):
            raise CleanAdoptionError(f"{label} contains a symlink or reparse point")
    return current


def _git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _stable_worktree_blob(root: Path, relative: str, *, label: str) -> str:
    path = _assert_safe_parent_chain(root, relative, label=label)
    try:
        before = path.lstat()
        raw = _read_regular_file_no_follow(path)
        after = path.lstat()
    except (DocExportError, OSError, ValueError) as exc:
        raise CleanAdoptionError(f"{label} could not be read safely") from exc
    if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(after.st_mode):
        raise CleanAdoptionError(f"{label} is not a regular file")
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CleanAdoptionError(f"{label} changed during attestation")
    return _git_blob_id(raw)


def _repository_identity(root: Path, *, label: str) -> tuple[str, str, str]:
    top = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise CleanAdoptionError(f"{label} Git top-level is not the trusted directory")
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    _validate_sha(head, _HEX_SHA1, field=f"{label}.HEAD")
    return branch, head, _git(root, "rev-parse", "HEAD^{tree}")


def _head_blob(root: Path, head: str, relative: str, *, label: str) -> str:
    entries = _git_bytes(root, "ls-tree", "-z", head, "--", relative).split(b"\0")
    matches = []
    for entry in entries:
        if not entry or b"\t" not in entry:
            continue
        metadata, path_raw = entry.split(b"\t", 1)
        parts = metadata.decode("ascii", errors="strict").split()
        if len(parts) == 3 and parts[1] == "blob" and path_raw.decode("utf-8") == relative:
            matches.append(parts[2])
    if len(matches) != 1 or not _HEX_SHA1.fullmatch(matches[0]):
        raise CleanAdoptionError(f"{label} HEAD path is missing or ambiguous")
    return matches[0]


def _check_baseline(root: Path, expected: tuple[tuple[str, str, str], ...], expected_sha: str, *, label: str) -> None:
    observed = read_dirty_baseline(root)
    if observed != expected or dirty_baseline_fingerprint(observed) != expected_sha:
        raise CleanAdoptionError(f"{label} dirty baseline is stale or changed")


def prepare_clean_target_adoption(request: CleanAdoptionRequest) -> dict[str, Any]:
    """Return a content-hashed, non-adopting attestation manifest.

    Every operation is read-only.  A successful return means only that the
    supplied clean target currently contains exactly the requested overlay.
    Trusted-host identity and the subsequent commit remain unproven.
    """
    allowlist, identities, fence = _validate_request(request)
    root = _assert_regular_directory(Path(request.root_workspace), label="root workspace")
    target = _assert_regular_directory(Path(request.clean_target), label="clean target")
    if root == target:
        raise CleanAdoptionError("root workspace and clean target must be distinct")

    root_branch, root_head, root_tree = _repository_identity(root, label="root workspace")
    if root_branch != request.expected_branch or root_head != request.expected_head:
        raise CleanAdoptionError("root branch or HEAD is stale/ref-moved")
    if (
        fence["workspace_path"] != str(root)
        or fence["branch"] != root_branch
        or fence["head"] != root_head
    ):
        raise CleanAdoptionError("fence identity does not match the current root snapshot")
    _check_baseline(root, request.root_dirty_baseline, request.root_dirty_baseline_sha256, label="root workspace")

    target_branch, target_head, target_tree = _repository_identity(target, label="clean target")
    if target_branch != request.expected_branch or target_head != request.expected_head:
        raise CleanAdoptionError("clean target branch or HEAD is not pinned to the expected identity")
    target_baseline = read_dirty_baseline(target)
    target_paths = tuple(sorted(path for path, _, _ in target_baseline))
    if target_paths != allowlist or any(status != " M" for _, status, _ in target_baseline):
        raise CleanAdoptionError("clean target has extra, staged, missing, or ambiguous overlay changes")

    observed_paths: list[dict[str, str]] = []
    for identity in identities:
        root_head_blob = _head_blob(root, root_head, identity.path, label=f"root {identity.path}")
        target_head_blob = _head_blob(target, target_head, identity.path, label=f"target {identity.path}")
        if root_head_blob != identity.head_blob or target_head_blob != identity.head_blob:
            raise CleanAdoptionError(f"{identity.path} HEAD blob identity is stale or conflicting")
        root_worktree_blob = _stable_worktree_blob(root, identity.path, label=f"root {identity.path}")
        target_worktree_blob = _stable_worktree_blob(target, identity.path, label=f"target {identity.path}")
        if root_worktree_blob != identity.worktree_blob or target_worktree_blob != identity.worktree_blob:
            raise CleanAdoptionError(f"{identity.path} worktree bytes changed or do not match the supplied overlay")
        observed_paths.append(
            {
                "path": identity.path,
                "head_blob": identity.head_blob,
                "worktree_blob": identity.worktree_blob,
            }
        )

    manifest = {
        "schema": SCHEMA,
        "outcome": PARTIAL,
        "adoption_status": NOT_ADOPTED,
        "activation_status": NOT_ACTIVATED,
        "repository": request.repository,
        "root": {
            "workspace": str(root),
            "branch": root_branch,
            "head": root_head,
            "tree": root_tree,
            "dirty_baseline": [[path, status, identity] for path, status, identity in request.root_dirty_baseline],
            "dirty_baseline_sha256": request.root_dirty_baseline_sha256,
        },
        "clean_target": {
            "workspace": str(target),
            "branch": target_branch,
            "head": target_head,
            "tree": target_tree,
            "overlay_status": [[path, status, identity] for path, status, identity in target_baseline],
        },
        "fence": {
            "fence_id": request.fence_id,
            "fence_version": request.fence_version,
            "sha256": request.fence_sha256,
        },
        "allowlist": list(allowlist),
        "overlay_identities": observed_paths,
        "host_identity": {
            "trusted_host_proven": False,
            "reason": "This local helper cannot prove the future trusted host or operator authority.",
        },
        "next_trusted_host": {
            "commit_method": "bridge.CutoverWatcher._bridge_owned_exact_path_commit",
            "commit_parent_head": request.expected_head,
            "commit_paths": list(allowlist),
            "commit_ref": f"refs/heads/{request.expected_branch}",
            "commit_scope": "one direct child containing exactly the four allowlisted paths",
            "successor_fence": "after commit, write and independently verify a successor exact branch/HEAD/fence attestation before any activation",
            "native_doc_export": "separate explicit host integration and end-to-end test remains required",
        },
        "next_trusted_host_steps": [
            "Re-read this manifest and re-attest the same clean target at the exact pinned branch/HEAD, fence identity/digest, allowlist, root dirty baseline, and four blob pairs.",
            "In the trusted host only, invoke the existing _bridge_owned_exact_path_commit with parent_head equal to the pinned HEAD and paths exactly equal to the four-path allowlist.",
            "Verify the result is one direct child on the pinned branch, with no unrelated staged paths or worktree changes; do not adopt the root checkout.",
            "Write a successor exact branch/HEAD/fence attestation and separately authorize the dormant native Doc export host integration and end-to-end pickup test.",
        ],
    }
    manifest["manifest_sha256"] = hashlib.sha256(_canonical_bytes(manifest)).hexdigest()
    return manifest


__all__ = [
    "CleanAdoptionError",
    "CleanAdoptionRequest",
    "OverlayIdentity",
    "NOT_ACTIVATED",
    "NOT_ADOPTED",
    "PARTIAL",
    "dirty_baseline_fingerprint",
    "prepare_clean_target_adoption",
    "read_dirty_baseline",
]
