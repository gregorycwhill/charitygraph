"""Run the complete Phase-5 workload through fake Batch/Flex/Standard control planes."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_delivery import FakeDeliveryAdapter, build_delivery_plan
from charitygraph.phase5_factory import FactoryPlan, FakeProviderReceipt, ReferenceFactory
from charitygraph.runtime import SQLiteCatalog


def run_reference(manifest: Path, runtime_root: Path) -> dict[str, object]:
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    logical = json.loads(manifest.read_text(encoding="utf-8"))
    plan = FactoryPlan.from_manifest(logical)
    if len(plan.logical_tasks) != 1331:
        raise RuntimeError("authoritative Phase-5 task count changed")
    delivery = build_delivery_plan(plan.logical_tasks)
    runtime_root.mkdir(parents=True, exist_ok=True)
    catalog = SQLiteCatalog(runtime_root / "factory.sqlite3").open(initialize=True)
    cohort = deterministic_id("cohort:", {"rehearsal": "phase5-delivery-v1"})
    run = deterministic_id("run:", {"rehearsal": "phase5-delivery-v1"})
    catalog.register_cohort({"record_id": cohort, "cohort_code": "P5_DELIVERY", "definition_version": "1", "membership_hash": plan.manifest_hash, "budget_cap": {"amount": "10000", "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "phase5_factory_delivery_reference", "status": "planned", "configuration_hash": plan.manifest_hash, "created_at": now})
    catalog.transition_run(run, "running", now=now)
    factory = ReferenceFactory(catalog, plan, cohort_id=cohort, run_id=run)
    runtime = {task["logical_task_id"]: task for task in factory.seed(now)}
    # Deterministic tasks never create provider request items or delivery jobs.
    for logical_id in delivery.deterministic_logical_task_ids:
        task = runtime[logical_id]
        factory.finalise_package_children((task,), package_id=deterministic_id("taskrun:", {"deterministic": task["record_id"]}), receipt=None, now=now)
    items = {item.request_item_id: item for item in delivery.request_items}
    adapter = FakeDeliveryAdapter()
    completed = 0
    for job in delivery.delivery_jobs:
        catalog.create_delivery_job(delivery_job_id=job.delivery_job_id, run_id=run, provider_id=job.provider_id, model_route=job.model_route, delivery_mode=job.delivery_mode, pricing_snapshot_id=delivery.pricing.snapshot_id, now=now)
        job_items = [items[item_id] for item_id in job.request_item_ids]
        for item in job_items:
            task = runtime[item.logical_task_ids[0]]
            catalog.create_provider_request_item(provider_request_item_id=item.request_item_id, run_id=run, model_task_id=task["record_id"], provider_id=item.provider_id, model_route=item.model_route, requested_delivery_mode=item.requested_delivery_mode, effective_service_tier=item.effective_service_tier, delivery_job_id=job.delivery_job_id, now=now)
        if job.delivery_mode == "batch":
            adapter.submit_batch(catalog, job, now=now)
            catalog.transition_delivery_job(job.delivery_job_id, "in_progress", now=now)
        for item in job_items:
            task = runtime[item.logical_task_ids[0]]
            request = deterministic_id("requestitem:", {"provider": "fake", "item": item.request_item_id})
            receipt = FakeProviderReceipt(request, deterministic_id("requestitem:", {"receipt": request}), "fake-result:" + item.request_item_id, {"input_tokens": 1, "output_tokens": 1})
            catalog.transition_provider_request_item(item.request_item_id, "submitted", now=now, provider_request_id=request)
            catalog.transition_provider_request_item(item.request_item_id, "in_progress", now=now)
            package = deterministic_id("taskrun:", {"members": [task["record_id"]], "mode": item.effective_service_tier})
            physical = "physical:" + package.split(":", 1)[1]
            reservation = deterministic_id("reservation:", {"physical_attempt": package})
            catalog.reserve_cost({"record_id": reservation, "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "0.010000", "currency": "AUD"}, "model_task_ids": (task["record_id"],), "expires_at": None}, now=now)
            catalog.prepare_physical_attempt(physical_attempt_id=physical, run_id=run, subject_id=task["subject_id"], delivery_mode=item.effective_service_tier, provider_request_id=request, model_task_ids=(task["record_id"],), reservation_id=reservation, now=now, provider_batch_id=(job.delivery_job_id if job.delivery_mode == "batch" else None))
            catalog.mark_physical_send_started(physical, now=now)
            catalog.persist_provider_receipt(physical_attempt_id=physical, provider_receipt_id=receipt.receipt_id, raw_result_ref=receipt.raw_result_ref, usage=receipt.usage, now=now)
            factory.finalise_package_children((task,), package_id=package, receipt=receipt, now=now)
            catalog.transition_provider_request_item(item.request_item_id, "completed", now=now, provider_receipt_id=receipt.receipt_id, result_ref=receipt.raw_result_ref, usage=receipt.usage)
            completed += 1
        if job.delivery_mode == "batch":
            catalog.transition_delivery_job(job.delivery_job_id, "completed", now=now)
        else:
            catalog.transition_delivery_job(job.delivery_job_id, "submitted", now=now)
            catalog.transition_delivery_job(job.delivery_job_id, "in_progress", now=now)
            catalog.transition_delivery_job(job.delivery_job_id, "completed", now=now)
    noop = sum(1 for task in catalog.list_provider_request_items(run) if task["status"] != "completed")
    catalog.transition_run(run, "succeeded", now=now)
    report = {"logical_tasks": len(plan.logical_tasks), "deterministic": len(delivery.deterministic_logical_task_ids), "semantic": delivery.semantic_count, "provider_request_items": len(delivery.request_items), "batch_jobs": sum(1 for job in delivery.delivery_jobs if job.delivery_mode == "batch"), "mode_counts": delivery.count_modes(), "economics": {key: str(value) for key, value in delivery.economics().items()}, "completed_semantic_items": completed, "terminal_noop_unfinished_items": noop, "network_calls": 0, "provider_calls": 0, "semantic_knowledge_production": 0}
    (runtime_root / "delivery-reference-summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
