import builtins
import hashlib
import json
import socket
from datetime import datetime, timezone

from charitygraph.contracts.canonical import canonical_json_bytes
from charitygraph.phase5_t4a8_durable_accounting_export import (
    ReadOnlyDurableAccountingView,
    build_durable_accounting_source_export,
)


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
PROJECT = "charitygraph-project"
SOURCE_HASH = "a" * 64


def provenance(source_id, *, source_hash=None):
    return [{
        "source_id": source_id,
        "source_kind": "runtime-catalogue",
        "content_sha256": SOURCE_HASH if source_hash is None else source_hash,
    }]


def authority():
    return {
        "source_id": "source:runtime-catalogue",
        "source_kind": "runtime-catalogue",
        "source_version": "catalogue-v29-readonly-2026-10-29",
        "content_sha256": SOURCE_HASH,
        "authority_id": "authority:runtime-accounting",
        "authority_version": "2026-10-29",
        "retention_id": "retention:private-analytical-runtime",
        "retention_version": "1",
        "retention_status": "authorized",
    }


def coverage():
    return {
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


def manifest(*, coverage_override=None):
    return {
        "schema_id": "charitygraph.project-wide-paid-work-coverage-manifest/1",
        "manifest_id": "manifest:project:1",
        "manifest_version": "1",
        "project_id": PROJECT,
        "as_of": "2026-10-29T00:00:00Z",
        "authority": {
            "authority_id": "authority:runtime-accounting",
            "authority_version": "2026-10-29",
            "source_provenance": provenance("source:runtime-catalogue"),
        },
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
        "coverage": coverage() if coverage_override is None else coverage_override,
        "accounting_sources": [{
            "source_id": "source:runtime-catalogue",
            "source_type": "runtime-catalogue",
            "content_sha256": SOURCE_HASH,
            "scope": "project",
            "source_provenance": provenance("source:runtime-catalogue"),
        }],
        "cohorts": [
            {"cohort_id": "cohort:a", "accounting_source_ids": ["source:runtime-catalogue"], "scope": "project/cohort-a", "source_provenance": provenance("manifest:cohort-a")},
            {"cohort_id": "cohort:b", "accounting_source_ids": ["source:runtime-catalogue"], "scope": "project/cohort-b", "source_provenance": provenance("manifest:cohort-b")},
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
        "physical_attempts": [{"physical_attempt_id": "physical:a", "cohort_id": "cohort:a", "logical_task_ids": ["task:a"], "scope": "subject:a", "source_provenance": provenance("manifest:physical-a")}],
        "reservation_ids": ["reservation:a", "reservation:b"],
        "cost_entry_ids": ["cost:actual-a", "cost:actual-b", "cost:release-a"],
    }


def evidence(*, physical_status="validated", priced=True):
    source_provenance = provenance("source:runtime-catalogue")
    actual_a = {
        "entry_key": "cost:actual-a", "cohort_id": "cohort:a", "run_id": "run:a", "task_run_id": "taskrun:a:1",
        "reservation_id": "reservation:a", "entry_type": "actual", "accounting_amount": "1.25", "accounting_currency": "AUD",
        "physical_attempt_id": "physical:a", "pricing_snapshot_id": "pricing:1" if priced else None, "fx_snapshot_id": "fx:1" if priced else None,
    }
    return {
        "schema_id": "charitygraph.durable-accounting-evidence/1",
        "evidence_id": "evidence:catalogue:1", "evidence_version": "1", "project_id": PROJECT,
        "as_of": "2026-10-29T00:00:00Z", "source_provenance": source_provenance,
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
            {"entry_key": "cost:actual-b", "cohort_id": "cohort:b", "run_id": "run:b", "task_run_id": "taskrun:b:1", "reservation_id": "reservation:b", "entry_type": "actual", "accounting_amount": "0.75", "accounting_currency": "AUD", "pricing_snapshot_id": "pricing:2" if priced else None, "fx_snapshot_id": "fx:2" if priced else None},
            {"entry_key": "cost:release-a", "cohort_id": "cohort:a", "run_id": "run:a", "task_run_id": None, "reservation_id": "reservation:a", "entry_type": "reservation_release", "accounting_amount": "0.25", "accounting_currency": "AUD"},
        ],
        "physical_attempts": [{"physical_attempt_id": "physical:a", "run_id": "run:a", "cohort_id": "cohort:a", "reservation_id": "reservation:a", "status": physical_status}],
        "provider_request_attempts": [
            {"delivery_attempt_id": "delivery:a:1", "provider_request_item_id": "item:a", "physical_attempt_id": "physical:a", "attempt_ordinal": 1, "status": "failed"},
            {"delivery_attempt_id": "delivery:a:2", "provider_request_item_id": "item:a", "physical_attempt_id": "physical:a", "attempt_ordinal": 2, "status": "completed"},
        ],
    }


def view(e=None, m=None, a=None):
    return ReadOnlyDurableAccountingView(a or authority(), evidence() if e is None else e, manifest() if m is None else m)


def build(source=None):
    return build_durable_accounting_source_export(source or view(), project_id=PROJECT, now=NOW)


def test_all_cohorts_and_retries_reconcile_without_double_counting_physical_attempt():
    result = build()

    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert result.candidate.actual_aud == 2
    assert result.candidate.outstanding_reservations_aud == 2.75
    assert result.pricing_fx_identity_ids == (("pricing:1", "fx:1"), ("pricing:2", "fx:2"))
    inventory = {item["record_class"]: item for item in result.source_inventory}
    assert inventory["cohorts"]["row_count"] == 2
    assert inventory["task_attempts"]["row_count"] == 3
    assert inventory["physical_attempts"]["row_count"] == 1
    assert result.candidate_sha256 == hashlib.sha256(result.candidate_bytes).hexdigest()


def test_duplicate_record_is_not_attestable_and_ambiguous_is_blocked():
    duplicate = evidence()
    duplicate["cost_entries"].append(dict(duplicate["cost_entries"][0]))
    duplicate_result = build(view(e=duplicate))
    assert duplicate_result.status == "NOT_ATTESTABLE"
    assert "source_record_duplicate:cost_entries:cost:actual-a" in duplicate_result.reasons

    ambiguous_result = build(view(e=evidence(physical_status="held")))
    assert ambiguous_result.status == "BLOCKED"
    assert "unresolved_physical_attempts_present" in ambiguous_result.reasons


def test_unpriced_and_missing_coverage_fail_closed():
    unpriced_result = build(view(e=evidence(priced=False)))
    assert unpriced_result.status == "BLOCKED"
    assert "unpriced_physical_attempts_present" in unpriced_result.reasons
    assert unpriced_result.pricing_fx_identity_ids == ()

    incomplete = coverage()
    incomplete["actuals_complete"] = False
    missing_coverage_result = build(view(m=manifest(coverage_override=incomplete)))
    assert missing_coverage_result.status == "NOT_ATTESTABLE"
    assert "coverage_manifest_incomplete" in missing_coverage_result.reasons


def test_missing_source_or_retention_identity_is_not_attestable():
    missing = authority()
    del missing["retention_id"]
    result = build(view(a=missing))
    assert result.status == "NOT_ATTESTABLE"
    assert "source_authority_field_missing:retention_id" in result.reasons

    unavailable = authority()
    unavailable["retention_status"] = "unknown"
    result = build(view(a=unavailable))
    assert result.status == "NOT_ATTESTABLE"
    assert "source_retention_not_authorized" in result.reasons


def test_candidate_hash_is_not_an_independent_pin_and_replay_is_deterministic():
    first = build()
    shuffled = evidence()
    for key in ("cost_entries", "physical_attempts", "provider_request_attempts", "logical_tasks", "task_attempts", "cohorts", "runs", "reservations"):
        shuffled[key] = list(reversed(shuffled[key]))
    second = build(view(e=shuffled))

    assert first.candidate_bytes == second.candidate_bytes
    assert first.candidate_sha256 == second.candidate_sha256
    assert first.independent_trust == "NOT_SUPPLIED"
    assert first.request_ticket is None
    assert first.send_authorization == "not_authorized_for_send"
    candidate_document = json.loads(first.candidate_bytes)
    assert candidate_document["attestation"]["independent_trust"] == "NOT_SUPPLIED"
    assert "trusted_sha256" not in candidate_document["attestation"]


def test_unknown_physical_status_is_blocked_and_not_silently_counted_as_terminal():
    result = build(view(e=evidence(physical_status="unknown_status")))

    assert result.status == "BLOCKED"
    assert "physical_attempt_status_unknown:physical:a" in result.reasons


def test_adapter_has_no_filesystem_network_or_provider_mutation(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("filesystem")))

    before = json.dumps(evidence(), sort_keys=True)
    result = build()
    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert json.dumps(evidence(), sort_keys=True) == before


def test_noncanonical_bytes_and_source_binding_fail_closed():
    raw = canonical_json_bytes(evidence())
    noncanonical = raw.replace(b" ", b"", 1) if b" " in raw else raw + b" "
    result = build(view(e=noncanonical))
    assert result.status == "NOT_ATTESTABLE"
    assert "accounting_evidence_invalid:non_canonical" in result.reasons

    unbound = evidence()
    unbound["source_provenance"] = provenance("other-source", source_hash="b" * 64)
    result = build(view(e=unbound))
    assert result.status == "NOT_ATTESTABLE"
    assert "accounting_evidence_source_binding_missing" in result.reasons
