from __future__ import annotations

import json
from decimal import Decimal

import pytest

from charitygraph.phase5_operator_health import (
    SCHEMA,
    OperatorHealthError,
    OperatorHealthSnapshot,
    canonical_operator_health_json,
    operator_health_sha256,
    project_operator_health,
)


AS_OF = "2026-10-31T00:00:00+00:00"


def snapshot(**changes):
    value = {
        "as_of": AS_OF,
        "source_id": "catalog:test",
        "source_version": "sqlite-v29:abc",
        "evidence_basis": "synthetic structured runtime rows",
        "reporting_window_start": "2026-10-30T00:00:00+00:00",
        "reporting_window_end": AS_OF,
        "project_id": "project:test",
        "runs": [],
        "jobs": [],
        "requests": [],
        "tasks": [],
        "attempts": [],
        "receipts": [],
        "reservations": [],
        "cost_entries": [],
        **changes,
    }
    return value


def valid_ledger(**changes):
    return {
        "ledger_source_id": "ledger:test",
        "ledger_version": "ledger-v1",
        "ledger_as_of": AS_OF,
        "ledger_stale_after": "2026-11-01T00:00:00+00:00",
        "ledger_complete": True,
        **changes,
    }


def valid_cost(entry_key="cost:1", receipt="receipt:1", amount="1.20", **extra):
    return {
        "entry_key": entry_key,
        "entry_type": "actual",
        "provider_receipt_id": receipt,
        "provider_amount": "0.80",
        "provider_currency": "USD",
        "accounting_amount": amount,
        "accounting_currency": "AUD",
        "pricing_snapshot_id": "pricing:v1",
        "fx_snapshot_id": "fx:v1",
        "source_id": "ledger:test",
        "source_version": "ledger-v1",
        **extra,
    }


def test_empty_catalog_is_deterministic_and_does_not_turn_missing_cost_into_zero():
    first = project_operator_health(snapshot())
    second = project_operator_health(snapshot())

    assert first.sha256 == second.sha256
    assert first.canonical_json == second.canonical_json
    assert first.document["schema"] == SCHEMA
    assert first.document["status"]["requests"] == {
        "count": 0,
        "status_counts": {},
        "rates": {},
        "denominator_basis": "observed_requests_rows",
    }
    assert first.document["throughput"]["completed_requests_per_observed_second"]["value"] is None
    assert first.document["cost"]["actual"]["state"] == "missing"
    assert first.document["cost"]["actual"]["amount"] is None


def test_missing_timestamps_make_stall_and_throughput_unknown():
    result = project_operator_health(snapshot(
        reporting_window_start=None,
        reporting_window_end=None,
        stalled_after_seconds=60,
        requests=[{"request_item_id": "request:1", "run_id": "run:1", "status": "in_progress"}],
    ))

    assert result.document["throughput"]["completed_requests_per_observed_second"]["value"] is None
    assert result.document["flags"]["stalled"] == []
    codes = {issue["code"] for issue in result.document["issues"]}
    assert {"NO_OBSERVED_ELAPSED_TIME", "STALL_UNDETERMINED"} <= codes


def test_status_rates_use_exact_denominators_and_preserve_failed_ambiguous_jobs():
    result = project_operator_health(snapshot(
        jobs=[{"delivery_job_id": "job:1", "run_id": "run:1", "status": "failed"}],
        requests=[
            {"request_item_id": "request:1", "run_id": "run:1", "status": "completed"},
            {"request_item_id": "request:2", "run_id": "run:1", "status": "send_ambiguous"},
            {"request_item_id": "request:3", "run_id": "run:1", "status": "failed"},
        ],
    ))

    rates = result.document["status"]["requests"]["rates"]
    assert rates["completed"] == {"count": 1, "denominator": 3, "rate": "0.3333333333333333333333333333"}
    assert result.document["flags"]["ambiguous"][0]["id"] == "request:2"
    assert {row["id"] for row in result.document["flags"]["failed"]} == {"job:1", "request:3"}
    assert result.document["status"]["jobs"]["status_counts"] == {"failed": 1}


def test_retry_recovery_and_duplicate_receipt_are_visible_without_double_counting():
    rows = [valid_cost(), valid_cost(entry_key="cost:duplicate", amount="1.20")]
    result = project_operator_health(snapshot(
        **valid_ledger(),
        requests=[{"request_item_id": "request:1", "run_id": "run:1", "status": "completed"}],
        attempts=[
            {"attempt_id": "attempt:1", "run_id": "run:1", "attempt_number": 1},
            {"attempt_id": "attempt:2", "run_id": "run:1", "attempt_number": 2, "predecessor_attempt_id": "attempt:1"},
        ],
        receipts=[{"provider_receipt_id": "receipt:1", "run_id": "run:1"}, {"provider_receipt_id": "receipt:1", "run_id": "run:1"}],
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2.00", "accounting_currency": "AUD"}],
        cost_entries=rows,
    ))

    assert result.document["cost"]["actual"]["amount"] == "1.2"
    assert len(result.document["flags"]["retry"]) == 1
    assert len(result.document["flags"]["recovery"]) == 1
    codes = {issue["code"] for issue in result.document["issues"]}
    assert {"DUPLICATE_RECEIPT_ID", "DUPLICATE_RECEIPT"} <= codes


def test_conflicting_duplicate_receipt_fails_cost_closed():
    result = project_operator_health(snapshot(
        **valid_ledger(),
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2.00", "accounting_currency": "AUD"}],
        cost_entries=[valid_cost(amount="1.20"), valid_cost(entry_key="cost:2", amount="1.30")],
    ))

    assert result.document["cost"]["actual"]["state"] == "ambiguous"
    assert result.document["cost"]["actual"]["amount"] is None
    assert result.document["cost"]["reconciliation"]["state"] == "AMBIGUOUS"


def test_mixed_subjects_scopes_and_source_lineage_remain_run_scoped():
    result = project_operator_health(snapshot(
        runs=[{"run_id": "run:1", "status": "succeeded", "source_id": "source:a"}, {"run_id": "run:2", "status": "failed", "source_id": "source:b"}],
        tasks=[
            {"model_task_id": "task:1", "run_id": "run:1", "subject_id": "subject:a", "scope_id": "scope:a", "status": "succeeded", "source_id": "source:a"},
            {"model_task_id": "task:2", "run_id": "run:2", "subject_id": "subject:b", "scope_id": "scope:b", "status": "failed", "source_id": "source:b"},
        ],
    ))

    assert result.document["scope"]["run_ids"] == ["run:1", "run:2"]
    assert result.document["scope"]["source_ids"] == ["catalog:test", "source:a", "source:b"]
    assert [row["run_id"] for row in result.document["per_run"]] == ["run:1", "run:2"]
    assert result.document["per_run"][0]["source_ids"] == ["source:a"]
    assert result.document["per_run"][1]["source_ids"] == ["source:b"]
    assert all(row["as_of"] == AS_OF for row in result.document["per_run"])


def test_zero_and_non_positive_window_do_not_create_rates_or_throughput_division():
    result = project_operator_health(snapshot(
        reporting_window_start=AS_OF,
        reporting_window_end=AS_OF,
        requests=[{"request_item_id": "request:1", "status": "completed"}],
    ))

    assert result.document["reporting_window"]["elapsed_seconds"] is None
    assert result.document["throughput"]["completed_requests_per_observed_second"]["value"] is None
    assert result.document["status"]["requests"]["rates"]["completed"]["denominator"] == 1
    assert "NON_POSITIVE_WINDOW" in {issue["code"] for issue in result.document["issues"]}


def test_decimal_currency_and_fx_provenance_are_retained():
    result = project_operator_health(snapshot(
        **valid_ledger(),
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": Decimal("2.00"), "accounting_currency": "AUD"}],
        cost_entries=[valid_cost(amount=Decimal("1.20"))],
    ))

    assert result.document["cost"]["actual"]["amount"] == "1.2"
    assert result.document["cost"]["committed_reserved"]["amount"] == "2"
    assert result.document["cost"]["provenance"]["pricing_versions"] == ["pricing:v1"]
    assert result.document["cost"]["provenance"]["fx_versions"] == ["fx:v1"]
    assert result.document["cost"]["reconciliation"]["state"] == "RECONCILED"


def test_latency_scheduling_and_receipt_usage_are_reported_only_from_explicit_evidence():
    result = project_operator_health(snapshot(
        requests=[{
            "request_item_id": "request:1",
            "run_id": "run:1",
            "status": "completed",
            "created_at": "2026-10-30T00:00:00+00:00",
            "scheduled_at": "2026-10-30T00:00:01+00:00",
            "started_at": "2026-10-30T00:00:03+00:00",
            "submitted_at": "2026-10-30T00:00:04+00:00",
            "send_started_at": "2026-10-30T00:00:04+00:00",
            "received_at": "2026-10-30T00:00:08+00:00",
            "completed_at": "2026-10-30T00:00:09+00:00",
        }],
        receipts=[{"provider_receipt_id": "receipt:1", "input_tokens": 10, "output_tokens": 4}],
    ))

    assert result.document["latency"]["queue_wait"]["value"] == "4"
    assert result.document["latency"]["provider_crossing"]["value"] == "4"
    assert result.document["scheduling"]["health"] == "OBSERVED"
    assert result.document["scheduling"]["lag"]["value"] == "2"
    assert result.document["provider_usage"]["input_tokens"] == 10
    assert result.document["provider_usage"]["output_tokens"] == 4


def test_missing_fx_or_negative_amount_is_ambiguous_not_zero():
    result = project_operator_health(snapshot(
        **valid_ledger(),
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2.00", "accounting_currency": "AUD"}],
        cost_entries=[valid_cost(amount="-1.20", fx_snapshot_id=None)],
    ))

    assert result.document["cost"]["actual"]["state"] == "ambiguous"
    assert result.document["cost"]["actual"]["amount"] is None
    assert "INVALID_DECIMAL" in {issue["code"] for issue in result.document["issues"]}


def test_stale_or_missing_project_ledger_keeps_totals_unknown():
    stale = project_operator_health(snapshot(
        **valid_ledger(ledger_stale_after="2026-10-30T00:00:00+00:00"),
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2.00", "accounting_currency": "AUD"}],
        cost_entries=[valid_cost()],
    ))
    missing = project_operator_health(snapshot(
        reservations=[{"reservation_id": "reservation:1", "status": "active", "reserved_amount": "2.00", "accounting_currency": "AUD"}],
        cost_entries=[valid_cost()],
    ))

    assert stale.document["cost"]["ledger_state"] == "stale"
    assert stale.document["cost"]["actual"]["amount"] is None
    assert missing.document["cost"]["ledger_state"] == "missing"
    assert missing.document["cost"]["actual"]["state"] == "missing"


def test_serialization_is_canonical_and_provider_free(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: pytest.fail("operator health must not open files"))
    projection = project_operator_health(snapshot())

    assert projection.canonical_json == canonical_operator_health_json(projection)
    assert projection.sha256 == operator_health_sha256(projection)
    assert json.loads(projection.canonical_json)["schema"] == SCHEMA
    assert "provider invocation" in " ".join(projection.document["limitations"])


def test_adapter_accepts_existing_persisted_run_shape_without_catalog_access():
    persisted = {
        "snapshot_observed_at": AS_OF,
        "database_path": "sqlite:fixture",
        "snapshot_hash": "hash:fixture",
        "run_record": {"run_id": "run:1", "status": "succeeded"},
        "ledger_snapshot": {"tasks": [], "attempts": [], "receipts": [], "reservations": [], "cost_entries": []},
    }

    result = project_operator_health(persisted)
    assert result.document["scope"]["run_ids"] == ["run:1"]
    assert result.document["diagnostic_identity"]["snapshot_source_version"] == "hash:fixture"


def test_rejects_float_input_before_any_diagnostic_work():
    with pytest.raises(OperatorHealthError, match="binary floating-point"):
        project_operator_health(snapshot(requests=[{"request_item_id": "request:1", "ratio": 0.5}]))
