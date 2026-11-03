"""Isolated provider-free Factory orchestration for approved Phase-5 plans."""
from __future__ import annotations

import hashlib
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from .contracts.ids import deterministic_id
from .phase5_delivery import DeliveryPolicy


@dataclass(frozen=True)
class FactoryPlan:
    logical_tasks: tuple[dict[str, Any], ...]

    @classmethod
    def from_manifest(cls, items: list[dict[str, Any]]) -> "FactoryPlan":
        ordered = tuple(sorted(items, key=lambda item: item["logical_task_id"]))
        ids = [item["logical_task_id"] for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("planned logical task identities must be unique")
        return cls(ordered)

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256("\n".join(item["logical_task_id"] for item in self.logical_tasks).encode()).hexdigest()

    def packages(self) -> tuple[tuple[dict[str, Any], ...], ...]:
        """Package only same-subject compatible opportunities; IDs stay logical."""
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in self.logical_tasks:
            groups[(item["subject_id"], item.get("physical_bundle_opportunity") or item["logical_task_id"])].append(item)
        return tuple(tuple(sorted(group, key=lambda item: item["logical_task_id"])) for _, group in sorted(groups.items()))

    def physical_packages(self, *, delivery_mode: str = "standard") -> tuple[tuple[dict[str, Any], ...], ...]:
        """Only semantic work is batchable; deterministic work stays single-task."""
        if delivery_mode not in {"batch", "flex", "standard"}: raise ValueError("unknown delivery mode")
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in self.logical_tasks:
            kind = "single" if item.get("difficulty") == "deterministic" else (item.get("physical_bundle_opportunity") or item["logical_task_id"])
            groups[(item["subject_id"], kind, delivery_mode)].append(item)
        return tuple(tuple(sorted(group,key=lambda item:item["logical_task_id"])) for _,group in sorted(groups.items()))

    def runtime_tasks(self, *, cohort_id: str) -> tuple[dict[str, Any], ...]:
        tasks=[]
        for item in self.logical_tasks:
            cache=hashlib.sha256(item["logical_task_id"].encode()).hexdigest()
            tasks.append({"record_id": deterministic_id("modeltask:", {"logical_task_id": item["logical_task_id"]}), "subject_id":item["subject_id"], "cohort_id":cohort_id, "task_type":"structured_extraction", "task_schema":{"schema_id":"urn:charitygraph:phase5:rehearsal:1"}, "cache_key":cache, "provider_id":"fake", "model_snapshot":"phase5-rehearsal-v1", "logical_task_id":item["logical_task_id"], "difficulty":item["difficulty"]})
        return tuple(tasks)


@dataclass(frozen=True)
class FakeProviderReceipt:
    request_id: str
    receipt_id: str
    raw_result_ref: str
    usage: dict[str, int]


class RehearsalFakeProvider:
    """Network-free provider seam; it exposes no knowledge-producing output."""
    provider_id = "fake"
    tariffs = {"batch": "0.000500", "flex": "0.001000", "standard": "0.002000"}
    def execute(self, task: dict[str, Any], *, delivery_mode: str = "batch") -> FakeProviderReceipt:
        if delivery_mode not in self.tariffs: raise ValueError("unknown rehearsal delivery mode")
        request = "fake-request:" + task["cache_key"]
        return FakeProviderReceipt(request, "fake-receipt:" + hashlib.sha256(request.encode()).hexdigest(), "rehearsal-result:" + task["cache_key"], {"input_tokens": 1, "output_tokens": 1})

    def receipt_for_package(self, package_id: str, *, delivery_mode: str) -> FakeProviderReceipt:
        """Deterministic local stand-in for a provider receipt or later reconciliation lookup."""
        if delivery_mode not in self.tariffs: raise ValueError("unknown rehearsal delivery mode")
        request = "fake-package-request:" + hashlib.sha256(package_id.encode()).hexdigest()
        token = hashlib.sha256((package_id + delivery_mode).encode()).hexdigest()
        return FakeProviderReceipt(request, "fake-receipt:" + token, "rehearsal-result:" + token, {"input_tokens": 1, "output_tokens": 1})

    def execute_package(self, package_id: str, *, delivery_mode: str) -> FakeProviderReceipt:
        """The only fake send boundary; it exposes no semantic content."""
        return self.receipt_for_package(package_id, delivery_mode=delivery_mode)


class FactoryInterrupted(RuntimeError):
    """Deliberate process-loss simulation after a durable recovery boundary."""


class AmbiguousSendError(RuntimeError):
    """A send was durably started but no receipt is persisted; never auto-resend."""


class ReferenceFactory:
    """Synchronous isolated runner; fake-only and never a knowledge producer."""
    def __init__(self, catalog: Any, plan: FactoryPlan, *, cohort_id: str, run_id: str, provider: RehearsalFakeProvider | None = None, delivery_mode: str | None = None, delivery_policy: DeliveryPolicy | None = None) -> None:
        self.catalog, self.plan, self.cohort_id, self.run_id = catalog, plan, cohort_id, run_id
        self.provider = provider or RehearsalFakeProvider()
        self.delivery_policy = delivery_policy or DeliveryPolicy.build()
        requested = {"delivery_mode": delivery_mode} if delivery_mode is not None else {}
        self.delivery_mode = self.delivery_policy.resolve(requested)
        self.interruptions_observed: list[str] = []
    def seed(self, now: datetime) -> tuple[dict[str, Any], ...]:
        tasks=self.plan.runtime_tasks(cohort_id=self.cohort_id)
        for task in tasks: self.catalog.register_task(task, run_id=self.run_id, now=now)
        return tasks
    def _physical_id(self, package_id: str) -> str:
        return "physical:" + package_id.split(":", 1)[1]

    def _claim_package(self, tasks: tuple[dict[str, Any], ...], *, now: datetime) -> bool:
        owner="phase5-factory-reference"
        for task in tasks:
            state=self.catalog.get_task(task["record_id"])
            if state["status"] == "succeeded":
                continue
            if state["status"] == "leased" and state["lease_owner"] == owner:
                continue
            if not self.catalog.claim_task(task["record_id"], owner=owner, lease_expires_at=now+timedelta(hours=1), now=now):
                return False
        return True

    def _receipt_from_catalog(self, physical_id: str) -> FakeProviderReceipt:
        row=self.catalog.get_physical_receipt(physical_id)
        if row is None: raise AmbiguousSendError("receipt was not persisted")
        import json
        return FakeProviderReceipt(row["provider_request_id"], row["provider_receipt_id"], row["raw_result_ref"], json.loads(row["usage_json"]))

    def prepare_package(self, tasks: tuple[dict[str, Any], ...], *, now: datetime, interruption: str | None = None) -> tuple[str, FakeProviderReceipt | None]:
        """Durably prepare/send one same-subject physical package.

        Logical child completion remains separate; this method deliberately
        establishes the one-send/one-receipt boundary shared by its members.
        """
        if not tasks or len({task["subject_id"] for task in tasks}) != 1: raise ValueError("package must contain one subject")
        semantic = [task for task in tasks if task["difficulty"] != "deterministic"]
        package_id = deterministic_id("taskrun:", {"members": [task["record_id"] for task in tasks], "mode": self.delivery_mode})
        if not semantic: return package_id, None
        if not self._claim_package(tasks, now=now):
            return package_id, None
        request_id = "fake-package-request:" + hashlib.sha256(package_id.encode()).hexdigest()
        reservation_id = deterministic_id("reservation:", {"physical_attempt": package_id})
        physical_id=self._physical_id(package_id)
        physical=self.catalog.get_physical_attempt(physical_id)
        if physical and physical["status"] in {"receipt_persisted", "validated"}:
            return package_id, self._receipt_from_catalog(physical_id)
        if physical and physical["status"] == "send_started":
            raise AmbiguousSendError(f"{physical_id} has a started send and requires explicit reconciliation")
        if physical is None:
            self.catalog.reserve_cost({"record_id": reservation_id, "cohort_id": self.cohort_id, "run_id": self.run_id, "reserved_aud": {"amount": "0.010000", "currency": "AUD"}, "model_task_ids": tuple(task["record_id"] for task in tasks), "expires_at": None}, now=now)
            self.catalog.prepare_physical_attempt(physical_attempt_id=physical_id,run_id=self.run_id,subject_id=tasks[0]["subject_id"],delivery_mode=self.delivery_mode,provider_request_id=request_id,model_task_ids=tuple(task["record_id"] for task in tasks),reservation_id=reservation_id,now=now,provider_batch_id=("fake-batch:"+package_id.split(":",1)[1] if self.delivery_mode=="batch" else None))
        if interruption == "pre_send":
            raise FactoryInterrupted(f"simulated loss before send for {physical_id}")
        self.catalog.mark_physical_send_started(physical_id,now=now)
        receipt=self.provider.execute_package(package_id,delivery_mode=self.delivery_mode)
        if interruption == "send_ambiguous":
            raise AmbiguousSendError(f"simulated loss after send for {physical_id}")
        self.catalog.persist_provider_receipt(physical_attempt_id=physical_id,provider_receipt_id=receipt.receipt_id,raw_result_ref=receipt.raw_result_ref,usage=receipt.usage,now=now)
        if interruption == "receipt_restart":
            raise FactoryInterrupted(f"simulated loss after receipt for {physical_id}")
        return package_id, receipt
    def reconcile_ambiguous_package(self, package_id: str, *, now: datetime) -> FakeProviderReceipt:
        """Explicit reconciliation path.  It derives a fake receipt; it never sends again."""
        physical_id=self._physical_id(package_id)
        row=self.catalog.get_physical_attempt(physical_id)
        if row is None or row["status"] != "send_started": raise AmbiguousSendError("only started sends can be reconciled")
        receipt=self.provider.receipt_for_package(package_id, delivery_mode=self.delivery_mode)
        self.catalog.persist_provider_receipt(physical_attempt_id=physical_id,provider_receipt_id=receipt.receipt_id,raw_result_ref=receipt.raw_result_ref,usage=receipt.usage,now=now)
        return receipt

    def finalise_package_children(self, tasks: tuple[dict[str, Any], ...], *, package_id: str, receipt: FakeProviderReceipt | None, now: datetime, failure: str | None = None) -> int:
        """Terminalise children independently without another provider send."""
        owner="phase5-factory-reference"; completed=0
        for index, task in enumerate(tasks):
            if self.catalog.get_task(task["record_id"])["status"] == "succeeded": continue
            state=self.catalog.get_task(task["record_id"])
            if not (state["status"] == "leased" and state["lease_owner"] == owner) and not self.catalog.claim_task(task["record_id"],owner=owner,lease_expires_at=now+timedelta(hours=1),now=now): continue
            child_id=deterministic_id("taskrun:",{ "physical":package_id,"logical":task["record_id"]})
            request_id=receipt.request_id if receipt else "deterministic:"+task["cache_key"]
            result_ref=receipt.raw_result_ref if receipt else "rehearsal-result:"+task["cache_key"]
            self.catalog.begin_task_attempt(task["record_id"],owner=owner,task_run_id=child_id,now=now,provider_request_id=request_id)
            if failure == "structural" and index == 0:
                self.catalog.finish_failed_attempt(child_id,owner=owner,completed_at=now,retryable=False,error_class="structural_validation",error_message_redacted="synthetic structural rejection")
            elif failure == "grounding" and index == 0:
                self.catalog.finish_held_attempt(child_id,owner=owner,completed_at=now,error_class="grounding_validation",error_message_redacted="synthetic grounding hold")
            elif failure == "partial" and index == len(tasks)-1:
                self.catalog.finish_failed_attempt(child_id,owner=owner,completed_at=now,retryable=False,error_class="partial_bundle_member",error_message_redacted="synthetic partial bundle failure")
            else:
                self.catalog.finish_successful_attempt(child_id,owner=owner,completed_at=now,result_artifact_id=result_ref,provider_request_id=request_id,usage=receipt.usage if receipt else {},pricing_snapshot_id="pricing:rehearsal",fx_snapshot_id="fx:rehearsal")
            completed+=1
        if receipt is not None:
            reservation_id=deterministic_id("reservation:", {"physical_attempt": package_id})
            amount=self.provider.tariffs[self.delivery_mode]
            actual={"cohort_id":self.cohort_id,"run_id":self.run_id,"task_run_id":package_id,"reservation_id":reservation_id,"entry_type":"actual","paid_output_category":"extraction","provider_cost":{"amount":amount,"currency":"USD"},"aud_cost":{"amount":amount,"currency":"AUD"},"usage":receipt.usage,"recorded_at":now,"pricing_snapshot_id":deterministic_id("pricing:",{"rehearsal":"phase5"}),"fx_snapshot_id":deterministic_id("fx:",{"rehearsal":"phase5"})}
            self.catalog.record_cost_entry(actual,entry_key="actual:"+reservation_id)
            release = Decimal("0.010000") - Decimal(amount)
            self.catalog.release_reservation(reservation_id,{"amount":format(release, "f"),"currency":"AUD"},now=now,entry_key="release:"+reservation_id)
            self.catalog.mark_physical_validated(self._physical_id(package_id),now=now)
        return completed
    def run(self, now: datetime, *, interruptions: dict[str, str] | None = None, failures: dict[str, str] | None = None, continue_interruptions: bool = False) -> int:
        """Execute physical packages; each semantic package sends once."""
        by_logical={task["logical_task_id"]: task for task in self.plan.runtime_tasks(cohort_id=self.cohort_id)}
        completed=0
        for package in self.plan.physical_packages(delivery_mode=self.delivery_mode):
            tasks=tuple(by_logical[item["logical_task_id"]] for item in package)
            if all(self.catalog.get_task(task["record_id"])["status"] == "succeeded" for task in tasks):
                # A crash after child terminalisation but before physical closure
                # is recoverable without another send or logical attempt.
                package_id=deterministic_id("taskrun:", {"members": [task["record_id"] for task in tasks], "mode": self.delivery_mode})
                physical=self.catalog.get_physical_attempt(self._physical_id(package_id))
                if physical and physical["status"] == "receipt_persisted":
                    self.finalise_package_children(tasks, package_id=package_id, receipt=self._receipt_from_catalog(self._physical_id(package_id)), now=now)
                continue
            physical_id=self._physical_id(deterministic_id("taskrun:", {"members": [task["record_id"] for task in tasks], "mode": self.delivery_mode}))
            try:
                package_id,receipt=self.prepare_package(tasks,now=now,interruption=(interruptions or {}).get(physical_id))
            except (FactoryInterrupted, AmbiguousSendError):
                if not continue_interruptions:
                    raise
                self.interruptions_observed.append(physical_id)
                continue
            completed += self.finalise_package_children(tasks,package_id=package_id,receipt=receipt,now=now,failure=(failures or {}).get(self._physical_id(package_id)))
        return completed

    def _single_task_compatibility_run(self, now: datetime) -> int:
        completed=0
        for task in self.plan.runtime_tasks(cohort_id=self.cohort_id):
            if self.catalog.get_task(task["record_id"])["status"] == "succeeded": continue
            owner="phase5-factory-reference"
            if not self.catalog.claim_task(task["record_id"], owner=owner, lease_expires_at=now+timedelta(hours=1), now=now):
                continue
            receipt = None; reservation_id = None
            if task["difficulty"] != "deterministic":
                reservation_id = deterministic_id("reservation:", {"task": task["record_id"], "rehearsal": "phase5-reference-v1"})
                self.catalog.reserve_cost({"record_id": reservation_id, "cohort_id": self.cohort_id, "run_id": self.run_id, "reserved_aud": {"amount": "0.010000", "currency": "AUD"}, "model_task_ids": (task["record_id"],), "expires_at": None}, now=now)
            attempt_id=deterministic_id("taskrun:", {"task":task["record_id"],"attempt":1})
            request_id = "fake-request:" + task["cache_key"] if reservation_id else "deterministic:"+task["cache_key"]
            if reservation_id is not None:
                self.catalog.prepare_physical_attempt(physical_attempt_id="physical:"+attempt_id.split(":",1)[1], run_id=self.run_id, subject_id=task["subject_id"], delivery_mode=self.delivery_mode, provider_request_id=request_id, model_task_ids=(task["record_id"],), reservation_id=reservation_id, now=now)
                self.catalog.mark_physical_send_started("physical:"+attempt_id.split(":",1)[1], now=now)
                receipt = self.provider.execute(task, delivery_mode=self.delivery_mode)
                self.catalog.persist_provider_receipt(physical_attempt_id="physical:"+attempt_id.split(":",1)[1], provider_receipt_id=receipt.receipt_id, raw_result_ref=receipt.raw_result_ref, usage=receipt.usage, now=now)
            result_ref = receipt.raw_result_ref if receipt else "rehearsal-result:"+task["cache_key"]
            usage = receipt.usage if receipt else {"input_tokens":0,"output_tokens":0}
            self.catalog.begin_task_attempt(task["record_id"], owner=owner, task_run_id=attempt_id, now=now, provider_request_id=request_id, reservation_id=reservation_id)
            self.catalog.finish_successful_attempt(attempt_id, owner=owner, completed_at=now, result_artifact_id=result_ref, provider_request_id=request_id, usage=usage, pricing_snapshot_id="pricing:rehearsal", fx_snapshot_id="fx:rehearsal")
            if reservation_id is not None:
                actual = {"cohort_id": self.cohort_id, "run_id": self.run_id, "task_run_id": attempt_id, "reservation_id": reservation_id, "entry_type": "actual", "paid_output_category": "extraction", "provider_cost": {"amount": "0.001000", "currency": "USD"}, "aud_cost": {"amount": "0.001000", "currency": "AUD"}, "usage": {"input_tokens": 1, "output_tokens": 1}, "recorded_at": now, "pricing_snapshot_id": deterministic_id("pricing:", {"rehearsal": "phase5"}), "fx_snapshot_id": deterministic_id("fx:", {"rehearsal": "phase5"})}
                self.catalog.record_cost_entry(actual, entry_key="actual:"+reservation_id)
                self.catalog.release_reservation(reservation_id, {"amount": "0.009000", "currency": "AUD"}, now=now, entry_key="release:"+reservation_id)
            completed+=1
        return completed
