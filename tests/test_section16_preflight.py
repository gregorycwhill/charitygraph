import json
from pathlib import Path

from charitygraph.section16_preflight import (
    SUBJECT_ID,
    build_pressure_case_bundles,
    bundle_locators,
    bundle_prompt,
    plan_pressure_case,
)


RUNTIME = Path(r"C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901")
PACKET = RUNTIME / "packet.json"
STORE = RUNTIME


def test_four_bundles_are_source_partitioned_and_registration_is_empty_control():
    bundles = build_pressure_case_bundles(PACKET, STORE)
    assert [b["bundle_name"] for b in bundles] == [
        "2020_compliance_action", "2023_enforceable_undertaking", "2025_compliance_action", "current_registration_negative_control"
    ]
    assert [len(b["source_record_ids"]) for b in bundles] == [1, 2, 1, 1]
    assert bundles[-1]["negative_control"] is True
    assert "registration_status" not in bundle_prompt(bundles[-1])
    assert all(bundle_locators(bundle) for bundle in bundles)
    assert all(len(json.dumps(bundle, ensure_ascii=False)) < 240000 for bundle in bundles)


def test_bundle_hashes_and_representation_are_deterministic():
    first = build_pressure_case_bundles(PACKET, STORE)
    second = build_pressure_case_bundles(PACKET, STORE)
    assert [b["bundle_sha256"] for b in first] == [b["bundle_sha256"] for b in second]
    assert first[1]["representations"][1]["representation_type"] == "native_pdf_all_pages"
    assert len(first[1]["representations"][1]["pages"]) == 6


def test_task_preflight_has_distinct_ids_and_cost_ceiling_comparison(tmp_path):
    report = plan_pressure_case(PACKET, STORE, tmp_path)
    assert report["provider_calls"] == 0
    assert report["authorization_state"] == "not_authorized"
    assert report["aggregate_projected_max_usd"]
    assert len({item["task_id"] for item in report["bundles"]}) == 4
    for item in report["bundles"]:
        assert item["max_output_tokens"] == 24000
        assert set(item["projected_usd"]) == {"12000", "16000", "24000"}
        assert item["authorization_state"] == "not_authorized"
        assert item["task_id"].startswith("modeltask:")
        assert item["run_id"].startswith("run:")
        assert item["task_run_id"].startswith("taskrun:")
        assert item["represented_characters"] > 0
        assert item["task_id"]
    assert {item["negative_control"] for item in report["bundles"]} == {False, True}
