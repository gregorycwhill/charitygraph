from __future__ import annotations

from pathlib import Path

import pytest

from charitygraph.phase5_real_five_charity_factory_v2 import (
    load_real_five_charity_evidence,
    preflight_real_five_charity_references,
    replay_real_five_charity_factory_v2,
)


EVIDENCE_ROOT = Path("evidence/gate4-t3-five-subject-v1")


@pytest.fixture(scope="module")
def replay_result(tmp_path_factory: pytest.TempPathFactory) -> dict:
    work_root = tmp_path_factory.mktemp("g4-o1c-v2-external-work")
    return replay_real_five_charity_factory_v2(work_root=work_root)


def test_real_positive_replay_has_metadata_only_product_result(replay_result: dict) -> None:
    assert replay_result["schema"].endswith("/v2")
    assert replay_result["private_material_exclusion"] == {
        "metadata_only": True,
        "raw_source_bytes_in_artifact": False,
        "representation_bytes_in_artifact": False,
        "publisher_original_acnc_csv_claim": False,
    }
    assert replay_result["replay"]["stable"]["identities_and_diagnostics_stable"] is True


def test_double_run_identities_are_stable(replay_result: dict) -> None:
    replay = replay_result["replay"]
    assert replay["first"]["cohort_id"] == replay["second"]["cohort_id"]
    assert replay["first"]["run_id"] == replay["second"]["run_id"]
    assert replay["first"]["diagnostic_sha256"] == replay["second"]["diagnostic_sha256"]
    assert replay["stable"]["task_ids"]


def test_five_bound_five_missing_zero_blocked_and_twenty_coverage(replay_result: dict) -> None:
    cohort = replay_result["cohort"]
    assert (cohort["bound_count"], cohort["missing_count"], cohort["blocked_count"]) == (5, 5, 0)
    assert cohort["bound_register_ordinals"] == [1, 3, 5, 7, 9]
    assert cohort["missing_ais_ordinals"] == [2, 4, 6, 8, 10]
    assert len(replay_result["north_star_coverage"]) == 20
    assert len(replay_result["source_silence_records"]) == 5
    assert all(row["status"] == "BOUND" for row in replay_result["binding"]["statuses"] if row["ordinal"] in {1, 3, 5, 7, 9})
    assert all(row["status"] == "MISSING" for row in replay_result["binding"]["statuses"] if row["ordinal"] in {2, 4, 6, 8, 10})


def test_no_provider_sends_when_authority_is_false(replay_result: dict) -> None:
    assert replay_result["cohort"]["provider_calls"] == 0
    assert replay_result["factory"]["provider_calls"] == 0
    assert replay_result["factory"]["provider_send_tasks"] == []
    assert replay_result["factory"]["executed_tasks"] == 5
    assert replay_result["factory"]["second_run_executed_tasks"] == 0


def test_mixed_scope_reference_is_rejected() -> None:
    evidence = load_real_five_charity_evidence(evidence_root=EVIDENCE_ROOT)
    other_scope = evidence.references[1].scope_id
    bad = evidence.references[0].model_copy(update={"scope_id": other_scope})
    result = preflight_real_five_charity_references(evidence, (bad, *evidence.references[1:]))
    assert any(item.state == "mismatched" and item.reason == "scope is owned by a different subject" for item in result.diagnostics)


def test_invalid_rights_reference_is_rejected() -> None:
    evidence = load_real_five_charity_evidence(evidence_root=EVIDENCE_ROOT)
    bad = evidence.references[0].model_copy(update={"rights_decision_ids": ("rights:invalid",)})
    result = preflight_real_five_charity_references(evidence, (bad, *evidence.references[1:]))
    assert any(item.state == "rights_missing" for item in result.diagnostics)
