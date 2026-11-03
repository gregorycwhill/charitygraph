import json
from hashlib import sha256
from pathlib import Path

import pytest

from charitygraph.stage_manifest import BINDING_FOR_STAGE, STAGES, StageManifestError, make_manifest, verify_chain, verify_manifest


def _hash(value): return sha256(value.encode()).hexdigest()


def _chain(tmp_path):
    bindings = {"cohort_sha256": _hash("exact-frozen-cohort")}
    predecessor = None; manifests = []
    for stage in STAGES:
        key = BINDING_FOR_STAGE[stage]
        payload = f"immutable {stage} artifact"
        artifact = tmp_path / f"{stage}.json"; artifact.write_text(payload, encoding="utf-8")
        bindings[key] = _hash(payload)
        manifest = make_manifest(stage=stage, artifact_path=artifact.name, artifact_sha256=bindings[key], bindings=bindings, predecessor=predecessor)
        verify_manifest(manifest, base_dir=tmp_path, predecessor=predecessor)
        manifests.append(manifest); predecessor = manifest
    return manifests


def test_valid_stage_chain_replays_deterministically(tmp_path):
    one = _chain(tmp_path); two = _chain(tmp_path)
    assert [x["manifest_sha256"] for x in one] == [x["manifest_sha256"] for x in two]
    assert one[-1]["predecessor_manifest_sha256"] == one[-2]["manifest_sha256"]


def test_mismatched_cohort_or_inherited_binding_fails_before_successor(tmp_path):
    manifests = _chain(tmp_path)
    bad = json.loads(json.dumps(manifests[2])); bad["bindings"]["cohort_sha256"] = _hash("other cohort")
    bad["manifest_sha256"] = make_manifest(stage=bad["stage"], artifact_path=bad["artifact"]["path"], artifact_sha256=bad["artifact"]["sha256"], bindings=bad["bindings"], predecessor=manifests[1])["manifest_sha256"]
    with pytest.raises(StageManifestError, match="inherited binding"):
        verify_manifest(bad, base_dir=tmp_path, predecessor=manifests[1])


def test_stale_artifact_fails_before_provider_execution(tmp_path):
    manifests = _chain(tmp_path)
    (tmp_path / "extraction_request_set.json").write_text("changed", encoding="utf-8")
    with pytest.raises(StageManifestError, match="stale"):
        verify_manifest(manifests[3], base_dir=tmp_path, predecessor=manifests[2])


def test_chain_requires_all_predecessors_and_their_own_artifact_locations(tmp_path):
    manifests = _chain(tmp_path)
    paths = []
    for item in manifests[:4]:
        path = tmp_path / (item["stage"] + ".manifest.json")
        path.write_text(json.dumps(item), encoding="utf-8")
        paths.append(path)
    assert verify_chain(paths)[-1]["stage"] == "extraction_request_set"
    with pytest.raises(StageManifestError, match="complete ordered"):
        verify_chain(paths[:-1])


def test_checked_in_schema_example_has_a_valid_self_identity():
    example = Path(__file__).parents[2] / "schemas" / "examples" / "builder-stage-manifest-v1.cohort.example.json"
    verify_manifest(json.loads(example.read_text(encoding="utf-8")))
