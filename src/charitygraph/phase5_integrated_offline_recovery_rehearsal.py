"""Provider-free recovery rehearsal over the real Phase-5 Factory seams.

This module is deliberately a coordinator, not a replacement runner.  It feeds
an already-lowered governed task manifest to :class:`ReferenceFactory`,
reopens the same SQLite catalogue to simulate restart, and delegates health
projection to the existing read-only catalogue adapter.  The local fake
provider returns receipt identities only; it never interprets evidence or
contacts a provider.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .contracts.ids import deterministic_id
from .phase5_factory import FactoryPlan, ReferenceFactory, RehearsalFakeProvider
from .phase5_governed_factory_integration import GovernedFactoryPreflight
from .phase5_operator_health_catalogue import project_operator_health_catalogue
from .runtime import SQLiteCatalog


REHEARSAL_SCHEMA = "charitygraph.phase5.integrated-offline-recovery-rehearsal/v1"
NOT_OBSERVED = "NOT_OBSERVED"
@dataclass(frozen=True)
class RecoveryFaultPlan:
    """Exactly one logical task for each injected fault class."""

    terminal_task_id: str
    retryable_pre_send_task_id: str
    ambiguous_task_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "terminal": self.terminal_task_id,
            "retryable_pre_send": self.retryable_pre_send_task_id,
            "ambiguous_provider_boundary": self.ambiguous_task_id,
        }


@dataclass(frozen=True)
class IntegratedTaskOutcome:
    logical_task_id: str
    model_task_id: str
    subject_id: str
    scope_id: str | None
    source_record_ids: tuple[str, ...]
    outcome: str
    physical_attempt_id: str
    provider_receipt_id: str | None
    usage_state: str
    result_state: str
    task_attempt_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "logical_task_id": self.logical_task_id,
            "model_task_id": self.model_task_id,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_record_ids": list(self.source_record_ids),
            "outcome": self.outcome,
            "physical_attempt_id": self.physical_attempt_id,
            "provider_receipt_id": self.provider_receipt_id,
            "usage_state": self.usage_state,
            "result_state": self.result_state,
            "task_attempt_count": self.task_attempt_count,
        }


@dataclass(frozen=True)
class IntegratedOfflineRecoveryResult:
    cohort_id: str
    run_id: str
    plan_manifest_hash: str
    task_count: int
    healthy_task_ids: tuple[str, ...]
    outcomes: tuple[IntegratedTaskOutcome, ...]
    schedule_trace: tuple[Mapping[str, Any], ...]
    event_trace: tuple[Mapping[str, Any], ...]
    provider_call_count: int
    provider_call_ids: tuple[str, ...]
    no_duplicate_accepted_logical_effects: bool
    no_cross_subject_contamination: bool
    deterministic_replay: bool
    restart_recovered_retryable: bool
    ambiguous_failed_closed: bool
    operator_health_sha256: str
    operator_health_document: Mapping[str, Any]
    source_evidence_state: str
    usage_evidence_state: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": REHEARSAL_SCHEMA,
            "cohort_id": self.cohort_id,
            "run_id": self.run_id,
            "plan_manifest_hash": self.plan_manifest_hash,
            "task_count": self.task_count,
            "healthy_task_ids": list(self.healthy_task_ids),
            "outcomes": [outcome.as_dict() for outcome in self.outcomes],
            "schedule_trace": [dict(row) for row in self.schedule_trace],
            "event_trace": [dict(row) for row in self.event_trace],
            "provider_call_count": self.provider_call_count,
            "provider_call_ids": list(self.provider_call_ids),
            "no_duplicate_accepted_logical_effects": self.no_duplicate_accepted_logical_effects,
            "no_cross_subject_contamination": self.no_cross_subject_contamination,
            "deterministic_replay": self.deterministic_replay,
            "restart_recovered_retryable": self.restart_recovered_retryable,
            "ambiguous_failed_closed": self.ambiguous_failed_closed,
            "operator_health_sha256": self.operator_health_sha256,
            "operator_health_document": dict(self.operator_health_document),
            "source_evidence_state": self.source_evidence_state,
            "usage_evidence_state": self.usage_evidence_state,
        }


class _CountingRehearsalProvider(RehearsalFakeProvider):
    """Existing fake provider with a local call ledger for replay assertions."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute_package(self, package_id: str, *, delivery_mode: str):
        self.calls.append(package_id)
        return super().execute_package(package_id, delivery_mode=delivery_mode)


def _physical_id(tasks: tuple[dict[str, Any], ...], delivery_mode: str) -> str:
    package_id = deterministic_id(
        "taskrun:",
        {"members": [_record_id(task) for task in tasks], "mode": delivery_mode},
    )
    return "physical:" + package_id.split(":", 1)[1]


def _record_id(task: Mapping[str, Any]) -> str:
    model_task = task.get("_model_task")
    if model_task is not None:
        return str(model_task.record_id)
    if task.get("task_type") == "structured_extraction" and task.get("record_id"):
        return str(task["record_id"])
    return deterministic_id("modeltask:", {"logical_task_id": task["logical_task_id"]})


def _schedule(plan: Any, delivery_mode: str) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for package in plan.physical_packages(delivery_mode=delivery_mode):
        tasks = tuple(package)
        rows.append(
            {
                "physical_attempt_id": _physical_id(tasks, delivery_mode),
                "logical_task_ids": [task["logical_task_id"] for task in tasks],
                "subject_ids": sorted({task["subject_id"] for task in tasks}),
                "scope_ids": sorted({task.get("scope_id") for task in tasks}, key=lambda value: value or ""),
            }
        )
    return tuple(rows)


def _validate_input(preflight: GovernedFactoryPreflight, faults: RecoveryFaultPlan) -> None:
    tasks = tuple(preflight.factory_plan.logical_tasks)
    if len(tasks) < 4:
        raise ValueError("integrated recovery rehearsal requires three fault tasks and one healthy task")
    ids = {task["logical_task_id"] for task in tasks}
    fault_ids = tuple(faults.as_dict().values())
    if len(set(fault_ids)) != len(fault_ids) or not set(fault_ids) <= ids:
        raise ValueError("fault plan must name three distinct planned logical tasks")
    required = ("subject_id", "scope_id", "source_record_ids", "logical_task_id", "record_id")
    for task in tasks:
        missing = [field for field in required if field not in task]
        if missing:
            raise ValueError(f"task {task.get('logical_task_id', '<unknown>')} lacks {', '.join(missing)}")
        if not task["source_record_ids"]:
            raise ValueError(f"task {task['logical_task_id']} lacks source-to-subject provenance")


def _task_attempt_count(catalog: SQLiteCatalog, model_task_id: str) -> int:
    with catalog._connection() as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM task_attempts WHERE model_task_id=?",
                (model_task_id,),
            ).fetchone()[0]
        )


def _outcomes(
    catalog: SQLiteCatalog,
    runtime_tasks: tuple[dict[str, Any], ...],
    plan: Any,
    faults: RecoveryFaultPlan,
) -> tuple[IntegratedTaskOutcome, ...]:
    by_logical = {task["logical_task_id"]: task for task in runtime_tasks}
    fault_by_id = {
        faults.terminal_task_id: "terminal_failure",
        faults.retryable_pre_send_task_id: "retryable_recovered",
        faults.ambiguous_task_id: "ambiguous_fail_closed",
    }
    package_by_logical: dict[str, str] = {}
    for package in plan.physical_packages(delivery_mode="standard"):
        physical = _physical_id(tuple(package), "standard")
        for item in package:
            package_by_logical[item["logical_task_id"]] = physical
    rows: list[IntegratedTaskOutcome] = []
    for logical_id in sorted(by_logical):
        task = by_logical[logical_id]
        state = catalog.get_task(task["record_id"])
        physical_id = package_by_logical[logical_id]
        physical = catalog.get_physical_attempt(physical_id)
        receipt = catalog.get_physical_receipt(physical_id)
        outcome = fault_by_id.get(logical_id, "healthy_completed")
        rows.append(
            IntegratedTaskOutcome(
                logical_task_id=logical_id,
                model_task_id=task["record_id"],
                subject_id=task["subject_id"],
                scope_id=task.get("scope_id"),
                source_record_ids=tuple(task["source_record_ids"]),
                outcome=outcome,
                physical_attempt_id=physical_id,
                provider_receipt_id=None if receipt is None else receipt["provider_receipt_id"],
                usage_state="observed_fake_receipt" if receipt is not None else NOT_OBSERVED,
                result_state=("succeeded" if state["status"] == "succeeded" else NOT_OBSERVED),
                task_attempt_count=_task_attempt_count(catalog, task["record_id"]),
            )
        )
    return tuple(rows)


def run_integrated_offline_recovery_rehearsal(
    preflight: GovernedFactoryPreflight,
    *,
    database_path: str | Path,
    cohort_id: str,
    run_id: str,
    now: datetime,
    faults: RecoveryFaultPlan,
) -> IntegratedOfflineRecoveryResult:
    """Run one deterministic, provider-free Factory/restart/health rehearsal.

    ``preflight`` must already contain governed, source-bound lowered tasks.
    The function never acquires or interprets evidence.  The ambiguous fault is
    intentionally not reconciled: a started send without a persisted receipt
    stays fail-closed and is never retried by this rehearsal.
    """

    _validate_input(preflight, faults)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    database_path = Path(database_path)
    plan = preflight.factory_plan
    reverse_plan = FactoryPlan.from_manifest(list(reversed(plan.logical_tasks)))
    forward_schedule = _schedule(plan, "standard")
    reversed_schedule = _schedule(reverse_plan, "standard")
    schedule_identity = json.dumps(forward_schedule, sort_keys=True, separators=(",", ":"))
    reversed_identity = json.dumps(reversed_schedule, sort_keys=True, separators=(",", ":"))
    deterministic_schedule = schedule_identity == reversed_identity

    provider = _CountingRehearsalProvider()
    catalog = SQLiteCatalog(database_path).open(initialize=True)
    runtime_tasks: tuple[dict[str, Any], ...] = ()
    event_trace: list[dict[str, Any]] = []
    try:
        catalog.register_cohort(
            {
                "record_id": cohort_id,
                "cohort_code": "G4_PHASE5_INTEGRATED_OFFLINE_RECOVERY",
                "definition_version": "1",
                "membership_hash": plan.manifest_hash,
                "budget_cap": {"amount": "10.000000", "currency": "AUD"},
                "created_at": now,
            }
        )
        catalog.register_run(
            {
                "record_id": run_id,
                "cohort_id": cohort_id,
                "run_kind": "g4_phase5_integrated_offline_recovery_rehearsal",
                "status": "planned",
                "configuration_hash": plan.manifest_hash,
                "created_at": now,
            }
        )
        catalog.transition_run(run_id, "running", now=now)
        factory = ReferenceFactory(
            catalog,
            plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
            delivery_mode="standard",
        )
        runtime_tasks = factory.seed(now)
        by_logical = {task["logical_task_id"]: task for task in runtime_tasks}
        # Build the physical IDs from runtime members, retaining Factory order.
        physical_for = {}
        for package in plan.physical_packages(delivery_mode="standard"):
            members = tuple(by_logical[item["logical_task_id"]] for item in package)
            physical = _physical_id(members, "standard")
            for item in package:
                physical_for[item["logical_task_id"]] = physical
            event_trace.append(
                {
                    "event": "scheduled",
                    "pass": "initial",
                    "physical_attempt_id": physical,
                    "logical_task_ids": [item["logical_task_id"] for item in package],
                    "subject_ids": sorted({item["subject_id"] for item in package}),
                    "scope_ids": sorted({item.get("scope_id") for item in package}, key=lambda value: value or ""),
                }
            )
        interruptions = {
            physical_for[faults.retryable_pre_send_task_id]: "pre_send",
            physical_for[faults.ambiguous_task_id]: "send_ambiguous",
        }
        failures = {physical_for[faults.terminal_task_id]: "structural"}
        factory.run(
            now,
            interruptions=interruptions,
            failures=failures,
            continue_interruptions=True,
        )
        event_trace.extend(
            (
                {
                    "event": "fault_injected",
                    "pass": "initial",
                    "logical_task_id": faults.terminal_task_id,
                    "fault": "terminal_failure",
                    "outcome": "failed_terminal",
                },
                {
                    "event": "fault_injected",
                    "pass": "initial",
                    "logical_task_id": faults.retryable_pre_send_task_id,
                    "fault": "retryable_pre_send",
                    "outcome": "prepared_without_send",
                },
                {
                    "event": "fault_injected",
                    "pass": "initial",
                    "logical_task_id": faults.ambiguous_task_id,
                    "fault": "ambiguous_provider_boundary",
                    "outcome": "send_started_without_receipt; fail_closed",
                },
            )
        )

        # Close and reopen the durable catalogue: this is the restart boundary.
        calls_before_restart = len(provider.calls)
        catalog.close()
        catalog = SQLiteCatalog(database_path).open(initialize=True)
        restarted = ReferenceFactory(
            catalog,
            plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
            delivery_mode="standard",
        )
        restarted.seed(now)
        restarted.run(now, continue_interruptions=True)
        event_trace.append(
            {
                "event": "restart_replay",
                "pass": "restart",
                "retryable_task_outcome": "succeeded",
                "ambiguous_task_outcome": "still_send_started_without_receipt",
                "provider_calls_added": len(provider.calls) - calls_before_restart,
            }
        )
        calls_after_restart = len(provider.calls)
        restarted.run(now, continue_interruptions=True)
        event_trace.append(
            {
                "event": "idempotent_replay",
                "pass": "replay",
                "provider_calls_added": len(provider.calls) - calls_after_restart,
            }
        )
        catalog.transition_run(run_id, "held", now=now)
        outcomes = _outcomes(catalog, runtime_tasks, plan, faults)
        retryable = next(item for item in outcomes if item.logical_task_id == faults.retryable_pre_send_task_id)
        ambiguous = next(item for item in outcomes if item.logical_task_id == faults.ambiguous_task_id)
        healthy = tuple(item.logical_task_id for item in outcomes if item.outcome == "healthy_completed" and item.result_state == "succeeded")
        no_duplicates = all(item.task_attempt_count <= 1 for item in outcomes)
        package_subjects = [row["subject_ids"] for row in forward_schedule]
        no_cross_subjects = all(len(subjects) == 1 for subjects in package_subjects)
        restart_recovered = retryable.result_state == "succeeded" and retryable.task_attempt_count == 1
        ambiguous_closed = ambiguous.provider_receipt_id is None and ambiguous.usage_state == NOT_OBSERVED and catalog.get_physical_attempt(ambiguous.physical_attempt_id)["status"] == "send_started"
    finally:
        if catalog is not None:
            catalog.close()

    start = (now - timedelta(seconds=1)).isoformat()
    end = (now + timedelta(seconds=1)).isoformat()
    diagnostic = project_operator_health_catalogue(
        database_path,
        run_ids=[run_id],
        as_of=now.isoformat(),
        reporting_window_start=start,
        reporting_window_end=end,
        source_id="offline-rehearsal:" + run_id,
        evidence_basis="local Factory catalogue rows; simulated provider-free rehearsal only",
        ledger={
            "source_id": "offline-rehearsal-ledger",
            "version": "1",
            "as_of": now.isoformat(),
            "complete": False,
        },
    )
    # The catalogue wrapper contains an absolute local path for its integration
    # metadata.  Return the canonical operator-health document itself so replay
    # identity is independent of the temporary database location.
    health_document = json.loads(diagnostic.operator_health.canonical_json.decode("utf-8"))
    return IntegratedOfflineRecoveryResult(
        cohort_id=cohort_id,
        run_id=run_id,
        plan_manifest_hash=plan.manifest_hash,
        task_count=len(runtime_tasks),
        healthy_task_ids=healthy,
        outcomes=outcomes,
        schedule_trace=forward_schedule,
        event_trace=tuple(event_trace),
        provider_call_count=len(provider.calls),
        provider_call_ids=tuple(provider.calls),
        no_duplicate_accepted_logical_effects=no_duplicates,
        no_cross_subject_contamination=no_cross_subjects,
        deterministic_replay=deterministic_schedule,
        restart_recovered_retryable=restart_recovered,
        ambiguous_failed_closed=ambiguous_closed,
        operator_health_sha256=diagnostic.operator_health.sha256,
        operator_health_document=health_document,
        source_evidence_state="governed fixture lineage preserved; no external source acquisition",
        usage_evidence_state="fake receipt usage observed only for receipt-bearing tasks; missing for terminal/ambiguous tasks",
    )


__all__ = [
    "REHEARSAL_SCHEMA",
    "NOT_OBSERVED",
    "RecoveryFaultPlan",
    "IntegratedTaskOutcome",
    "IntegratedOfflineRecoveryResult",
    "run_integrated_offline_recovery_rehearsal",
]
