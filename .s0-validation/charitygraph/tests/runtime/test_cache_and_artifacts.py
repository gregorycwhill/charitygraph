from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def catalog(tmp_path):
    value = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    now = NOW
    cohort = {"record_id": "cohort:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "cohort_code": "SPIKE", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": "100", "currency": "AUD"}, "created_at": now}
    run = {"record_id": "run:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "cohort_id": cohort["record_id"], "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": now}
    task = {"record_id": "modeltask:1", "subject_id": "subject:1", "task_type": "structured_extraction", "task_schema": {"schema_id": "urn:test"}, "cache_key": "c" * 64, "provider_id": "fake", "model_snapshot": "test"}
    value.register_cohort(cohort)
    value.register_run(run)
    value.register_task(task, run_id=run["record_id"], now=now)
    return value


def test_operation_receipts_are_idempotent(tmp_path):
    value = catalog(tmp_path)
    first = value.begin_operation("op-1", operation_type="test", request_hash="a" * 64, now=NOW)
    assert value.begin_operation("op-1", operation_type="test", request_hash="a" * 64, now=NOW)["state"] == "started"
    completed = value.complete_operation("op-1", request_hash="a" * 64, result_ref="result:1", now=NOW)
    assert completed["state"] == "completed"
    assert value.complete_operation("op-1", request_hash="a" * 64, result_ref="result:2", now=NOW)["result_ref"] == "result:1"
    with pytest.raises(ConflictError):
        value.begin_operation("op-1", operation_type="test", request_hash="b" * 64, now=NOW)


def test_cache_invalidation_requires_explicit_replacement(tmp_path):
    value = catalog(tmp_path)
    value.put_cache(cache_key="cache-1", model_task_id="modeltask:1", result_artifact_id="artifact:1", result_content_hash="a" * 64, created_at=NOW)
    assert value.get_cache("cache-1")["status"] == "valid"
    value.invalidate_cache("cache-1", invalidated_at=NOW, reason="source changed")
    assert value.get_cache("cache-1") is None
    with pytest.raises(ConflictError):
        value.put_cache(cache_key="cache-1", model_task_id="modeltask:1", result_artifact_id="artifact:2", result_content_hash="b" * 64, created_at=NOW)
    assert value.put_cache(cache_key="cache-1", model_task_id="modeltask:1", result_artifact_id="artifact:2", result_content_hash="b" * 64, created_at=NOW, replace_invalidated=True)["status"] == "valid"


def test_artifact_index_is_metadata_only_and_hash_conflicts_fail(tmp_path):
    value = catalog(tmp_path)
    indexed = value.index_artifact(artifact_id="artifact:1", content_hash="a" * 64, schema_id="urn:test", schema_version="1", storage_path="private/path", availability="available", created_at=NOW, indexed_at=NOW)
    assert value.index_artifact(artifact_id="artifact:1", content_hash="a" * 64, schema_id="urn:test", schema_version="1", storage_path="private/path", availability="available", created_at=NOW, indexed_at=NOW)["artifact_id"] == indexed["artifact_id"]
    with pytest.raises(ConflictError):
        value.index_artifact(artifact_id="artifact:1", content_hash="b" * 64, schema_id="urn:test", schema_version="1", storage_path="private/path", availability="available", created_at=NOW, indexed_at=NOW)
