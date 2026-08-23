from datetime import datetime, timezone

import pytest

from charitygraph.runtime import BudgetExceededError, ConflictError, SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
COHORT_ID = "cohort:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
RUN_ID = "run:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
RES_A = "reservation:cccccccccccccccccccccccccccccccc"
RES_B = "reservation:dddddddddddddddddddddddddddddddd"
BASE_COHORT = {"record_id": COHORT_ID, "cohort_code": "SPIKE", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "100", "currency": "AUD"}, "created_at": NOW}
BASE_RUN = {"record_id": RUN_ID, "cohort_id": COHORT_ID, "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": NOW}


def reservation(rid, amount):
    return {"record_id": rid, "cohort_id": COHORT_ID, "run_id": RUN_ID, "reserved_aud": {"amount": str(amount), "currency": "AUD"}, "model_task_ids": (), "expires_at": None}


def entry(key, kind, amount, rid, *, direction=None):
    return {"cohort_id": COHORT_ID, "run_id": RUN_ID, "task_run_id": "taskrun:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "reservation_id": rid, "entry_type": kind, "paid_output_category": "extraction", "provider_cost": {"amount": str(amount), "currency": "USD"}, "aud_cost": {"amount": str(amount), "currency": "AUD"}, "usage": {"input_tokens": 1}, "recorded_at": NOW, "adjustment_direction": direction, "pricing_snapshot_id": "pricing:ffffffffffffffffffffffffffffffff", "fx_snapshot_id": "fx:11111111111111111111111111111111"}


def opened(tmp_path, cap="100"):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort({**BASE_COHORT, "budget_cap": {"amount": cap, "currency": "AUD"}})
    catalog.register_run(BASE_RUN)
    return catalog


def test_cap_reservation_release_actual_overrun_and_unreserved_actual(tmp_path):
    catalog = opened(tmp_path)
    catalog.reserve_cost(reservation(RES_A, 100), now=NOW)
    catalog.record_cost_entry(entry("actual-a", "actual", 110, RES_A), entry_key="actual-a")
    position = catalog.budget_position(COHORT_ID)
    assert position.reservation_overrun_aud == 10
    assert position.remaining_budget_aud == -10
    assert position.breach

    with pytest.raises(BudgetExceededError):
        catalog.reserve_cost(reservation(RES_B, 1), now=NOW)
    catalog.record_cost_entry(entry("actual-unreserved", "actual", 5, "reservation:99999999999999999999999999999999"), entry_key="actual-unreserved")
    assert catalog.budget_position(COHORT_ID).unreserved_actual_aud == 5


def test_release_is_checked_against_its_own_reservation_and_cost_entries_idempotent(tmp_path):
    catalog = opened(tmp_path, cap="200")
    catalog.reserve_cost(reservation(RES_A, 100), now=NOW)
    catalog.reserve_cost(reservation(RES_B, 100), now=NOW)
    catalog.record_cost_entry(entry("actual-a", "actual", 30, RES_A), entry_key="actual-a")
    with pytest.raises(ConflictError):
        catalog.release_reservation(RES_A, 71, now=NOW)
    release = catalog.release_reservation(RES_A, 70, now=NOW)
    assert release["entry_type"] == "reservation_release"
    assert catalog.release_reservation(RES_A, 70, now=NOW)["entry_key"] == release["entry_key"]
    assert catalog.budget_position(COHORT_ID).released_reserve_aud == 70
    duplicate = catalog.record_cost_entry(entry("credit-1", "credit", 2, RES_A), entry_key="credit-1")
    assert catalog.record_cost_entry(entry("credit-1", "credit", 2, RES_A), entry_key="credit-1")["entry_key"] == duplicate["entry_key"]
    with pytest.raises(ConflictError):
        catalog.record_cost_entry(entry("credit-1", "credit", 3, RES_A), entry_key="credit-1")


def test_credits_and_signed_adjustments_reconcile(tmp_path):
    catalog = opened(tmp_path)
    rid = "reservation:99999999999999999999999999999999"
    catalog.record_cost_entry(entry("actual", "actual", 10, rid), entry_key="actual")
    catalog.record_cost_entry(entry("credit", "credit", 20, rid), entry_key="credit")
    catalog.record_cost_entry(entry("debit", "adjustment", 5, rid, direction="debit"), entry_key="debit")
    catalog.record_cost_entry(entry("adj-credit", "adjustment", 3, rid, direction="credit"), entry_key="adj-credit")
    position = catalog.budget_position(COHORT_ID)
    assert position.net_actual_spend_aud == -8
    assert position.committed_exposure_aud == -8
