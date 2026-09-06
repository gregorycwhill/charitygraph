"""Isolated provider-free Factory orchestration for approved Phase-5 plans."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from .contracts.ids import deterministic_id


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

    def runtime_tasks(self, *, cohort_id: str) -> tuple[dict[str, Any], ...]:
        tasks=[]
        for item in self.logical_tasks:
            cache=hashlib.sha256(item["logical_task_id"].encode()).hexdigest()
            tasks.append({"record_id": deterministic_id("modeltask:", {"logical_task_id": item["logical_task_id"]}), "subject_id":item["subject_id"], "cohort_id":cohort_id, "task_type":"structured_extraction", "task_schema":{"schema_id":"urn:charitygraph:phase5:rehearsal:1"}, "cache_key":cache, "provider_id":"fake", "model_snapshot":"phase5-rehearsal-v1", "logical_task_id":item["logical_task_id"], "difficulty":item["difficulty"]})
        return tuple(tasks)


class ReferenceFactory:
    """Synchronous isolated runner; fake-only and never a knowledge producer."""
    def __init__(self, catalog: Any, plan: FactoryPlan, *, cohort_id: str, run_id: str) -> None:
        self.catalog, self.plan, self.cohort_id, self.run_id = catalog, plan, cohort_id, run_id
    def seed(self, now: datetime) -> tuple[dict[str, Any], ...]:
        tasks=self.plan.runtime_tasks(cohort_id=self.cohort_id)
        for task in tasks: self.catalog.register_task(task, run_id=self.run_id, now=now)
        return tasks
    def run(self, now: datetime) -> int:
        completed=0
        for task in self.plan.runtime_tasks(cohort_id=self.cohort_id):
            if self.catalog.get_task(task["record_id"])["status"] == "succeeded": continue
            owner="phase5-factory-reference"
            if not self.catalog.claim_task(task["record_id"], owner=owner, lease_expires_at=now+timedelta(hours=1), now=now):
                continue
            attempt_id=deterministic_id("taskrun:", {"task":task["record_id"],"attempt":1})
            self.catalog.begin_task_attempt(task["record_id"], owner=owner, task_run_id=attempt_id, now=now, provider_request_id="fake-request:"+task["cache_key"])
            self.catalog.finish_successful_attempt(attempt_id, owner=owner, completed_at=now, result_artifact_id="rehearsal-result:"+task["cache_key"], provider_request_id="fake-request:"+task["cache_key"], usage={"input_tokens":1,"output_tokens":1}, pricing_snapshot_id="pricing:rehearsal", fx_snapshot_id="fx:rehearsal")
            completed+=1
        return completed
