from datetime import datetime, timedelta, timezone

import pytest

from charitygraph.runtime import ConflictError, InvalidTransitionError, LeaseError, SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
COHORT = {"record_id": "cohort:11111111111111111111111111111111", "cohort_code": "SPIKE", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "100", "currency": "AUD"}, "created_at": NOW}
RUN = {"record_id": "run:22222222222222222222222222222222", "cohort_id": COHORT["record_id"], "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": NOW}
TASK = {"record_id": "modeltask:33333333333333333333333333333333", "subject_id": "subject:44444444444444444444444444444444", "cohort_id": COHORT["record_id"], "task_type": "structured_extraction", "task_schema": {"schema_id": "urn:charitygraph:builder:schema:test:1.0"}, "cache_key": "c" * 64, "provider_id": "fake", "model_snapshot": "test"}


def opened(tmp_path, *, authorization=False):
    path = tmp_path / "state.sqlite3"
    catalog = SQLiteCatalog(path, authorization_path=path if authorization else None).open(initialize=True)
    catalog.register_cohort(COHORT)
    catalog.register_run(RUN)
    catalog.register_task(TASK, run_id=RUN["record_id"], now=NOW)
    return catalog


def _register_task(catalog, task_id, *, subject_id=TASK["subject_id"], scope_id=None, run_id=RUN["record_id"]):
    catalog.register_task(
        {
            **TASK,
            "record_id": task_id,
            "subject_id": subject_id,
            "scope_id": scope_id,
        },
        run_id=run_id,
        now=NOW,
    )
    return task_id


def _physical_counts(catalog):
    with catalog._connection() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("physical_attempts", "physical_attempt_members", "provider_receipts", "cost_entries", "budget_reservations", "provider_request_attempts", "provider_pre_send_replacements")
        }


def _replacement_fixture(tmp_path, *, mixed_scope=False):
    catalog = opened(tmp_path, authorization=True)
    task_a = _register_task(catalog, "modeltask:replacement-a", scope_id="scope:one")
    task_b = _register_task(catalog, "modeltask:replacement-b", scope_id="scope:one")
    task_null = _register_task(catalog, "modeltask:replacement-null")
    old_job = "deliveryjob:replacement-old"
    new_job = "deliveryjob:replacement-new"
    old_reservation = "reservation:replacement-old"
    new_reservation = "reservation:replacement-new"
    item = "requestitem:replacement"
    old_physical = "physical:replacement-old"
    old_attempt = "deliveryattempt:replacement-old"
    new_physical = "physical:replacement-new"
    new_attempt = "deliveryattempt:replacement-new"
    for job in (old_job, new_job):
        catalog.create_delivery_job(delivery_job_id=job, run_id=RUN["record_id"], provider_id="fake", model_route="synthetic", delivery_mode="standard", pricing_snapshot_id="pricing:test", now=NOW)
    for mandate_id, manifest_hash in (("mandate:replacement-old", "d" * 64), ("mandate:replacement-new", "e" * 64)):
        catalog.register_execution_mandate(mandate_id=mandate_id, manifest_hash=manifest_hash, authorization_text_hash=manifest_hash, scope={"test": mandate_id}, contract_allowlist=(), aggregate_hard_aud="10", per_request_hard_aud="10", phase_scope="test", now=NOW)
    for reservation_id in (old_reservation, new_reservation):
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": COHORT["record_id"], "run_id": RUN["record_id"], "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": (task_a, task_b)}, now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id=old_physical, run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="standard", provider_request_id=item, model_task_ids=(task_a, task_b), reservation_id=old_reservation, now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=item, run_id=RUN["record_id"], model_task_id=task_a, provider_id="fake", model_route="synthetic", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=old_job, physical_attempt_id=old_physical, now=NOW)
    catalog.create_provider_request_attempt(delivery_attempt_id=old_attempt, provider_request_item_id=item, physical_attempt_id=old_physical, delivery_job_id=old_job, attempt_ordinal=1, authorization_id="mandate:replacement-old", attempt_class="initial", predecessor_attempt_id=None, now=NOW)
    catalog.settle_standard_failure(old_attempt, failure_class="pre_send_validation", message="synthetic local validation failure", ambiguous=False, now=NOW)
    if mixed_scope:
        with catalog._connection(immediate=True) as conn:
            conn.execute("INSERT INTO physical_attempt_members(physical_attempt_id,model_task_id) VALUES (?,?)", (old_physical, task_null))
            catalog._commit(conn)
    return catalog, {"task_a": task_a, "task_b": task_b, "old_job": old_job, "new_job": new_job, "old_reservation": old_reservation, "new_reservation": new_reservation, "item": item, "old_physical": old_physical, "old_attempt": old_attempt, "new_physical": new_physical, "new_attempt": new_attempt}


def _create_replacement(catalog, ids, *, replacement_id="presendreplacement:replacement", new_reservation=None, reason="synthetic local correction"):
    return catalog.create_zero_crossing_pre_send_replacement(replacement_id=replacement_id, provider_request_item_id=ids["item"], new_physical_attempt_id=ids["new_physical"], new_delivery_attempt_id=ids["new_attempt"], new_delivery_job_id=ids["new_job"], new_reservation_id=new_reservation or ids["new_reservation"], authorization_id="mandate:replacement-new", provider_material_sha256="a" * 64, expected_provider_material_sha256="a" * 64, reason=reason, now=NOW)


def test_prepare_physical_attempt_enforces_member_scope_before_side_effects_and_is_idempotent(tmp_path):
    catalog = opened(tmp_path)
    same_scope_a = _register_task(catalog, "modeltask:scope-a", scope_id="scope:one")
    same_scope_b = _register_task(catalog, "modeltask:scope-b", scope_id="scope:one")
    other_scope = _register_task(catalog, "modeltask:scope-c", scope_id="scope:two")
    unscoped = _register_task(catalog, "modeltask:scope-null")
    unscoped_b = _register_task(catalog, "modeltask:scope-null-b")

    first = catalog.prepare_physical_attempt(
        physical_attempt_id="physical:scope-valid",
        run_id=RUN["record_id"],
        subject_id=TASK["subject_id"],
        delivery_mode="batch",
        provider_request_id="request:scope-valid",
        model_task_ids=(same_scope_a, same_scope_b),
        reservation_id=None,
        now=NOW,
    )
    assert first["status"] == "prepared"
    assert catalog.prepare_physical_attempt(
        physical_attempt_id="physical:scope-valid",
        run_id=RUN["record_id"],
        subject_id=TASK["subject_id"],
        delivery_mode="batch",
        provider_request_id="request:scope-valid",
        model_task_ids=(same_scope_b, same_scope_a),
        reservation_id=None,
        now=NOW,
    ) == first
    null_first = catalog.prepare_physical_attempt(
        physical_attempt_id="physical:scope-null-valid",
        run_id=RUN["record_id"],
        subject_id=TASK["subject_id"],
        delivery_mode="batch",
        provider_request_id="request:scope-null-valid",
        model_task_ids=(TASK["record_id"], unscoped_b),
        reservation_id=None,
        now=NOW,
    )
    assert catalog.prepare_physical_attempt(
        physical_attempt_id="physical:scope-null-valid",
        run_id=RUN["record_id"],
        subject_id=TASK["subject_id"],
        delivery_mode="batch",
        provider_request_id="request:scope-null-valid",
        model_task_ids=(unscoped_b, TASK["record_id"]),
        reservation_id=None,
        now=NOW,
    ) == null_first

    before = _physical_counts(catalog)
    with pytest.raises(ConflictError, match="stable unique identities"):
        catalog.prepare_physical_attempt(
            physical_attempt_id="physical:duplicate-members",
            run_id=RUN["record_id"],
            subject_id=TASK["subject_id"],
            delivery_mode="batch",
            provider_request_id="request:duplicate-members",
            model_task_ids=(same_scope_a, same_scope_a),
            reservation_id=None,
            now=NOW,
        )
    assert _physical_counts(catalog) == before

    before = _physical_counts(catalog)
    with pytest.raises(ConflictError, match="share one task scope_id"):
        catalog.prepare_physical_attempt(
            physical_attempt_id="physical:scope-mixed",
            run_id=RUN["record_id"],
            subject_id=TASK["subject_id"],
            delivery_mode="batch",
            provider_request_id="request:scope-mixed",
            model_task_ids=(same_scope_a, other_scope),
            reservation_id=None,
            now=NOW,
        )
    assert _physical_counts(catalog) == before

    before = _physical_counts(catalog)
    with pytest.raises(ConflictError, match="share one task scope_id"):
        catalog.prepare_physical_attempt(
            physical_attempt_id="physical:scope-null-mixed",
            run_id=RUN["record_id"],
            subject_id=TASK["subject_id"],
            delivery_mode="batch",
            provider_request_id="request:scope-null-mixed",
            model_task_ids=(same_scope_a, unscoped),
            reservation_id=None,
            now=NOW,
        )
    assert _physical_counts(catalog) == before

    with pytest.raises(ConflictError, match="member set conflicts"):
        catalog.prepare_physical_attempt(
            physical_attempt_id="physical:scope-valid",
            run_id=RUN["record_id"],
            subject_id=TASK["subject_id"],
            delivery_mode="batch",
            provider_request_id="request:scope-valid",
            model_task_ids=(same_scope_a,),
            reservation_id=None,
            now=NOW,
        )


def test_prepare_physical_attempt_retains_subject_and_run_guards(tmp_path):
    catalog = opened(tmp_path)
    scoped = _register_task(catalog, "modeltask:guard-scoped", scope_id="scope:one")
    other_subject = _register_task(catalog, "modeltask:guard-subject", subject_id="subject:other", scope_id="scope:one")
    other_run = {
        **RUN,
        "record_id": "run:other",
        "configuration_hash": "f" * 64,
    }
    catalog.register_run(other_run)
    other_run_task = _register_task(catalog, "modeltask:guard-run", scope_id="scope:one", run_id=other_run["record_id"])

    for attempt_id, task_id in (("physical:cross-subject", other_subject), ("physical:cross-run", other_run_task)):
        before = _physical_counts(catalog)
        with pytest.raises(ConflictError, match="belong to its run and subject"):
            catalog.prepare_physical_attempt(
                physical_attempt_id=attempt_id,
                run_id=RUN["record_id"],
                subject_id=TASK["subject_id"],
                delivery_mode="batch",
                provider_request_id="request:" + attempt_id.split(":", 1)[1],
                model_task_ids=(scoped, task_id),
                reservation_id=None,
                now=NOW,
            )
        assert _physical_counts(catalog) == before


def test_prepare_physical_attempt_reentry_rejects_changed_identity_without_side_effects(tmp_path):
    catalog = opened(tmp_path)
    task_id = _register_task(catalog, "modeltask:reentry")
    arguments = {"physical_attempt_id": "physical:reentry", "run_id": RUN["record_id"], "subject_id": TASK["subject_id"], "delivery_mode": "batch", "provider_request_id": "request:reentry", "model_task_ids": (task_id,), "reservation_id": None, "provider_batch_id": "batch:reentry", "now": NOW}
    first = catalog.prepare_physical_attempt(**arguments)
    for field, value in (("delivery_mode", "standard"), ("provider_request_id", "request:other"), ("reservation_id", "reservation:other"), ("provider_batch_id", "batch:other")):
        before = _physical_counts(catalog)
        with pytest.raises(ConflictError, match=f"re-entry {field}"):
            catalog.prepare_physical_attempt(**{**arguments, field: value})
        assert _physical_counts(catalog) == before
        assert catalog.get_physical_attempt(arguments["physical_attempt_id"]) == first


def test_prepare_physical_attempt_rejects_historical_mixed_scope_without_repairing_it(tmp_path):
    catalog, ids = _replacement_fixture(tmp_path, mixed_scope=True)
    before = _physical_counts(catalog)
    with pytest.raises(ConflictError, match="historical mixed task scopes"):
        catalog.prepare_physical_attempt(physical_attempt_id=ids["old_physical"], run_id=RUN["record_id"], subject_id=TASK["subject_id"], delivery_mode="standard", provider_request_id=ids["item"], model_task_ids=(ids["task_a"], ids["task_b"]), reservation_id=ids["old_reservation"], now=NOW)
    assert _physical_counts(catalog) == before


def test_same_scope_pre_send_replacement_preserves_members_and_is_idempotent(tmp_path):
    catalog, ids = _replacement_fixture(tmp_path)
    first = _create_replacement(catalog, ids)
    with catalog._connection() as conn:
        members = [row[0] for row in conn.execute("SELECT model_task_id FROM physical_attempt_members WHERE physical_attempt_id=? ORDER BY model_task_id", (ids["new_physical"],)).fetchall()]
    assert members == sorted((ids["task_a"], ids["task_b"]))
    assert catalog.get_physical_attempt(ids["new_physical"])["run_id"] == RUN["record_id"]
    assert catalog.get_physical_attempt(ids["new_physical"])["subject_id"] == TASK["subject_id"]
    before = _physical_counts(catalog)
    assert _create_replacement(catalog, ids) == first
    assert _physical_counts(catalog) == before
    with pytest.raises(ConflictError, match="durable execution identity"):
        _create_replacement(catalog, ids, new_reservation="reservation:replacement-other")
    assert _physical_counts(catalog) == before


def test_pre_send_replacement_rejects_historical_mixed_scope_without_side_effects(tmp_path):
    catalog, ids = _replacement_fixture(tmp_path, mixed_scope=True)
    before = _physical_counts(catalog)
    with pytest.raises(ConflictError, match="historical mixed task scopes"):
        _create_replacement(catalog, ids)
    assert _physical_counts(catalog) == before
    assert catalog.get_physical_attempt(ids["new_physical"]) is None
    assert catalog.get_provider_request_attempt(ids["new_attempt"]) is None
    assert catalog.get_provider_request_item(ids["item"])["physical_attempt_id"] == ids["old_physical"]


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
