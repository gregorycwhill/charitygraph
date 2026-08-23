import pytest

from charitygraph.contracts.tasks import ProviderUsage
from charitygraph.providers.fake import DeterministicFakeProvider
from ._helpers import Payload, task


def test_fake_provider_is_typed_deterministic_and_observable():
    model_task=task()
    provider=DeterministicFakeProvider("fake", ProviderUsage(input_tokens=2, output_tokens=1))
    provider.register(model_task.cache_key, lambda _: Payload(value="synthetic"))
    execution=provider.execute(model_task)
    assert execution.logical_result.output.value == "synthetic"
    assert provider.received_task_ids == [model_task.record_id]
    assert execution.task_run.usage.input_tokens == 2
    assert "prompt" not in execution.logical_result.raw_response_ref
    assert "response" in execution.logical_result.raw_response_ref


def test_fake_provider_rejects_unknown_cache_and_untyped_output():
    model_task=task()
    provider=DeterministicFakeProvider("fake")
    with pytest.raises(KeyError):
        provider.execute(model_task)
    provider.register(model_task.cache_key, lambda _: {"not":"typed"})
    with pytest.raises(TypeError):
        provider.execute(model_task)
