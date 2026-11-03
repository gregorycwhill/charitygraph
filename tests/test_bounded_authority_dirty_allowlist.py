import subprocess

import pytest

from charitygraph.bounded_authority import (
    DirtyBaselineViolation,
    capture_workspace,
    validate_clean_commit_paths,
    verify_clean_commit_changes,
)


def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "allowed.py").write_text("base = 1\nvalue = 2\nthird = 3\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("unrelated base\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/allowed.py", "unrelated.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
    return repo


@pytest.mark.parametrize("stage_dirty_file", [False, True])
def test_dirty_or_staged_allowlisted_tracked_product_path_admits(tmp_path, stage_dirty_file):
    repo = _git_repo(tmp_path)
    allowed = repo / "src" / "allowed.py"
    allowed.write_text("base = 'preexisting'\nvalue = 2\nthird = 3\n", encoding="utf-8")
    if stage_dirty_file:
        subprocess.run(["git", "add", "src/allowed.py"], cwd=repo, check=True)

    snapshot = capture_workspace(repo, preserve_dirty_paths={"src/allowed.py"})
    validate_clean_commit_paths(snapshot, allowed_paths=["src/allowed.py"])

    assert "src/allowed.py" in snapshot.dirty_file_baselines


def test_unallowlisted_change_remains_excluded_from_bounded_verification(tmp_path):
    repo = _git_repo(tmp_path)
    allowed = repo / "src" / "allowed.py"
    allowed.write_text("base = 'preexisting'\nvalue = 2\nthird = 3\n", encoding="utf-8")
    before = capture_workspace(repo, preserve_dirty_paths={"src/allowed.py"})

    allowed.write_text("base = 'preexisting'\nvalue = 2\nthird = 'worker'\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("unrelated worker change\n", encoding="utf-8")

    with pytest.raises(DirtyBaselineViolation, match="unrelated.txt"):
        verify_clean_commit_changes(
            before,
            capture_workspace(repo),
            allowed_paths=["src/allowed.py"],
        )


def test_preexisting_unrelated_work_is_not_absorbed_by_allowlisted_worker_change(tmp_path):
    repo = _git_repo(tmp_path)
    allowed = repo / "src" / "allowed.py"
    allowed.write_text("base = 'preexisting'\nvalue = 2\nthird = 3\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("unrelated preexisting work\n", encoding="utf-8")
    before = capture_workspace(repo, preserve_dirty_paths={"src/allowed.py"})

    allowed.write_text("base = 'preexisting'\nvalue = 2\nthird = 'worker'\n", encoding="utf-8")
    verification = verify_clean_commit_changes(
        before,
        capture_workspace(repo),
        allowed_paths=["src/allowed.py"],
    )

    assert verification["changed_paths"] == ["src/allowed.py"]
    assert (repo / "unrelated.txt").read_text(encoding="utf-8") == "unrelated preexisting work\n"
    assert "unrelated.txt" in before.entries
