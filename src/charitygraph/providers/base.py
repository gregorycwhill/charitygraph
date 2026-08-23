"""Provider-neutral test seam; networking and scheduling belong to later PRs."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from pydantic import model_validator

from charitygraph.contracts.common import StrictModel, require_nonblank
from charitygraph.contracts.knowledge import CanonicalObservation
from charitygraph.contracts.tasks import EmbeddingResult, ModelResult, ModelTask, TaskRun


PayloadT = TypeVar("PayloadT")


class ProviderExecution(StrictModel):
    """One synchronous logical result, not a production scheduler abstraction."""

    task: ModelTask
    task_run: TaskRun
    logical_result: ModelResult | EmbeddingResult

    @model_validator(mode="after")
    def _consistent(self) -> "ProviderExecution":
        task_id = self.task.record_id
        if task_id not in self.task_run.model_task_ids:
            raise ValueError("TaskRun does not reference the executed task")
        if self.task_run.subject_id != self.task.subject_id:
            raise ValueError("provider execution subject mismatch")
        if self.task_run.provider_id != self.task.provider_id or self.task_run.model_snapshot != self.task.model_snapshot:
            raise ValueError("provider execution provider/model mismatch")
        if self.logical_result.model_task_id != task_id or self.logical_result.task_run_id != self.task_run.record_id:
            raise ValueError("logical result references do not match execution")
        if isinstance(self.logical_result, ModelResult):
            if self.logical_result.provider_id != self.task.provider_id or self.logical_result.model_snapshot != self.task.model_snapshot:
                raise ValueError("model result provider/model mismatch")
        elif self.logical_result.embedding_model_snapshot != self.task.model_snapshot:
            raise ValueError("embedding result model mismatch")
        return self


class ModelProvider(Protocol, Generic[PayloadT]):
    provider_id: str

    def execute(self, task: ModelTask[PayloadT]) -> ProviderExecution: ...
