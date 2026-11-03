import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from charitygraph.runtime.catalog import SQLiteCatalog
from charitygraph.phase5_t4a_sqlite_accounting_export import (
    _EXPORT_COLUMNS,
    _validate_graph,
    extract_sqlite_accounting_source,
    required_column_schema_sha256,
)


NOW = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
SOURCE_HASH = "a" * 64
AUTHORITY = {
    "source_id": "source:sqlite-accounting",
    "source_kind": "runtime-catalogue",
    "source_version": "catalogue-v29",
    "content_sha256": SOURCE_HASH,
    "authority_id": "authority:accounting",
    "authority_version": "2026-10-30",
    "retention_id": "retention:private-runtime",
    "retention_version": "1",
    "retention_status": "authorized",
}
COVERAGE = {
    "population_complete": True,
    "project_wide": True,
    "scope": "all durable paid work in supplied SQLite source",
    "source_provenance": [{"source_id": AUTHORITY["source_id"], "source_kind": AUTHORITY["source_kind"], "content_sha256": SOURCE_HASH}],
    "logical_paid_tasks_complete": True,
    "retries_complete": True,
    "physical_attempts_complete": True,
    "cohorts_complete": True,
    "accounting_sources_complete": True,
    "reservations_complete": True,
    "actuals_complete": True,
    "pricing_complete": True,
}


def _db(tmp_path):
    path = tmp_path / "accounting.sqlite3"
    SQLiteCatalog(path).open(initialize=True).close()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        INSERT INTO cohorts VALUES ('cohort:one','one','1','membership','2.00','2026-10-29T00:00:00+00:00','h-cohort','2.00','AUD');
        INSERT INTO runs(run_id,cohort_id,run_kind,status,configuration_hash,created_at,updated_at,material_hash)
            VALUES ('run:one','cohort:one','semantic','succeeded','h-run','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','h-run');
        INSERT INTO tasks(model_task_id,run_id,subject_id,scope_id,cohort_id,task_type,task_schema_id,cache_key,provider_id,model_snapshot,status,attempt_count,created_at,updated_at,material_hash)
            VALUES ('task:one','run:one','subject:one','scope:one','cohort:one','judgement','schema:one','cache:one','provider:offline','model:one','succeeded',1,'2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','h-task');
        INSERT INTO budget_reservations VALUES ('reservation:one','cohort:one','run:one','2.00','partially_consumed','2026-10-29T00:00:00+00:00',NULL,'2026-10-29T00:00:00+00:00','h-reservation','2.00','AUD');
        INSERT INTO reservation_tasks VALUES ('reservation:one','task:one');
        INSERT INTO task_attempts(task_run_id,model_task_id,attempt_number,status,provider_request_id,pricing_snapshot_id,fx_snapshot_id,reservation_id,usage_json)
            VALUES ('taskrun:one:1','task:one',1,'succeeded','provider-request:one','pricing:one','fx:one','reservation:one','{}');
        INSERT INTO physical_attempts VALUES ('physical:one','run:one','subject:one','standard','validated','provider-request:one','reservation:one',NULL,'2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00');
        INSERT INTO physical_attempt_members VALUES ('physical:one','task:one');
        INSERT INTO delivery_jobs(delivery_job_id,run_id,provider_id,model_route,delivery_mode,status,pricing_snapshot_id,created_at,updated_at)
            VALUES ('job:one','run:one','provider:offline','route:one','standard','completed','pricing:one','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00');
        INSERT INTO provider_request_items(provider_request_item_id,run_id,model_task_id,physical_attempt_id,delivery_job_id,provider_id,model_route,requested_delivery_mode,effective_service_tier,status,provider_request_id,provider_receipt_id,created_at,updated_at)
            VALUES ('item:one','run:one','task:one','physical:one','job:one','provider:offline','route:one','standard','standard','completed','provider-request:one','receipt:one','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00');
        INSERT INTO provider_receipts(provider_receipt_id,physical_attempt_id,provider_request_id,raw_result_ref,usage_json,received_at)
            VALUES ('receipt:one','physical:one','provider-request:one','redacted:result','{}','2026-10-29T00:00:00+00:00');
        INSERT INTO provider_request_attempts(delivery_attempt_id,provider_request_item_id,physical_attempt_id,delivery_job_id,attempt_ordinal,authorization_id,attempt_class,status,provider_request_id,provider_receipt_id,created_at,completed_at,updated_at)
            VALUES ('delivery:one','item:one','physical:one','job:one',1,'authorization:one','initial','completed','provider-request:one','receipt:one','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00','2026-10-29T00:00:00+00:00');
        INSERT INTO cost_entries(entry_key,entry_hash,cohort_id,run_id,task_run_id,reservation_id,entry_type,provider_amount,provider_currency,aud_amount,pricing_snapshot_id,fx_snapshot_id,usage_json,recorded_at,accounting_amount,accounting_currency)
            VALUES ('cost:actual','h-cost','cohort:one','run:one','taskrun:one:1','reservation:one','actual','1.00','AUD','1.00','pricing:one','fx:one','{"provider_request_item_id":"item:one","provider_receipt_id":"receipt:one"}','2026-10-29T00:00:00+00:00','1.00','AUD');
        INSERT INTO cost_entries(entry_key,entry_hash,cohort_id,run_id,task_run_id,reservation_id,entry_type,aud_amount,recorded_at,accounting_amount,accounting_currency)
            VALUES ('cost:release','h-release','cohort:one','run:one',NULL,'reservation:one','reservation_release','0.50','2026-10-29T00:00:00+00:00','0.50','AUD');
        """
    )
    conn.commit()
    conn.close()
    return path


def _extract(path, coverage=COVERAGE):
    return extract_sqlite_accounting_source(path, project_id="charitygraph-project", as_of=NOW, source_authority=AUTHORITY, coverage_authority=coverage)


def test_current_migration_graph_exports_deterministic_candidate(tmp_path):
    path = _db(tmp_path)
    first = _extract(path)
    second = _extract(path)

    assert first.status == "NOT_ATTESTABLE"
    assert first.migration_version == 29
    assert first.candidate.actual_aud == 1
    assert first.candidate.outstanding_reservations_aud == 0.5
    assert first.evidence_bytes == second.evidence_bytes
    assert first.manifest_bytes == second.manifest_bytes
    assert first.candidate_bytes == second.candidate_bytes
    assert first.candidate_sha256 == hashlib.sha256(first.candidate_bytes).hexdigest()
    assert first.independent_trust == "NOT_SUPPLIED"
    assert first.request_ticket is None
    assert first.send_authorization == "not_authorized_for_send"
    assert required_column_schema_sha256() == first.column_schema_sha256
    assert "pricing_fx_authority_records_unavailable" in first.diagnostics
    assert first.candidate.status == "INCOMPLETE_OR_UNKNOWN"


def test_missing_tables_fail_closed(tmp_path):
    path = _db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DROP TABLE provider_receipts")
    conn.commit()
    conn.close()

    result = _extract(path)

    assert result.status == "NOT_ATTESTABLE"
    assert "required_table_missing:provider_receipts" in result.diagnostics
    assert result.candidate_bytes is None


def test_orphan_member_and_currency_mismatch_are_blocked(tmp_path):
    path = _db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("INSERT INTO physical_attempt_members VALUES ('physical:missing','task:one')")
    conn.execute("INSERT INTO provider_receipts(provider_receipt_id,physical_attempt_id,provider_request_id,raw_result_ref,usage_json,received_at) VALUES ('receipt:orphan','physical:missing','provider-request:orphan','redacted:orphan','{}','2026-10-29T00:00:00+00:00')")
    conn.execute("UPDATE cost_entries SET accounting_currency='USD' WHERE entry_key='cost:actual'")
    conn.commit()
    conn.close()

    result = _extract(path)

    assert result.status == "BLOCKED"
    assert "orphaned_physical_attempt_member:task:one" in result.diagnostics
    assert "orphaned_provider_receipt:receipt:orphan" in result.diagnostics
    assert "cost_entry_currency_invalid:cost:actual" in result.diagnostics


def test_unpriced_actual_and_missing_population_assertion_never_become_zero(tmp_path):
    path = _db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE cost_entries SET pricing_snapshot_id=NULL, fx_snapshot_id=NULL WHERE entry_key='cost:actual'")
    conn.commit()
    conn.close()

    unpriced = _extract(path)
    incomplete = _extract(path, {"project_wide": False})

    assert unpriced.status == "BLOCKED"
    assert "unpriced_actual_cost:cost:actual" in unpriced.diagnostics
    assert "actual_receipt_item_provenance_missing:cost:actual" not in unpriced.diagnostics
    assert incomplete.status in {"NOT_ATTESTABLE", "BLOCKED"}
    assert "global_population_completeness_not_asserted" in incomplete.diagnostics
    assert incomplete.candidate.actual_aud == 1
    assert incomplete.candidate.outstanding_reservations_aud == 0.5


def test_ambiguous_physical_attempt_is_blocked(tmp_path):
    path = _db(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE physical_attempts SET status='held' WHERE physical_attempt_id='physical:one'")
    conn.commit()
    conn.close()

    result = _extract(path)

    assert result.status == "BLOCKED"
    assert "unresolved_physical_attempts_present" in result.diagnostics


def test_read_only_connection_is_query_only_and_does_not_mutate(tmp_path):
    path = _db(tmp_path)
    conn = sqlite3.connect(path)
    before = conn.execute("SELECT count(*) FROM cost_entries").fetchone()[0]

    result = extract_sqlite_accounting_source(conn, project_id="charitygraph-project", as_of=NOW, source_authority=AUTHORITY, coverage_authority=COVERAGE)

    assert result.status == "NOT_ATTESTABLE"
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO operation_receipts VALUES ('blocked','test','hash','started',NULL,'now','now')")
    assert conn.execute("SELECT count(*) FROM cost_entries").fetchone()[0] == before
    conn.close()


def test_t4a8r_duplicate_provider_physical_linkage_is_rejected():
    rows = {table: [] for table in _EXPORT_COLUMNS}
    rows["provider_request_attempts"] = [
        {"delivery_attempt_id": "delivery:one", "physical_attempt_id": "physical:one", "provider_request_item_id": "item:one", "delivery_job_id": "job:one"},
        {"delivery_attempt_id": "delivery:two", "physical_attempt_id": "physical:one", "provider_request_item_id": "item:one", "delivery_job_id": "job:one"},
    ]
    reasons = []
    _validate_graph(rows, reasons)

    assert "provider_request_attempts_physical_attempt_id_not_unique" in reasons

