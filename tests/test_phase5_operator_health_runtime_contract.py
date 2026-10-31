from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from charitygraph.phase5_operator_health import project_operator_health
from charitygraph.phase5_operator_health_runtime_contract import (
    SCHEMA,
    canonical_runtime_contract_json,
    project_phase5_operator_health_runtime_contract,
    runtime_contract_sha256,
)


AS_OF = "2026-10-31T10:00:00+00:00"
WINDOW_START = "2026-10-31T09:00:00+00:00"
SOURCE_ID = "source:synthetic-runtime-contract"
RUN = "run:contract"


def _make_catalogue(
    path: Path,
    *,
    usage_json: str | None = '{"input_tokens": 0, "output_tokens": 0}',
    reverse_rows: bool = False,
    receipts: list[tuple[str | None, str | None]] | None = None,
) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_migrations (version INTEGER NOT NULL);
        CREATE TABLE runs (run_id TEXT, status TEXT, created_at TEXT, started_at TEXT, completed_at TEXT, updated_at TEXT);
        CREATE TABLE tasks (model_task_id TEXT, run_id TEXT, subject_id TEXT, scope_id TEXT, status TEXT, attempt_count INTEGER, created_at TEXT, updated_at TEXT, task_material_json TEXT);
        CREATE TABLE task_attempts (task_run_id TEXT, model_task_id TEXT, attempt_number INTEGER, status TEXT, provider_request_id TEXT, provider_batch_id TEXT, reservation_id TEXT, submitted_at TEXT, started_at TEXT, completed_at TEXT);
        CREATE TABLE budget_reservations (reservation_id TEXT, cohort_id TEXT, run_id TEXT, reserved_amount TEXT, reserved_aud TEXT, accounting_currency TEXT, status TEXT, reserved_at TEXT, expires_at TEXT, updated_at TEXT);
        CREATE TABLE reservation_tasks (reservation_id TEXT, model_task_id TEXT);
        CREATE TABLE cost_entries (entry_key TEXT, entry_hash TEXT, cohort_id TEXT, run_id TEXT, task_run_id TEXT, reservation_id TEXT, provider_receipt_id TEXT, entry_type TEXT, provider_amount TEXT, provider_currency TEXT, accounting_amount TEXT, aud_amount TEXT, adjustment_direction TEXT, accounting_currency TEXT, pricing_snapshot_id TEXT, fx_snapshot_id TEXT, recorded_at TEXT);
        CREATE TABLE physical_attempts (physical_attempt_id TEXT, run_id TEXT, subject_id TEXT, delivery_mode TEXT, status TEXT, provider_request_id TEXT, reservation_id TEXT, created_at TEXT, send_started_at TEXT, receipt_persisted_at TEXT, updated_at TEXT);
        CREATE TABLE physical_attempt_members (physical_attempt_id TEXT, model_task_id TEXT);
        CREATE TABLE provider_receipts (provider_receipt_id TEXT, physical_attempt_id TEXT, provider_request_id TEXT, received_at TEXT, usage_json TEXT, raw_result_ref TEXT);
        CREATE TABLE delivery_jobs (delivery_job_id TEXT, run_id TEXT, provider_id TEXT, model_route TEXT, delivery_mode TEXT, provider_batch_id TEXT, status TEXT, pricing_snapshot_id TEXT, created_at TEXT, submitted_at TEXT, completed_at TEXT, updated_at TEXT);
        CREATE TABLE provider_request_items (provider_request_item_id TEXT, run_id TEXT, model_task_id TEXT, physical_attempt_id TEXT, delivery_job_id TEXT, provider_id TEXT, model_route TEXT, requested_delivery_mode TEXT, effective_service_tier TEXT, status TEXT, provider_request_id TEXT, provider_receipt_id TEXT, created_at TEXT, scheduled_at TEXT, started_at TEXT, submitted_at TEXT, send_started_at TEXT, received_at TEXT, completed_at TEXT, updated_at TEXT, result_ref TEXT);
        CREATE TABLE provider_request_attempts (delivery_attempt_id TEXT, provider_request_item_id TEXT, physical_attempt_id TEXT, delivery_job_id TEXT, attempt_ordinal INTEGER, attempt_class TEXT, predecessor_attempt_id TEXT, status TEXT, provider_request_id TEXT, provider_receipt_id TEXT, failure_class TEXT, created_at TEXT, submitted_at TEXT, completed_at TEXT, updated_at TEXT);
        """
    )
    connection.executemany("INSERT INTO schema_migrations VALUES (?)", [(number,) for number in range(1, 30)])
    rows = {
        "runs": [(RUN, "succeeded", WINDOW_START, WINDOW_START, AS_OF, AS_OF)],
        "tasks": [
            ("task:2", RUN, "subject:2", "scope:2", "failed_terminal", 2, WINDOW_START, AS_OF, "PROMPT_SENTINEL"),
            ("task:1", RUN, "subject:1", "scope:1", "succeeded", 1, WINDOW_START, AS_OF, "SOURCE_SENTINEL"),
        ],
        "task_attempts": [
            ("taskrun:1", "task:1", 1, "succeeded", "request:1", None, "reservation:1", WINDOW_START, WINDOW_START, AS_OF),
            ("taskrun:2", "task:2", 2, "failed_terminal", "request:2", None, "reservation:1", WINDOW_START, WINDOW_START, AS_OF),
        ],
        "budget_reservations": [("reservation:1", "cohort:1", RUN, "2.000000", "2.000000", "AUD", "active", WINDOW_START, AS_OF, AS_OF)],
        "reservation_tasks": [("reservation:1", "task:1"), ("reservation:1", "task:2")],
        "cost_entries": [
            ("actual:1", None, "cohort:1", RUN, "taskrun:1", "reservation:1", "receipt:1", "actual", "0.125000", "USD", "0.125000", None, None, "AUD", "pricing:v1", "fx:v1", AS_OF),
            ("release:1", None, "cohort:1", RUN, None, "reservation:1", None, "reservation_release", None, None, "0.000000", None, None, "AUD", None, None, AS_OF),
        ],
        "physical_attempts": [("physical:1", RUN, "subject:1", "standard", "validated", "request:1", "reservation:1", WINDOW_START, WINDOW_START, AS_OF, AS_OF)],
        "physical_attempt_members": [("physical:1", "task:1")],
        "provider_receipts": [("receipt:1", "physical:1", "provider-request:1", AS_OF, usage_json, "RAW_RESULT_SENTINEL")],
        "delivery_jobs": [("job:1", RUN, "provider", "model", "standard", None, "completed", "pricing:v1", WINDOW_START, WINDOW_START, AS_OF, AS_OF)],
        "provider_request_items": [
            ("request:2", RUN, "task:2", "physical:1", "job:1", "provider", "model", "standard", "standard", "failed", "provider-request:2", None, WINDOW_START, WINDOW_START, WINDOW_START, WINDOW_START, WINDOW_START, None, None, AS_OF, "RESULT_REF_SENTINEL"),
            ("request:1", RUN, "task:1", "physical:1", "job:1", "provider", "model", "standard", "standard", "in_progress", "provider-request:1", "receipt:1", WINDOW_START, WINDOW_START, WINDOW_START, WINDOW_START, WINDOW_START, None, None, WINDOW_START, "RESULT_REF_SENTINEL"),
        ],
        "provider_request_attempts": [
            ("delivery:1", "request:1", "physical:1", "job:1", 2, "retry", "delivery:0", "failed", "provider-request:1", None, "retryable", WINDOW_START, WINDOW_START, AS_OF, AS_OF),
        ],
    }
    statements = {
        "runs": "INSERT INTO runs VALUES (?,?,?,?,?,?)",
        "tasks": "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
        "task_attempts": "INSERT INTO task_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
        "budget_reservations": "INSERT INTO budget_reservations VALUES (?,?,?,?,?,?,?,?,?,?)",
        "reservation_tasks": "INSERT INTO reservation_tasks VALUES (?,?)",
        "cost_entries": "INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        "physical_attempts": "INSERT INTO physical_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        "physical_attempt_members": "INSERT INTO physical_attempt_members VALUES (?,?)",
        "provider_receipts": "INSERT INTO provider_receipts VALUES (?,?,?,?,?,?)",
        "delivery_jobs": "INSERT INTO delivery_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        "provider_request_items": "INSERT INTO provider_request_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        "provider_request_attempts": "INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    }
    for table, values in rows.items():
        values = list(reversed(values)) if reverse_rows else values
        connection.executemany(statements[table], values)
    connection.commit()
    connection.close()


def _kwargs() -> dict:
    return {
        "run_ids": [RUN],
        "as_of": AS_OF,
        "reporting_window_start": WINDOW_START,
        "reporting_window_end": AS_OF,
        "source_id": SOURCE_ID,
        "ledger": {"source_id": "ledger:fixture", "version": "ledger:v1", "as_of": AS_OF, "stale_after": "2026-11-01T00:00:00+00:00", "complete": True},
        "stalled_after_seconds": 60,
    }


def _sidecar_hashes(path: Path) -> dict[str, str]:
    return {str(candidate): hashlib.sha256(candidate.read_bytes()).hexdigest() for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")) if candidate.exists()}


def test_contract_calls_actual_readonly_export_and_matches_direct_observer(tmp_path: Path):
    database = tmp_path / "runtime.sqlite3"
    _make_catalogue(database)
    before = _sidecar_hashes(database)

    result = project_phase5_operator_health_runtime_contract(database, **_kwargs())

    assert result.document["schema"] == SCHEMA
    assert all(result.checks.values())
    assert result.runtime_export.operator_health.canonical_json == result.direct_observer.canonical_json
    assert result.document["operator_health"]["scope"]["run_ids"] == [RUN]
    assert result.document["operator_health"]["per_run"][0]["subject_ids"] == ["subject:1", "subject:2"]
    assert result.document["operator_health"]["per_run"][0]["scope_ids"] == ["scope:1", "scope:2"]
    assert result.document["operator_health"]["flags"]["stalled"][0]["id"] == "request:1"
    assert result.document["operator_health"]["flags"]["retry"][0]["id"] == "delivery:1"
    assert result.document["operator_health"]["flags"]["recovery"][0]["id"] == "delivery:1"
    assert {row["id"] for row in result.document["operator_health"]["flags"]["failed"]} >= {"request:2", "delivery:1"}
    # The persisted health adapter deliberately does not expose the provider
    # receipt identity from cost rows, so the direct observer must keep all
    # dependent totals ambiguous rather than manufacture a spend total.
    assert result.document["operator_health"]["cost"]["actual"]["amount"] is None
    assert result.document["operator_health"]["cost"]["committed_reserved"]["amount"] is None
    assert result.document["operator_health"]["cost"]["forecast"]["amount"] is None
    assert result.document["operator_health"]["cost"]["reconciliation"]["state"] == "AMBIGUOUS"
    assert result.document["operator_health"]["cost"]["provenance"]["ledger_source_id"] == "ledger:fixture"
    payload = result.canonical_json.decode("utf-8")
    assert all(sentinel not in payload for sentinel in ("PROMPT_SENTINEL", "SOURCE_SENTINEL", "RAW_RESULT_SENTINEL", "RESULT_REF_SENTINEL"))
    assert _sidecar_hashes(database) == before


def test_contract_canonical_bytes_are_stable_under_fixture_row_reordering(tmp_path: Path):
    first_db = tmp_path / "first.sqlite3"
    second_db = tmp_path / "second.sqlite3"
    _make_catalogue(first_db)
    _make_catalogue(second_db, reverse_rows=True)

    first = project_phase5_operator_health_runtime_contract(first_db, **_kwargs())
    second = project_phase5_operator_health_runtime_contract(second_db, **_kwargs())

    assert first.canonical_json == second.canonical_json
    assert first.sha256 == second.sha256 == runtime_contract_sha256(first)
    assert canonical_runtime_contract_json(second) == second.canonical_json


@pytest.mark.parametrize(
    ("usage_json", "state", "input_tokens", "reason"),
    [
        (None, "missing", None, "MISSING_USAGE_JSON"),
        ('{"input_tokens": 4,', "ambiguous", None, "INVALID_USAGE_JSON"),
        ('{"input_tokens": 0, "output_tokens": 0}', "observed", 0, "OBSERVED_COMPLETE_USAGE"),
    ],
)
def test_contract_preserves_usage_missingness_and_explicit_zero(tmp_path: Path, usage_json: str | None, state: str, input_tokens: int | None, reason: str):
    database = tmp_path / "usage.sqlite3"
    _make_catalogue(database, usage_json=usage_json)

    result = project_phase5_operator_health_runtime_contract(database, **_kwargs())
    usage = result.document["operator_health"]["provider_usage"]

    assert usage["state"] == state
    assert usage["input_tokens"] == input_tokens
    assert reason in usage["coverage_reasons"]


def test_contract_direct_observer_fails_closed_for_receipt_identity_and_cost_ledger_gaps():
    base = {
        "as_of": AS_OF,
        "source_id": SOURCE_ID,
        "source_version": "fixture:v1",
        "evidence_basis": "synthetic structured runtime rows",
        "reporting_window_start": WINDOW_START,
        "reporting_window_end": AS_OF,
        "ledger_source_id": "ledger:fixture",
        "ledger_version": "ledger:v1",
        "ledger_as_of": AS_OF,
        "ledger_stale_after": "2026-11-01T00:00:00+00:00",
        "ledger_complete": True,
        "reservations": [{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2", "accounting_currency": "AUD"}],
        "cost_entries": [{"entry_key": "cost:1", "entry_type": "actual", "provider_receipt_id": "receipt:1", "provider_amount": "1", "provider_currency": "USD", "accounting_amount": "1", "accounting_currency": "AUD", "pricing_snapshot_id": "pricing:v1", "fx_snapshot_id": "fx:v1"}],
    }
    for receipts, expected in (
        ([{"provider_receipt_id": "receipt:1", "input_tokens": 1, "output_tokens": 1}, {"provider_receipt_id": "receipt:1", "input_tokens": 2, "output_tokens": 1}], "ambiguous"),
        ([{"input_tokens": 1, "output_tokens": 1}], "ambiguous"),
    ):
        result = project_operator_health({**base, "receipts": receipts})
        assert result.document["provider_usage"]["state"] == expected
        assert result.document["provider_usage"]["input_tokens"] is None

    duplicate = project_operator_health({**base, "receipts": [{"provider_receipt_id": "receipt:1", "input_tokens": 1, "output_tokens": 1}] * 2})
    assert duplicate.document["provider_usage"]["state"] == "observed"
    assert duplicate.document["provider_usage"]["input_tokens"] == 1
    assert "DUPLICATE_RECEIPT_ID" in {issue["code"] for issue in duplicate.document["issues"]}

    complete = project_operator_health({**base, "receipts": [{"provider_receipt_id": "receipt:1", "input_tokens": 1, "output_tokens": 1}]})
    assert complete.document["cost"]["actual"]["amount"] == "1"
    assert complete.document["cost"]["committed_reserved"]["amount"] == "2"
    assert complete.document["cost"]["forecast"]["state"] == "missing"
    assert complete.document["cost"]["provenance"]["pricing_versions"] == ["pricing:v1"]
    assert complete.document["cost"]["provenance"]["fx_versions"] == ["fx:v1"]

    unidentifiable_cost = {**base, "receipts": [{"input_tokens": 1, "output_tokens": 1}], "cost_entries": [{**base["cost_entries"][0], "provider_receipt_id": None}]}
    unidentifiable = project_operator_health(unidentifiable_cost)
    assert unidentifiable.document["cost"]["actual"]["state"] == "ambiguous"
    assert unidentifiable.document["cost"]["actual"]["amount"] is None
    assert "UNIDENTIFIABLE_RECEIPT_IDENTITY" in {issue["code"] for issue in unidentifiable.document["issues"]}

    missing_ledger = project_operator_health({"as_of": AS_OF, "source_id": SOURCE_ID, "source_version": "fixture:v1", "evidence_basis": "fixture", "receipts": [], "reservations": [], "cost_entries": []})
    assert missing_ledger.document["cost"]["ledger_state"] == "missing"
    assert missing_ledger.document["cost"]["actual"]["amount"] is None
    assert missing_ledger.document["cost"]["committed_reserved"]["amount"] is None
    assert missing_ledger.document["cost"]["forecast"]["amount"] is None
