"""Provider-free delivery planning for the Phase-5 Factory rehearsal.

Logical tasks, application requests, and provider delivery aggregations are
deliberately distinct.  The fake adapter models control-plane state only.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from .contracts.ids import deterministic_id

DELIVERY_MODES = ("batch", "flex", "standard")


@dataclass(frozen=True)
class PricingSnapshot:
    snapshot_id: str = "pricing:phase5-fake-v1"
    batch: Decimal = Decimal("0.000500")
    flex: Decimal = Decimal("0.001000")
    standard: Decimal = Decimal("0.002000")

    def price(self, mode: str) -> Decimal:
        return getattr(self, mode)


@dataclass(frozen=True)
class ProviderRequestItem:
    request_item_id: str
    logical_task_ids: tuple[str, ...]
    subject_id: str
    provider_id: str
    model_route: str
    requested_delivery_mode: str
    effective_service_tier: str
    multiplex_contract: str | None = None


@dataclass(frozen=True)
class DeliveryJob:
    delivery_job_id: str
    delivery_mode: str
    provider_id: str
    model_route: str
    request_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class DeliveryPlan:
    request_items: tuple[ProviderRequestItem, ...]
    delivery_jobs: tuple[DeliveryJob, ...]
    deterministic_logical_task_ids: tuple[str, ...]
    pricing: PricingSnapshot

    @property
    def semantic_count(self) -> int:
        return sum(len(item.logical_task_ids) for item in self.request_items)

    def count_modes(self) -> dict[str, int]:
        counts = {mode: 0 for mode in DELIVERY_MODES}
        for item in self.request_items:
            counts[item.effective_service_tier] += 1
        return counts

    def economics(self) -> dict[str, Decimal]:
        standard = self.pricing.standard * Decimal(len(self.request_items))
        selected = sum((self.pricing.price(item.effective_service_tier) for item in self.request_items), Decimal("0"))
        return {"all_standard": standard, "selected": selected, "delivery_tier_savings": standard - selected, "application_bundle_savings": Decimal("0"), "cache_savings": Decimal("0")}


def application_bundle_compatible(tasks: Iterable[dict[str, Any]]) -> bool:
    """Only explicit common multiplex contracts authorise multi-task requests."""
    members = tuple(tasks)
    if len(members) < 2:
        return True
    subject_ids = {item["subject_id"] for item in members}
    routes = {(item.get("provider_id", "fake"), item.get("model_route", item.get("model_snapshot", "phase5-rehearsal-v1"))) for item in members}
    reasoning = {item.get("reasoning_settings") for item in members}
    tools = {item.get("tool_policy") for item in members}
    envelopes = {item.get("response_envelope") for item in members}
    multiplex = {item.get("multiplex_contract") for item in members}
    return len(subject_ids) == len(routes) == len(reasoning) == len(tools) == len(envelopes) == 1 and None not in multiplex


def select_delivery_mode(task: dict[str, Any]) -> str:
    if task.get("difficulty") == "deterministic":
        return "standard"
    if task.get("latency_required"):
        return "standard"
    if task.get("batch_supported", True):
        return "batch"
    return "flex"


def build_delivery_plan(tasks: Iterable[dict[str, Any]], *, pricing: PricingSnapshot | None = None, batch_size: int = 100) -> DeliveryPlan:
    pricing = pricing or PricingSnapshot()
    logical = tuple(sorted(tasks, key=lambda item: item["logical_task_id"]))
    deterministic = tuple(item["logical_task_id"] for item in logical if item.get("difficulty") == "deterministic")
    semantic = [item for item in logical if item.get("difficulty") != "deterministic"]
    items: list[ProviderRequestItem] = []
    # Opportunity is only considered if all explicit wire-contract checks pass.
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for task in semantic:
        grouped[(task["subject_id"], task.get("physical_bundle_opportunity") or task["logical_task_id"])].append(task)
    for _, group in sorted(grouped.items()):
        groups = (group,) if application_bundle_compatible(group) else tuple((task,) for task in group)
        for members in groups:
            first = members[0]
            mode = select_delivery_mode(first)
            ids = tuple(task["logical_task_id"] for task in members)
            items.append(ProviderRequestItem(
                request_item_id=deterministic_id("requestitem:", {"logical_task_ids": ids, "mode": mode}),
                logical_task_ids=ids, subject_id=first["subject_id"], provider_id=first.get("provider_id", "fake"),
                model_route=first.get("model_route", first.get("model_snapshot", "phase5-rehearsal-v1")),
                requested_delivery_mode=mode, effective_service_tier=mode, multiplex_contract=first.get("multiplex_contract"),
            ))
    jobs: list[DeliveryJob] = []
    buckets: dict[tuple[str, str, str], list[ProviderRequestItem]] = defaultdict(list)
    for item in items:
        buckets[(item.effective_service_tier, item.provider_id, item.model_route)].append(item)
    for (mode, provider, route), members in sorted(buckets.items()):
        if mode == "batch":
            for offset in range(0, len(members), batch_size):
                chunk = tuple(members[offset:offset + batch_size])
                jobs.append(DeliveryJob(deterministic_id("deliveryjob:", {"mode": mode, "items": [item.request_item_id for item in chunk]}), mode, provider, route, tuple(item.request_item_id for item in chunk)))
        else:
            for item in members:
                jobs.append(DeliveryJob(deterministic_id("deliveryjob:", {"mode": mode, "items": [item.request_item_id]}), mode, provider, route, (item.request_item_id,)))
    return DeliveryPlan(tuple(items), tuple(jobs), deterministic, pricing)


class FakeDeliveryAdapter:
    """Asynchronous-in-state fake adapter; never performs HTTP or emits knowledge."""
    provider_id = "fake"

    def serialize_standard(self, item: ProviderRequestItem) -> dict[str, Any]: return {"route": item.model_route, "tier": "standard", "request_item_id": item.request_item_id}
    def serialize_flex(self, item: ProviderRequestItem) -> dict[str, Any]: return {"route": item.model_route, "tier": "flex", "request_item_id": item.request_item_id}
    def serialize_batch(self, job: DeliveryJob, items: Iterable[ProviderRequestItem]) -> dict[str, Any]: return {"route": job.model_route, "tier": "batch", "batch_job_id": job.delivery_job_id, "items": [item.request_item_id for item in items]}

    def submit_batch(self, catalog: Any, job: DeliveryJob, *, now: Any) -> str:
        """Persist asynchronous fake submission; repeating it never creates another job."""
        provider_batch_id = deterministic_id("deliveryjob:", {"provider": self.provider_id, "job": job.delivery_job_id})
        catalog.transition_delivery_job(job.delivery_job_id, "submitted", now=now, provider_batch_id=provider_batch_id)
        return provider_batch_id

    def advance_batch(self, catalog: Any, job: DeliveryJob, items: Iterable[ProviderRequestItem], *, now: Any) -> None:
        """Deterministic clock advancement: in-progress then independent completed items."""
        catalog.transition_delivery_job(job.delivery_job_id, "in_progress", now=now)
        for item in items:
            request = deterministic_id("requestitem:", {"provider": self.provider_id, "item": item.request_item_id})
            receipt = deterministic_id("requestitem:", {"receipt": request})
            catalog.transition_provider_request_item(item.request_item_id, "submitted", now=now, provider_request_id=request)
            catalog.transition_provider_request_item(item.request_item_id, "in_progress", now=now)
            catalog.transition_provider_request_item(item.request_item_id, "completed", now=now, provider_receipt_id=receipt, result_ref="fake-result:" + item.request_item_id, usage={"input_tokens": 1, "output_tokens": 1})
        catalog.transition_delivery_job(job.delivery_job_id, "completed", now=now)

    def reconcile_batch(self, catalog: Any, job: DeliveryJob) -> dict[str, Any]:
        """Read-only fake-provider reconciliation: never submits a replacement job."""
        stored = catalog.get_delivery_job(job.delivery_job_id)
        if stored is None:
            raise RuntimeError("fake provider has no durable batch job to reconcile")
        items = [item for item in catalog.list_provider_request_items(stored["run_id"]) if item["delivery_job_id"] == job.delivery_job_id]
        return {"delivery_job_id": job.delivery_job_id, "provider_batch_id": stored["provider_batch_id"], "status": stored["status"], "items": tuple({"request_item_id": item["provider_request_item_id"], "status": item["status"], "provider_request_id": item["provider_request_id"], "provider_receipt_id": item["provider_receipt_id"]} for item in items)}
