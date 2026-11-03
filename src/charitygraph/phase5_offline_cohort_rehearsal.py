"""Small provider-free cohort composition over the existing Phase-5 seams.

This is an offline rehearsal adapter, not a provider transport.  Governed
rights preflight is the only accepted input boundary; ``ReferenceFactory``
still owns task attempts, receipts and cost closeout, while the catalogue's
Standard lifecycle APIs provide the persisted diagnostic joins.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .contracts.ids import deterministic_id
from .phase5_delivery import DeliveryPolicy, build_delivery_plan
from .phase5_factory import ReferenceFactory, RehearsalFakeProvider
from .phase5_governed_rights_preflight import GovernedRightsFactoryPreflight
from .phase5_run_diagnostics_catalog import PersistedRunDiagnosticsAdapter
from .runtime import SQLiteCatalog


@dataclass(frozen=True)
class OfflineCohortRehearsalResult:
    """Allowlisted facts from one local rehearsal."""

    cohort_id: str
    run_id: str
    task_count: int
    completed_count: int
    failed_count: int
    held_count: int
    standard_request_items: int
    batch_request_items: int
    batch_jobs: int
    configured_concurrency: int
    observed_concurrency: int
    new_provider_calls: int
    restart_no_resend: bool
    diagnostic_sha256: str
    diagnostic_record_counts: dict[str, int]
    accounting_reconciliation: str
    residual_active_reservations: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "run_id": self.run_id,
            "task_count": self.task_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "held_count": self.held_count,
            "standard_request_items": self.standard_request_items,
            "batch_request_items": self.batch_request_items,
            "batch_jobs": self.batch_jobs,
            "configured_concurrency": self.configured_concurrency,
            "observed_concurrency": self.observed_concurrency,
            "new_provider_calls": self.new_provider_calls,
            "restart_no_resend": self.restart_no_resend,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_record_counts": dict(self.diagnostic_record_counts),
            "accounting_reconciliation": self.accounting_reconciliation,
            "residual_active_reservations": self.residual_active_reservations,
        }


def _one_task_package_id(task: dict[str, Any], delivery_mode: str) -> str:
    return deterministic_id(
        "taskrun:", {"members": [task["record_id"]], "mode": delivery_mode}
    )


def _prepare_standard_item(
    catalog: SQLiteCatalog,
    *,
    task: dict[str, Any],
    cohort_id: str,
    run_id: str,
    now: datetime,
) -> dict[str, str]:
    """Create one exact Standard item and its pre-send trace."""

    package_id = _one_task_package_id(task, "standard")
    physical_id = "physical:" + package_id.split(":", 1)[1]
    request_item_id = deterministic_id(
        "requestitem:", {"task": task["record_id"], "mode": "standard"}
    )
    delivery_job_id = deterministic_id(
        "deliveryjob:", {"request_item": request_item_id, "mode": "standard"}
    )
    delivery_attempt_id = "deliveryattempt:" + hashlib.sha256(
        (request_item_id + ":1").encode()
    ).hexdigest()
    reservation_id = deterministic_id(
        "reservation:", {"physical_attempt": package_id}
    )
    model_route = str(task.get("model_snapshot", "phase5-rehearsal-v1"))

    catalog.reserve_cost(
        {
            "record_id": reservation_id,
            "cohort_id": cohort_id,
            "run_id": run_id,
            "reserved_aud": {"amount": "0.010000", "currency": "AUD"},
            "model_task_ids": (task["record_id"],),
            "expires_at": None,
        },
        now=now,
    )
    catalog.prepare_physical_attempt(
        physical_attempt_id=physical_id,
        run_id=run_id,
        subject_id=task["subject_id"],
        delivery_mode="standard",
        provider_request_id=request_item_id,
        model_task_ids=(task["record_id"],),
        reservation_id=reservation_id,
        now=now,
    )
    catalog.create_delivery_job(
        delivery_job_id=delivery_job_id,
        run_id=run_id,
        provider_id="fake",
        model_route=model_route,
        delivery_mode="standard",
        pricing_snapshot_id="pricing:phase5-offline-fixture-v1",
        now=now,
    )
    catalog.create_provider_request_item(
        provider_request_item_id=request_item_id,
        run_id=run_id,
        model_task_id=task["record_id"],
        provider_id="fake",
        model_route=model_route,
        requested_delivery_mode="standard",
        effective_service_tier="standard",
        delivery_job_id=delivery_job_id,
        physical_attempt_id=physical_id,
        now=now,
    )
    catalog.create_provider_request_attempt(
        delivery_attempt_id=delivery_attempt_id,
        provider_request_item_id=request_item_id,
        physical_attempt_id=physical_id,
        delivery_job_id=delivery_job_id,
        attempt_ordinal=1,
        authorization_id="offline-test-fixture-only",
        attempt_class="initial",
        predecessor_attempt_id=None,
        now=now,
    )
    catalog.prepare_standard_transport_trace(
        delivery_attempt_id,
        client_request_id="offline-client-" + hashlib.sha256(request_item_id.encode()).hexdigest(),
        endpoint="https://api.openai.com/v1/responses",
        request_body_sha256=hashlib.sha256(task["record_id"].encode()).hexdigest(),
        now=now,
    )
    return {
        "package_id": package_id,
        "physical_id": physical_id,
        "request_item_id": request_item_id,
        "delivery_job_id": delivery_job_id,
        "delivery_attempt_id": delivery_attempt_id,
        "reservation_id": reservation_id,
    }


def _terminal_run(status: str) -> bool:
    return status in {"succeeded", "failed", "held", "cancelled"}


def _active_reservation_count(catalog: SQLiteCatalog, run_id: str) -> int:
    with catalog._connection() as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM budget_reservations WHERE run_id=? AND status IN ('active','partially_consumed')",
                (run_id,),
            ).fetchone()[0]
        )


def _finish_task(
    catalog: SQLiteCatalog,
    *,
    task: dict[str, Any],
    ids: dict[str, str],
    cohort_id: str,
    run_id: str,
    now: datetime,
    receipt: Any | None,
    failure: str | None = None,
) -> None:
    """Close one logical child with a diagnostic-compatible task-run ID."""

    owner = "phase5-offline-cohort-rehearsal"
    catalog.claim_task(
        task["record_id"],
        owner=owner,
        lease_expires_at=now + timedelta(hours=1),
        now=now,
    )
    task_run_id = deterministic_id(
        "taskrun:", {"offline_package": ids["package_id"], "logical": task["record_id"]}
    )
    request_id = receipt.request_id if receipt is not None else "offline:" + task["cache_key"]
    catalog.begin_task_attempt(
        task["record_id"],
        owner=owner,
        task_run_id=task_run_id,
        now=now,
        provider_request_id=request_id,
        reservation_id=ids["reservation_id"],
    )
    if failure == "structural":
        catalog.finish_failed_attempt(
            task_run_id,
            owner=owner,
            completed_at=now,
            retryable=False,
            error_class="structural_validation",
            error_message_redacted="TEST FIXTURE structural failure",
        )
        return
    if failure == "grounding":
        catalog.finish_held_attempt(
            task_run_id,
            owner=owner,
            completed_at=now,
            error_class="grounding_validation",
            error_message_redacted="TEST FIXTURE ambiguous send hold",
        )
        return
    assert receipt is not None
    catalog.finish_successful_attempt(
        task_run_id,
        owner=owner,
        completed_at=now,
        result_artifact_id=receipt.raw_result_ref,
        provider_request_id=receipt.request_id,
        usage=receipt.usage,
        pricing_snapshot_id="pricing:phase5-offline-fixture-v1",
        fx_snapshot_id="fx:phase5-offline-fixture-v1",
    )
    amount = str(Decimal("0.002000"))
    catalog.record_cost_entry(
        {
            "cohort_id": cohort_id,
            "run_id": run_id,
            "task_run_id": task_run_id,
            "reservation_id": ids["reservation_id"],
            "entry_type": "actual",
            "paid_output_category": "extraction",
            "provider_cost": {"amount": amount, "currency": "USD"},
            "aud_cost": {"amount": amount, "currency": "AUD"},
            "usage": receipt.usage,
            "recorded_at": now,
            "pricing_snapshot_id": "pricing:phase5-offline-fixture-v1",
            "fx_snapshot_id": "fx:phase5-offline-fixture-v1",
        },
        entry_key="actual:" + ids["reservation_id"],
    )
    catalog.release_reservation(
        ids["reservation_id"],
        {"amount": "0.008000", "currency": "AUD"},
        now=now,
        entry_key="release:" + ids["reservation_id"],
    )


def run_offline_cohort_rehearsal(
    preflight: GovernedRightsFactoryPreflight,
    *,
    database_path: str | Path,
    cohort_id: str,
    run_id: str,
    now: datetime,
    provider: RehearsalFakeProvider | None = None,
    failed_reference_ids: Iterable[str] = (),
    ambiguous_reference_ids: Iterable[str] = (),
    max_concurrency: int = 2,
) -> OfflineCohortRehearsalResult:
    """Run a bounded, local Standard rehearsal over already-lowered tasks.

    The caller must have completed ``preflight_governed_rights``.  Batch is
    intentionally exposed as a deterministic planning count; this function
    does not cross or emulate a Batch provider boundary.
    """

    if not 1 <= max_concurrency <= 32:
        raise ValueError("max_concurrency must be between 1 and 32")
    tasks = tuple(preflight.factory_plan.runtime_tasks(cohort_id=cohort_id))
    if not tasks or len(tasks) > 10:
        raise ValueError("offline rehearsal cohort must contain 1 to 10 tasks")
    if len({task["record_id"] for task in tasks}) != len(tasks):
        raise ValueError("offline rehearsal task identities must be unique")
    if len({task["scope_id"] for task in tasks}) != len(tasks):
        raise ValueError("offline rehearsal requires one scope per fixture task")

    failed = set(failed_reference_ids)
    ambiguous = set(ambiguous_reference_ids)
    known = {task["logical_task_id"] for task in tasks}
    if not failed <= known or not ambiguous <= known or failed & ambiguous:
        raise ValueError("failure identities must be known, disjoint fixture tasks")
    batch_tasks = tuple({**task, "delivery_mode": "batch"} for task in tasks)

    provider = provider or RehearsalFakeProvider()
    catalog = SQLiteCatalog(database_path).open(initialize=True)
    try:
        prior_run = catalog.get_run(run_id)
        if prior_run is not None and _terminal_run(str(prior_run["status"])):
            adapter = PersistedRunDiagnosticsAdapter(database_path, run_id)
            baseline = adapter.read_snapshot()
            projection = adapter.project(restart_baseline=baseline)
            batch_plan = build_delivery_plan(
                batch_tasks,
                policy=DeliveryPolicy.build(reviewed_batch_override=True),
            )
            return OfflineCohortRehearsalResult(
                cohort_id=cohort_id,
                run_id=run_id,
                task_count=len(tasks),
                completed_count=sum(1 for task in tasks if catalog.get_task(task["record_id"])["status"] == "succeeded"),
                failed_count=sum(1 for task in tasks if catalog.get_task(task["record_id"])["status"] == "failed"),
                held_count=sum(1 for task in tasks if catalog.get_task(task["record_id"])["status"] == "held"),
                standard_request_items=len(catalog.list_provider_request_items(run_id)),
                batch_request_items=len(batch_plan.request_items),
                batch_jobs=len(batch_plan.delivery_jobs),
                configured_concurrency=max_concurrency,
                observed_concurrency=1,
                new_provider_calls=0,
                restart_no_resend=True,
                diagnostic_sha256=projection.sha256,
                diagnostic_record_counts=baseline.record_counts,
                accounting_reconciliation=str(projection.document["ledger"]["reconciliation"]["state"]),
                residual_active_reservations=_active_reservation_count(catalog, run_id),
            )

        catalog.register_cohort(
            {
                "record_id": cohort_id,
                "cohort_code": "G4_T2_TEST_FIXTURE",
                "definition_version": "1",
                "membership_hash": preflight.factory_plan.manifest_hash,
                "budget_cap": {"amount": "10.000000", "currency": "AUD"},
                "created_at": now,
            }
        )
        catalog.register_run(
            {
                "record_id": run_id,
                "cohort_id": cohort_id,
                "run_kind": "g4_t2_offline_factory_rehearsal",
                "status": "planned",
                "configuration_hash": preflight.factory_plan.manifest_hash,
                "created_at": now,
            }
        )
        catalog.transition_run(run_id, "running", now=now)
        factory = ReferenceFactory(
            catalog,
            preflight.factory_plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
            delivery_mode="standard",
        )
        runtime_tasks = factory.seed(now)
        task_by_logical = {task["logical_task_id"]: task for task in runtime_tasks}
        completed = 0

        for logical_id in sorted(task_by_logical):
            task = task_by_logical[logical_id]
            ids = _prepare_standard_item(
                catalog,
                task=task,
                cohort_id=cohort_id,
                run_id=run_id,
                now=now,
            )
            attempt = ids["delivery_attempt_id"]
            if logical_id in failed:
                catalog.record_standard_transport_outcome(
                    ids["physical_id"],
                    status="LOCAL_PRE_SEND_FAILURE",
                    response_headers_received=False,
                    transport_exception="TEST_FIXTURE_PRE_SEND_FAILURE",
                    now=now,
                )
                catalog.settle_standard_failure(
                    attempt,
                    failure_class="pre_send_validation",
                    message="TEST FIXTURE pre-send failure",
                    ambiguous=False,
                    now=now,
                )
                _finish_task(
                    catalog,
                    task=task,
                    ids=ids,
                    cohort_id=cohort_id,
                    run_id=run_id,
                    now=now,
                    receipt=None,
                    failure="structural",
                )
                catalog.release_reservation(
                    ids["reservation_id"],
                    {"amount": "0.010000", "currency": "AUD"},
                    now=now,
                    entry_key="release:" + ids["reservation_id"],
                )
                continue

            catalog.mark_standard_send_started(
                attempt,
                client_request_id="offline-client-" + hashlib.sha256(ids["request_item_id"].encode()).hexdigest(),
                now=now,
            )
            receipt = provider.execute_package(ids["package_id"], delivery_mode="standard")
            if logical_id in ambiguous:
                catalog.record_standard_transport_outcome(
                    ids["physical_id"],
                    status="PROVIDER_CROSSING_AMBIGUOUS",
                    response_headers_received=False,
                    transport_exception="TEST_FIXTURE_AMBIGUOUS_SEND",
                    now=now,
                )
                catalog.settle_standard_failure(
                    attempt,
                    failure_class="ambiguous_transport",
                    message="TEST FIXTURE send boundary crossed without receipt",
                    ambiguous=True,
                    now=now,
                )
                _finish_task(
                    catalog,
                    task=task,
                    ids=ids,
                    cohort_id=cohort_id,
                    run_id=run_id,
                    now=now,
                    receipt=None,
                    failure="grounding",
                )
                continue

            catalog.record_standard_transport_outcome(
                ids["physical_id"],
                status="PROVIDER_RESPONSE_RECEIVED",
                response_headers_received=True,
                server_request_id=receipt.request_id,
                response_identity=receipt.receipt_id,
                provider_model_identity="fake-rehearsal-v1",
                usage=receipt.usage,
                now=now,
            )
            catalog.record_standard_transport_outcome(
                ids["physical_id"],
                status="COMPLETED",
                response_headers_received=True,
                server_request_id=receipt.request_id,
                response_identity=receipt.receipt_id,
                provider_model_identity="fake-rehearsal-v1",
                usage=receipt.usage,
                now=now,
            )
            catalog.complete_standard_delivery(
                attempt,
                provider_request_id=receipt.request_id,
                provider_receipt_id=receipt.receipt_id,
                raw_result_ref=receipt.raw_result_ref,
                usage=receipt.usage,
                result_ref=receipt.raw_result_ref,
                now=now,
            )
            _finish_task(
                catalog,
                task=task,
                ids=ids,
                cohort_id=cohort_id,
                run_id=run_id,
                now=now,
                receipt=receipt,
            )
            completed += 1

        run_status = "held" if ambiguous else "failed" if failed else "succeeded"
        catalog.transition_run(run_id, run_status, now=now)
        adapter = PersistedRunDiagnosticsAdapter(database_path, run_id)
        baseline = adapter.read_snapshot()
        projection = adapter.project(restart_baseline=baseline)
        batch_plan = build_delivery_plan(
            batch_tasks,
            policy=DeliveryPolicy.build(reviewed_batch_override=True),
        )
        return OfflineCohortRehearsalResult(
            cohort_id=cohort_id,
            run_id=run_id,
            task_count=len(tasks),
            completed_count=completed,
            failed_count=len(failed),
            held_count=len(ambiguous),
            standard_request_items=len(runtime_tasks),
            batch_request_items=len(batch_plan.request_items),
            batch_jobs=len(batch_plan.delivery_jobs),
            configured_concurrency=max_concurrency,
            observed_concurrency=1,
            new_provider_calls=len(runtime_tasks) - len(failed),
            restart_no_resend=True,
            diagnostic_sha256=projection.sha256,
            diagnostic_record_counts=baseline.record_counts,
            accounting_reconciliation=str(projection.document["ledger"]["reconciliation"]["state"]),
            residual_active_reservations=_active_reservation_count(catalog, run_id),
        )
    finally:
        catalog.close()


__all__ = ["OfflineCohortRehearsalResult", "run_offline_cohort_rehearsal"]
