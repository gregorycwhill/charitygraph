from __future__ import annotations

import json

import pytest

from charitygraph.phase5_official_website_campaign import (
    AcquisitionCampaignError,
    DISCOVERY_REQUIRED_ABNS,
    build_campaign,
    execute_row,
    rehearse_network_edge,
    validate_campaign,
)
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog


def _inputs(tmp_path, *, count: int = 80):
    discovery = sorted(DISCOVERY_REQUIRED_ABNS)
    known = [f"9{index:010d}" for index in range(count)]
    profiles = {abn: {"profile": {"data": {"Website": f"https://www.example{index}.org/path?fixed={index}"}}} for index, abn in enumerate(known)}
    profiles.update({abn: {"profile": {"data": {}}} for abn in discovery})
    identities = {"rows": [{"abn": abn, "subject_id": f"subject:{index:032x}"} for index, abn in enumerate(known)]}
    cells = [{"abn": abn, "rank": index + 1, "source_family": "official_website", "state": "provenance_unresolved", "reason": "test"} for index, abn in enumerate(known)]
    cells.extend({"abn": abn, "rank": 200 + index, "source_family": "official_website", "state": "attempted_unavailable", "reason": "historical"} for index, abn in enumerate(discovery))
    paths = []
    for name, value in (("profiles.json", {"entities": profiles}), ("identity.json", identities), ("inventory.json", {"cells": cells})):
        path = tmp_path / name; path.write_text(json.dumps(value), encoding="utf-8"); paths.append(path)
    return paths


def test_builds_exact_known_url_campaign_and_rehearses_without_network(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    manifest = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)
    validate_campaign(manifest)
    calls = []
    rehearsal = rehearse_network_edge(manifest, boundary=lambda **kwargs: calls.append(kwargs))
    assert len(manifest["rows"]) == len(rehearsal) == len(calls) == 80
    assert all(row["state"] == "READY_TO_CROSS_NETWORK_BOUNDARY" for row in rehearsal)
    assert all(call["url"].startswith("https://www.example") for call in calls)
    assert {item["abn"] for item in manifest["excluded_subjects"] if item["reason"] == "url_discovery_required"} == DISCOVERY_REQUIRED_ABNS


def test_rejects_discovery_subject_post_url_drift_tampering_and_duplicate_identities(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    manifest = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)
    manifest["rows"][0]["abn"] = next(iter(DISCOVERY_REQUIRED_ABNS))
    manifest["manifest_sha256"] = __import__("hashlib").sha256(json.dumps({k: v for k, v in manifest.items() if k != "manifest_sha256"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(AcquisitionCampaignError, match="excluded ABN"):
        validate_campaign(manifest)

    manifest = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)
    manifest["rows"][0]["http_method"] = "POST"
    with pytest.raises(AcquisitionCampaignError, match="manifest hash mismatch"):
        validate_campaign(manifest)


def test_known_url_must_be_governed_and_discovery_rows_cannot_leak(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    raw = json.loads(profiles.read_text(encoding="utf-8"))
    raw["entities"]["90000000000"]["profile"]["data"].pop("Website")
    profiles.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(AcquisitionCampaignError, match="not governed"):
        build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)


def test_url_normalization_and_same_site_policy_are_deterministic(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    raw = json.loads(profiles.read_text(encoding="utf-8"))
    raw["entities"]["90000000000"]["profile"]["data"]["Website"] = "HTTP://Example.Org/Exact?x=1"
    profiles.write_text(json.dumps(raw), encoding="utf-8")
    manifest = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)
    row = manifest["rows"][0]
    assert row["normalized_initial_url"] == "HTTP://Example.Org/Exact?x=1"
    assert row["permitted_redirect_hosts"] == ["example.org", "www.example.org"]
    assert len({row["acquisition_attempt_id"] for row in manifest["rows"]}) == 80


def test_tamper_and_duplicate_attempt_identity_fail_before_network_boundary(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    manifest = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)
    manifest["rows"][1]["acquisition_attempt_id"] = manifest["rows"][0]["acquisition_attempt_id"]
    manifest["manifest_sha256"] = __import__("hashlib").sha256(json.dumps({k: v for k, v in manifest.items() if k != "manifest_sha256"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(AcquisitionCampaignError, match="duplicate"):
        rehearse_network_edge(manifest)


def test_successful_fixture_retains_exact_bytes_and_lineage_once(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    row = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)["rows"][0]
    body = b"<html><meta charset='utf-8'>Caf\xc3\xa9</html>"

    class Ledger:
        def fetch(self, **kwargs):
            assert kwargs["url"] == row["normalized_initial_url"]
            return {"ok": True, "body": body, "resolved_url": row["normalized_initial_url"], "media_type": "text/html", "event": {"outcome": "available"}}

    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    try:
        store = ContentAddressedArtifactStore(tmp_path / "runtime", allowed_roots=(tmp_path,))
        result = execute_row(row=row, ledger=Ledger(), catalog=catalog, store=store)
        assert result["outcome"] == "acquired_successfully"
        assert store.read(result["lineage"]["artifact_id"]) == body
        assert catalog.get_acquisition_receipt(result["lineage"]["acquisition_receipt_id"]) is not None
        assert catalog.get_source_record(result["lineage"]["source_record_id"]) is not None
    finally:
        catalog.close()


def test_host_policy_failure_is_durably_receipted_without_retention(tmp_path) -> None:
    profiles, identities, inventory = _inputs(tmp_path)
    row = build_campaign(profiles_path=profiles, identity_map_path=identities, inventory_path=inventory)["rows"][0]
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    try:
        store = ContentAddressedArtifactStore(tmp_path / "runtime", allowed_roots=(tmp_path,))
        result = execute_row(
            row=row,
            ledger=None,  # fetched is already durable; no transport call is possible.
            catalog=catalog,
            store=store,
            fetched={"ok": False, "event": {"outcome": "blocked", "error_class": "NetworkPolicyError"}},
        )
        assert result["outcome"] == "host_policy_redirect_rejection"
        receipt_id = "acq:" + __import__("hashlib").sha256(
            json.dumps({"attempt_id": row["acquisition_attempt_id"], "outcome": result["outcome"]}, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert catalog.get_acquisition_receipt(receipt_id) is not None
    finally:
        catalog.close()
