from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
COHORT = {"record_id": "cohort:" + "1" * 32, "cohort_code": "AUTH", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "100", "currency": "AUD"}, "created_at": NOW}
RUN = {"record_id": "run:" + "2" * 32, "cohort_id": COHORT["record_id"], "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": NOW}

def opened(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort(COHORT)
    catalog.register_run(RUN)
    return catalog

def claim(catalog, subject="subject:" + "3" * 32, material="c" * 64, owner="process-a"):
    return catalog.claim_authorized_call(authorization_scope_hash="d" * 64, subject_id=subject, task_family="semantic_interpretation", material_hash=material, owner=owner, now=NOW)

def test_separate_catalog_processes_fail_closed_while_active_and_after_completion(tmp_path):
    first = opened(tmp_path)
    second = SQLiteCatalog(tmp_path / "state.sqlite3").open()
    slot = claim(first)
    with pytest.raises(ConflictError):
        claim(second, owner="process-b")
    first.complete_authorized_call(slot["slot_key"], now=NOW)
    with pytest.raises(ConflictError):
        claim(second, owner="process-b")
    assert second.get_authorized_call(slot["slot_key"])["status"] == "completed"

def test_transport_retry_stays_with_same_claimed_slot(tmp_path):
    catalog = opened(tmp_path)
    slot = claim(catalog)
    # Existing retry machinery creates another task attempt but does not claim a new authorization slot.
    assert catalog.get_authorized_call(slot["slot_key"])["status"] == "claimed"
    catalog.complete_authorized_call(slot["slot_key"], now=NOW)
    assert catalog.get_authorized_call(slot["slot_key"])["provider_transmitted"] == 1

def test_ambiguous_abandonment_is_not_reopened_without_review(tmp_path):
    catalog = opened(tmp_path)
    slot = claim(catalog)
    catalog.abandon_authorized_call(slot["slot_key"], now=NOW, provider_transmitted=False, reason="process_lost_before_transmission")
    with pytest.raises(ConflictError):
        claim(catalog, owner="process-b")
    catalog.reset_abandoned_authorized_call(slot["slot_key"], now=NOW, review_ref="review:no-transmission")
    reclaimed = claim(catalog, owner="process-b")
    assert reclaimed["status"] == "claimed"

def test_different_material_and_subject_slots_are_independent(tmp_path):
    catalog = opened(tmp_path)
    first = claim(catalog)
    second = claim(catalog, subject="subject:" + "4" * 32)
    third = claim(catalog, material="e" * 64)
    assert len({first["slot_key"], second["slot_key"], third["slot_key"]}) == 3
