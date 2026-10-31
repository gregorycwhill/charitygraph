from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from charitygraph import g4_clean_target_commit as transaction


def _run(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if check and result.returncode:
        raise AssertionError(result.stdout)
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "main"
    repo.mkdir()
    _run(repo, "init", "-b", "main")
    _run(repo, "config", "user.email", "test@example.invalid")
    _run(repo, "config", "user.name", "test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run(repo, "add", "README.md")
    _run(repo, "commit", "-m", "base")
    return repo, _run(repo, "rev-parse", "HEAD")


def _proof() -> tuple[transaction.ExactByteCandidateManifest, transaction.AnchoredContent, dict[str, bytes]]:
    content = {"src/new.py": b"value = 1\n", "tests/test_new.py": b"def test_new(): pass\n"}
    anchor = transaction.AnchoredContent.from_content(content)
    manifest = transaction.ExactByteCandidateManifest.from_entries(
        transaction.ManifestEntry(path, hashlib.sha256(value).hexdigest()) for path, value in content.items()
    )
    return manifest, anchor, dict(content)


def _target_clone(tmp_path: Path, repo: Path) -> Path:
    target = tmp_path / "isolated-target"
    _run(tmp_path, "clone", "--no-local", "--no-hardlinks", str(repo), str(target))
    return target


def _call(repo: Path, head: str, *, target: Path | None = None, dry_run: bool = True, **kwargs):
    manifest, anchor, candidate = _proof()
    return transaction.create_clean_target_commit(
        repository=repo,
        branch="main",
        expected_head=head,
        allowlist=tuple(candidate),
        manifest=kwargs.pop("manifest", manifest),
        source_anchor=kwargs.pop("source_anchor", anchor),
        candidate_bytes=kwargs.pop("candidate_bytes", candidate),
        isolated_target=target,
        dry_run=dry_run,
        **kwargs,
    )


def test_success_is_dry_run_and_builds_exact_direct_child(tmp_path: Path):
    repo, head = _repo(tmp_path)
    before = _run(repo, "status", "--porcelain", "--ignored")
    result = _call(repo, head)
    assert result.dry_run is True
    assert result.parent_head == head
    assert result.committed_paths == ("src/new.py", "tests/test_new.py")
    assert _run(repo, "rev-parse", "HEAD") == head
    assert _run(repo, "status", "--porcelain", "--ignored") == before == ""


def test_stale_head_is_rejected_before_transaction(tmp_path: Path):
    repo, head = _repo(tmp_path)
    (repo / "later.txt").write_text("later\n", encoding="utf-8")
    _run(repo, "add", "later.txt")
    _run(repo, "commit", "-m", "later")
    with pytest.raises(transaction.CleanTargetCommitError, match="stale HEAD"):
        _call(repo, head)


def test_altered_candidate_bytes_or_hash_are_rejected(tmp_path: Path):
    repo, head = _repo(tmp_path)
    manifest, anchor, candidate = _proof()
    altered = dict(candidate)
    altered["src/new.py"] = b"altered\n"
    with pytest.raises(transaction.CleanTargetCommitError, match="do not match"):
        _call(repo, head, manifest=manifest, source_anchor=anchor, candidate_bytes=altered)
    bad = transaction.ExactByteCandidateManifest.from_entries(
        [transaction.ManifestEntry("src/new.py", "0" * 64), transaction.ManifestEntry("tests/test_new.py", hashlib.sha256(candidate["tests/test_new.py"]).hexdigest())]
    )
    with pytest.raises(transaction.CleanTargetCommitError, match="independently anchored"):
        _call(repo, head, manifest=bad)


def test_wrong_path_is_rejected_by_exact_allowlist(tmp_path: Path):
    repo, head = _repo(tmp_path)
    manifest, anchor, candidate = _proof()
    with pytest.raises(transaction.CleanTargetCommitError, match="exactly match"):
        transaction.create_clean_target_commit(
            repository=repo,
            branch="main",
            expected_head=head,
            allowlist=("src/wrong.py", "tests/test_new.py"),
            manifest=manifest,
            source_anchor=anchor,
            candidate_bytes=candidate,
        )


def test_dirty_isolated_target_is_rejected(tmp_path: Path):
    repo, head = _repo(tmp_path)
    target = _target_clone(tmp_path, repo)
    (target / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(transaction.CleanTargetCommitError, match="staged or dirty"):
        _call(repo, head, target=target)


def test_main_dirty_worktree_and_index_are_preserved_on_real_cas(tmp_path: Path):
    repo, head = _repo(tmp_path)
    target = _target_clone(tmp_path, repo)
    (repo / "README.md").write_text("user edit\n", encoding="utf-8")
    (repo / "staged.txt").write_text("keep staged\n", encoding="utf-8")
    _run(repo, "add", "staged.txt")
    before_index = _run(repo, "ls-files", "-s")
    before_cached = _run(repo, "diff", "--cached", "--name-status", head)
    result = _call(repo, head, target=target, dry_run=False)
    assert result.ref_updated is True
    assert _run(repo, "rev-parse", "HEAD") == result.proposed_head
    assert (repo / "README.md").read_text(encoding="utf-8") == "user edit\n"
    assert _run(repo, "ls-files", "-s") == before_index
    assert _run(repo, "diff", "--cached", "--name-status", head) == before_cached == "A\tstaged.txt"
    status = _run(repo, "status", "--porcelain", "--ignored").splitlines()
    assert any(line.endswith("README.md") for line in status)
    assert "A  staged.txt" in status


def test_cas_rollback_leaves_ref_and_target_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, head = _repo(tmp_path)
    target = _target_clone(tmp_path, repo)
    monkeypatch.setattr(transaction, "_compare_and_swap_ref", lambda *args: False)
    with pytest.raises(transaction.CleanTargetCommitError, match="CAS failed"):
        _call(repo, head, target=target, dry_run=False)
    assert _run(repo, "rev-parse", "HEAD") == head
    assert _run(repo, "status", "--porcelain", "--ignored") == ""
    assert _run(target, "status", "--porcelain", "--ignored") == ""


def test_no_unexpected_mutations_on_validation_failure(tmp_path: Path):
    repo, head = _repo(tmp_path)
    target = _target_clone(tmp_path, repo)
    before_refs = _run(repo, "show-ref")
    before_status = _run(repo, "status", "--porcelain", "--ignored")
    manifest, anchor, candidate = _proof()
    with pytest.raises(transaction.CleanTargetCommitError):
        _call(repo, head, target=target, manifest=manifest, source_anchor=anchor, candidate_bytes={**candidate, "unexpected": b"x"})
    assert _run(repo, "show-ref") == before_refs
    assert _run(repo, "status", "--porcelain", "--ignored") == before_status
    assert _run(target, "status", "--porcelain", "--ignored") == ""

