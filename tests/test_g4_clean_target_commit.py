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
    assert result.object_import.import_attempted is False
    assert result.object_import.objects_may_have_been_installed == ()
    assert result.as_dict()["object_import"]["garbage_collection_policy"].startswith("not_applicable")
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
    assert result.object_import.import_attempted is True
    assert result.object_import.fetch_completed is True
    assert result.object_import.fetch_head_changed is False
    assert result.object_import.objects_may_have_been_installed
    assert set(result.object_import.objects_may_have_been_installed).issubset(
        result.object_import.reachable_object_ids
    )
    assert set(result.object_import.objects_observed_present_after) == set(
        result.object_import.objects_may_have_been_installed
    )
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
    fetch_head = Path(_run(repo, "rev-parse", "--git-path", "FETCH_HEAD"))
    if not fetch_head.is_absolute():
        fetch_head = repo / fetch_head
    fetch_head.write_bytes(b"pre-existing fetch head\n")
    before_fetch_head = fetch_head.read_bytes()
    monkeypatch.setattr(transaction, "_compare_and_swap_ref", lambda *args: False)
    with pytest.raises(transaction.CleanTargetCommitError, match="CAS failed") as raised:
        _call(repo, head, target=target, dry_run=False)
    attestation = raised.value.object_import_attestation
    assert attestation is not None
    assert attestation.import_attempted is True
    assert attestation.fetch_completed is True
    assert attestation.fetch_head_changed is False
    assert attestation.fetch_head_before_sha256 == hashlib.sha256(before_fetch_head).hexdigest()
    assert attestation.fetch_head_after_sha256 == attestation.fetch_head_before_sha256
    assert attestation.objects_may_have_been_installed
    assert set(attestation.objects_observed_present_after) == set(attestation.objects_may_have_been_installed)
    assert attestation.unlink_performed is False
    assert "no unlink" in attestation.garbage_collection_policy
    assert raised.value.as_dict()["object_import"]["objects_may_have_been_installed"] == list(
        attestation.objects_may_have_been_installed
    )
    assert fetch_head.read_bytes() == before_fetch_head
    assert _run(repo, "rev-parse", "HEAD") == head
    assert _run(repo, "status", "--porcelain", "--ignored") == ""
    assert _run(target, "status", "--porcelain", "--ignored") == ""


def test_concurrent_branch_movement_is_rejected_without_dirty_overlay_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, head = _repo(tmp_path)
    target = _target_clone(tmp_path, repo)
    (repo / "README.md").write_text("user edit\n", encoding="utf-8")
    (repo / "staged.txt").write_text("keep staged\n", encoding="utf-8")
    _run(repo, "add", "staged.txt")
    before_index = _run(repo, "ls-files", "-s")
    before_status = _run(repo, "status", "--porcelain", "--ignored")

    moved: list[str] = []

    def move_then_fail(repository: Path, ref: str, new_head: str, expected_head: str) -> bool:
        tree = _run(repository, "rev-parse", f"{expected_head}^{{tree}}")
        created = subprocess.run(
            ["git", "commit-tree", tree, "-p", expected_head],
            cwd=repository,
            input="concurrent branch movement\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert created.returncode == 0, created.stdout
        moved_head = created.stdout.strip()
        _run(repository, "update-ref", ref, moved_head, expected_head)
        moved.append(moved_head)
        return False

    monkeypatch.setattr(transaction, "_compare_and_swap_ref", move_then_fail)
    with pytest.raises(transaction.CleanTargetCommitError, match="CAS failed") as raised:
        _call(repo, head, target=target, dry_run=False)

    assert moved
    assert _run(repo, "rev-parse", "HEAD") == moved[0]
    assert _run(repo, "ls-files", "-s") == before_index
    assert _run(repo, "status", "--porcelain", "--ignored") == before_status
    assert raised.value.object_import_attestation is not None
    assert raised.value.object_import_attestation.unlink_performed is False


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

