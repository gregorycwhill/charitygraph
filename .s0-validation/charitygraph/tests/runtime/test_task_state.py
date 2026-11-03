from datetime import datetime, timedelta, timezone

import pytest

from charitygraph.runtime import ConflictError, InvalidTransitionError, LeaseError, SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
COHORT = {"record_id": "cohort:11111111111111111111111111111111", "cohort_code": "SPIKE", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "100", "currency": "AUD"}, "created_at": NOW}
RUN = {"record_id": "run:22222222222222222222222222222222", "cohort_id": COHORT["record_id"], "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": NOW}
TASK = {"record_id": "modeltask:33333333333333333333333333333333", "subject_id": "subject:44444444444444444444444444444444", "cohort_id": COHORT["record_id"], "task_type": "structured_extraction", "task_schema": {"schema_id": "urn:charitygraph:builder:schema:test:1.0"}, "cache_key": "c" * 64, "provider_id": "fake", "model_snapshot": "test"}


def opened(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort(COHORT)
    catalog.register_run(RUN)
    catalog.register_task(TASK, run_id=RUN["record_id"], now=NOW)
    return catalog


def test_registration_is_idempotent_and_conflicts_are_rejected(tmp_path):
    catalog = opened(tmp_path)
    assert catalog.register_task(TASK, run_id=RUN["record_id"], now=NOW)["status"] == "ready"
    with pytest.raises(ConflictError):
        catalog.register_task({**TASK, "provider_id": "different"}, run_id=RUN["record_id"], now=NOW)


def test_competing_claims_only_one_succeeds(tmp_path):
    first = opened(tmp_path)
    second = SQLiteCatalog(tmp_path / "state.sqlite3").open()
    expiry = NOW + timedelta(minutes=5)
    assert first.claim_task(TASK["record_id"], owner="one", lease_expires_at=expiry, now=NOW)
    assert not second.claim_task(TASK["record_id"], owner="two", lease_expires_at=expiry, now=NOW)


def test_attempt_success_failure_retry_and_forbidden_terminal_transition(tmp_path):
    catalog = opened(tmp_path)
    expiry = NOW + timedelta(minutes=5)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=expiry, now=NOW)
    attempt = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:55555555555555555555555555555555", now=NOW)
    assert attempt["attempt_number"] == 1
    catalog.finish_failed_attempt(attempt["task_run_id"], owner="worker", completed_at=NOW + timedelta(seconds=1), retryable=True, error_class="timeout", error_message_redacted="timeout")
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=expiry + timedelta(minutes=1), now=NOW + timedelta(seconds=2))
    attempt2 = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:66666666666666666666666666666666", now=NOW + timedelta(seconds=2))
    catalog.finish_successful_attempt(attempt2["task_run_id"], owner="worker", completed_at=NOW + timedelta(seconds=3), result_artifact_id="artifact:result")
    with pytest.raises(InvalidTransitionError):
        catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:77777777777777777777777777777777", now=NOW + timedelta(seconds=4))


def test_wrong_owner_and_expired_leases_recover(tmp_path):
    catalog = opened(tmp_path)
    expiry = NOW + timedelta(seconds=1)
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=expiry, now=NOW)
    with pytest.raises(LeaseError):
        catalog.begin_task_attempt(TASK["record_id"], owner="other", task_run_id="taskrun:88888888888888888888888888888888", now=NOW)
    assert catalog.recover_expired_leases(now=NOW + timedelta(seconds=2)) == 1
    assert catalog.get_task(TASK["record_id"])["status"] == "ready"
    catalog.claim_task(TASK["record_id"], owner="worker", lease_expires_at=NOW + timedelta(minutes=1), now=NOW + timedelta(seconds=2))
    attempt = catalog.begin_task_attempt(TASK["record_id"], owner="worker", task_run_id="taskrun:99999999999999999999999999999999", now=NOW + timedelta(seconds=2))
    assert attempt["attempt_number"] == 1
    assert catalog.recover_expired_leases(now=NOW + timedelta(minutes=2)) == 1
    assert catalog.get_task(TASK["record_id"])["status"] == "failed_retryable"
