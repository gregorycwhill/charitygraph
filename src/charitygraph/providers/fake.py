"""Deterministic in-memory provider used only by synthetic contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from pydantic import BaseModel

from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.tasks import ModelResult, ModelTask, ProviderUsage, TaskRun

from .base import ProviderExecution


OutputFactory = Callable[[ModelTask], BaseModel]
Clock = Callable[[], datetime]
FixtureIdFactory = Callable[[str, ModelTask, int], str]


def _default_clock() -> datetime:
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


class DeterministicFakeProvider:
    """A file-free, network-free provider seam with injected deterministic execution metadata."""

    def __init__(
        self,
        provider_id: str = "fake",
        usage: ProviderUsage | None = None,
        *,
        clock: Clock = _default_clock,
        id_factory: FixtureIdFactory | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.usage = usage or ProviderUsage()
        self._clock = clock
        self._id_factory = id_factory or self._default_id
        self._factories: dict[str, OutputFactory] = {}
        self.received_task_ids: list[str] = []
        self._execution_sequence = 0

    def _default_id(self, prefix: str, task: ModelTask, sequence: int) -> str:
        return deterministic_id(prefix, {
            "fixture_provider": self.provider_id,
            "task_cache_key": task.cache_key,
            "execution_sequence": sequence,
        })

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
        sequence = self._execution_sequence
        self._execution_sequence += 1
        self.received_task_ids.append(task.record_id)
        now = self._clock()
        task_run_id = self._id_factory("taskrun:", task, sequence)
        pricing_snapshot_id = self._id_factory("pricing:", task, sequence)
        task_run = TaskRun(
            record_id=task_run_id,
            created_at=now,
            producer={"kind": "code", "producer_id": "fake-provider", "version": "1"},
            model_task_ids=(task.record_id,),
            subject_id=task.subject_id,
            provider_id=self.provider_id,
            model_snapshot=task.model_snapshot,
            provider_request_id=f"fake-request:{task.cache_key}:{sequence}",
            attempt_number=sequence + 1,
            status="succeeded",
            submitted_at=now,
            started_at=now,
            completed_at=now,
            usage=self.usage,
            pricing_snapshot_id=pricing_snapshot_id,
        )
        output = factory(task)
        if not isinstance(output, BaseModel):
            raise TypeError("fake output factories must return a typed Pydantic model")
        result = ModelResult(
            record_id=self._id_factory("modelresult:", task, sequence),
            created_at=now,
            producer={"kind": "code", "producer_id": "fake-provider", "version": "1"},
            model_task_id=task.record_id,
            task_run_id=task_run.record_id,
            output_schema=task.output_schema,
            output=output,
            validation_status="valid",
            raw_response_ref=f"fake-response:{task.cache_key}:{sequence}",
            completed_at=now,
            provider_id=self.provider_id,
            model_snapshot=task.model_snapshot,
        )
        return ProviderExecution(task=task, task_run=task_run, logical_result=result)
