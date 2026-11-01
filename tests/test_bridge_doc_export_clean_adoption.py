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
FENCE_ID = "cg-g4-o1b-dormant-state-fence-20261020-v98"
FENCE_VERSION = 98


def _run(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _fence_bytes(root: Path, head: str, *, fence_id: str = FENCE_ID, fence_version: int = FENCE_VERSION, **overrides: object) -> bytes:
    fence = {
        "branch": BRANCH,
        "fence_id": fence_id,
        "fence_version": fence_version,
        "head": head,
        "schema": "charitygraph.g4-o1b-dormant-fence/v1",
        "state": "ACTIVE",
        "workspace_path": str(root.resolve()),
    }
    fence.update(overrides)
    return (json.dumps(fence, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


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
    fence_bytes = _fence_bytes(root, head)
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
        fence_sha256=hashlib.sha256(fence_bytes).hexdigest(),
        fence_id=FENCE_ID,
        fence_version=FENCE_VERSION,
        fence_bytes=fence_bytes,
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
    assert manifest["fence"] == {
        "fence_id": FENCE_ID,
        "fence_version": FENCE_VERSION,
        "sha256": request.fence_sha256,
    }
    assert "fence_v97_sha256" not in manifest
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


def test_stale_v97_fence_is_rejected_when_v98_digest_is_pinned(tmp_path):
    request, root, target = _fixture(tmp_path)
    stale_bytes = _fence_bytes(
        root,
        request.expected_head,
        fence_id="cg-g4-o1b-dormant-state-fence-20261020-v97",
        fence_version=97,
    )
    stale = replace(
        request,
        fence_id="cg-g4-o1b-dormant-state-fence-20261020-v97",
        fence_version=97,
        fence_bytes=stale_bytes,
    )
    with pytest.raises(CleanAdoptionError, match="SHA"):
        prepare_clean_target_adoption(stale)


def test_forged_v98_bytes_are_rejected_against_pinned_digest(tmp_path):
    request, root, target = _fixture(tmp_path)
    forged_bytes = _fence_bytes(root, request.expected_head, authority="caller-forged")
    forged = replace(request, fence_bytes=forged_bytes)
    with pytest.raises(CleanAdoptionError, match="SHA"):
        prepare_clean_target_adoption(forged)


def test_self_consistent_caller_fence_remains_untrusted(tmp_path):
    request, root, target = _fixture(tmp_path)
    caller_fence = _fence_bytes(root, request.expected_head, authority="caller-created")
    manifest = prepare_clean_target_adoption(
        replace(request, fence_bytes=caller_fence, fence_sha256=hashlib.sha256(caller_fence).hexdigest())
    )
    assert manifest["outcome"] == "PARTIAL"
    assert manifest["adoption_status"] == "NOT_ADOPTED"
    assert manifest["activation_status"] == "NOT_ACTIVATED"
    assert manifest["host_identity"]["trusted_host_proven"] is False


@pytest.mark.parametrize("identity", [{"branch": "wrong-branch"}, {"head": "a" * 40}])
def test_fence_branch_and_head_must_match_current_snapshot(tmp_path, identity):
    request, root, target = _fixture(tmp_path)
    fence_identity = dict(identity)
    fence_head = fence_identity.pop("head", request.expected_head)
    altered = _fence_bytes(root, fence_head, **fence_identity)
    with pytest.raises(CleanAdoptionError, match="current root snapshot"):
        prepare_clean_target_adoption(
            replace(request, fence_bytes=altered, fence_sha256=hashlib.sha256(altered).hexdigest())
        )


@pytest.mark.parametrize("field, value", [("fence_id", "caller-claimed-v98"), ("fence_version", 99)])
def test_conflicting_caller_fence_identity_is_rejected(tmp_path, field, value):
    request, root, target = _fixture(tmp_path)
    with pytest.raises(CleanAdoptionError, match="ID or version"):
        prepare_clean_target_adoption(replace(request, **{field: value}))


def test_missing_fence_bytes_fails_closed(tmp_path):
    request, root, target = _fixture(tmp_path)
    with pytest.raises(CleanAdoptionError, match="fence bytes"):
        prepare_clean_target_adoption(replace(request, fence_bytes=b""))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw[:-1],
        lambda raw: b"\xef\xbb\xbf" + raw,
        lambda raw: raw.replace(b"{", b"{ ", 1),
        lambda raw: raw.replace(b'\"state\":\"ACTIVE\"', b'\"state\":\"ACTIVE\",\"state\":\"ACTIVE\"', 1),
    ],
    ids=["altered-newline", "bom", "pretty", "duplicate-key"],
)
def test_fence_bytes_must_be_exact_canonical_json(tmp_path, mutate):
    request, root, target = _fixture(tmp_path)
    altered = mutate(request.fence_bytes)
    with pytest.raises(CleanAdoptionError):
        prepare_clean_target_adoption(
            replace(request, fence_bytes=altered, fence_sha256=hashlib.sha256(altered).hexdigest())
        )


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
