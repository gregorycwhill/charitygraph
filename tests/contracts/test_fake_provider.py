from datetime import datetime, timezone

import pytest

from charitygraph.contracts.tasks import ProviderUsage
from charitygraph.providers.fake import DeterministicFakeProvider
from ._helpers import Payload, task


def configured_provider():
    return DeterministicFakeProvider(
        "fake", ProviderUsage(input_tokens=2, output_tokens=1),
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_fake_provider_is_typed_deterministic_and_observable():
    model_task = task()
    first = configured_provider()
    second = configured_provider()
    for provider in (first, second):
        provider.register(model_task.cache_key, lambda _: Payload(value="synthetic"))
    first_execution = first.execute(model_task)
    second_execution = second.execute(model_task)
    assert first_execution.model_dump() == second_execution.model_dump()
    assert first.received_task_ids == [model_task.record_id]
    assert first_execution.task_run.usage.input_tokens == 2
    assert "prompt" not in first_execution.logical_result.raw_response_ref
    assert "response" in first_execution.logical_result.raw_response_ref


def test_fake_provider_uses_a_deterministic_sequence_for_distinct_attempts():
    model_task = task()
    provider = configured_provider()
    provider.register(model_task.cache_key, lambda _: Payload(value="synthetic"))
    first = provider.execute(model_task)
    second = provider.execute(model_task)
    assert first.task_run.record_id != second.task_run.record_id
    assert first.task_run.attempt_number == 1
    assert second.task_run.attempt_number == 2
    assert first.task_run.completed_at == second.task_run.completed_at


def test_fake_provider_rejects_unknown_cache_and_untyped_output():
    model_task = task()
    provider = configured_provider()
    with pytest.raises(KeyError):
        provider.execute(model_task)
    provider.register(model_task.cache_key, lambda _: {"not": "typed"})
    with pytest.raises(TypeError):
        provider.execute(model_task)
