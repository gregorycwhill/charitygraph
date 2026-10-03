"""Validate immutable Attempt-20 history and current Attempt-21 bindings without writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from charitygraph.s0_authorisation import load_authorisation_package
from charitygraph.s0_lineage import validate_lineage
from charitygraph.s0_structured_authority import (
    FrozenLocatorQueries, GovernedLocatorBinding, compile_locator_authority,
    structured_authority_from_material, validate_mandate_binding, canonical_sha256,
)


def validate(root: Path) -> dict:
    index = validate_lineage(root)
    current = load_authorisation_package(root)[0]
    historical = load_authorisation_package(root, historical=True)[0]
    assert historical.identity_hash == index["historical_runtime_mandate"]["sha256"]
    assert current.mandate_id == "scale-s0-authorised-balanced-v3"
    assert load_authorisation_package(root, authority="shadow")[0].mandate_id == "scale-s0-shadow-balanced-v3"
    historical_raw = json.loads((root / "SCALE_S0_ATTEMPT20_STRUCTURED_AUTHORITY_2026-09-26.json").read_text())
    historical_frozen = json.loads((root / "SCALE_S0_ATTEMPT20_FROZEN_MATERIAL_2026-09-26.json").read_text())
    historical_authority = structured_authority_from_material(historical_raw, historical=True)
    assert historical_frozen["structured_authority_hash"] == canonical_sha256(historical_authority.material())
    raw = json.loads((root / "SCALE_S0_ATTEMPT21_STRUCTURED_AUTHORITY_2026-10-03.json").read_text())
    frozen = json.loads((root / "SCALE_S0_ATTEMPT21_FROZEN_MATERIAL_2026-10-03.json").read_text())
    authority = structured_authority_from_material(raw)
    assert authority.attempt_id == "attempt:s0:21"
    validate_mandate_binding(authority, mandate_id=current.mandate_id, mandate_hash=current.identity_hash)
    assert authority.population_policy_hash == current.policy_hashes["population"]
    bundle = json.loads((root / index["packages"]["current"]["bundle"]).read_text())
    assert authority.aggregate_policy_bundle_hash == bundle["aggregate_bundle_hash"]
    assert frozen["structured_authority_hash"] == authority.hash
    assert frozen["data_lineage_anchor"] == raw["data_merge_sha"] == index["data_lineage_anchor"]
    for key in ("mandate_id", "mandate_hash", "aggregate_policy_bundle_hash", "population_policy_hash", "builder_commit_sha"):
        assert frozen[key] == raw[key]
    subjects = tuple(FrozenLocatorQueries(GovernedLocatorBinding(**s["binding"]), tuple(q["query"] for q in s["query_candidates"])) for s in frozen["subjects"])
    compiled = compile_locator_authority(authority, subjects)
    assert [x.executable_body_sha256 for x in compiled.slots] == [s["query_candidates"][0]["body_sha256"] for s in frozen["subjects"]]
    for subject in frozen["subjects"]:
        for query in subject["query_candidates"]:
            assert hashlib.sha256(query["canonical_body"].encode()).hexdigest() == query["body_sha256"]
    assert raw["conservative_aggregate_exposure_usd"] == "0.40"
    assert raw["attempt_17_unresolved_held_exposure_usd"] == "0.10"
    return {"historical_mandate_hash": historical.identity_hash, "current_mandate_hash": current.identity_hash,
            "population_policy_hash": authority.population_policy_hash,
            "bundle_hash": authority.aggregate_policy_bundle_hash, "structured_authority_hash": authority.hash,
            "frozen_query_hash": authority.frozen_material_sha256, "artifacts": len(index["artifacts"])}


def verify_history(root: Path) -> None:
    base = "0935d7e470b3702323107ab0c8d56b3d977d881f"
    files = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "--name-only", base], text=True).splitlines()
    preserved = [p for p in files if any(f"ATTEMPT{number}_" in p for number in (8, 17, 18, 19))]
    for path in preserved:
        before = subprocess.check_output(["git", "-C", str(root), "show", f"{base}:{path}"])
        assert (root / path).read_bytes().replace(b"\r\n", b"\n") == before, path
    historical = "0f73f399b0d5feeff75b0716fc31da07866b6d14"
    for path in ("policies/scale-s0/population-v1.yaml", "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml", "SCALE_S0_SHADOW_MANDATE_V2.yaml", "SCALE_S0_MANDATE_AUTHORISED_V2.yaml"):
        assert (root / path).read_bytes().replace(b"\r\n", b"\n") == subprocess.check_output(["git", "-C", str(root), "show", f"{historical}:{path}"]), path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_root", type=Path)
    parser.add_argument("--verify-git-history", action="store_true")
    args = parser.parse_args()
    result = validate(args.data_root)
    if args.verify_git_history:
        verify_history(args.data_root)
        result["historical_evidence_unchanged"] = True
    print(json.dumps(result, indent=2))
