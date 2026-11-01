"""Pure, read-only alert projection for the Phase-5 operator-health export.

This module consumes the existing ``operator_health`` document and, when
available, its ``persisted_representation.records`` safe view.  It does not
read a catalogue, contact a provider, schedule work, or mutate runtime state.
Only structured identifiers, statuses, timestamps and provenance are used;
arbitrary runtime payloads are never copied into the result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


SCHEMA_ID = "charitygraph.phase5.operator-health-alert-contract"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"


class AlertContractError(ValueError):
    """Raised for an invalid threshold policy, not for missing observations."""


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class AlertDisposition(str, Enum):
    STOP_RESEND = "STOP_RESEND"
    PREVENT_SPEND_ASSUMPTION = "PREVENT_SPEND_ASSUMPTION"
    ISOLATE_TASK = "ISOLATE_TASK"
    REVIEW_UNVERIFIED = "REVIEW_UNVERIFIED"


class ObservationState(str, Enum):
    OBSERVED = "OBSERVED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class AlertThresholdPolicy:
    """Versioned, mechanical thresholds supplied by the operator.

    ``stale_after_seconds`` is intentionally optional.  A value is applied
    only when the export carries explicit trusted clock provenance; the
    existing caller-created ``as_of`` timestamp is not sufficient.
    """

    policy_id: str = "phase5.operator-health-alerts"
    policy_version: str = "1"
    stale_after_seconds: int | None = None
    retryable_attempt_number: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise AlertContractError("policy_id must be a non-empty string")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise AlertContractError("policy_version must be a non-empty string")
        if self.stale_after_seconds is not None and (
            not isinstance(self.stale_after_seconds, int)
            or isinstance(self.stale_after_seconds, bool)
            or self.stale_after_seconds < 0
        ):
            raise AlertContractError("stale_after_seconds must be a non-negative integer or null")
        if not isinstance(self.retryable_attempt_number, int) or isinstance(self.retryable_attempt_number, bool) or self.retryable_attempt_number < 0:
            raise AlertContractError("retryable_attempt_number must be a non-negative integer")
        if self.retryable_attempt_number < 2:
            raise AlertContractError("retryable_attempt_number must be at least 2")

    @classmethod
    def from_input(cls, value: "AlertThresholdPolicy | Mapping[str, Any] | None") -> "AlertThresholdPolicy":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise AlertContractError("threshold_policy must be a versioned mapping")
        thresholds = value.get("thresholds")
        if thresholds is None:
            thresholds = value
        if not isinstance(thresholds, Mapping):
            raise AlertContractError("threshold_policy.thresholds must be a mapping")
        policy_id = value.get("policy_id", value.get("id", cls.policy_id))
        policy_version = value.get("policy_version", value.get("version"))
        if policy_version is None:
            raise AlertContractError("threshold_policy requires policy_version")
        return cls(
            policy_id=policy_id,
            policy_version=str(policy_version),
            stale_after_seconds=thresholds.get("stale_after_seconds"),
            retryable_attempt_number=thresholds.get("retryable_attempt_number", 2),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "thresholds": {
                "stale_after_seconds": self.stale_after_seconds,
                "retryable_attempt_number": self.retryable_attempt_number,
            },
        }


@dataclass(frozen=True)
class OperatorHealthAlertProjection:
    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


_FAILURE_STATUSES = {"failed", "failed_terminal", "rejected", "provider_rejected", "cancelled", "expired"}
_CROSSING_STATUSES = {
    "crossing_started",
    "provider_crossing_ambiguous",
    "provider_rejected",
    "provider_response_received",
    "completed",
    "validated",
    "receipt_persisted",
}
_ACTIVE_STATUSES = {"planned", "ready", "leased", "running", "prepared", "submitted", "in_progress", "send_started"}
_RECORD_GROUPS = ("runs", "jobs", "requests", "tasks", "attempts", "task_attempts", "physical", "receipts", "reservations", "cost_entries")


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(child) for child in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _record_id(row: Mapping[str, Any], group: str) -> str | None:
    names = {
        "requests": ("provider_request_item_id", "request_item_id", "request_id", "id"),
        "attempts": ("delivery_attempt_id", "attempt_id", "task_run_id", "id"),
        "task_attempts": ("task_run_id", "attempt_id", "id"),
        "tasks": ("model_task_id", "task_id", "id"),
        "receipts": ("provider_receipt_id", "receipt_id", "id"),
        "runs": ("run_id", "id"),
        "jobs": ("delivery_job_id", "job_id", "id"),
        "physical": ("physical_attempt_id", "id"),
        "reservations": ("reservation_id", "id"),
        "cost_entries": ("entry_key", "entry_id", "id"),
    }.get(group, ("id", "record_id"))
    for name in names:
        result = _text(row.get(name))
        if result is not None:
            return result
    return None


def _rows(records: Mapping[str, Any] | None, group: str) -> list[Mapping[str, Any]]:
    if not isinstance(records, Mapping):
        return []
    value = records.get(group, ())
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _source_lineage(health: Mapping[str, Any], wrapper: Mapping[str, Any], persisted: Mapping[str, Any] | None) -> dict[str, Any]:
    scope = _mapping(health.get("scope")) or {}
    persisted_lineage = _mapping((persisted or {}).get("source_lineage")) or {}
    identity = _mapping(health.get("diagnostic_identity")) or {}
    scope_source_ids = scope.get("source_ids", ()) if isinstance(scope.get("source_ids"), Sequence) and not isinstance(scope.get("source_ids"), (str, bytes, bytearray)) else ()
    return {
        "source_ids": sorted({value for value in (_text(scope.get("source_id")), _text(persisted_lineage.get("source_id")), _text(identity.get("snapshot_source_id")), *(_text(item) for item in scope_source_ids)) if value}),
        "source_versions": sorted({value for value in (_text(identity.get("snapshot_source_version")), _text(persisted_lineage.get("source_version"))) if value}),
        "evidence_basis": _text(scope.get("evidence_basis")) or _text(persisted_lineage.get("evidence_basis")),
    }


def _normalise_input(export: Any) -> tuple[ObservationState, Mapping[str, Any] | None, Mapping[str, Any] | None, str, dict[str, Any]]:
    object_document = getattr(export, "document", None)
    object_snapshot = getattr(export, "snapshot", None)
    document: Any = object_document if isinstance(object_document, Mapping) else export
    if isinstance(document, Mapping) and isinstance(document.get("document"), Mapping):
        document = document["document"]
    if not isinstance(document, Mapping):
        return ObservationState.UNSUPPORTED, None, None, "NON_MAPPING_EXPORT", {}

    schema = _text(document.get("schema")) or ""
    if schema == "charitygraph.phase5.operator-health-runtime-contract/v1":
        health = _mapping(document.get("operator_health"))
        persisted = _mapping(document.get("persisted_representation"))
        if health is None:
            return ObservationState.UNKNOWN, None, persisted, "MISSING_OPERATOR_HEALTH", {}
        integration = _mapping(document.get("catalogue_integration"))
        timestamp_provenance = _mapping(integration.get("timestamp_provenance")) if integration else None
        if timestamp_provenance:
            persisted = {**(persisted or {}), "clock_provenance": timestamp_provenance}
        return ObservationState.OBSERVED, health, persisted, "", {}
    if schema == "charitygraph.phase5.operator-health/v1":
        persisted = _mapping(document.get("persisted_representation"))
        if object_snapshot is not None:
            records = getattr(object_snapshot, "records", None)
            if isinstance(records, Mapping):
                persisted = {"records": records, "source_lineage": {
                    "source_id": getattr(object_snapshot, "source_id", None),
                    "source_version": getattr(object_snapshot, "source_version", None),
                    "evidence_basis": getattr(object_snapshot, "evidence_basis", None),
                }}
        return ObservationState.OBSERVED, document, persisted, "", {}
    if schema:
        return ObservationState.UNSUPPORTED, None, None, "UNSUPPORTED_RUNTIME_EXPORT_SCHEMA", {"input_schema": schema}
    return ObservationState.UNKNOWN, None, None, "MISSING_RUNTIME_EXPORT_SCHEMA", {}


def _clock_provenance(document: Mapping[str, Any], persisted: Mapping[str, Any] | None) -> tuple[bool, str]:
    candidates = [
        _mapping(document.get("clock_provenance")),
        _mapping(document.get("timestamp_provenance")),
        _mapping((document.get("catalogue_integration") or {}).get("timestamp_provenance")) if isinstance(document.get("catalogue_integration"), Mapping) else None,
        _mapping((persisted or {}).get("clock_provenance")),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        state = _text(candidate.get("state"))
        if state in {"trusted", "source_authenticated", "durable"}:
            return True, state
        return False, state or "present_but_untrusted"
    return False, "missing"


def _index(records: Mapping[str, Any] | None) -> dict[tuple[str, str], Mapping[str, Any]]:
    candidates: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for group in _RECORD_GROUPS:
        for row in _rows(records, group):
            identifier = _record_id(row, group)
            if identifier is not None:
                candidates.setdefault((group, identifier), []).append(row)
    return {key: min(rows, key=_canonical_bytes) for key, rows in candidates.items()}


def _related(row: Mapping[str, Any] | None, health: Mapping[str, Any], records: Mapping[str, Any] | None) -> dict[str, list[str]]:
    row = row or {}
    run_ids = {_text(row.get("run_id"))} if _text(row.get("run_id")) else set()
    subject_ids = {_text(row.get("subject_id")) or _text(row.get("durable_subject_id"))}
    scope_ids = {_text(row.get("scope_id")) or _text(row.get("durable_scope_id"))}
    task_ids = {_text(row.get("model_task_id")) or _text(row.get("task_id"))}
    for values in (subject_ids, scope_ids, task_ids):
        values.discard(None)
    request_id = _text(row.get("provider_request_item_id"))
    physical_id = _text(row.get("physical_attempt_id"))
    if physical_id:
        for receipt in _rows(records, "receipts"):
            if _text(receipt.get("physical_attempt_id")) == physical_id:
                run_ids.add(_text(receipt.get("run_id")))
        for physical in _rows(records, "physical"):
            if _record_id(physical, "physical") == physical_id:
                run_ids.add(_text(physical.get("run_id")))
                subject_ids.add(_text(physical.get("subject_id")))
    if request_id:
        for attempt in _rows(records, "attempts"):
            if _text(attempt.get("provider_request_item_id")) == request_id:
                task_ids.add(_text(attempt.get("model_task_id")))
    for run_id in list(run_ids):
        if not run_id:
            continue
        for per_run in health.get("per_run", ()) if isinstance(health.get("per_run"), Sequence) else ():
            if isinstance(per_run, Mapping) and _text(per_run.get("run_id")) == run_id:
                subject_ids.update(_text(value) for value in per_run.get("subject_ids", ()) if _text(value))
                scope_ids.update(_text(value) for value in per_run.get("scope_ids", ()) if _text(value))
    return {
        "run_ids": sorted(value for value in run_ids if value),
        "task_ids": sorted(value for value in task_ids if value),
        "subject_ids": sorted(value for value in subject_ids if value),
        "scope_ids": sorted(value for value in scope_ids if value),
    }


def _evidence(lineage: Mapping[str, Any], group: str, identifier: str | None, pointer: str) -> list[dict[str, Any]]:
    source_ids = lineage.get("source_ids") or []
    source_versions = lineage.get("source_versions") or []
    refs = []
    for source_id in source_ids or [None]:
        refs.append({
            "source_id": source_id,
            "source_version": source_versions[0] if len(source_versions) == 1 else None,
            "evidence_basis": lineage.get("evidence_basis"),
            "record_group": group,
            "record_id": identifier,
            "pointer": pointer,
        })
    return refs


def _event(
    *,
    family: str,
    severity: AlertSeverity,
    disposition: AlertDisposition,
    state: ObservationState,
    reason_code: str,
    ids: Mapping[str, Sequence[str]],
    evidence_refs: Sequence[Mapping[str, Any]],
    policy: AlertThresholdPolicy,
    follow_up: str,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "family": family,
        "severity": severity.value,
        "disposition": disposition.value,
        "observation_state": state.value,
        "reason_code": reason_code,
        "run_ids": sorted(set(ids.get("run_ids", ()))),
        "task_ids": sorted(set(ids.get("task_ids", ()))),
        "subject_ids": sorted(set(ids.get("subject_ids", ()))),
        "scope_ids": sorted(set(ids.get("scope_ids", ()))),
        "evidence_refs": sorted((_canonical(dict(ref)) for ref in evidence_refs), key=_canonical_bytes),
        "threshold_policy": {"policy_id": policy.policy_id, "policy_version": policy.policy_version},
        "suggested_follow_up": follow_up,
    }
    if detail:
        payload["detail"] = _canonical(dict(detail))
    event_id = "alert-event:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return {"event_id": event_id, **payload}


def _diagnostic(code: str, state: ObservationState, policy: AlertThresholdPolicy, lineage: Mapping[str, Any], follow_up: str, *, detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "code": code,
        "observation_state": state.value,
        "severity": AlertSeverity.UNKNOWN.value if state != ObservationState.OBSERVED else AlertSeverity.INFO.value,
        "disposition": AlertDisposition.REVIEW_UNVERIFIED.value,
        "threshold_policy": {"policy_id": policy.policy_id, "policy_version": policy.policy_version},
        "source_ids": list(lineage.get("source_ids") or []),
        "suggested_follow_up": follow_up,
    }
    if detail:
        payload["detail"] = _canonical(dict(detail))
    diagnostic_id = "alert-diagnostic:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return {"diagnostic_id": diagnostic_id, **payload}


def _crossing(row: Mapping[str, Any] | None) -> bool:
    if not row:
        return False
    status = _text(row.get("status"))
    trace = _text(row.get("trace_status"))
    return bool(
        status in _CROSSING_STATUSES
        or trace in _CROSSING_STATUSES
        or any(_text(row.get(name)) for name in ("send_started_at", "submitted_at", "provider_request_id", "provider_receipt_id", "received_at"))
    )


def _flag_row(flag: Mapping[str, Any], index: Mapping[tuple[str, str], Mapping[str, Any]]) -> tuple[str | None, Mapping[str, Any] | None]:
    identifier = _text(flag.get("id"))
    if identifier is None:
        return None, None
    for group in ("requests", "jobs", "attempts", "task_attempts", "tasks"):
        row = index.get((group, identifier))
        if row is not None:
            return group, row
    return None, None


def _health_alerts(health: Mapping[str, Any], records: Mapping[str, Any] | None, lineage: Mapping[str, Any], policy: AlertThresholdPolicy, persisted: Mapping[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    alerts: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    index = _index(records)
    flags = health.get("flags")
    if not isinstance(flags, Mapping):
        diagnostics.append(_diagnostic("MISSING_OPERATOR_HEALTH_FLAGS", ObservationState.UNKNOWN, policy, lineage, "Retain the existing operator-health flags in the runtime export before evaluating alerts."))
        return alerts, diagnostics

    seen: set[str] = set()
    def add_unique(alert: dict[str, Any]) -> None:
        if alert["event_id"] not in seen:
            seen.add(alert["event_id"])
            alerts.append(alert)

    for key in ("ambiguous", "failed", "retry", "stalled"):
        values = flags.get(key, ())
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
            diagnostics.append(_diagnostic(f"MALFORMED_{key.upper()}_FLAGS", ObservationState.UNKNOWN, policy, lineage, "Repair the structured operator-health export before relying on this alert family."))
            continue
        for position, candidate in enumerate(values):
            if not isinstance(candidate, Mapping):
                diagnostics.append(_diagnostic(f"MALFORMED_{key.upper()}_FLAG", ObservationState.UNKNOWN, policy, lineage, "Retain structured flag identifiers in the runtime export."))
                continue
            group, row = _flag_row(candidate, index)
            identifier = _text(candidate.get("id"))
            ids = _related(row or candidate, health, records)
            refs = _evidence(lineage, group or "operator_health", identifier, f"operator_health.flags.{key}.{identifier or position}")
            if key == "ambiguous":
                add_unique(_event(
                    family="provider_crossing_ambiguous",
                    severity=AlertSeverity.CRITICAL,
                    disposition=AlertDisposition.STOP_RESEND,
                    state=ObservationState.OBSERVED,
                    reason_code="AMBIGUOUS_PROVIDER_CROSSING",
                    ids=ids,
                    evidence_refs=refs,
                    policy=policy,
                    follow_up="Hold this physical attempt and reconcile provider receipt state before any resend or recovery dispatch.",
                    detail={"record_group": group, "record_id": identifier},
                ))
            elif key == "failed":
                status = _text((row or {}).get("status"))
                if _crossing(row):
                    add_unique(_event(
                        family="terminal_provider_crossing",
                        severity=AlertSeverity.HIGH,
                        disposition=AlertDisposition.STOP_RESEND,
                        state=ObservationState.OBSERVED,
                        reason_code="TERMINAL_FAILURE_AFTER_PROVIDER_CROSSING",
                        ids=ids,
                        evidence_refs=refs,
                        policy=policy,
                        follow_up="Stop resend for this physical attempt; reconcile the terminal provider outcome and receipt lineage.",
                        detail={"record_group": group, "record_id": identifier, "status": status},
                    ))
                else:
                    add_unique(_event(
                        family="failed_task_isolation",
                        severity=AlertSeverity.HIGH if status == "failed_terminal" else AlertSeverity.WARNING,
                        disposition=AlertDisposition.ISOLATE_TASK,
                        state=ObservationState.OBSERVED,
                        reason_code="FAILED_TASK_REQUIRES_ISOLATION",
                        ids=ids,
                        evidence_refs=refs,
                        policy=policy,
                        follow_up="Isolate the failed task and inspect durable attempt evidence; do not infer provider non-invocation from missing crossing events.",
                        detail={"record_group": group, "record_id": identifier, "status": status, "provider_crossing": "UNVERIFIED"},
                    ))
            elif key == "retry":
                add_unique(_event(
                    family="retryable_task_isolation",
                    severity=AlertSeverity.WARNING,
                    disposition=AlertDisposition.ISOLATE_TASK,
                    state=ObservationState.OBSERVED,
                    reason_code="RETRYABLE_ATTEMPT_REQUIRES_ISOLATION",
                    ids=ids,
                    evidence_refs=refs,
                    policy=policy,
                    follow_up="Keep the retry lineage isolated and review the predecessor attempt before any bounded recovery decision.",
                    detail={"record_group": group, "record_id": identifier, "attempt_number": candidate.get("attempt_number")},
                ))
            elif key == "stalled":
                trusted_clock, clock_state = _clock_provenance(health, persisted)
                if trusted_clock and policy.stale_after_seconds is not None:
                    add_unique(_event(
                        family="host_or_run_staleness",
                        severity=AlertSeverity.WARNING,
                        disposition=AlertDisposition.ISOLATE_TASK,
                        state=ObservationState.OBSERVED,
                        reason_code="DURABLE_TIMESTAMP_EXCEEDS_STALENESS_THRESHOLD",
                        ids=ids,
                        evidence_refs=refs,
                        policy=policy,
                        follow_up="Review the durable run/task heartbeat and isolate only the affected bounded work item.",
                        detail={"record_group": group, "record_id": identifier, "clock_provenance": clock_state, "threshold_seconds": policy.stale_after_seconds},
                    ))
                else:
                    add_unique(_event(
                        family="host_or_run_staleness",
                        severity=AlertSeverity.UNKNOWN,
                        disposition=AlertDisposition.REVIEW_UNVERIFIED,
                        state=ObservationState.UNVERIFIED,
                        reason_code="CLOCK_PROVENANCE_UNSUPPORTED" if not trusted_clock else "MISSING_STALENESS_THRESHOLD",
                        ids=ids,
                        evidence_refs=refs,
                        policy=policy,
                        follow_up="Obtain durable, trusted clock/heartbeat provenance before claiming host or run staleness.",
                        detail={"record_group": group, "record_id": identifier, "clock_provenance": clock_state, "threshold_seconds": policy.stale_after_seconds},
                    ))
    return alerts, diagnostics


def _usage_alerts(health: Mapping[str, Any], records: Mapping[str, Any] | None, lineage: Mapping[str, Any], policy: AlertThresholdPolicy) -> list[dict[str, Any]]:
    usage = _mapping(health.get("provider_usage"))
    state = _text(usage.get("state")) if usage else None
    if state == "observed":
        return []
    receipt_rows = _rows(records, "receipts")
    candidates = []
    for row in receipt_rows:
        marker = _text(row.get("usage_coverage_state"))
        if marker and marker.lower() != "observed":
            candidates.append(row)
    if not candidates:
        candidates = receipt_rows or [{}]
    output = []
    for row in candidates:
        identifier = _record_id(row, "receipts")
        ids = _related(row, health, records)
        output.append(_event(
            family="provider_usage_unverified",
            severity=AlertSeverity.HIGH if ids["run_ids"] else AlertSeverity.UNKNOWN,
            disposition=AlertDisposition.PREVENT_SPEND_ASSUMPTION,
            state=ObservationState.UNVERIFIED if state in {"missing", "ambiguous"} else ObservationState.UNKNOWN,
            reason_code="MISSING_OR_UNVERIFIED_PROVIDER_USAGE" if state != "ambiguous" else "AMBIGUOUS_PROVIDER_USAGE",
            ids=ids,
            evidence_refs=_evidence(lineage, "receipts" if identifier else "operator_health", identifier, "operator_health.provider_usage"),
            policy=policy,
            follow_up="Reconcile authoritative provider usage and receipt identity before relying on token totals or spend assumptions.",
            detail={"usage_state": state or "UNKNOWN", "receipt_id": identifier},
        ))
    return output


def _budget_alerts(health: Mapping[str, Any], records: Mapping[str, Any] | None, lineage: Mapping[str, Any], policy: AlertThresholdPolicy) -> list[dict[str, Any]]:
    cost = _mapping(health.get("cost"))
    provenance = _mapping(cost.get("provenance")) if cost else None
    reserved = _mapping(cost.get("committed_reserved")) if cost else None
    observed = bool(
        cost
        and cost.get("ledger_state") == "observed"
        and reserved
        and reserved.get("state") == "committed_reserved"
        and _text(provenance.get("ledger_source_id"))
        and _text(provenance.get("ledger_version"))
        and _text(provenance.get("ledger_as_of"))
    )
    if observed:
        return []
    run_ids = sorted({_text(row.get("run_id")) for group in ("runs", "tasks", "requests", "reservations", "cost_entries") for row in _rows(records, group) if _text(row.get("run_id"))})
    ids = {"run_ids": [value for value in run_ids if value], "task_ids": [], "subject_ids": [], "scope_ids": []}
    if len(ids["run_ids"]) == 1:
        ids = _related({"run_id": ids["run_ids"][0]}, health, records)
    return [_event(
        family="authoritative_budget_unverified",
        severity=AlertSeverity.HIGH if ids["run_ids"] else AlertSeverity.UNKNOWN,
        disposition=AlertDisposition.PREVENT_SPEND_ASSUMPTION,
        state=ObservationState.UNVERIFIED if cost else ObservationState.UNKNOWN,
        reason_code="MISSING_OR_UNVERIFIED_AUTHORITATIVE_BUDGET",
        ids=ids,
        evidence_refs=_evidence(lineage, "cost", None, "operator_health.cost"),
        policy=policy,
        follow_up="Reconcile the governed budget/ledger authority before authorising or assuming further spend.",
        detail={"ledger_state": cost.get("ledger_state") if cost else "UNKNOWN", "reserved_state": reserved.get("state") if reserved else "UNKNOWN"},
    )]


def project_phase5_operator_health_alerts(
    runtime_export: Any,
    *,
    threshold_policy: AlertThresholdPolicy | Mapping[str, Any] | None = None,
) -> OperatorHealthAlertProjection:
    """Project deterministic operator alerts from an existing runtime export."""

    policy = AlertThresholdPolicy.from_input(threshold_policy)
    input_state, health, persisted, reason, input_detail = _normalise_input(runtime_export)
    if input_state != ObservationState.OBSERVED or health is None:
        lineage = {"source_ids": [], "source_versions": [], "evidence_basis": None}
        diagnostics = [_diagnostic(reason or "UNOBSERVED_RUNTIME_EXPORT", input_state, policy, lineage, "Supply a supported existing Phase-5 operator-health/runtime export; no runtime action was taken.", detail=input_detail)]
        document = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "evaluation_state": input_state.value,
            "threshold_policy": policy.as_dict(),
            "scope": {"source_ids": [], "run_ids": [], "task_ids": [], "subject_ids": [], "scope_ids": []},
            "alerts": [],
            "diagnostics": diagnostics,
            "summary": {"alert_count": 0, "observed_event_denominator": None, "rate": None, "rate_state": "UNKNOWN"},
            "limitations": ["Unsupported or unobserved runtime exports produce no alert claim.", "No missing event is interpreted as absence of failure."],
        }
    else:
        records = _mapping(persisted.get("records")) if persisted else None
        lineage = _source_lineage(health, {}, persisted)
        alerts, diagnostics = _health_alerts(health, records, lineage, policy, persisted)
        alerts.extend(_usage_alerts(health, records, lineage, policy))
        alerts.extend(_budget_alerts(health, records, lineage, policy))
        unique: dict[str, dict[str, Any]] = {alert["event_id"]: alert for alert in alerts}
        alerts = sorted(unique.values(), key=lambda alert: alert["event_id"])
        diagnostics = sorted(diagnostics, key=lambda item: item["diagnostic_id"])
        health_scope = _mapping(health.get("scope")) or {}
        run_ids = sorted({_text(value) for value in health_scope.get("run_ids", ()) if _text(value)})
        observed_denominator = len(run_ids) if run_ids else None
        document = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "evaluation_state": ObservationState.OBSERVED.value,
            "threshold_policy": policy.as_dict(),
            "scope": {
                "source_ids": lineage.get("source_ids", []),
                "run_ids": run_ids,
                "task_ids": [],
                "subject_ids": [],
                "scope_ids": [],
                "evidence_basis": lineage.get("evidence_basis"),
            },
            "alerts": alerts,
            "diagnostics": diagnostics,
            "summary": {
                "alert_count": len(alerts),
                "observed_event_denominator": observed_denominator,
                "rate": None,
                "rate_state": "UNKNOWN" if observed_denominator in (None, 0) else "NOT_COMPUTED_NO_SLO_POLICY",
            },
            "limitations": [
                "This is a pure projection over supplied runtime evidence; it performs no monitoring side effect, restart, requeue, duplicate dispatch or provider call.",
                "Missing events remain UNKNOWN/UNVERIFIED rather than zero or no-failure evidence.",
                "Host/run staleness is actionable only with explicit trusted clock provenance; caller-created as_of timestamps are not live host health.",
                "No aggregate charity/service SLO is claimed without explicit versioned thresholds and denominators.",
                "Provider exactly-once effects and project-wide budget completeness remain outside this bounded export.",
            ],
        }

    canonical_json = _canonical_bytes(document)
    return OperatorHealthAlertProjection(document=document, canonical_json=canonical_json, sha256=hashlib.sha256(canonical_json).hexdigest())


def project_operator_health_alerts(*args: Any, **kwargs: Any) -> OperatorHealthAlertProjection:
    """Short alias for the bounded alert projection."""

    return project_phase5_operator_health_alerts(*args, **kwargs)


def canonical_operator_health_alert_json(projection: OperatorHealthAlertProjection | Mapping[str, Any]) -> bytes:
    document = projection.document if isinstance(projection, OperatorHealthAlertProjection) else projection
    return _canonical_bytes(document)


def operator_health_alert_sha256(projection: OperatorHealthAlertProjection | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_operator_health_alert_json(projection)).hexdigest()


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "AlertContractError",
    "AlertSeverity",
    "AlertDisposition",
    "ObservationState",
    "AlertThresholdPolicy",
    "OperatorHealthAlertProjection",
    "project_phase5_operator_health_alerts",
    "project_operator_health_alerts",
    "canonical_operator_health_alert_json",
    "operator_health_alert_sha256",
]
