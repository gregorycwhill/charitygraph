from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from charitygraph.phase5_operator_health_catalogue import (
    Phase5CatalogueAdapterError,
    Phase5OperatorHealthCatalogueAdapter,
    project_operator_health_catalogue,
)


AS_OF = "2026-10-31T00:00:00+00:00"
WINDOW_START = "2026-10-30T00:00:00+00:00"
RUN = "run:one"
OTHER_RUN = "run:outside"


def _create_catalogue(path: Path, *, incomplete: bool = False) -> None:
    scope_column = "" if incomplete else "scope_id TEXT,"
    connection = sqlite3.connect(path)
    connection.executescript(
        f"""
        CREATE TABLE schema_migrations(version INTEGER NOT NULL);
        INSERT INTO schema_migrations VALUES (29);
        CREATE TABLE runs(run_id TEXT PRIMARY KEY, status TEXT, created_at TEXT, started_at TEXT, completed_at TEXT, updated_at TEXT);
        CREATE TABLE tasks(model_task_id TEXT PRIMARY KEY, run_id TEXT, subject_id TEXT, {scope_column} status TEXT, attempt_count INTEGER, created_at TEXT, updated_at TEXT);
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
    if incomplete:
        connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (RUN, "succeeded", WINDOW_START, WINDOW_START, AS_OF, AS_OF))
    else:
        connection.executemany("INSERT INTO runs VALUES (?,?,?,?,?,?)", [
            (RUN, "succeeded", WINDOW_START, WINDOW_START, AS_OF, AS_OF),
            (OTHER_RUN, "failed", WINDOW_START, WINDOW_START, AS_OF, AS_OF),
        ])
        connection.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)", [
            ("task:one", RUN, "subject:one", "scope:one", "succeeded", 1, WINDOW_START, AS_OF),
            ("task:two", RUN, "subject:two", "scope:two", "failed_terminal", 2, WINDOW_START, AS_OF),
            ("task:outside", OTHER_RUN, "subject:outside", "scope:outside", "succeeded", 1, WINDOW_START, AS_OF),
        ])
        connection.executemany("INSERT INTO task_attempts VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("taskrun:one", "task:one", 1, "completed", "provider-request:one", None, WINDOW_START, WINDOW_START, AS_OF, "reservation:one"),
            ("taskrun:two", "task:two", 1, "failed_terminal", None, None, WINDOW_START, WINDOW_START, AS_OF, "reservation:two"),
        ])
        connection.execute("INSERT INTO delivery_jobs VALUES (?,?,?,?,?)", ("job:one", RUN, "completed", WINDOW_START, AS_OF))
        connection.executemany("INSERT INTO physical_attempts VALUES (?,?,?,?,?,?)", [
            ("physical:one", RUN, "subject:one", "validated", WINDOW_START, AS_OF),
            ("physical:two", RUN, "subject:two", "failed", WINDOW_START, AS_OF),
        ])
        connection.executemany("INSERT INTO provider_request_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("request:one", RUN, "task:one", "physical:one", "job:one", "provider", "model", "completed", "provider-request:one", "receipt:one", WINDOW_START, AS_OF),
            ("request:two", RUN, "task:two", "physical:two", "job:one", "provider", "model", "failed", "provider-request:two", None, WINDOW_START, AS_OF),
        ])
        connection.executemany("INSERT INTO provider_request_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("delivery:one", "request:one", "physical:one", "job:one", "completed", 1, None, "provider-request:one", "receipt:one", WINDOW_START, WINDOW_START, AS_OF, AS_OF),
            ("delivery:two", "request:two", "physical:two", "job:one", "failed", 1, None, "provider-request:two", None, WINDOW_START, WINDOW_START, AS_OF, AS_OF),
        ])
        connection.executemany("INSERT INTO provider_receipts VALUES (?,?,?,?,?)", [
            ("receipt:one", "physical:one", "provider-request:one", json.dumps({"input_tokens": 10, "output_tokens": 4}), AS_OF),
        ])
        connection.executemany("INSERT INTO budget_reservations VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("reservation:one", "cohort:one", RUN, "2.00", "2.00", "AUD", "active", WINDOW_START, None, AS_OF),
            ("reservation:two", "cohort:one", RUN, "3.00", "3.00", "AUD", "active", WINDOW_START, None, AS_OF),
        ])
        # The persisted cost schema has no provider_receipt_id column.  The
        # adapter must therefore leave actual cost non-observed rather than
        # deriving identity from row position or entry_key.
        connection.executemany("INSERT INTO cost_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("actual:one", RUN, None, "reservation:one", "actual", "1.00", "AUD", "1.00", "1.00", None, "AUD", "pricing:one", "fx:one", AS_OF),
            ("release:one", RUN, None, "reservation:one", "reservation_release", None, None, "1.00", "1.00", None, "AUD", None, None, AS_OF),
        ])
    connection.commit()
    connection.close()


def _adapter(path: Path, **changes):
    args = {
        "run_ids": [RUN],
        "as_of": AS_OF,
        "reporting_window_start": WINDOW_START,
        "reporting_window_end": AS_OF,
        "source_id": "source:runtime-catalogue",
        "evidence_basis": "test persisted rows",
        "ledger": {"source_id": "ledger:test", "version": "ledger:v1", "as_of": AS_OF, "stale_after": "2026-11-01T00:00:00+00:00", "complete": True},
    }
    args.update(changes)
    return Phase5OperatorHealthCatalogueAdapter(path, **args)


def test_persisted_catalogue_adapter_is_bounded_read_only_and_stable(tmp_path: Path):
    path = tmp_path / "catalogue.sqlite3"
    _create_catalogue(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    first = _adapter(path).project()
    second = _adapter(path).project()

    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert first.canonical_json == second.canonical_json
    assert first.sha256 == second.sha256
    assert first.snapshot.coverage["state"] == "complete"
    assert first.snapshot.coverage["run_selection"] == {"requested": [RUN], "found": [RUN], "missing": [], "bounded": True}
    assert first.document["provider_usage"] == {
        "basis": "deduplicated provider receipt identities only; no provider invocation",
        "coverage_reasons": ["OBSERVED_COMPLETE_USAGE"],
        "input_tokens": 10,
        "output_tokens": 4,
        "receipt_count": 1,
        "receipts_with_usage": 1,
        "state": "observed",
    }
    assert first.document["cost"]["actual"]["state"] == "ambiguous"
    assert first.document["cost"]["actual"]["amount"] is None
    assert first.document["scope"]["run_ids"] == [RUN]
    assert first.document["per_run"][0]["subject_ids"] == ["subject:one", "subject:two"]
    assert first.document["per_run"][0]["scope_ids"] == ["scope:one", "scope:two"]
    assert first.document["catalogue_integration"]["coverage"]["source_lineage"]["source_id"] == "source:runtime-catalogue"
    assert "UNIDENTIFIABLE_RECEIPT_IDENTITY" in {issue["code"] for issue in first.document["issues"]}


@pytest.mark.parametrize(
    ("usage_json", "expected_state", "expected_issue"),
    [
        ('{"input_tokens": 4}', "missing", "MISSING_REQUIRED_TOKEN_COUNTS"),
        ('{"input_tokens": "bad", "output_tokens": 2}', "ambiguous", "INVALID_PROVIDER_USAGE"),
        ('{"input_tokens": 1.5, "output_tokens": 2}', "ambiguous", "INVALID_PROVIDER_USAGE"),
        ('{"input_tokens": 4, "output_tokens":', "ambiguous", "INVALID_USAGE_JSON"),
    ],
)
def test_adapter_usage_missingness_is_explicit_and_payload_free(tmp_path: Path, usage_json, expected_state, expected_issue):
    path = tmp_path / "usage.sqlite3"
    _create_catalogue(path)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE provider_receipts SET usage_json = ? WHERE provider_receipt_id = ?", (usage_json, "receipt:one"))
    connection.commit()
    connection.close()

    projection = _adapter(path).project()
    usage = projection.document["provider_usage"]

    assert usage["state"] == expected_state
    if expected_state == "observed":
        assert usage["input_tokens"] == 4
        assert usage["output_tokens"] == 2
    else:
        assert usage["input_tokens"] is None
        assert usage["output_tokens"] is None
    if expected_issue:
        assert expected_issue in {issue["code"] for issue in projection.document["issues"]}
    assert "bad" not in projection.canonical_json.decode("utf-8")


def test_connection_is_forced_query_only_and_source_lineage_is_explicit(tmp_path: Path):
    path = tmp_path / "connection.sqlite3"
    _create_catalogue(path)
    connection = sqlite3.connect(path)
    projection = project_operator_health_catalogue(
        connection,
        run_ids=[RUN],
        as_of=AS_OF,
        reporting_window_start=WINDOW_START,
        reporting_window_end=AS_OF,
        source_id="source:explicit-connection",
    )

    assert projection.snapshot.coverage["source_lineage"]["state"] == "explicit"
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO schema_migrations VALUES (30)")
    connection.close()


def test_missing_schema_is_unknown_not_empty_success(tmp_path: Path):
    path = tmp_path / "incomplete.sqlite3"
    _create_catalogue(path, incomplete=True)

    projection = _adapter(path).project()

    assert projection.snapshot.coverage["state"] == "unknown"
    assert projection.snapshot.coverage["schema"]["missing_columns"]["tasks"] == ["scope_id"]
    assert projection.document["catalogue_integration"]["record_counts"]["tasks"] == 0
    assert "INCOMPLETE_CATALOGUE_SCHEMA" in {issue["code"] for issue in projection.snapshot.coverage["issues"]}
    assert projection.document["cost"]["actual"]["amount"] is None


def test_adapter_rejects_unbounded_or_implicit_time_requests(tmp_path: Path):
    path = tmp_path / "invalid.sqlite3"
    _create_catalogue(path)

    with pytest.raises(Phase5CatalogueAdapterError):
        Phase5OperatorHealthCatalogueAdapter(path, run_ids=[], as_of=AS_OF, reporting_window_start=WINDOW_START, reporting_window_end=AS_OF)
    with pytest.raises(Phase5CatalogueAdapterError):
        Phase5OperatorHealthCatalogueAdapter(path, run_ids=[RUN], as_of="2026-10-31T00:00:00", reporting_window_start=WINDOW_START, reporting_window_end=AS_OF)
