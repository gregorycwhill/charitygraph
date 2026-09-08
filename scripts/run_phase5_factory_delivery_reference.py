"""Run the complete Phase-5 workload through fake Batch/Flex/Standard control planes."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_delivery import DeliveryPolicy, FakeDeliveryAdapter, build_delivery_plan
from charitygraph.phase5_factory import FactoryPlan, FakeProviderReceipt, ReferenceFactory
from charitygraph.runtime import SQLiteCatalog


def run_reference(manifest: Path, runtime_root: Path, *, scenario: str | None = None, selected_item_ids: set[str] | None = None, reviewed_batch_harness: bool = False) -> dict[str, object]:
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    logical = json.loads(manifest.read_text(encoding="utf-8"))
    plan = FactoryPlan.from_manifest(logical)
    if len(plan.logical_tasks) != 1331:
        raise RuntimeError("authoritative Phase-5 task count changed")
    policy = DeliveryPolicy.build(reviewed_batch_override=reviewed_batch_harness)
    delivery = build_delivery_plan(plan.logical_tasks, policy=policy)
    runtime_root.mkdir(parents=True, exist_ok=True)
    catalog = SQLiteCatalog(runtime_root / "factory.sqlite3").open(initialize=True)
    label = scenario or "reference"
    cohort = deterministic_id("cohort:", {"rehearsal": "phase5-delivery-v1", "scenario": label})
    run = deterministic_id("run:", {"rehearsal": "phase5-delivery-v1", "scenario": label})
    summary_path = runtime_root / "delivery-reference-summary.json"
    existing_run = catalog.get_run(run)
    if existing_run is not None and existing_run["status"] in {"succeeded", "failed", "held"}:
        # A terminal rehearsal is an immutable execution event.  Reopening it
        # returns its recorded result and cannot submit or reconcile anew.
        if not summary_path.exists():
            raise RuntimeError("terminal delivery rehearsal is missing its summary")
        return json.loads(summary_path.read_text(encoding="utf-8"))
    catalog.register_cohort({"record_id": cohort, "cohort_code": "P5_DELIVERY", "definition_version": "1", "membership_hash": plan.manifest_hash, "budget_cap": {"amount": "10000", "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "phase5_factory_delivery_reference", "status": "planned", "configuration_hash": plan.manifest_hash, "created_at": now})
    catalog.transition_run(run, "running", now=now)
    factory = ReferenceFactory(catalog, plan, cohort_id=cohort, run_id=run, delivery_policy=policy)
    runtime = {task["logical_task_id"]: task for task in factory.seed(now)}
    # Deterministic tasks never create provider request items or delivery jobs.
    for logical_id in delivery.deterministic_logical_task_ids:
        task = runtime[logical_id]
        factory.finalise_package_children((task,), package_id=deterministic_id("taskrun:", {"deterministic": task["record_id"]}), receipt=None, now=now)
    items = {item.request_item_id: item for item in delivery.request_items}
    adapter = FakeDeliveryAdapter()
    completed = 0
    selected_item_ids = selected_item_ids or set()
    deferred: dict[str, tuple[object, object, object]] = {}

    def receipt_for(item: object) -> FakeProviderReceipt:
        request = deterministic_id("requestitem:", {"provider": "fake", "item": item.request_item_id})
        return FakeProviderReceipt(request, deterministic_id("requestitem:", {"receipt": request}), "fake-result:" + item.request_item_id, {"input_tokens": 1, "output_tokens": 1})

    def start_send(item: object, job: object, task: dict[str, object], receipt: FakeProviderReceipt) -> tuple[str, str]:
        package = deterministic_id("taskrun:", {"members": [task["record_id"]], "mode": item.effective_service_tier})
        physical = "physical:" + package.split(":", 1)[1]
        reservation = deterministic_id("reservation:", {"physical_attempt": package})
        catalog.reserve_cost({"record_id": reservation, "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "0.010000", "currency": "AUD"}, "model_task_ids": (task["record_id"],), "expires_at": None}, now=now)
        catalog.prepare_physical_attempt(physical_attempt_id=physical, run_id=run, subject_id=task["subject_id"], delivery_mode=item.effective_service_tier, provider_request_id=receipt.request_id, model_task_ids=(task["record_id"],), reservation_id=reservation, now=now, provider_batch_id=(job.delivery_job_id if job.delivery_mode == "batch" else None))
        catalog.mark_physical_send_started(physical, now=now)
        return package, physical

    def persist_receipt(item: object, job: object, task: dict[str, object], receipt: FakeProviderReceipt) -> tuple[str, str]:
        package, physical = start_send(item, job, task, receipt)
        catalog.persist_provider_receipt(physical_attempt_id=physical, provider_receipt_id=receipt.receipt_id, raw_result_ref=receipt.raw_result_ref, usage=receipt.usage, now=now)
        return package, physical

    def finalise(item: object, task: dict[str, object], package: str, receipt: FakeProviderReceipt, *, failure: str | None = None) -> None:
        nonlocal completed
        factory.delivery_mode = item.effective_service_tier
        completed += factory.finalise_package_children((task,), package_id=package, receipt=receipt, now=now, failure=failure)
        catalog.transition_provider_request_item(item.request_item_id, "completed", now=now, provider_receipt_id=receipt.receipt_id, result_ref=receipt.raw_result_ref, usage=receipt.usage)

    for job in delivery.delivery_jobs:
        catalog.create_delivery_job(delivery_job_id=job.delivery_job_id, run_id=run, provider_id=job.provider_id, model_route=job.model_route, delivery_mode=job.delivery_mode, pricing_snapshot_id=delivery.pricing.snapshot_id, now=now)
        job_items = [items[item_id] for item_id in job.request_item_ids]
        for item in job_items:
            task = runtime[item.logical_task_ids[0]]
            catalog.create_provider_request_item(provider_request_item_id=item.request_item_id, run_id=run, model_task_id=task["record_id"], provider_id=item.provider_id, model_route=item.model_route, requested_delivery_mode=item.requested_delivery_mode, effective_service_tier=item.effective_service_tier, delivery_job_id=job.delivery_job_id, now=now)
        if job.delivery_mode == "batch":
            adapter.submit_batch(catalog, job, now=now)
        else:
            catalog.transition_delivery_job(job.delivery_job_id, "submitted", now=now)
        catalog.transition_delivery_job(job.delivery_job_id, "in_progress", now=now)
        for item in job_items:
            task = runtime[item.logical_task_ids[0]]
            faulted = item.request_item_id in selected_item_ids
            if faulted and scenario == "C1_pre_send":
                # No provider boundary is crossed.  The durable prepared item
                # is resumed only after a fresh catalogue open.
                deferred[item.request_item_id] = (item, job, task)
                continue
            receipt = receipt_for(item)
            catalog.transition_provider_request_item(item.request_item_id, "submitted", now=now, provider_request_id=receipt.request_id)
            if faulted and scenario == "C2_send_ambiguous":
                # The provider identity and send boundary are durable, but no
                # receipt exists.  Recovery is reconciliation, never resend.
                start_send(item, job, task, receipt)
                catalog.transition_provider_request_item(item.request_item_id, "send_ambiguous", now=now)
                deferred[item.request_item_id] = (item, job, task)
                continue
            catalog.transition_provider_request_item(item.request_item_id, "in_progress", now=now)
            package, _ = persist_receipt(item, job, task, receipt)
            if faulted and scenario == "C3_receipt_restart":
                deferred[item.request_item_id] = (item, job, task)
                continue
            finalise(item, task, package, receipt, failure=("structural" if faulted and scenario == "C4_structural" else "grounding" if faulted and scenario == "C5_grounding" else "partial" if faulted and scenario == "C6_partial_bundle" else None))
        catalog.transition_delivery_job(job.delivery_job_id, "completed", now=now)

    # Fresh-open recovery is part of the rehearsal evidence, not a logical
    # shortcut.  C2 reconciles a persisted send without an automatic resend.
    if deferred or (scenario == "C2_send_ambiguous" and selected_item_ids):
        catalog.close()
        catalog = SQLiteCatalog(runtime_root / "factory.sqlite3").open(initialize=False)
        factory.catalog = catalog
    for item, job, task in deferred.values():
        receipt = receipt_for(item)
        if scenario == "C1_pre_send":
            catalog.transition_provider_request_item(item.request_item_id, "submitted", now=now, provider_request_id=receipt.request_id)
            catalog.transition_provider_request_item(item.request_item_id, "in_progress", now=now)
            package, _ = persist_receipt(item, job, task, receipt)
            finalise(item, task, package, receipt)
        elif scenario == "C3_receipt_restart":
            package = deterministic_id("taskrun:", {"members": [task["record_id"]], "mode": item.effective_service_tier})
            finalise(item, task, package, receipt)
        elif scenario == "C2_send_ambiguous":
            # This lookup observes the existing fake Batch identity; it does
            # not create a replacement request or Batch job.
            adapter.reconcile_batch(catalog, job)
            package = deterministic_id("taskrun:", {"members": [task["record_id"]], "mode": item.effective_service_tier})
            physical = "physical:" + package.split(":", 1)[1]
            catalog.persist_provider_receipt(physical_attempt_id=physical, provider_receipt_id=receipt.receipt_id, raw_result_ref=receipt.raw_result_ref, usage=receipt.usage, now=now)
            finalise(item, task, package, receipt)
    noop = sum(1 for task in catalog.list_provider_request_items(run) if task["status"] != "completed")
    run_status = "failed" if scenario in {"C4_structural", "C6_partial_bundle"} and selected_item_ids else "held" if scenario == "C5_grounding" and selected_item_ids else "succeeded"
    catalog.transition_run(run, run_status, now=now)
    report = {"scenario": scenario or "reference", "run_status": run_status, "logical_tasks": len(plan.logical_tasks), "deterministic": len(delivery.deterministic_logical_task_ids), "semantic": delivery.semantic_count, "provider_request_items": len(delivery.request_items), "selected_fault_items": len(selected_item_ids), "batch_jobs": sum(1 for job in delivery.delivery_jobs if job.delivery_mode == "batch"), "mode_counts": delivery.count_modes(), "economics": {key: str(value) for key, value in delivery.economics().items()}, "completed_semantic_items": completed, "terminal_noop_unfinished_items": noop, "network_calls": 0, "provider_calls": 0, "semantic_knowledge_production": 0}
    summary_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-factory-delivery-v1"))
    report=run_reference(parser.parse_args().manifest, parser.parse_args().runtime_root)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
