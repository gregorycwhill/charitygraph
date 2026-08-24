"""Append-only SQLite catalogue migrations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


CATALOGUE_SQL_V1 = """
CREATE TABLE cohorts (
    cohort_id TEXT PRIMARY KEY,
    cohort_code TEXT NOT NULL,
    definition_version TEXT NOT NULL,
    membership_hash TEXT NOT NULL,
    budget_cap_aud TEXT NOT NULL,
    created_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    cohort_id TEXT REFERENCES cohorts(cohort_id),
    run_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    configuration_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE tasks (
    model_task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    subject_id TEXT NOT NULL,
    scope_id TEXT,
    cohort_id TEXT REFERENCES cohorts(cohort_id),
    task_type TEXT NOT NULL,
    task_schema_id TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_snapshot TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ready','leased','running','succeeded','failed_retryable','failed_terminal','held','cancelled')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    lease_owner TEXT,
    lease_expires_at TEXT,
    next_eligible_at TEXT,
    result_artifact_id TEXT,
    error_class TEXT,
    error_message_redacted TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE INDEX tasks_claim_idx ON tasks(status, next_eligible_at, lease_expires_at);
CREATE TABLE task_attempts (
    task_run_id TEXT PRIMARY KEY,
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
    status TEXT NOT NULL,
    provider_request_id TEXT,
    provider_batch_id TEXT,
    submitted_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    retryable INTEGER,
    pricing_snapshot_id TEXT,
    fx_snapshot_id TEXT,
    reservation_id TEXT,
    usage_json TEXT,
    result_artifact_id TEXT,
    error_class TEXT,
    error_message_redacted TEXT,
    UNIQUE(model_task_id, attempt_number)
);
CREATE UNIQUE INDEX task_attempts_one_running_idx
    ON task_attempts(model_task_id)
    WHERE status='running';
CREATE TABLE operation_receipts (
    operation_key TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('started','completed','failed')),
    result_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    cohort_id TEXT NOT NULL REFERENCES cohorts(cohort_id),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    reserved_aud TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','partially_consumed','consumed','released','expired')),
    reserved_at TEXT NOT NULL,
    expires_at TEXT,
    updated_at TEXT NOT NULL,
    material_hash TEXT NOT NULL
);
CREATE TABLE reservation_tasks (
    reservation_id TEXT NOT NULL REFERENCES budget_reservations(reservation_id),
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    PRIMARY KEY(reservation_id, model_task_id)
);
CREATE TABLE cost_entries (
    entry_key TEXT PRIMARY KEY,
    entry_hash TEXT NOT NULL,
    cohort_id TEXT NOT NULL REFERENCES cohorts(cohort_id),
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    task_run_id TEXT,
    reservation_id TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('reservation','reservation_release','actual','credit','adjustment')),
    paid_output_category TEXT,
    provider_amount TEXT,
    provider_currency TEXT,
    aud_amount TEXT NOT NULL,
    adjustment_direction TEXT CHECK(adjustment_direction IN ('debit','credit') OR adjustment_direction IS NULL),
    pricing_snapshot_id TEXT,
    fx_snapshot_id TEXT,
    usage_json TEXT,
    provider_invoice_ref TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX cost_entries_cohort_idx ON cost_entries(cohort_id, entry_type, reservation_id);
CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    model_task_id TEXT NOT NULL REFERENCES tasks(model_task_id),
    result_artifact_id TEXT NOT NULL,
    result_content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('valid','invalidated')),
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    invalidation_reason TEXT
);
CREATE TABLE cache_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('created','invalidated','replaced')),
    event_at TEXT NOT NULL,
    result_artifact_id TEXT,
    result_content_hash TEXT,
    reason TEXT
);
CREATE INDEX cache_events_key_idx ON cache_events(cache_key, event_id);

CREATE TABLE artifact_index (
    artifact_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    availability TEXT NOT NULL CHECK(availability IN ('available','missing','quarantined')),
    created_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);
""".strip() + "\n"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial_operational_catalogue", CATALOGUE_SQL_V1),
)

SUPPORTED_VERSION = MIGRATIONS[-1].version
CATALOGUE_SQL_V2 = __import__('base64').b64decode('Q1JFQVRFIFRBQkxFIHNvdXJjZV9kZWZpbml0aW9ucyAoc291cmNlX2RlZmluaXRpb25faWQgVEVYVCBQUklNQVJZIEtFWSwgZGVmaW5pdGlvbl92ZXJzaW9uIFRFWFQgTk9UIE5VTEwsIHB1Ymxpc2hlciBURVhUIE5PVCBOVUxMLCBzb3VyY2VfY2xhc3MgVEVYVCBOT1QgTlVMTCwgYXV0aG9yaXR5X3JvbGVzX2pzb24gVEVYVCBOT1QgTlVMTCwgbWF0ZXJpYWxfanNvbiBURVhUIE5PVCBOVUxMLCBtYXRlcmlhbF9oYXNoIFRFWFQgTk9UIE5VTEwsIGNyZWF0ZWRfYXQgVEVYVCBOT1QgTlVMTCwgdXBkYXRlZF9hdCBURVhUIE5PVCBOVUxMKTsKQ1JFQVRFIFRBQkxFIGFjcXVpc2l0aW9uX3JlY2VpcHRzIChhY3F1aXNpdGlvbl9pZCBURVhUIFBSSU1BUlkgS0VZLCBz' 'b3VyY2VfZGVmaW5pdGlvbl9pZCBURVhUIE5PVCBOVUxMIFJFRkVSRU5DRVMgc291cmNlX2RlZmluaXRpb25zKHNvdXJjZV9kZWZpbml0aW9uX2lkKSwgcmVxdWVzdGVkX2xvY2F0b3IgVEVYVCBOT1QgTlVMTCwgcmVzb2x2ZWRfbG9jYXRvciBURVhULCByZXRyaWV2ZWRfYXQgVEVYVCwgZWZmZWN0aXZlX2F0IFRFWFQsIG91dGNvbWUgVEVYVCBOT1QgTlVMTCBDSEVDSyhvdXRjb21lIElOICgnYXZhaWxhYmxlJywnbm90X21vZGlmaWVkJywnYWJzZW50JywnYmxvY2tlZCcsJ2ZhaWxlZCcsJ3BhcnRpYWwnLCd1bmF2YWlsYWJsZScpKSwgcmVzcG9uc2Vfc3RhdHVzIElOVEVHRVIsIG1lZGlhX3R5cGUgVEVYVCwgY29udGVudF9oYXNoIFRFWFQsIGJ5dGVfc2l6ZSBJ' 'TlRFR0VSIENIRUNLKGJ5dGVfc2l6ZSBJUyBOVUxMIE9SIGJ5dGVfc2l6ZSA+PSAwKSwgYXJ0aWZhY3RfaWQgVEVYVCwgdG9vbF9pZCBURVhULCB0b29sX3ZlcnNpb24gVEVYVCwgbWF0ZXJpYWxfcGFyYW1ldGVyc19qc29uIFRFWFQgTk9UIE5VTEwsIHJldHJ5X29mIFRFWFQsIHJlcGxhY2VzX3JlY2VpcHRfaWQgVEVYVCwgZXJyb3JfY2xhc3MgVEVYVCwgbWF0ZXJpYWxfanNvbiBURVhUIE5PVCBOVUxMLCBtYXRlcmlhbF9oYXNoIFRFWFQgTk9UIE5VTEwsIGNyZWF0ZWRfYXQgVEVYVCBOT1QgTlVMTCk7CkNSRUFURSBJTkRFWCBhY3F1aXNpdGlvbl9yZWNlaXB0c19zb3VyY2VfaWR4IE9OIGFjcXVpc2l0aW9uX3JlY2VpcHRzKHNvdXJjZV9kZWZpbml0aW9uX2lk' 'LCByZXRyaWV2ZWRfYXQpOwpDUkVBVEUgVEFCTEUgYXJ0aWZhY3RfbGluZWFnZSAoYXJ0aWZhY3RfaWQgVEVYVCBOT1QgTlVMTCwgaW5wdXRfYXJ0aWZhY3RfaWQgVEVYVCBOT1QgTlVMTCwgZWRnZV90eXBlIFRFWFQgTk9UIE5VTEwgQ0hFQ0soZWRnZV90eXBlIElOICgnZGVyaXZlZF9mcm9tJywnYWNxdWlyZWRfYXMnLCdwYXJzZWRfZnJvbScsJ2V4Y2VycHRlZF9mcm9tJykpLCBQUklNQVJZIEtFWShhcnRpZmFjdF9pZCwgaW5wdXRfYXJ0aWZhY3RfaWQpKTsKQ1JFQVRFIElOREVYIGFydGlmYWN0X2xpbmVhZ2VfaW5wdXRfaWR4IE9OIGFydGlmYWN0X2xpbmVhZ2UoaW5wdXRfYXJ0aWZhY3RfaWQpOwpDUkVBVEUgVEFCTEUgZXZpZGVuY2VfbG9jYXRvcnMgKGV2' 'aWRlbmNlX2xvY2F0b3JfaWQgVEVYVCBQUklNQVJZIEtFWSwgYXJ0aWZhY3RfaWQgVEVYVCwgc291cmNlX3JlY29yZF9pZCBURVhULCBraW5kIFRFWFQgTk9UIE5VTEwgQ0hFQ0soa2luZCBJTiAoJ3N0cnVjdHVyZWRfZmllbGQnLCd0ZXh0X3NwYW4nLCdkb2N1bWVudCcpKSwgbG9jYXRvcl9qc29uIFRFWFQgTk9UIE5VTEwsIG1hdGVyaWFsX2hhc2ggVEVYVCBOT1QgTlVMTCwgY3JlYXRlZF9hdCBURVhUIE5PVCBOVUxMLCBDSEVDSyhhcnRpZmFjdF9pZCBJUyBOT1QgTlVMTCBPUiBzb3VyY2VfcmVjb3JkX2lkIElTIE5PVCBOVUxMKSk7CkNSRUFURSBJTkRFWCBldmlkZW5jZV9sb2NhdG9yX2FydGlmYWN0X2lkeCBPTiBldmlkZW5jZV9sb2NhdG9ycyhhcnRpZmFj' 'dF9pZCk7CkNSRUFURSBJTkRFWCBldmlkZW5jZV9sb2NhdG9yX3NvdXJjZV9pZHggT04gZXZpZGVuY2VfbG9jYXRvcnMoc291cmNlX3JlY29yZF9pZCk7CkNSRUFURSBJTkRFWCBhcnRpZmFjdF9pbmRleF9jb250ZW50X2lkeCBPTiBhcnRpZmFjdF9pbmRleChjb250ZW50X2hhc2gpOw==').decode('utf-8')
MIGRATIONS = (Migration(1, 'initial_operational_catalogue', CATALOGUE_SQL_V1), Migration(2, 'source_evidence_foundation', CATALOGUE_SQL_V2))
SUPPORTED_VERSION = MIGRATIONS[-1].version
