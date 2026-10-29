import builtins
import hashlib
import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from charitygraph.contracts.canonical import canonical_json_bytes
from charitygraph.phase5_t4a_project_budget_snapshot import (
    ACCOUNTING_EVIDENCE_SCHEMA,
    COVERAGE_MANIFEST_SCHEMA,
    PROJECT_BUDGET_SNAPSHOT_SCHEMA,
    build_project_budget_snapshot,
)


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
AS_OF = "2026-10-29T00:00:00Z"
PROJECT = "charitygraph-project"


def provenance(source_id):
    return [{"source_id": source_id, "source_kind": "durable-catalogue-export", "content_sha256": hashlib.sha256(source_id.encode()).hexdigest()}]


def manifest(*, physical=True, coverage=None, as_of=AS_OF):
    coverage = coverage or {
        "project_wide": True,
        "logical_paid_tasks_complete": True,
        "retries_complete": True,
        "physical_attempts_complete": True,
        "cohorts_complete": True,
        "accounting_sources_complete": True,
        "reservations_complete": True,
        "actuals_complete": True,
        "pricing_complete": True,
    }
    physical_rows = [
        {"physical_attempt_id": "physical:a", "cohort_id": "cohort:a", "logical_task_ids": ["task:a"], "scope": "project/paid", "source_provenance": provenance("manifest:physical")}
    ] if physical else []
    return {
        "schema_id": COVERAGE_MANIFEST_SCHEMA,
        "manifest_id": "manifest:project:1",
        "manifest_version": "1",
        "project_id": PROJECT,
        "as_of": as_of,
        "authority": {"authority_id": "authority:ledger", "authority_version": "2026-10-29", "source_provenance": provenance("authority:ledger")},
        "coverage_semantics": {
            "scope": "all paid work in the project",
            "logical_paid_tasks": "every logical paid task",
            "retries": "every task retry",
            "physical_attempts": "every physical provider attempt",
            "cohorts": "every accounting cohort",
            "accounting_sources": "every durable accounting source",
            "reservations": "every reservation and release",
            "actuals": "every actual, credit and adjustment",
            "pricing": "every priced actual has pricing and FX identities",
        },
        "coverage": coverage,
        "accounting_sources": [{"source_id": "source:catalogue", "source_type": "runtime-catalogue", "content_sha256": "a" * 64, "scope": "project", "source_provenance": provenance("source:catalogue")}],
        "cohorts": [
            {"cohort_id": "cohort:a", "accounting_source_ids": ["source:catalogue"], "scope": "project/cohort-a", "source_provenance": provenance("manifest:cohort-a")},
            {"cohort_id": "cohort:b", "accounting_source_ids": ["source:catalogue"], "scope": "project/cohort-b", "source_provenance": provenance("manifest:cohort-b")},
        ],
        "logical_paid_tasks": [
            {"logical_task_id": "task:a", "cohort_id": "cohort:a", "scope": "subject:a", "source_provenance": provenance("manifest:task-a")},
            {"logical_task_id": "task:b", "cohort_id": "cohort:b", "scope": "subject:b", "source_provenance": provenance("manifest:task-b")},
        ],
        "retries": [
            {"task_run_id": "taskrun:a:1", "logical_task_id": "task:a", "attempt_number": 1, "physical_attempt_ids": ["physical:a"], "scope": "subject:a", "source_provenance": provenance("manifest:retry-a1")},
            {"task_run_id": "taskrun:a:2", "logical_task_id": "task:a", "attempt_number": 2, "physical_attempt_ids": ["physical:a"], "scope": "subject:a", "source_provenance": provenance("manifest:retry-a2")},
            {"task_run_id": "taskrun:b:1", "logical_task_id": "task:b", "attempt_number": 1, "physical_attempt_ids": [], "scope": "subject:b", "source_provenance": provenance("manifest:retry-b1")},
        ],
        "physical_attempts": physical_rows,
        "reservation_ids": ["reservation:a", "reservation:b"],
        "cost_entry_ids": ["cost:actual-a", "cost:actual-b", "cost:release-a"],
    }


def evidence(*, physical_status="validated", as_of=AS_OF, priced=True):
    actual_a = {"entry_key": "cost:actual-a", "cohort_id": "cohort:a", "run_id": "run:a", "task_run_id": "taskrun:a:1", "reservation_id": "reservation:a", "entry_type": "actual", "accounting_amount": "1.25", "accounting_currency": "AUD", "physical_attempt_id": "physical:a", "pricing_snapshot_id": "pricing:1" if priced else None, "fx_snapshot_id": "fx:1" if priced else None}
    return {
        "schema_id": ACCOUNTING_EVIDENCE_SCHEMA,
        "evidence_id": "evidence:catalogue:1",
        "evidence_version": "1",
        "project_id": PROJECT,
        "as_of": as_of,
        "source_provenance": provenance("source:catalogue"),
        "runs": [
            {"run_id": "run:a", "cohort_id": "cohort:a", "scope": "project/cohort-a", "source_provenance": provenance("evidence:run-a")},
            {"run_id": "run:b", "cohort_id": "cohort:b", "scope": "project/cohort-b", "source_provenance": provenance("evidence:run-b")},
        ],
        "cohorts": [
            {"cohort_id": "cohort:a", "accounting_currency": "AUD", "scope": "project/cohort-a", "source_provenance": provenance("evidence:cohort-a")},
            {"cohort_id": "cohort:b", "accounting_currency": "AUD", "scope": "project/cohort-b", "source_provenance": provenance("evidence:cohort-b")},
        ],
        "logical_tasks": [
            {"model_task_id": "task:a", "run_id": "run:a", "cohort_id": "cohort:a", "scope_id": "subject:a", "source_provenance": provenance("evidence:task-a")},
            {"model_task_id": "task:b", "run_id": "run:b", "cohort_id": "cohort:b", "scope_id": "subject:b", "source_provenance": provenance("evidence:task-b")},
        ],
        "task_attempts": [
            {"task_run_id": "taskrun:a:1", "model_task_id": "task:a", "attempt_number": 1, "status": "failed_retryable"},
            {"task_run_id": "taskrun:a:2", "model_task_id": "task:a", "attempt_number": 2, "status": "succeeded"},
            {"task_run_id": "taskrun:b:1", "model_task_id": "task:b", "attempt_number": 1, "status": "succeeded"},
        ],
        "reservations": [
            {"reservation_id": "reservation:a", "cohort_id": "cohort:a", "run_id": "run:a", "reserved_amount": "2.00", "status": "partially_consumed", "accounting_currency": "AUD"},
            {"reservation_id": "reservation:b", "cohort_id": "cohort:b", "run_id": "run:b", "reserved_amount": "3.00", "status": "active", "accounting_currency": "AUD"},
        ],
        "cost_entries": [
            actual_a,
            {"entry_key": "cost:actual-b", "cohort_id": "cohort:b", "run_id": "run:b", "task_run_id": "taskrun:b:1", "reservation_id": "reservation:b", "entry_type": "actual", "accounting_amount": "0.75", "accounting_currency": "AUD", "pricing_snapshot_id": "pricing:2", "fx_snapshot_id": "fx:2"},
            {"entry_key": "cost:release-a", "cohort_id": "cohort:a", "run_id": "run:a", "task_run_id": None, "reservation_id": "reservation:a", "entry_type": "reservation_release", "accounting_amount": "0.25", "accounting_currency": "AUD"},
        ],
        "physical_attempts": [
            {"physical_attempt_id": "physical:a", "run_id": "run:a", "cohort_id": "cohort:a", "reservation_id": "reservation:a", "status": physical_status},
        ],
        "provider_request_attempts": [
            {"delivery_attempt_id": "delivery:a:1", "provider_request_item_id": "item:a", "physical_attempt_id": "physical:a", "attempt_ordinal": 1, "status": "failed"},
            {"delivery_attempt_id": "delivery:a:2", "provider_request_item_id": "item:a", "physical_attempt_id": "physical:a", "attempt_ordinal": 2, "status": "completed"},
        ],
    }


def build(e=None, m=None, **kwargs):
    return build_project_budget_snapshot(evidence() if e is None else e, manifest() if m is None else m, project_id=PROJECT, now=NOW, **kwargs)


def test_cross_cohort_reconciliation_and_retry_physical_deduplication():
    result = build()
    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert result.actual_aud == Decimal("2.00")
    assert result.outstanding_reservations_aud == Decimal("2.75")
    assert result.pending_or_ambiguous_physical_attempt_ids == ()
    assert result.unpriced_physical_attempt_ids == ()
    assert result.snapshot_sha256 == hashlib.sha256(result.snapshot_bytes).hexdigest()


def test_ambiguous_pending_and_unpriced_attempts_fail_closed():
    ambiguous = evidence(physical_status="held")
    result = build(ambiguous)
    assert result.status == "INCOMPLETE_OR_UNKNOWN"
    assert result.pending_or_ambiguous_physical_attempt_ids == ("physical:a",)
    assert "unresolved_physical_attempts_present" in result.reasons

    unpriced = evidence(priced=False)
    unpriced["physical_attempts"][0]["status"] = "validated"
    result = build(unpriced)
    assert result.status == "INCOMPLETE_OR_UNKNOWN"
    assert result.unpriced_physical_attempt_ids == ("physical:a",)


def test_missing_manifest_and_missing_physical_evidence_are_unknown():
    result = build_project_budget_snapshot(evidence(), None, project_id=PROJECT, now=NOW)
    assert result.status == "INCOMPLETE_OR_UNKNOWN"
    assert "coverage_manifest_missing_or_invalid" in result.reasons

    no_physical = evidence()
    no_physical["physical_attempts"] = []
    result = build(no_physical, manifest(physical=False))
    assert result.status == "INCOMPLETE_OR_UNKNOWN"
    assert "physical_attempt_evidence_empty" in result.reasons


def test_stale_and_contradictory_evidence_fail_closed():
    stale = build(evidence(as_of="2026-10-27T00:00:00Z"), manifest(as_of="2026-10-27T00:00:00Z"))
    assert "accounting_evidence_stale" in stale.reasons

    contradictory = evidence()
    contradictory["logical_tasks"][1]["cohort_id"] = "cohort:a"
    result = build(contradictory)
    assert result.status == "INCOMPLETE_OR_UNKNOWN"
    assert any(reason.startswith("logical_task_cross_cohort_mismatch") for reason in result.reasons)


def test_manifest_coverage_and_decimal_amounts_fail_closed():
    incomplete = manifest(coverage={"project_wide": True})
    result = build(m= incomplete)
    assert "coverage_manifest_assertion_invalid" in result.reasons

    negative = evidence()
    negative["cost_entries"][0]["accounting_amount"] = "-1"
    result = build(negative)
    assert "accounting_amount_negative" in result.reasons


def test_deterministic_canonical_replay_and_no_side_effects(monkeypatch):
    first = build()
    shuffled_evidence = evidence()
    for key in ("cost_entries", "physical_attempts", "provider_request_attempts", "logical_tasks", "task_attempts", "cohorts", "runs", "reservations"):
        shuffled_evidence[key] = list(reversed(shuffled_evidence[key]))
    second = build(shuffled_evidence)
    assert first.snapshot_bytes == second.snapshot_bytes
    assert first.snapshot_sha256 == second.snapshot_sha256
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("filesystem")))
    assert build().snapshot_bytes == first.snapshot_bytes

