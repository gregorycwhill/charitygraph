"""Regression coverage for immutable S0 package history and current selection."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog
from charitygraph.s0_authorisation import load_authorisation_package
from charitygraph.s0_lineage import artifact_hash, validate_lineage
from charitygraph.s0_structured_authority import canonical_sha256, structured_authority_from_material, validate_mandate_binding
from charitygraph.scale_s0 import ScalePreflightError, ScaleS0Preflight
from charitygraph.scale_s0 import ExecutionAttemptIdentity
from charitygraph.runtime.catalog import CatalogError
from charitygraph.s0_live_preparation import checkpoint_structured_locator_preprovider
from charitygraph.s0_structured_authority import FrozenLocatorQueries, GovernedLocatorBinding

ROOT = Path(os.environ.get("CHARITYGRAPH_S0_DATA_PACKAGE", Path(__file__).resolve().parents[2] / ".s0-policy-data"))


def package(tmp_path):
    for path in ROOT.glob("SCALE_S0_*"):
        if path.is_file(): shutil.copy2(path, tmp_path / path.name)
    shutil.copytree(ROOT / "policies", tmp_path / "policies")
    return tmp_path


def test_historical_and_current_mandates_coexist_idempotently(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    old = load_authorisation_package(ROOT, historical=True)
    current = load_authorisation_package(ROOT)
    assert old[0].identity_hash == "6050d7dd652385dbe1f84136110d06e3d1f396b63bf4ef4de9c55e83b0fd6e33"
    assert old[0].policy_hashes["population"] == "45110269021C495B4970F310D093297A11413DD36F5F0B03B291AC6883F62D8D"
    assert current[0].mandate_id == "scale-s0-authorised-balanced-v3"
    assert load_authorisation_package(ROOT, authority="shadow")[0].mandate_id == "scale-s0-shadow-balanced-v3"
    for _ in range(2):
        for mandate, registry, routing, _, policies in (old, current):
            row = ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies)
            assert row["mandate_hash"] == mandate.identity_hash
    with pytest.raises(ConflictError, match="identity conflict"):
        ScaleS0Preflight.register_durable_mandate(catalog, replace(current[0], mandate_id=old[0].mandate_id), current[1], current[2], current[4])


def test_changed_policy_bytes_fail_even_when_bundle_is_rehashed(tmp_path):
    root = package(tmp_path)
    path = root / "policies/scale-s0/population-v2.yaml"
    value = json.loads(path.read_text())
    value["selection_strategy"] = "changed"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="hash drift"):
        load_authorisation_package(root)


def test_duplicate_identity_with_different_bytes_fails_closed(tmp_path):
    root = package(tmp_path)
    path = root / "policies/scale-s0/population-v2.yaml"
    value = json.loads(path.read_text())
    value.update(policy_id="scale-s0-population-balanced-v1", policy_version="1")
    path.write_text(json.dumps(value), encoding="utf-8")
    index = root / "SCALE_S0_IDENTITY_LINEAGE_V1.json"
    lineage = json.loads(index.read_text())
    entry = next(e for e in lineage["artifacts"] if e["path"] == path.relative_to(root).as_posix())
    entry.update(identity=value["policy_id"], version="1", sha256=artifact_hash(path))
    entry.pop("supersedes_path", None)
    index.write_text(json.dumps(lineage), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="duplicate stable identity"):
        validate_lineage(root)


def test_successor_requires_next_version(tmp_path):
    root = package(tmp_path)
    index = root / "SCALE_S0_IDENTITY_LINEAGE_V1.json"
    lineage = json.loads(index.read_text())
    entry = next(e for e in lineage["artifacts"] if e["path"] == "policies/scale-s0/population-v2.yaml")
    entry["version"] = "1"
    index.write_text(json.dumps(lineage), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="next version"):
        validate_lineage(root)


def test_attempt20_is_historical_only_after_authorised_successor():
    raw = json.loads((ROOT / "SCALE_S0_ATTEMPT20_STRUCTURED_AUTHORITY_2026-09-26.json").read_text())
    authority = structured_authority_from_material(raw, historical=True)
    with pytest.raises(ScalePreflightError, match="superseded"):
        authority.validate()
    mandate = load_authorisation_package(ROOT)[0]
    with pytest.raises(ScalePreflightError, match="superseded"):
        validate_mandate_binding(authority, mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash)
    with pytest.raises(ScalePreflightError, match="authorised successor"):
        replace(authority, mandate_id="scale-s0-shadow-balanced-v3").validate(historical=True)
    assert (authority.mandate_id, authority.mandate_hash) == (mandate.mandate_id, mandate.identity_hash)
    with pytest.raises(ScalePreflightError, match="complete immutable"):
        structured_authority_from_material({k:v for k,v in raw.items() if k != "mandate_hash"}, historical=True)


def test_attempt20_material_and_policy_hashes_agree():
    raw = json.loads((ROOT / "SCALE_S0_ATTEMPT20_STRUCTURED_AUTHORITY_2026-09-26.json").read_text())
    frozen = json.loads((ROOT / "SCALE_S0_ATTEMPT20_FROZEN_MATERIAL_2026-09-26.json").read_text())
    bundle = json.loads((ROOT / "SCALE_S0_POLICY_BUNDLE_BALANCED_V2.yaml").read_text())
    authority = structured_authority_from_material(raw, historical=True)
    assert canonical_sha256(authority.material()) == frozen["structured_authority_hash"]
    assert authority.aggregate_policy_bundle_hash == bundle["aggregate_bundle_hash"]
    assert authority.population_policy_hash == load_authorisation_package(ROOT)[0].policy_hashes["population"]
    assert raw["conservative_aggregate_exposure_usd"] == "0.40"
    assert raw["attempt_17_unresolved_held_exposure_usd"] == "0.10"
    assert raw["data_merge_sha"] == frozen["data_lineage_anchor"]


def test_durable_attempt21_checkpoint_checks_mandate_and_policy_hashes(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    mandate, registry, routing, _, policies = load_authorisation_package(ROOT)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies)
    authority = structured_authority_from_material(
        json.loads((ROOT / "SCALE_S0_ATTEMPT21_STRUCTURED_AUTHORITY_2026-10-03.json").read_text()),
    )
    frozen = json.loads((ROOT / "SCALE_S0_ATTEMPT21_FROZEN_MATERIAL_2026-10-03.json").read_text())
    subjects = tuple(FrozenLocatorQueries(GovernedLocatorBinding(**s["binding"]), tuple(q["query"] for q in s["query_candidates"])) for s in frozen["subjects"])
    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    attempt = ExecutionAttemptIdentity(authority.attempt_id, mandate.mandate_id, mandate.identity_hash, mandate.slice_id, authority.run_id,
        "gregorycwhill/charitygraph", authority.builder_commit_sha, "gregorycwhill/charitygraph-data", authority.data_merge_sha,
        "S0_ACQUISITION_PACKET_BRIDGE_CERTIFIED", "1", 28, authority.authority_id, "pending", "prepared", now.isoformat())
    attempt = replace(attempt, configuration_hash=attempt.canonical_configuration_hash)
    catalog.register_run({"record_id": attempt.run_id, "run_kind": "s0", "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": now})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    for field in ("mandate_hash", "population_policy_hash", "aggregate_policy_bundle_hash"):
        with pytest.raises((CatalogError, ScalePreflightError)):
            checkpoint_structured_locator_preprovider(catalog=catalog, attempt=attempt, authority=replace(authority, **{field: "0" * 64}), frozen_subjects=subjects, now=now)
    first = checkpoint_structured_locator_preprovider(catalog=catalog, attempt=attempt, authority=authority, frozen_subjects=subjects, now=now)
    second = checkpoint_structured_locator_preprovider(catalog=catalog, attempt=attempt, authority=authority, frozen_subjects=subjects, now=now)
    assert first["material_hash"] == second["material_hash"]
    with catalog._connection() as conn:
        for table in ("budget_reservations", "physical_attempts", "provider_request_attempts", "scale_s0_attestation_windows"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
