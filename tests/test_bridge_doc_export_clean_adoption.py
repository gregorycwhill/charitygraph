import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from bridge.g4_doc_export_clean_adoption import (
    CleanAdoptionError,
    CleanAdoptionRequest,
    FENCE_V97_SHA256,
    OverlayIdentity,
    dirty_baseline_fingerprint,
    prepare_clean_target_adoption,
    read_dirty_baseline,
)


ALLOWLIST = (
    "bridge/bridge.py",
    "bridge/g4_doc_export_ingress.py",
    "tests/test_bridge_cutover.py",
    "tests/test_bridge_doc_export_ingress.py",
)
BRANCH = "gate3-cg406-remediation"


def _run(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _repository(path: Path) -> None:
    subprocess.run(["git", "init", "-b", BRANCH], cwd=path, check=True, stdout=subprocess.DEVNULL)
    _run(path, "config", "user.email", "test@example.invalid")
    _run(path, "config", "user.name", "Test")
    for relative in ALLOWLIST + ("unrelated.txt",):
        _write(path / relative, f"HEAD {relative}\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, stdout=subprocess.DEVNULL)


def _fixture(tmp_path: Path) -> tuple[CleanAdoptionRequest, Path, Path]:
    root = tmp_path / "root"
    root.mkdir()
    _repository(root)
    target = tmp_path / "clean-target"
    subprocess.run(["git", "clone", "--no-local", str(root), str(target)], check=True, stdout=subprocess.DEVNULL)
    _run(target, "config", "user.email", "test@example.invalid")
    _run(target, "config", "user.name", "Test")

    for relative in ALLOWLIST:
        value = f"OVERLAY {relative}\n"
        _write(root / relative, value)
        _write(target / relative, value)
    _write(root / "unrelated.txt", "unrelated root dirty baseline\n")

    head = _run(root, "rev-parse", "HEAD")
    identities = tuple(
        OverlayIdentity(
            relative,
            _run(root, "rev-parse", f"HEAD:{relative}"),
            _git_blob((root / relative).read_bytes()),
        )
        for relative in ALLOWLIST
    )
    baseline = read_dirty_baseline(root)
    request = CleanAdoptionRequest(
        repository="charitygraph",
        root_workspace=str(root),
        clean_target=str(target),
        expected_branch=BRANCH,
        expected_head=head,
        fence_sha256=FENCE_V97_SHA256,
        allowlist=ALLOWLIST,
        overlay_identities=identities,
        root_dirty_baseline=baseline,
        root_dirty_baseline_sha256=dirty_baseline_fingerprint(baseline),
    )
    return request, root, target


def _immutable_state(path: Path) -> tuple[str, str, bytes, bytes]:
    return (
        _run(path, "rev-parse", "HEAD"),
        _run(path, "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        b"".join((path / relative).read_bytes() for relative in ALLOWLIST),
        _run(path, "diff", "--cached", "--binary").encode("utf-8"),
    )


def test_successful_attestation_is_hashed_and_does_not_adopt_or_activate(tmp_path):
    request, root, target = _fixture(tmp_path)
    before_root = _immutable_state(root)
    before_target = _immutable_state(target)

    manifest = prepare_clean_target_adoption(request)

    assert manifest["outcome"] == "PARTIAL"
    assert manifest["adoption_status"] == "NOT_ADOPTED"
    assert manifest["activation_status"] == "NOT_ACTIVATED"
    assert manifest["host_identity"]["trusted_host_proven"] is False
    unsigned = dict(manifest)
    digest = unsigned.pop("manifest_sha256")
    expected = hashlib.sha256((json.dumps(unsigned, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
    assert digest == expected
    assert manifest["allowlist"] == sorted(ALLOWLIST)
    assert [item["path"] for item in manifest["overlay_identities"]] == sorted(ALLOWLIST)
    assert _immutable_state(root) == before_root
    assert _immutable_state(target) == before_target


@pytest.mark.parametrize(
    "change",
    [
        lambda request: replace(request, expected_head="a" * 40),
        lambda request: replace(request, fence_sha256="d" * 64),
        lambda request: replace(request, allowlist=("../escape.txt",) + ALLOWLIST[1:]),
        lambda request: replace(request, overlay_identities=(request.overlay_identities[0], request.overlay_identities[0], *request.overlay_identities[2:])),
    ],
    ids=["stale-head", "stale-fence", "path-traversal", "duplicate-conflict"],
)
def test_identity_policy_rejects_stale_or_ambiguous_requests(tmp_path, change):
    request, root, target = _fixture(tmp_path)
    with pytest.raises(CleanAdoptionError):
        prepare_clean_target_adoption(change(request))
    assert _immutable_state(root)[0] == request.expected_head
    assert _immutable_state(target)[0] == request.expected_head


def test_altered_worktree_hash_is_rejected_without_side_effect(tmp_path):
    request, root, target = _fixture(tmp_path)
    _write(target / ALLOWLIST[0], "altered after manifest preparation\n")
    before_root = _immutable_state(root)
    before_target = _immutable_state(target)
    with pytest.raises(CleanAdoptionError, match="worktree bytes|overlay"):
        prepare_clean_target_adoption(request)
    assert _immutable_state(root) == before_root
    assert _immutable_state(target) == before_target


def test_unrelated_root_dirty_baseline_change_is_rejected(tmp_path):
    request, root, target = _fixture(tmp_path)
    _write(root / "unrelated.txt", "a different unrelated baseline\n")
    with pytest.raises(CleanAdoptionError, match="dirty baseline"):
        prepare_clean_target_adoption(request)


def test_extra_clean_target_overlay_is_rejected(tmp_path):
    request, root, target = _fixture(tmp_path)
    _write(target / "unrelated.txt", "extra target overlay\n")
    with pytest.raises(CleanAdoptionError, match="extra|ambiguous"):
        prepare_clean_target_adoption(request)


def test_stale_target_ref_is_rejected(tmp_path):
    request, root, target = _fixture(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "ref moved"], cwd=target, check=True, stdout=subprocess.DEVNULL)
    with pytest.raises(CleanAdoptionError, match="HEAD"):
        prepare_clean_target_adoption(request)


def test_missing_overlay_path_is_rejected(tmp_path):
    request, root, target = _fixture(tmp_path)
    (target / ALLOWLIST[0]).unlink()
    with pytest.raises(CleanAdoptionError, match="missing|overlay"):
        prepare_clean_target_adoption(request)


def test_symlink_overlay_is_rejected_when_windows_or_posix_allows_creation(tmp_path):
    request, root, target = _fixture(tmp_path)
    link = target / ALLOWLIST[0]
    replacement = target / "unrelated.txt"
    link.unlink()
    try:
        os.symlink(replacement, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(CleanAdoptionError):
        prepare_clean_target_adoption(request)
