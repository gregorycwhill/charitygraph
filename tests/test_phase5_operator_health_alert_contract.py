from __future__ import annotations

import copy
import json

from charitygraph.phase5_operator_health_alert_contract import (
    SCHEMA,
    AlertDisposition,
    AlertSeverity,
    ObservationState,
    canonical_operator_health_alert_json,
    operator_health_alert_sha256,
    project_phase5_operator_health_alerts,
)


def _export(*, flags=None, usage_state="observed", budget=True, records=None, reverse=False):
    records = records or {
        "runs": [{"run_id": "run:1", "status": "succeeded"}],
        "tasks": [{"model_task_id": "task:1", "run_id": "run:1", "subject_id": "subject:1", "scope_id": "scope:1", "status": "succeeded"}],
        "requests": [{"provider_request_item_id": "request:1", "run_id": "run:1", "model_task_id": "task:1", "status": "completed", "submitted_at": "2026-11-01T10:00:00Z", "provider_receipt_id": "receipt:1"}],
        "attempts": [{"delivery_attempt_id": "attempt:1", "provider_request_item_id": "request:1", "run_id": "run:1", "model_task_id": "task:1", "attempt_ordinal": 1, "status": "completed"}],
        "receipts": [{"provider_receipt_id": "receipt:1", "physical_attempt_id": "physical:1", "run_id": "run:1", "usage_coverage_state": "observed", "usage": {"input_tokens": 3, "output_tokens": 2}}],
        "reservations": [{"reservation_id": "reservation:1", "run_id": "run:1", "status": "active", "reserved_amount": "2", "accounting_currency": "AUD"}],
        "cost_entries": [{"entry_key": "cost:1", "run_id": "run:1", "entry_type": "actual", "provider_receipt_id": "receipt:1", "accounting_amount": "1", "accounting_currency": "AUD"}],
    }
    if reverse:
        records = {key: list(reversed(value)) for key, value in records.items()}
    health = {
        "schema": "charitygraph.phase5.operator-health/v1",
        "schema_version": 1,
        "diagnostic_identity": {"snapshot_source_id": "source:runtime", "snapshot_source_version": "source:v1"},
        "scope": {"source_ids": ["source:runtime"], "run_ids": ["run:1"], "evidence_basis": "synthetic structured runtime rows", "as_of": "2026-11-01T12:00:00Z"},
        "flags": flags or {"ambiguous": [], "failed": [], "retry": [], "recovery": [], "stalled": []},
        "provider_usage": {"state": usage_state},
        "cost": {
            "ledger_state": "observed" if budget else "missing",
            "committed_reserved": {"state": "committed_reserved" if budget else "missing"},
            "provenance": {"ledger_source_id": "ledger:1" if budget else None, "ledger_version": "ledger:v1" if budget else None, "ledger_as_of": "2026-11-01T12:00:00Z" if budget else None},
        },
        "per_run": [{"run_id": "run:1", "subject_ids": ["subject:1"], "scope_ids": ["scope:1"]}],
    }
    return {
        "schema": "charitygraph.phase5.operator-health-runtime-contract/v1",
        "schema_version": 1,
        "operator_health": health,
        "persisted_representation": {
            "schema": "charitygraph.phase5.persisted-runtime-safe-view/v1",
            "source_lineage": {"source_id": "source:runtime", "source_version": "source:v1", "evidence_basis": "synthetic structured runtime rows"},
            "records": records,
        },
    }


def test_healthy_real_format_export_has_no_alerts_and_is_canonical():
    result = project_phase5_operator_health_alerts(_export())
    assert result.document["schema"] == SCHEMA
    assert result.document["alerts"] == []
    assert result.document["summary"] == {"alert_count": 0, "observed_event_denominator": 1, "rate": None, "rate_state": "NOT_COMPUTED_NO_SLO_POLICY"}
    assert result.canonical_json == canonical_operator_health_alert_json(result)
    assert result.sha256 == operator_health_alert_sha256(result)


def test_terminal_and_ambiguous_crossings_stop_resend_with_evidence():
    export = _export(flags={
        "ambiguous": [{"id": "request:amb", "run_id": "run:1"}],
        "failed": [{"id": "request:1", "run_id": "run:1"}],
        "retry": [], "recovery": [], "stalled": [],
    })
    export["persisted_representation"]["records"]["requests"].append({
        "provider_request_item_id": "request:amb", "run_id": "run:1", "model_task_id": "task:1", "status": "send_ambiguous", "send_started_at": "2026-11-01T10:00:00Z",
    })
    result = project_phase5_operator_health_alerts(export)
    stop = [alert for alert in result.document["alerts"] if alert["disposition"] == AlertDisposition.STOP_RESEND.value]
    assert {alert["reason_code"] for alert in stop} == {"AMBIGUOUS_PROVIDER_CROSSING", "TERMINAL_FAILURE_AFTER_PROVIDER_CROSSING"}
    assert all(alert["run_ids"] == ["run:1"] for alert in stop)
    assert any(alert["task_ids"] == ["task:1"] for alert in stop)


def test_pre_send_retry_isolated_without_duplicate_dispatch_claim():
    export = _export(flags={"ambiguous": [], "failed": [], "retry": [{"id": "attempt:retry", "run_id": "run:1", "attempt_number": 2}], "recovery": [], "stalled": []})
    export["persisted_representation"]["records"]["attempts"].append({
        "delivery_attempt_id": "attempt:retry", "provider_request_item_id": "request:1", "run_id": "run:1", "model_task_id": "task:1", "attempt_ordinal": 2, "status": "failed", "failure_class": "pre_send_validation",
    })
    result = project_phase5_operator_health_alerts(export)
    alert = next(alert for alert in result.document["alerts"] if alert["family"] == "retryable_task_isolation")
    assert alert["disposition"] == AlertDisposition.ISOLATE_TASK.value
    assert "dispatch" not in alert["suggested_follow_up"].lower()


def test_missing_usage_and_budget_are_unverified_not_zero():
    result = project_phase5_operator_health_alerts(_export(usage_state="missing", budget=False))
    families = {alert["family"] for alert in result.document["alerts"]}
    assert {"provider_usage_unverified", "authoritative_budget_unverified"} <= families
    assert all(alert["disposition"] == AlertDisposition.PREVENT_SPEND_ASSUMPTION.value for alert in result.document["alerts"])
    encoded = result.canonical_json.decode()
    assert '"input_tokens":0' not in encoded
    assert '"amount":0' not in encoded


def test_staleness_is_unverified_for_caller_created_clock_and_observed_for_trusted_clock():
    flags = {"ambiguous": [], "failed": [], "retry": [], "recovery": [], "stalled": [{"id": "request:1", "run_id": "run:1"}]}
    unverified = project_phase5_operator_health_alerts(_export(flags=flags), threshold_policy={"policy_id": "policy:test", "policy_version": "2", "thresholds": {"stale_after_seconds": 60}})
    stale = next(alert for alert in unverified.document["alerts"] if alert["family"] == "host_or_run_staleness")
    assert stale["observation_state"] == ObservationState.UNVERIFIED.value
    trusted_export = _export(flags=flags)
    trusted_export["operator_health"]["timestamp_provenance"] = {"state": "durable"}
    trusted = project_phase5_operator_health_alerts(trusted_export, threshold_policy={"policy_id": "policy:test", "policy_version": "2", "thresholds": {"stale_after_seconds": 60}})
    assert next(alert for alert in trusted.document["alerts"] if alert["family"] == "host_or_run_staleness")["observation_state"] == ObservationState.OBSERVED.value


def test_mixed_subject_scope_duplicate_events_and_reordering_have_stable_sha():
    left = _export(flags={"ambiguous": [{"id": "request:1", "run_id": "run:1"}, {"id": "request:1", "run_id": "run:1"}], "failed": [], "retry": [], "recovery": [], "stalled": []})
    left["persisted_representation"]["records"]["tasks"].append({"model_task_id": "task:2", "run_id": "run:1", "subject_id": "subject:2", "scope_id": "scope:2", "status": "succeeded"})
    right = copy.deepcopy(left)
    right["persisted_representation"]["records"] = {key: list(reversed(value)) for key, value in right["persisted_representation"]["records"].items()}
    first = project_phase5_operator_health_alerts(left)
    second = project_phase5_operator_health_alerts(right)
    assert first.canonical_json == second.canonical_json
    assert first.sha256 == second.sha256
    assert len([a for a in first.document["alerts"] if a["family"] == "provider_crossing_ambiguous"]) == 1
    assert first.document["alerts"][0]["subject_ids"] == ["subject:1"]
    assert first.document["alerts"][0]["scope_ids"] == ["scope:1"]


def test_private_nested_runtime_material_is_not_projected():
    export = _export()
    export["persisted_representation"]["records"]["tasks"][0]["task_material"] = {"sentinel": "PRIVATE-NESTED-SENTINEL"}
    export["persisted_representation"]["records"]["requests"][0]["response_body"] = "PRIVATE-RESPONSE-SENTINEL"
    result = project_phase5_operator_health_alerts(export)
    assert "PRIVATE-NESTED-SENTINEL" not in result.canonical_json.decode()
    assert "PRIVATE-RESPONSE-SENTINEL" not in result.canonical_json.decode()


def test_zero_or_unknown_denominator_is_not_a_zero_rate_and_unsupported_is_explicit():
    empty = _export(records={"runs": [], "tasks": [], "requests": [], "attempts": [], "receipts": [], "reservations": [], "cost_entries": []})
    empty["operator_health"]["scope"]["run_ids"] = []
    empty["operator_health"]["provider_usage"] = {"state": "missing"}
    result = project_phase5_operator_health_alerts(empty)
    assert result.document["summary"]["observed_event_denominator"] is None
    assert result.document["summary"]["rate"] is None
    unsupported = project_phase5_operator_health_alerts({"schema": "provider-native/v99", "private": "sentinel"})
    assert unsupported.document["evaluation_state"] == ObservationState.UNSUPPORTED.value
    assert unsupported.document["alerts"] == []
    assert unsupported.document["diagnostics"][0]["observation_state"] == ObservationState.UNSUPPORTED.value
    assert "sentinel" not in json.dumps(unsupported.document)
