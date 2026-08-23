"""Deterministic in-memory provider used only by synthetic contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel

from charitygraph.contracts.ids import new_opaque_id
from charitygraph.contracts.tasks import ModelResult, ModelTask, ProviderUsage, TaskRun

from .base import ProviderExecution


OutputFactory = Callable[[ModelTask], BaseModel]


class DeterministicFakeProvider:
    """A file-free, network-free execution seam keyed by material cache identity."""

    def __init__(self, provider_id: str = "fake", usage: ProviderUsage | None = None) -> None:
        self.provider_id = provider_id
        self.usage = usage or ProviderUsage()
        self._factories: dict[str, OutputFactory] = {}
        self.received_task_ids: list[str] = []

    def register(self, cache_key: str, factory: OutputFactory) -> None:
        if not cache_key or cache_key in self._factories:
            raise ValueError("cache key must be nonblank and registered once")
        self._factories[cache_key] = factory

    def execute(self, task: ModelTask) -> ProviderExecution:
        factory = self._factories.get(task.cache_key)
        if factory is None:
            raise KeyError(f"no fake output registered for cache key {task.cache_key}")
        if task.provider_id != self.provider_id:
            raise ValueError("task provider_id does not match fake provider")
        self.received_task_ids.append(task.record_id)
        now = datetime.now(timezone.utc)
        task_run = TaskRun(
            record_id=new_opaque_id("taskrun:"),
            created_at=now,
            producer={"kind": "code", "producer_id": "fake-provider", "version": "1"},
            model_task_ids=(task.record_id,),
            subject_id=task.subject_id,
            provider_id=self.provider_id,
            model_snapshot=task.model_snapshot,
            provider_request_id=f"fake-request:{task.cache_key}",
            attempt_number=1,
            status="succeeded",
            submitted_at=now,
            started_at=now,
            completed_at=now,
            usage=self.usage,
            pricing_snapshot_id=new_opaque_id("pricing:"),
        )
        output = factory(task)
        if not isinstance(output, BaseModel):
            raise TypeError("fake output factories must return a typed Pydantic model")
        result = ModelResult(
            record_id=new_opaque_id("modelresult:"),
            created_at=now,
            producer={"kind": "code", "producer_id": "fake-provider", "version": "1"},
            model_task_id=task.record_id,
            task_run_id=task_run.record_id,
            output_schema=task.output_schema,
            output=output,
            validation_status="valid",
            raw_response_ref=f"fake-response:{task.cache_key}",
            completed_at=now,
            provider_id=self.provider_id,
            model_snapshot=task.model_snapshot,
        )
        return ProviderExecution(task=task, task_run=task_run, logical_result=result)
