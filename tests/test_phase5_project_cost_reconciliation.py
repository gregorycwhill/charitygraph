from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from charitygraph.phase5_project_cost_reconciliation import (
    project_phase5_project_cost_reconciliation,
)


AS_OF = "2026-10-31T00:00:00+00:00"
START = "2026-10-30T00:00:00+00:00"


def _create_catalogue(path: Path, *, schema_version: int = 29, with_rows: bool = True) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        f"""
        CREATE TABLE schema_migrations(version INTEGER NOT NULL);
        INSERT INTO schema_migrations VALUES ({schema_version});
        CREATE TABLE runs(run_id TEXT PRIMARY KEY, status TEXT, created_at TEXT, started_at TEXT, completed_at TEXT, updated_at TEXT);
        CREATE TABLE tasks(model_task_id TEXT PRIMARY KEY, run_id TEXT, subject_id TEXT, scope_id TEXT, status TEXT, attempt_count INTEGER, created_at TEXT, updated_at TEXT);
        CREATE TABLE task_attempts(task_run_id TEXT PRIMARY KEY, model_task_id TEXT, attempt_number INTEGER, status TEXT, provider_request_id TEXT, provider_batch_id TEXT, submitted_at TEXT, started_at TEXT, completed_at TEXT, reservation_id TEXT);
        CREATE TABLE budget_reservations(reservation_id TEXT PRIMARY KEY, cohort_id TEXT, run_id TEXT, reserved_amount TEXT, reserved_aud TEXT, accounting_currency TEXT, status TEXT, reserved_at TEXT, expires_at TEXT, updated_at TEXT);
        CREATE TABLE cost_entries(entry_key TEXT PRIMARY KEY, run_id TEXT, task_run_id TEXT, reservation_id TEXT, entry_type TEXT, provider_amount TEXT, provider_currency TEXT, accounting_amount TEXT, aud_amount TEXT, adjustment_direction TEXT, accounting_currency TEXT, pricing_snapshot_id TEXT, fx_snapshot_id TEXT, recorded_at TEXT);
        CREATE TABLE physical_attempts(physical_attempt_id TEXT PRIMARY KEY, run_id TEXT, subject_id TEXT, status TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE provider_receipts(provider_receipt_id TEXT PRIMARY KEY, physical_attempt_id TEXT, provider_request_id TEXT, usage_json TEXT, received_at TEXT);
        CREATE TABLE delivery_jobs(delivery_job_id TEXT PRIMARY KEY, run_id TEXT, status TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE provider_request_items(provider_request_item_id TEXT PRIMARY KEY, run_id TEXT, model_task_id TEXT, physical_attempt_id TEXT, delivery_job_id TEXT, provider_id TEXT, model_route TEXT, status TEXT, provider_request_id TEXT, provider_receipt_id TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE provider_request_attempts(delivery_attempt_id TEXT PRIMARY KEY, provider_request_item_id TEXT, physical_attempt_id TEXT, delivery_job_id TEXT, status TEXT, attempt_ordinal INTEGER, predecessor_attempt_id TEXT, provider_request_id TEXT, provider_receipt_id TEXT, created_at TEXT, submitted_at TEXT, completed_at TEXT, updated_at TEXT);
        """
    )
    if with_rows:
        for run_id, cohort_id, task_id, subject_id, scope_id, suffix, amount in (
            ("run:one", "cohort:one", "task:one", "subject:one", "scope:one", "one", "1.10"),
            ("run:two", "cohort:two", "task:two", "subject:two", "scope:two", "two", "2.20"),
        ):
            connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (run_id, "succeeded", START, START, AS_OF, AS_OF))
            connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)", (task_id, run_id, subject_id, scope_id, "succeeded", 1, START, AS_OF))
            connection.execute("INSERT INTO task_attempts VALUES (?,?,?,?,?,?,?,?,?,?)", (f"taskrun:{suffix}", task_id, 1, "completed", f"provider-request:{suffix}", None, START, START, AS_OF, f"reservation:{suffix}"))
            connection.execute("INSERT INTO budget_reservations VALUES (?,?,?,?,?,?,?,?,?,?)", (f"reservation:{suffix}", cohort_id, run_id, "5.00", "5.00", "AUD", "active", START, None, AS_OF))
            connection.execute("INSERT INTO physical_attempts VALUES (?,?,?,?,?,?)", (f"physical:{suffix}", run_id, subject_id, "validated", START, AS_OF))
            connection.execute("INSERT INTO delivery_jobs VALUES (?,?,?,?,?)", (f"job:{suffix}", run_id, "completed", START, AS_OF))
            connection.execute("INSERT INTO provider_request_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (f"request:{suffix}", run_id, task_id, f"physical:{suffix}", f"job:{suffix}", "provider:test", "model:test", "completed", f"provider-request:{suffix}", f"receipt:{suffix}", START, AS_OF))
            connection.execute("INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"delivery:{suffix}", f"request:{suffix}", f"physical:{suffix}", f"job:{suffix}", "completed", 1, None, f"provider-request:{suffix}", f"receipt:{suffix}", START, START, AS_OF, AS_OF))
            connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", (f"receipt:{suffix}", f"physical:{suffix}", f"provider-request:{suffix}", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
            connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"cost:{suffix}", run_id, f"taskrun:{suffix}", f"reservation:{suffix}", "actual", amount, "USD", amount, amount, None, "AUD", f"pricing:{suffix}", f"fx:{suffix}", AS_OF))
    connection.commit()
    connection.close()


def _project(path: Path, run_ids=("run:one", "run:two"), **kwargs):
    return project_phase5_project_cost_reconciliation(path, run_ids=run_ids, as_of=AS_OF, reporting_window_start=START, reporting_window_end=AS_OF, source_id="source:test", **kwargs)


def test_multi_run_known_charges_keep_exact_identity_and_decimal_total(tmp_path: Path):
    path = tmp_path / "multi.sqlite3"
    _create_catalogue(path)
    projection = _project(path)
    document = projection.document
    assert document["totals"]["actual_incurred_charges"] == {"state": "known", "amount": "3.3", "currency": "AUD", "entry_count": 2, "reason": "auditable actual charges deduplicated by provider receipt identity"}
    assert document["scope"]["cohort_ids_observed"] == ["cohort:one", "cohort:two"]
    assert {row["identity"]["provider_receipt_id"] for row in document["charges"]} == {"receipt:one", "receipt:two"}
    assert {row["identity"]["subject_id"] for row in document["charges"]} == {"subject:one", "subject:two"}
    assert document["coverage"]["project_wide_completeness_proven"] is False


def test_idempotent_duplicate_receipt_is_counted_once_and_conflict_is_blocked(tmp_path: Path):
    idempotent = tmp_path / "idempotent.sqlite3"
    _create_catalogue(idempotent)
    connection = sqlite3.connect(idempotent)
    connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("cost:replay", "run:one", "taskrun:one", "reservation:one", "actual", "1.10", "USD", "1.10", "1.10", None, "AUD", "pricing:one", "fx:one", AS_OF))
    connection.commit()
    connection.close()
    document = _project(idempotent, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["amount"] == "1.1"
    assert "DUPLICATE_OR_REPLAYED_RECEIPT" in {item["code"] for item in document["blockers"]}

    conflict = tmp_path / "conflict.sqlite3"
    _create_catalogue(conflict)
    connection = sqlite3.connect(conflict)
    connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("cost:conflict", "run:one", "taskrun:one", "reservation:one", "actual", "9.99", "USD", "9.99", "9.99", None, "AUD", "pricing:one", "fx:one", AS_OF))
    connection.commit()
    connection.close()
    conflict_document = _project(conflict, run_ids=("run:one",)).document
    assert conflict_document["totals"]["actual_incurred_charges"]["amount"] is None
    codes = {item["code"] for item in conflict_document["blockers"]}
    assert "CONFLICTING_DUPLICATE_RECEIPT" in codes


def test_missing_pricing_fx_and_usage_are_not_zero(tmp_path: Path):
    path = tmp_path / "missing.sqlite3"
    _create_catalogue(path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE cost_entries SET pricing_snapshot_id=NULL, fx_snapshot_id=NULL WHERE entry_key='cost:one'")
    connection.execute("UPDATE provider_receipts SET usage_json=? WHERE provider_receipt_id='receipt:one'", ('{"input_tokens": 2}',))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["state"] == "unknown"
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
    assert {item["code"] for item in document["blockers"]} >= {"MISSING_PRICING_SNAPSHOT", "MISSING_FX_SNAPSHOT", "MISSING_OR_AMBIGUOUS_USAGE"}


def test_stale_schema_is_unknown_and_empty_data_is_not_zero(tmp_path: Path):
    stale = tmp_path / "stale.sqlite3"
    _create_catalogue(stale, schema_version=27)
    stale_document = _project(stale, run_ids=("run:one",)).document
    assert stale_document["coverage"]["state"] == "unknown"
    assert "STALE_OR_UNSUPPORTED_SCHEMA" in {item["code"] for item in stale_document["blockers"]}

    empty = tmp_path / "empty.sqlite3"
    _create_catalogue(empty, with_rows=False)
    empty_document = _project(empty, run_ids=("run:missing",)).document
    assert empty_document["totals"]["actual_incurred_charges"]["state"] == "missing"
    assert empty_document["totals"]["actual_incurred_charges"]["amount"] is None
    assert "MISSING_REQUESTED_RUN" in {item["code"] for item in empty_document["blockers"]}


def test_ambiguous_crossing_and_unknown_cost_are_unreconciled(tmp_path: Path):
    path = tmp_path / "ambiguous.sqlite3"
    _create_catalogue(path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE provider_request_items SET status='send_ambiguous' WHERE provider_request_item_id='request:one'")
    connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("cost:unknown", "run:one", None, "reservation:one", "mystery", None, None, None, None, None, None, None, None, AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["state"] == "unknown"
    assert {item["code"] for item in document["blockers"]} >= {"AMBIGUOUS_PROVIDER_CROSSING", "UNKNOWN_OR_UNRECONCILED_COST"}
    assert any(row["identity"]["provider_request_item_id"] == "request:one" for row in document["unreconciled"]["records"])


def test_authenticated_boundary_is_required_for_completeness(tmp_path: Path):
    path = tmp_path / "boundary.sqlite3"
    _create_catalogue(path, with_rows=False)
    document = _project(path, run_ids=("run:missing",), coverage_boundary={"boundary_id": "project-ledger", "version": "v1", "as_of": AS_OF, "authenticated": True, "complete": True, "run_ids": []}).document
    assert document["coverage"]["project_wide_completeness_proven"] is False
    assert "MISSING_REQUESTED_RUN" in {item["code"] for item in document["blockers"]}
    assert document["coverage"]["project_wide_boundary"]["state"] == "authenticated_complete"


def test_canonical_hash_and_order_are_stable_without_raw_payload_leakage(tmp_path: Path):
    path = tmp_path / "stable.sqlite3"
    _create_catalogue(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    first = _project(path)
    second = _project(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert first.canonical_json == second.canonical_json
    assert first.sha256 == hashlib.sha256(first.canonical_json).hexdigest()
    encoded = first.canonical_json.decode("utf-8")
    assert "raw_result" not in encoded
    assert "usage_json" not in encoded
    assert "provider response" not in encoded


def test_replayed_attempt_is_marked_but_not_silently_merged(tmp_path: Path):
    path = tmp_path / "replayed.sqlite3"
    _create_catalogue(path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE provider_request_attempts SET attempt_ordinal=2, predecessor_attempt_id='delivery:previous' WHERE delivery_attempt_id='delivery:one'")
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["charges"][0]["replayed_attempt"] is True
    assert document["charges"][0]["identity"]["delivery_attempt_id"] == "delivery:one"


def test_multiple_requests_without_source_identity_are_ambiguous_and_excluded(tmp_path: Path):
    path = tmp_path / "multiple-requests.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE task_attempts SET provider_request_id=NULL WHERE task_run_id='taskrun:one'")
    connection.execute("INSERT INTO physical_attempts VALUES (?,?,?,?,?,?)", ("physical:one-retry", "run:one", "subject:one", "validated", START, AS_OF))
    connection.execute("INSERT INTO delivery_jobs VALUES (?,?,?,?,?)", ("job:one-retry", "run:one", "completed", START, AS_OF))
    connection.execute("INSERT INTO provider_request_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("request:one-retry", "run:one", "task:one", "physical:one-retry", "job:one-retry", "provider:test", "model:test", "completed", "provider-request:one-retry", "receipt:one-retry", START, AS_OF))
    connection.execute("INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("delivery:one-retry", "request:one-retry", "physical:one-retry", "job:one-retry", "completed", 1, None, "provider-request:one-retry", "receipt:one-retry", START, START, AS_OF, AS_OF))
    connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", ("receipt:one-retry", "physical:one-retry", "provider-request:one-retry", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["state"] == "unknown"
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
    assert "AMBIGUOUS_LINKAGE" in {item["code"] for item in document["blockers"]}
    assert document["charges"] == []


def test_multiple_delivery_attempts_without_discriminator_fail_closed(tmp_path: Path):
    path = tmp_path / "multiple-attempts.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE task_attempts SET provider_request_id=NULL WHERE task_run_id='taskrun:one'")
    connection.execute("UPDATE provider_request_items SET provider_receipt_id=NULL WHERE provider_request_item_id='request:one'")
    connection.execute("UPDATE provider_request_attempts SET provider_request_id=NULL, provider_receipt_id=NULL WHERE delivery_attempt_id='delivery:one'")
    connection.execute("INSERT INTO physical_attempts VALUES (?,?,?,?,?,?)", ("physical:one-retry", "run:one", "subject:one", "validated", START, AS_OF))
    connection.execute("INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("delivery:one-retry", "request:one", "physical:one-retry", "job:one", "completed", 2, "delivery:one", "provider-request:one-retry", "receipt:one-retry", START, START, AS_OF, AS_OF))
    connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", ("receipt:one-retry", "physical:one-retry", "provider-request:one-retry", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
    assert "INCOMPLETE_ATTEMPT_HISTORY" in {item["code"] for item in document["blockers"]}
    assert document["charges"] == []


def test_contradictory_request_and_attempt_receipt_ids_are_not_selected(tmp_path: Path):
    path = tmp_path / "contradictory-receipts.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE provider_request_attempts SET provider_receipt_id='receipt:other' WHERE delivery_attempt_id='delivery:one'")
    connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", ("receipt:other", "physical:one", "provider-request:one", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
    assert "CONTRADICTORY_RUNTIME_IDENTITIES" in {item["code"] for item in document["blockers"]}
    assert document["unreconciled"]["records"][0]["identity"]["provider_request_item_id"] == "request:one"


def test_multiple_physical_receipts_without_declared_identity_are_ambiguous(tmp_path: Path):
    path = tmp_path / "multiple-physical-receipts.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE provider_request_items SET provider_receipt_id=NULL WHERE provider_request_item_id='request:one'")
    connection.execute("UPDATE provider_request_attempts SET provider_receipt_id=NULL WHERE delivery_attempt_id='delivery:one'")
    connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", ("receipt:other", "physical:one", "provider-request:one", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
    assert "AMBIGUOUS_LINKAGE" in {item["code"] for item in document["blockers"]}


def test_reservation_release_is_separate_from_actual_and_net_is_explicit(tmp_path: Path):
    path = tmp_path / "reservation-release.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("release:one", "run:one", None, "reservation:one", "reservation_release", None, None, "2.00", "2.00", None, "AUD", None, None, AS_OF))
    connection.execute("UPDATE budget_reservations SET status='partially_consumed' WHERE reservation_id='reservation:one'")
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    reservations = document["totals"]["reservations"]
    assert reservations["gross"]["amount"] == "5"
    assert reservations["reserved"]["amount"] == "5"
    assert reservations["released"]["amount"] == "2"
    assert reservations["net"]["amount"] == "3"
    assert reservations["remaining_spend"]["state"] == "unknown"
    assert document["totals"]["actual_incurred_charges"]["amount"] == "1.1"


def test_unknown_reservation_release_does_not_claim_net_or_remaining_spend(tmp_path: Path):
    path = tmp_path / "unknown-reservation-release.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("release:unknown", "run:one", None, "reservation:missing", "reservation_release", None, None, None, None, None, "AUD", None, None, AS_OF))
    connection.commit()
    connection.close()
    document = _project(path, run_ids=("run:one",)).document
    reservations = document["totals"]["reservations"]
    assert reservations["state"] == "unknown"
    assert reservations["net"]["amount"] is None
    assert reservations["remaining_spend"]["state"] == "unknown"
    assert "UNRECONCILED_RESERVATION_RELEASE" in {item["code"] for item in document["blockers"]}


def test_supported_partial_charge_is_not_presented_as_project_total(tmp_path: Path):
    path = tmp_path / "partial-actuals.sqlite3"
    _create_catalogue(path, with_rows=True)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE task_attempts SET provider_request_id=NULL WHERE task_run_id='taskrun:one'")
    connection.execute("INSERT INTO physical_attempts VALUES (?,?,?,?,?,?)", ("physical:one-retry", "run:one", "subject:one", "validated", START, AS_OF))
    connection.execute("INSERT INTO delivery_jobs VALUES (?,?,?,?,?)", ("job:one-retry", "run:one", "completed", START, AS_OF))
    connection.execute("INSERT INTO provider_request_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("request:one-retry", "run:one", "task:one", "physical:one-retry", "job:one-retry", "provider:test", "model:test", "completed", "provider-request:one-retry", "receipt:one-retry", START, AS_OF))
    connection.execute("INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("delivery:one-retry", "request:one-retry", "physical:one-retry", "job:one-retry", "completed", 1, None, "provider-request:one-retry", "receipt:one-retry", START, START, AS_OF, AS_OF))
    connection.execute("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", ("receipt:one-retry", "physical:one-retry", "provider-request:one-retry", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF))
    connection.commit()
    connection.close()
    document = _project(path).document
    assert {row["identity"]["provider_receipt_id"] for row in document["charges"]} == {"receipt:two"}
    assert document["totals"]["actual_incurred_charges"]["state"] == "unknown"
    assert document["totals"]["actual_incurred_charges"]["amount"] is None
