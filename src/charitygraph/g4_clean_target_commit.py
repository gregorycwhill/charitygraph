"""Dormant, host-owned clean-target commit transaction for Gate 4 recovery.

This module is deliberately not wired into the bridge.  It consumes exact
bytes supplied by an independently verified manifest and a separate source
anchor, builds the proposed tree in a disposable clone, and (only when
``dry_run=False``) CAS-advances one pinned branch ref.  It never stages or
reads candidate bytes from a live worktree or its index.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")


class CleanTargetCommitError(ValueError):
    """Fail-closed validation or transaction error."""


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str


@dataclass(frozen=True)
class ExactByteCandidateManifest:
    """Immutable manifest bytes plus their independently parsed entries."""

    manifest_bytes: bytes
    manifest_sha256: str
    entries: tuple[ManifestEntry, ...]

    @classmethod
    def from_entries(cls, entries: Iterable[ManifestEntry]) -> "ExactByteCandidateManifest":
        parsed = tuple(entries)
        payload = _canonical_payload("candidate-manifest/v1", parsed)
        return cls(payload, _sha256(payload), parsed)


@dataclass(frozen=True)
class AnchoredContent:
    """Source/test bytes and a separate exact-byte anchor record."""

    anchor_bytes: bytes
    anchor_sha256: str
    content: tuple[tuple[str, bytes], ...]

    @classmethod
    def from_content(cls, content: Mapping[str, bytes]) -> "AnchoredContent":
        frozen = tuple((path, bytes(value)) for path, value in sorted(content.items()))
        entries = tuple(ManifestEntry(path, _sha256(value)) for path, value in frozen)
        payload = _canonical_payload("source-anchor/v1", entries)
        return cls(payload, _sha256(payload), frozen)


@dataclass(frozen=True)
class CleanTargetCommitResult:
    dry_run: bool
    parent_head: str
    proposed_head: str
    tree: str
    ref: str
    committed_paths: tuple[str, ...]
    ref_updated: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "parent_head": self.parent_head,
            "proposed_head": self.proposed_head,
            "tree": self.tree,
            "ref": self.ref,
            "committed_paths": list(self.committed_paths),
            "ref_updated": self.ref_updated,
        }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_payload(kind: str, entries: Iterable[ManifestEntry]) -> bytes:
    return (
        json.dumps(
            {"format": kind, "entries": [{"path": item.path, "sha256": item.sha256} for item in entries]},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _git(repo: Path, *args: str, env: Mapping[str, str] | None = None, input_bytes: bytes | None = None) -> bytes:
    command = ["git", "-c", f"safe.directory={repo}", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            env=dict(env) if env is not None else None,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        raise CleanTargetCommitError(f"Git operation failed: {args[0]}") from exc
    if completed.returncode != 0:
        detail = completed.stdout.decode("utf-8", errors="replace").strip()
        raise CleanTargetCommitError(f"Git operation failed: {' '.join(args)}: {detail}")
    return completed.stdout


def _git_text(repo: Path, *args: str, env: Mapping[str, str] | None = None) -> str:
    return _git(repo, *args, env=env).decode("utf-8", errors="strict").strip()


def _validate_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/") or ":" in path:
        raise CleanTargetCommitError(f"invalid candidate path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CleanTargetCommitError(f"invalid candidate path: {path!r}")
    return path


def _validate_allowlist(allowlist: Iterable[str]) -> tuple[str, ...]:
    paths = tuple(_validate_path(path) for path in allowlist)
    if not paths or len(set(paths)) != len(paths):
        raise CleanTargetCommitError("exact allowlist must be non-empty and unique")
    return tuple(sorted(paths))


def _verify_manifest(manifest: ExactByteCandidateManifest, allowlist: tuple[str, ...]) -> dict[str, str]:
    if not isinstance(manifest, ExactByteCandidateManifest):
        raise CleanTargetCommitError("candidate manifest must be an ExactByteCandidateManifest")
    if not _SHA256.fullmatch(manifest.manifest_sha256) or _sha256(manifest.manifest_bytes) != manifest.manifest_sha256:
        raise CleanTargetCommitError("candidate manifest bytes/hash do not match")
    entries = tuple(manifest.entries)
    if manifest.manifest_bytes != _canonical_payload("candidate-manifest/v1", entries):
        raise CleanTargetCommitError("candidate manifest is not the exact canonical manifest")
    result: dict[str, str] = {}
    for item in entries:
        path = _validate_path(item.path)
        if not _SHA256.fullmatch(item.sha256):
            raise CleanTargetCommitError(f"candidate hash is not lowercase SHA-256: {path}")
        if path in result:
            raise CleanTargetCommitError(f"candidate path is duplicated: {path}")
        result[path] = item.sha256
    if set(result) != set(allowlist):
        raise CleanTargetCommitError("candidate paths do not exactly match the allowlist")
    return result


def _verify_anchor(anchor: AnchoredContent, manifest_hashes: Mapping[str, str]) -> dict[str, bytes]:
    if not isinstance(anchor, AnchoredContent):
        raise CleanTargetCommitError("source/test content must be an AnchoredContent")
    if not _SHA256.fullmatch(anchor.anchor_sha256) or _sha256(anchor.anchor_bytes) != anchor.anchor_sha256:
        raise CleanTargetCommitError("source anchor bytes/hash do not match")
    entries = tuple(ManifestEntry(path, _sha256(value)) for path, value in anchor.content)
    if anchor.anchor_bytes != _canonical_payload("source-anchor/v1", entries):
        raise CleanTargetCommitError("source anchor is not the exact canonical anchor")
    source: dict[str, bytes] = {}
    for path, value in anchor.content:
        path = _validate_path(path)
        if path in source:
            raise CleanTargetCommitError(f"source anchor path is duplicated: {path}")
        if path not in manifest_hashes or _sha256(value) != manifest_hashes[path]:
            raise CleanTargetCommitError(f"source/test content is not independently anchored: {path}")
        source[path] = bytes(value)
    if set(source) != set(manifest_hashes):
        raise CleanTargetCommitError("source/test anchor paths do not match the candidate manifest")
    return source


def _verify_candidate_bytes(candidate_bytes: Mapping[str, bytes], hashes: Mapping[str, str], source: Mapping[str, bytes]) -> dict[str, bytes]:
    actual = {path: bytes(value) for path, value in candidate_bytes.items()}
    if set(actual) != set(hashes):
        raise CleanTargetCommitError("candidate bytes do not exactly match the manifest paths")
    for path, value in actual.items():
        if _sha256(value) != hashes[path] or value != source[path]:
            raise CleanTargetCommitError(f"candidate bytes do not match independently anchored content: {path}")
    return actual


def _assert_clean_target(target: Path, expected_head: str) -> None:
    if _git_text(target, "rev-parse", "--is-inside-work-tree") != "true":
        raise CleanTargetCommitError("isolated target must be a worktree")
    if _git_text(target, "rev-parse", "HEAD") != expected_head:
        raise CleanTargetCommitError("isolated target has a stale HEAD")
    status = _git_text(target, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching")
    if status:
        raise CleanTargetCommitError("isolated target is staged or dirty")


def _assert_pinned_ref(repository: Path, branch: str, expected_head: str) -> str:
    if not branch or branch.startswith("refs/") or _git_text(repository, "check-ref-format", "--branch", branch) != branch:
        raise CleanTargetCommitError("branch is not a valid exact local branch name")
    if _git_text(repository, "rev-parse", "--abbrev-ref", "HEAD") != branch:
        raise CleanTargetCommitError("repository is not on the pinned branch")
    if _git_text(repository, "rev-parse", "HEAD") != expected_head:
        raise CleanTargetCommitError("repository has a stale HEAD")
    return f"refs/heads/{branch}"


def _compare_and_swap_ref(repository: Path, ref: str, new_head: str, expected_head: str) -> bool:
    command = ["git", "-c", f"safe.directory={repository}", "update-ref", ref, new_head, expected_head]
    completed = subprocess.run(command, cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.returncode == 0


def create_clean_target_commit(
    *,
    repository: Path,
    branch: str,
    expected_head: str,
    allowlist: Iterable[str],
    manifest: ExactByteCandidateManifest,
    source_anchor: AnchoredContent,
    candidate_bytes: Mapping[str, bytes],
    isolated_target: Path | None = None,
    dry_run: bool = True,
    commit_message: str = "gate4: clean target recovery",
) -> CleanTargetCommitResult:
    """Build one direct-child commit, optionally advancing the pinned ref.

    ``repository`` is the host-owned ref/worktree.  It may have unrelated
    dirty files when ``isolated_target`` is a separate clean checkout.  The
    target checkout itself must be completely clean.  All Git writes used to
    construct the tree occur in a temporary clone outside both repositories;
    only the explicit non-dry-run CAS updates ``repository``'s branch ref.
    """
    repository = Path(repository).resolve()
    if not _HEAD.fullmatch(expected_head):
        raise CleanTargetCommitError("expected HEAD must be a full lowercase commit id")
    paths = _validate_allowlist(allowlist)
    hashes = _verify_manifest(manifest, paths)
    source = _verify_anchor(source_anchor, hashes)
    candidate = _verify_candidate_bytes(candidate_bytes, hashes, source)
    ref = _assert_pinned_ref(repository, branch, expected_head)

    if isolated_target is None:
        target = repository
        _assert_clean_target(target, expected_head)
    else:
        target = Path(isolated_target).resolve()
        if target == repository:
            raise CleanTargetCommitError("isolated target must be separate from the host repository")
        _assert_clean_target(target, expected_head)

    with tempfile.TemporaryDirectory(prefix="charitygraph-g4-clean-target-") as temporary:
        build = Path(temporary) / "build"
        _git(Path(temporary), "clone", "--no-local", "--no-hardlinks", "--no-checkout", str(target), str(build))
        if _git_text(build, "rev-parse", "HEAD") != expected_head:
            raise CleanTargetCommitError("disposable build clone has a stale HEAD")
        index = Path(temporary) / "isolated-index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        _git(build, "read-tree", expected_head, env=env)
        for path in paths:
            blob = _git(build, "hash-object", "-w", "--stdin", env=env, input_bytes=candidate[path]).decode("ascii").strip()
            _git(build, "update-index", "--add", f"--cacheinfo", f"100644,{blob},{path}", env=env)
        tree = _git_text(build, "write-tree", env=env)
        proposed = _git_text(build, "commit-tree", tree, "-p", expected_head, "-m", commit_message, env=env)
        parents = _git_text(build, "rev-list", "--parents", "-n", "1", proposed).split()
        if parents != [proposed, expected_head]:
            raise CleanTargetCommitError("proposed commit is not one direct non-merge child")
        if _git_text(build, "rev-list", "--count", f"{expected_head}..{proposed}") != "1":
            raise CleanTargetCommitError("proposed commit is not exactly one commit after the base")
        changed = tuple(sorted(filter(None, _git_text(build, "diff", "--name-only", "--no-renames", expected_head, proposed).splitlines())))
        if changed != paths:
            raise CleanTargetCommitError("proposed commit paths do not exactly match the allowlist")
        for path in paths:
            actual = _git(build, "show", f"{proposed}:{path}")
            if actual != candidate[path]:
                raise CleanTargetCommitError(f"proposed tree bytes do not match candidate bytes: {path}")
        if not dry_run:
            # The proposed objects live only in the disposable build clone.
            # Install them without touching the host ref/index/worktree, then
            # use update-ref's expected-old argument as the final CAS fence.
            _git(repository, "fetch", "--no-tags", str(build), proposed)
            if not _compare_and_swap_ref(repository, ref, proposed, expected_head):
                raise CleanTargetCommitError("branch ref CAS failed; no target ref was advanced")
        return CleanTargetCommitResult(dry_run, expected_head, proposed, tree, ref, paths, not dry_run)

