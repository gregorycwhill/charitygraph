from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.openai_batch_transport import BatchAuthorization, BatchSubmissionAmbiguous, OpenAIBatchTransport
from charitygraph.runtime import ConflictError, SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class MockBatchClient:
    def __init__(self, *, fail_create=False):
        self.fail_create = fail_create
        self.calls = []

    def upload_batch_file(self, content, *, purpose):
        self.calls.append(("upload", content, purpose))
        return "file-input:one"

    def create_batch(self, *, input_file_id, endpoint, completion_window, metadata):
        self.calls.append(("create", input_file_id, endpoint, completion_window, metadata))
        if self.fail_create:
            raise RuntimeError("synthetic ambiguous create")
        return "batch:one"

    def retrieve_batch(self, batch_id):
        self.calls.append(("status", batch_id))
        return {"id": batch_id, "status": "completed", "output_file_id": "file-output:one"}

    def retrieve_file_content(self, file_id):
        self.calls.append(("file", file_id))
        return b'{"custom_id":"requestitem:two","response":{"id":"resp:one","status":"completed","usage":{"input_tokens":3,"output_tokens":2}}}\n'


def _catalogue(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "runtime.sqlite3").open(initialize=True)
    cohort = "cohort:" + "a" * 32
    run = "run:" + "b" * 32
    task = "modeltask:" + "c" * 64
    catalog.register_cohort({"record_id": cohort, "cohort_code": "BATCH", "definition_version": "1", "membership_hash": "d" * 64, "budget_cap": {"amount": "10", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "batch", "status": "planned", "configuration_hash": "e" * 64, "created_at": NOW})
    catalog.register_task({"record_id": task, "subject_id": "subject:" + "1" * 32, "cohort_id": cohort, "task_type": "semantic_interpretation", "task_schema": {"schema_id": "urn:test"}, "cache_key": "f" * 64, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run, now=NOW)
    reservation = "reservation:" + "1" * 32
    catalog.reserve_cost({"record_id": reservation, "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": (task,)}, now=NOW)
    job = "deliveryjob:" + "2" * 64
    item_id = "requestitem:two"
    attempt = "physical:" + "3" * 64
    catalog.create_delivery_job(delivery_job_id=job, run_id=run, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="batch", pricing_snapshot_id="pricing:test", now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id=attempt, run_id=run, subject_id="subject:" + "1" * 32, delivery_mode="batch", provider_request_id=item_id, model_task_ids=(task,), reservation_id=reservation, now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=item_id, run_id=run, model_task_id=task, provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="batch", effective_service_tier="batch", delivery_job_id=job, physical_attempt_id=attempt, now=NOW)
    return catalog, run, job, item_id, attempt


def _auth(run):
    return BatchAuthorization(run, "plan:" + "a" * 64, "packet:" + "b" * 64, "pricing:test", "gpt-5.6-luna", Decimal("0.01"), Decimal("0.02"), Decimal("0.10"), Decimal("0.20"), real_provider_enabled=True)


def test_default_deny_happens_before_any_provider_operation(tmp_path):
    catalog, run, job, item, attempt = _catalogue(tmp_path)
    client = MockBatchClient()
    auth = _auth(run)
    auth = BatchAuthorization(**{**auth.__dict__, "real_provider_enabled": False})
    with pytest.raises(PermissionError):
        OpenAIBatchTransport(client).submit_batch(catalog, delivery_job_id=job, physical_attempt_id=attempt, request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna"}], jsonl=b"{}\n", authorization=auth, now=NOW)
    assert client.calls == []


def test_batch_lifecycle_persists_file_and_batch_ids_and_reconciles_items(tmp_path):
    catalog, run, job, item, attempt = _catalogue(tmp_path)
    client = MockBatchClient()
    result = OpenAIBatchTransport(client).submit_batch(catalog, delivery_job_id=job, physical_attempt_id=attempt, request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna"}], jsonl=b'{"custom_id":"requestitem:two"}\n', authorization=_auth(run), now=NOW)
    assert result["provider_batch_id"] == "batch:one"
    stored = catalog.get_delivery_job(job)
    assert stored["provider_input_file_id"] == "file-input:one" and stored["provider_batch_id"] == "batch:one"
    reconciled = OpenAIBatchTransport(client).reconcile_batch(catalog, delivery_job_id=job, now=NOW)
    assert reconciled.provider_status == "completed" and reconciled.output_retrieved is True
    assert reconciled.item_statuses[0]["status"] == "completed"
    call_count = len(client.calls)
    again = OpenAIBatchTransport(client).reconcile_batch(catalog, delivery_job_id=job, now=NOW)
    assert again.provider_status == "completed" and len(client.calls) == call_count


def test_ambiguous_create_persists_boundary_and_forbids_resend(tmp_path):
    catalog, run, job, item, attempt = _catalogue(tmp_path)
    client = MockBatchClient(fail_create=True)
    transport = OpenAIBatchTransport(client)
    with pytest.raises(BatchSubmissionAmbiguous):
        transport.submit_batch(catalog, delivery_job_id=job, physical_attempt_id=attempt, request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna"}], jsonl=b'{}\n', authorization=_auth(run), now=NOW)
    assert catalog.get_delivery_job(job)["provider_input_file_id"] == "file-input:one"
    assert catalog.get_physical_attempt(attempt)["status"] == "send_started"
    calls = len(client.calls)
    with pytest.raises(BatchSubmissionAmbiguous):
        transport.submit_batch(catalog, delivery_job_id=job, physical_attempt_id=attempt, request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna"}], jsonl=b'{}\n', authorization=_auth(run), now=NOW)
    assert len(client.calls) == calls


def test_request_item_identity_conflict_fails_closed(tmp_path):
    catalog, run, job, item, attempt = _catalogue(tmp_path)
    with pytest.raises(ConflictError, match="identity conflicts"):
        catalog.create_provider_request_item(provider_request_item_id=item, run_id=run, model_task_id="modeltask:" + "d" * 64, provider_id="openai", model_route="gpt-5.6-terra", requested_delivery_mode="batch", effective_service_tier="batch", delivery_job_id=job, physical_attempt_id=attempt, now=NOW)
