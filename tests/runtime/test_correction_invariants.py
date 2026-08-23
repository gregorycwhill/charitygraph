from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from charitygraph.runtime import CatalogError, ConflictError, InvalidTransitionError, LeaseError, SQLiteCatalog
from .test_budget_ledger import BASE_COHORT, BASE_RUN, COHORT_ID, NOW, RES_A, RES_B, entry, opened, reservation
from .test_task_state import TASK, opened as task_opened


def test_generic_transition_cannot_bypass_attempt_lifecycle(tmp_path):
    catalog = task_opened(tmp_path)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=NOW + timedelta(minutes=1), now=NOW)
    with pytest.raises(InvalidTransitionError):
        catalog.transition_task(TASK["record_id"], "running", owner="worker", now=NOW)
    assert catalog.get_task(TASK["record_id"])["status"] == "leased"


def test_expired_lease_cannot_transition_and_attempt_update_is_atomic(tmp_path):
    catalog = task_opened(tmp_path)
    expiry = NOW + timedelta(seconds=1)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=expiry, now=NOW)
    with pytest.raises(LeaseError):
        catalog.transition_task(TASK["record_id"], "held", owner="worker", now=NOW + timedelta(seconds=2))
    attempt = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", now=NOW)
    with pytest.raises(LeaseError):
        catalog.finish_successful_attempt(attempt["task_run_id"], owner="other", completed_at=NOW, result_artifact_id="artifact:1")
    assert catalog.get_task(TASK["record_id"])["status"] == "running"


def test_retryable_task_respects_next_eligible_at(tmp_path):
    catalog = task_opened(tmp_path)
    expiry = NOW + timedelta(minutes=1)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=expiry, now=NOW)
    attempt = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", now=NOW)
    eligible = NOW + timedelta(hours=1)
    catalog.finish_failed_attempt(attempt["task_run_id"], owner="worker", completed_at=NOW, retryable=True, error_class="retry", error_message_redacted="retry", next_eligible_at=eligible)
    assert not catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=eligible + timedelta(minutes=1), now=eligible - timedelta(seconds=1))
    assert catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=eligible + timedelta(minutes=1), now=eligible)


def test_cost_entry_reservation_scope_is_exact(tmp_path):
    catalog = opened(tmp_path)
    catalog.reserve_cost(reservation(RES_A, 50), now=NOW)
    other_cohort = {**BASE_COHORT, "record_id": "cohort:12121212121212121212121212121212", "budget_cap": {"amount": "100", "currency": "AUD"}}
    other_run = {**BASE_RUN, "record_id": "run:13131313131313131313131313131313", "cohort_id": other_cohort["record_id"]}
    catalog.register_cohort(other_cohort)
    catalog.register_run(other_run)
    with pytest.raises(ConflictError, match="cohort_id"):
        catalog.record_cost_entry({**entry("cross-cohort", "actual", 1, RES_A), "cohort_id": other_cohort["record_id"]}, entry_key="cross-cohort")
    with pytest.raises(ConflictError, match="cohort_id"):
        catalog.record_cost_entry({**entry("cross-run", "actual", 1, RES_A), "run_id": other_run["record_id"]}, entry_key="cross-run")


def test_reservation_lifecycle_and_expiry_remove_exposure(tmp_path):
    catalog = opened(tmp_path, cap="500")
    catalog.reserve_cost(reservation(RES_A, 100), now=NOW)
    catalog.record_cost_entry(entry("partial", "actual", 30, RES_A), entry_key="partial")
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("SELECT status FROM budget_reservations WHERE reservation_id=?", (RES_A,)).fetchone()[0] == "partially_consumed"
    catalog.release_reservation(RES_A, 70, now=NOW, entry_key="release-lifecycle")
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("SELECT status FROM budget_reservations WHERE reservation_id=?", (RES_A,)).fetchone()[0] == "released"
    catalog.reserve_cost(reservation(RES_B, 100), now=NOW)
    catalog.record_cost_entry(entry("consumed", "actual", 100, RES_B), entry_key="consumed")
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("SELECT status FROM budget_reservations WHERE reservation_id=?", (RES_B,)).fetchone()[0] == "consumed"
    expired = "reservation:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    catalog.reserve_cost({**reservation(expired, 100), "expires_at": NOW + timedelta(seconds=1)}, now=NOW)
    assert catalog.expire_reservations(now=NOW + timedelta(seconds=2)) == 1
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("SELECT status FROM budget_reservations WHERE reservation_id=?", (expired,)).fetchone()[0] == "expired"
    assert catalog.budget_position(COHORT_ID).outstanding_reserved_exposure_aud == 0


def test_release_key_is_stable_across_clock_retries(tmp_path):
    catalog = opened(tmp_path)
    catalog.reserve_cost(reservation(RES_A, 20), now=NOW)
    first = catalog.release_reservation(RES_A, 20, now=NOW, entry_key="release-stable")
    second = catalog.release_reservation(RES_A, 20, now=NOW + timedelta(days=1), entry_key="release-stable")
    assert first["entry_hash"] == second["entry_hash"]
    with pytest.raises(ConflictError):
        catalog.release_reservation(RES_A, 19, now=NOW + timedelta(days=1), entry_key="release-stable")


def test_cache_history_survives_explicit_replacement(tmp_path):
    catalog = __import__("tests.runtime.test_cache_and_artifacts", fromlist=["catalog"]).catalog(tmp_path)
    catalog.put_cache(cache_key="history", model_task_id="modeltask:1", result_artifact_id="artifact:1", result_content_hash="a" * 64, created_at=NOW)
    catalog.invalidate_cache("history", invalidated_at=NOW + timedelta(seconds=1), reason="superseded")
    catalog.put_cache(cache_key="history", model_task_id="modeltask:1", result_artifact_id="artifact:2", result_content_hash="b" * 64, created_at=NOW + timedelta(seconds=2), replace_invalidated=True)
    events = catalog.cache_events("history")
    assert [event["event_type"] for event in events] == ["created", "invalidated", "replaced"]
    assert events[1]["reason"] == "superseded"


def test_artifact_reuse_compares_all_material_metadata(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    kwargs = dict(artifact_id="artifact:1", content_hash="a" * 64, schema_id="urn:test", schema_version="1", storage_path="path/a", availability="available", created_at=NOW, indexed_at=NOW)
    catalog.index_artifact(**kwargs)
    for field, value in (("schema_version", "2"), ("storage_path", "path/b"), ("availability", "missing"), ("created_at", NOW + timedelta(seconds=1))):
        with pytest.raises(ConflictError):
            catalog.index_artifact(**{**kwargs, field: value})


@pytest.mark.parametrize("bad", [
    {"entry_type": "adjustment", "adjustment_direction": None},
    {"entry_type": "actual", "adjustment_direction": "credit"},
    {"entry_type": "not-valid", "adjustment_direction": None},
    {"entry_type": "actual", "aud_cost": {"amount": 1.5, "currency": "AUD"}},
    {"entry_type": "actual", "aud_cost": {"amount": "-1", "currency": "AUD"}},
])
def test_cost_persistence_reuses_contract_validation(tmp_path, bad):
    catalog = opened(tmp_path)
    value = entry("invalid", bad.get("entry_type", "actual"), 1, "reservation:99999999999999999999999999999999")
    value.update(bad)
    with pytest.raises(CatalogError):
        catalog.record_cost_entry(value, entry_key="invalid-" + str(abs(hash(str(bad)))))


def test_memory_catalogue_is_explicitly_rejected(tmp_path):
    with pytest.raises(CatalogError, match="file-backed"):
        SQLiteCatalog(":memory:")


def test_foreign_keys_and_integrity_check(tmp_path):
    catalog = opened(tmp_path)
    assert catalog.integrity_check() == "ok"
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_stale_attempt_completion_is_rejected_without_mutation(tmp_path):
    catalog = task_opened(tmp_path)
    first_expiry = NOW + timedelta(minutes=5)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=first_expiry, now=NOW)
    first = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:12121212121212121212121212121212", now=NOW)
    catalog.finish_failed_attempt(first["task_run_id"], owner="worker", completed_at=NOW + timedelta(seconds=1), retryable=True, error_class="retry", error_message_redacted="retry")
    second_now = NOW + timedelta(seconds=2)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=second_now + timedelta(minutes=5), now=second_now)
    second = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:13131313131313131313131313131313", now=second_now)
    with pytest.raises(InvalidTransitionError):
        catalog.finish_successful_attempt(first["task_run_id"], owner="worker", completed_at=NOW + timedelta(seconds=3), result_artifact_id="artifact:stale")
    assert catalog.get_task(TASK["record_id"])["status"] == "running"
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        rows = conn.execute("SELECT task_run_id, status FROM task_attempts WHERE model_task_id=? ORDER BY attempt_number", (TASK["record_id"],)).fetchall()
    assert rows == [(first["task_run_id"], "failed_retryable"), (second["task_run_id"], "running")]


def test_relational_cohort_run_and_task_scope_is_enforced(tmp_path):
    catalog = opened(tmp_path)
    other_cohort = {**BASE_COHORT, "record_id": "cohort:14141414141414141414141414141414"}
    other_run = {**BASE_RUN, "record_id": "run:15151515151515151515151515151515", "cohort_id": other_cohort["record_id"]}
    catalog.register_cohort(other_cohort)
    catalog.register_run(other_run)
    with pytest.raises(ConflictError):
        catalog.reserve_cost({**reservation("reservation:16161616161616161616161616161616", 10), "run_id": other_run["record_id"]}, now=NOW)
    with pytest.raises(ConflictError):
        catalog.register_task({**TASK, "record_id": "modeltask:17171717171717171717171717171717", "cohort_id": other_cohort["record_id"]}, run_id=BASE_RUN["record_id"], now=NOW)
    other_task = {**TASK, "record_id": "modeltask:18181818181818181818181818181818", "cohort_id": other_cohort["record_id"]}
    catalog.register_task(other_task, run_id=other_run["record_id"], now=NOW)
    with pytest.raises(ConflictError):
        catalog.reserve_cost({**reservation("reservation:19191919191919191919191919191919", 10), "model_task_ids": (other_task["record_id"],)}, now=NOW)
    with pytest.raises(ConflictError):
        catalog.record_cost_entry({**entry("wrong-run", "actual", 1, "reservation:20202020202020202020202020202020"), "run_id": other_run["record_id"]}, entry_key="wrong-run")


def test_attempt_reservation_must_match_run_and_task_association(tmp_path):
    catalog = opened(tmp_path)
    task_two = {**TASK, "record_id": "modeltask:21212121212121212121212121212121", "cohort_id": COHORT_ID}
    catalog.register_task(task_two, run_id=BASE_RUN["record_id"], now=NOW)
    task_associated = {**TASK, "record_id": "modeltask:26262626262626262626262626262626", "cohort_id": COHORT_ID}
    catalog.register_task(task_associated, run_id=BASE_RUN["record_id"], now=NOW)
    associated = "reservation:22222222222222222222222222222222"
    unassociated = "reservation:23232323232323232323232323232323"
    catalog.reserve_cost({**reservation(associated, 10), "model_task_ids": (task_associated["record_id"],)}, now=NOW)
    catalog.reserve_cost({**reservation(unassociated, 10), "model_task_ids": ()}, now=NOW)
    catalog.claim_task(task_two["record_id"], owner="worker", lease_expires_at=NOW + timedelta(minutes=5), now=NOW)
    with pytest.raises(ConflictError):
        catalog.begin_task_attempt(task_two["record_id"], owner="worker", task_run_id="taskrun:24242424242424242424242424242424", now=NOW, reservation_id=associated)
    with pytest.raises(ConflictError):
        catalog.begin_task_attempt(task_two["record_id"], owner="worker", task_run_id="taskrun:25252525252525252525252525252525", now=NOW, reservation_id=unassociated)


def test_actual_after_release_is_rejected_atomically_and_position_remains_valid(tmp_path):
    catalog = opened(tmp_path, cap="200")
    catalog.reserve_cost(reservation(RES_A, 100), now=NOW)
    catalog.record_cost_entry(entry("partial-before-release", "actual", 30, RES_A), entry_key="partial-before-release")
    catalog.release_reservation(RES_A, 70, now=NOW, entry_key="release-before-actual")
    with pytest.raises(ConflictError, match="prior reservation release"):
        catalog.record_cost_entry(entry("incompatible-after-release", "actual", 1, RES_A), entry_key="incompatible-after-release")
    position = catalog.budget_position(COHORT_ID)
    assert position.actual_spend_aud == 30
    assert position.released_reserve_aud == 70
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM cost_entries WHERE entry_key=?", ("incompatible-after-release",)).fetchone()[0] == 0
