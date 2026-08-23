from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from charitygraph.contracts import EmbeddingResult, ModelResult, TaskRun, model_task_cache_key, validate_task_run_tasks
from ._helpers import Payload, task


def test_cache_changes_on_material_inputs_and_not_operational_metadata():
    first = task()
    changed_evidence = task(evidence_hash="e" * 64)
    changed_model = task(model="model-2")
    assert first.cache_key != changed_evidence.cache_key
    assert first.cache_key != changed_model.cache_key
    assert first.record_id != changed_model.record_id
    assert first.model_copy(update={"created_at": datetime(2030, 1, 1, tzinfo=timezone.utc)}).cache_key == first.cache_key


def test_model_result_validation_and_embedding_references():
    model_task = task()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    run_id = "taskrun:" + "1" * 32
    with pytest.raises(ValidationError):
        ModelResult(
            record_id="modelresult:" + "2" * 32, created_at=now, producer={"kind":"code","producer_id":"test"},
            model_task_id=model_task.record_id, task_run_id=run_id, output_schema=model_task.output_schema,
            output=Payload(value="x"), validation_status="invalid", validation_errors=(), raw_response_ref="response:x",
            completed_at=now, provider_id="fake", model_snapshot="model-1",
        )
    embedding = EmbeddingResult(
        record_id="embedding:" + "3" * 32, created_at=now, producer={"kind":"code","producer_id":"embed"},
        model_task_id=model_task.record_id, task_run_id=run_id, source_text_artifact_id="derivative:" + "4" * 32,
        source_text_hash="a" * 64, embedding_model_snapshot="model-1", dimensions=3, vector_ref="vector:1",
        vector_hash="b" * 64, validation_status="valid", completed_at=now,
    )
    assert embedding.vector_ref == "vector:1"


def test_task_run_subject_isolation_and_success_requirements():
    first = task()
    second = task(subject_id="subject:" + "2" * 32)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        TaskRun(
            record_id="taskrun:" + "5" * 32, created_at=now, producer={"kind":"code","producer_id":"test"},
            model_task_ids=(first.record_id,), subject_id=first.subject_id, provider_id="fake", model_snapshot="model-1",
            status="succeeded", completed_at=now,
        )
    run = TaskRun(
        record_id="taskrun:" + "6" * 32, created_at=now, producer={"kind":"code","producer_id":"test"},
        model_task_ids=(first.record_id,), subject_id=first.subject_id, provider_id="fake", model_snapshot="model-1",
        status="succeeded", completed_at=now, usage={"input_tokens": 1}, pricing_snapshot_id="pricing:" + "7" * 32,
    )
    validate_task_run_tasks(run, (first,))
    with pytest.raises(ValueError):
        validate_task_run_tasks(run, (second,))
