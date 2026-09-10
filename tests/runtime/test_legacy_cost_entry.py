from datetime import datetime, timezone

from charitygraph.runtime import SQLiteCatalog


def test_existing_legacy_cohort_and_run_ids_can_reconcile_cost(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort({"record_id": "cohort:legacy-campaign", "cohort_code": "LEGACY", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "10", "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": "run:legacy-campaign", "cohort_id": "cohort:legacy-campaign", "run_kind": "legacy", "status": "planned", "configuration_hash": "b" * 64, "created_at": now})
    catalog.record_cost_entry({
        "cohort_id": "cohort:legacy-campaign", "run_id": "run:legacy-campaign",
        "task_run_id": "taskrun:" + "c" * 64, "reservation_id": "reservation:" + "d" * 64,
        "entry_type": "actual", "paid_output_category": "extraction",
        "provider_cost": {"amount": "1", "currency": "USD"}, "aud_cost": {"amount": "1", "currency": "AUD"},
        "usage": {"input_tokens": 1}, "recorded_at": now,
        "pricing_snapshot_id": "pricing:" + "e" * 64, "fx_snapshot_id": "fx:" + "f" * 64,
    }, entry_key="actual:legacy")
    assert catalog.budget_position("cohort:legacy-campaign").actual_spend_aud == 1
