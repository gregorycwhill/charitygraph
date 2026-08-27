from datetime import datetime, timedelta, timezone
import sqlite3
from decimal import Decimal

import pytest

from charitygraph.runtime import CatalogError, ConflictError, InvalidTransitionError, SQLiteCatalog
from charitygraph.runtime.migrations import MIGRATIONS
from .test_budget_ledger import BASE_COHORT, BASE_RUN, COHORT_ID, NOW, RES_A, reservation


def claim_catalog(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort(BASE_COHORT)
    catalog.register_run(BASE_RUN)
    return catalog


def claim(catalog, *, subject="subject:" + "1" * 32, material="a" * 64, owner="worker", lease=None):
    return catalog.claim_authorized_call(
        authorization_scope_hash="scope:" + "b" * 32,
        subject_id=subject,
        task_family="semantic_interpretation",
        material_hash=material,
        owner=owner,
        now=NOW,
        lease_expires_at=lease,
    )


def test_first_claim_and_second_connection_fail_closed(tmp_path):
    first = claim_catalog(tmp_path)
    second = SQLiteCatalog(tmp_path / "state.sqlite3").open()
    slot = claim(first)
    assert slot["status"] == "claimed"
    with pytest.raises(ConflictError):
        claim(second, owner="other")


def test_completed_slot_is_permanently_consumed(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog)
    completed = catalog.complete_authorized_call(slot["slot_key"], now=NOW, result_ref="provider:response")
    assert completed["status"] == "completed" and completed["provider_transmitted"] == 1
    with pytest.raises(ConflictError):
        claim(catalog)


def test_terminal_response_failure_consumes_slot(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog)
    failed = catalog.complete_authorized_call(slot["slot_key"], now=NOW, terminal_failure=True, result_ref="provider:invalid")
    assert failed["status"] == "failed_terminal"
    with pytest.raises(ConflictError):
        claim(catalog)


def test_abandoned_slot_remains_blocked(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog)
    catalog.abandon_authorized_call(slot["slot_key"], now=NOW, provider_transmitted=False, reason="worker_exit")
    with pytest.raises(ConflictError):
        claim(catalog)


def test_expired_lease_does_not_reopen_slot(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog, lease=NOW - timedelta(seconds=1))
    assert slot["lease_expires_at"] < NOW.isoformat()
    with pytest.raises(ConflictError):
        claim(catalog, owner="other")


def test_ambiguous_transmitted_abandonment_cannot_reset(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog)
    catalog.abandon_authorized_call(slot["slot_key"], now=NOW, provider_transmitted=True, reason="timeout_after_send")
    with pytest.raises(ConflictError):
        catalog.reset_abandoned_authorized_call(slot["slot_key"], now=NOW, review_ref="review:1")


def test_pretransmission_reset_requires_review_and_allows_one_reclaim(tmp_path):
    catalog = claim_catalog(tmp_path)
    slot = claim(catalog)
    catalog.abandon_authorized_call(slot["slot_key"], now=NOW, provider_transmitted=False)
    with pytest.raises(CatalogError):
        catalog.reset_abandoned_authorized_call(slot["slot_key"], now=NOW, review_ref=" ")
    catalog.reset_abandoned_authorized_call(slot["slot_key"], now=NOW, review_ref="review:confirmed-no-send")
    reclaimed = claim(catalog, owner="reviewed-worker")
    assert reclaimed["status"] == "claimed"
    catalog.complete_authorized_call(reclaimed["slot_key"], now=NOW)
    with pytest.raises(ConflictError):
        claim(catalog, owner="third-worker")


def test_distinct_subject_and_material_identities_are_independent(tmp_path):
    catalog = claim_catalog(tmp_path)
    one = claim(catalog)
    two = claim(catalog, subject="subject:" + "2" * 32)
    three = claim(catalog, material="c" * 64)
    assert len({one["slot_key"], two["slot_key"], three["slot_key"]}) == 3


def test_attempt_retains_provider_metadata_after_downstream_failure(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_cohort(BASE_COHORT)
    catalog.register_run(BASE_RUN)
    task = {"record_id": "modeltask:" + "3" * 32, "subject_id": "subject:" + "4" * 32, "cohort_id": COHORT_ID, "task_type": "structured_extraction", "task_schema": {"schema_id": "urn:charitygraph:test:1"}, "cache_key": "c" * 64, "provider_id": "fake", "model_snapshot": "test"}
    catalog.register_task(task, run_id=BASE_RUN["record_id"], now=NOW)
    catalog.claim_task(task["record_id"], owner="worker", lease_expires_at=NOW + timedelta(minutes=5), now=NOW)
    attempt = catalog.begin_task_attempt(task["record_id"], owner="worker", task_run_id="taskrun:" + "5" * 32, now=NOW)
    catalog.finish_failed_attempt(attempt["task_run_id"], owner="worker", completed_at=NOW, retryable=False, error_class="output_validation", error_message_redacted="invalid", result_artifact_id="artifact:response", provider_request_id="resp:1", usage={"input_tokens": 10, "output_tokens": 4}, pricing_snapshot_id="pricing:" + "4" * 32, fx_snapshot_id="fx:" + "5" * 32)
    with sqlite3.connect(tmp_path / "state.sqlite3") as conn:
        row = conn.execute("SELECT status, provider_request_id, usage_json, pricing_snapshot_id, fx_snapshot_id, result_artifact_id FROM task_attempts WHERE task_run_id=?", (attempt["task_run_id"],)).fetchone()
    assert row[0] == "failed_terminal" and row[1] == "resp:1" and '"input_tokens":10' in row[2]
    assert row[3:] == ("pricing:" + "4" * 32, "fx:" + "5" * 32, "artifact:response")


def test_run_and_reservation_read_models_are_queryable(tmp_path):
    catalog = claim_catalog(tmp_path)
    assert catalog.get_cohort(COHORT_ID)["cohort_id"] == COHORT_ID
    assert catalog.get_run(BASE_RUN["record_id"])["run_id"] == BASE_RUN["record_id"]
    assert catalog.transition_run(BASE_RUN["record_id"], "running", now=NOW)["status"] == "running"
    catalog.transition_run(BASE_RUN["record_id"], "failed", now=NOW)
    catalog.reserve_cost(reservation(RES_A, 10), now=NOW)
    position = catalog.reservation_position(RES_A)
    assert position == {"reserved": Decimal("10"), "actual": Decimal("0.000000"), "released": Decimal("0.000000"), "outstanding": Decimal("10.000000")}
    assert catalog.get_reservation(RES_A)["reservation_id"] == RES_A


def test_fresh_and_v4_databases_reach_execution_safety_v5(tmp_path):
    fresh = SQLiteCatalog(tmp_path / "fresh.sqlite3").open(initialize=True)
    assert fresh.migrate() == 5
    with sqlite3.connect(tmp_path / "fresh.sqlite3") as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(authorized_call_slots)")}
        assert {"slot_key", "authorization_scope_hash", "subject_id", "task_family", "material_hash", "status", "provider_transmitted", "review_ref", "result_ref"} <= columns
        assert "publication_eligibility" not in {row[1] for row in conn.execute("PRAGMA table_info(taxonomy_assignments)")}
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    legacy = tmp_path / "v4.sqlite3"
    with sqlite3.connect(legacy) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)")
        for migration in MIGRATIONS[:4]:
            conn.executescript(migration.sql)
            conn.execute("INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)", (migration.version, migration.name, migration.checksum, NOW.isoformat()))
        conn.commit()
    upgraded = SQLiteCatalog(legacy).open()
    assert upgraded.migrate() == 5
    with sqlite3.connect(legacy) as conn:
        assert conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()[0] == 5
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
