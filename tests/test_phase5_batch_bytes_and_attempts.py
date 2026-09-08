from datetime import datetime, timezone
from decimal import Decimal
import hashlib

import pytest

from charitygraph.openai_batch_transport import BatchAuthorization, BatchTransportError, OpenAIBatchTransport
from charitygraph.phase5_openai_dry_run import BatchPayloadError, canonical_batch_jsonl_bytes, validate_batch_jsonl_bytes
from charitygraph.runtime import SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_canonical_batch_bytes_are_utf8_lf_only_and_preserve_non_ascii():
    payload = canonical_batch_jsonl_bytes(({"custom_id": "requestitem:one", "body": {"text": "Café"}},), expected_custom_ids=("requestitem:one",))
    assert b"Caf\xc3\xa9" in payload
    assert b"Caf\xe9" not in payload
    assert b"\r" not in payload
    assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
    assert validate_batch_jsonl_bytes(payload)[0]["custom_id"] == "requestitem:one"


@pytest.mark.parametrize("payload", (b"\xef\xbb\xbf{}\n", b'{}\x00\n', b'{"custom_id":"x"\n', b'\xff\n'))
def test_invalid_batch_bytes_fail_closed(payload):
    with pytest.raises(BatchPayloadError):
        validate_batch_jsonl_bytes(payload)


def test_duplicate_or_missing_custom_ids_fail_closed():
    with pytest.raises(BatchPayloadError):
        canonical_batch_jsonl_bytes(({"custom_id": "x"}, {"custom_id": "x"}))
    with pytest.raises(BatchPayloadError):
        canonical_batch_jsonl_bytes(({"custom_id": "x"},), expected_custom_ids=("y",))


def _catalogue(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "runtime.sqlite3").open(initialize=True)
    cohort = "cohort:" + "a" * 32
    run = "run:" + "b" * 32
    task = "modeltask:" + "c" * 64
    catalog.register_cohort({"record_id": cohort, "cohort_code": "BATCH", "definition_version": "1", "membership_hash": "d" * 64, "budget_cap": {"amount": "10", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "batch", "status": "planned", "configuration_hash": "e" * 64, "created_at": NOW})
    catalog.register_task({"record_id": task, "subject_id": "subject:" + "1" * 32, "cohort_id": cohort, "task_type": "semantic_interpretation", "task_schema": {"schema_id": "urn:test"}, "cache_key": "f" * 64, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run, now=NOW)
    item = "requestitem:wire"
    catalog.reserve_cost({"record_id": "reservation:old", "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": (task,)}, now=NOW)
    catalog.create_delivery_job(delivery_job_id="deliveryjob:old", run_id=run, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="batch", pricing_snapshot_id="pricing:test", now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id="physical:old", run_id=run, subject_id="subject:" + "1" * 32, delivery_mode="batch", provider_request_id=item, model_task_ids=(task,), reservation_id="reservation:old", now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=item, run_id=run, model_task_id=task, provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="batch", effective_service_tier="batch", delivery_job_id="deliveryjob:old", physical_attempt_id="physical:old", now=NOW)
    return catalog, run, task, item


def test_reviewed_transport_correction_is_append_only(tmp_path):
    catalog, run, task, item = _catalogue(tmp_path)
    catalog.create_provider_request_attempt(delivery_attempt_id="deliveryattempt:old", provider_request_item_id=item, physical_attempt_id="physical:old", delivery_job_id="deliveryjob:old", attempt_ordinal=1, authorization_id="auth:old", attempt_class="initial", predecessor_attempt_id=None, now=NOW)
    catalog.transition_provider_request_attempt("deliveryattempt:old", "failed", now=NOW, failure_class="batch_validation", failure_message_redacted="invalid UTF-8")
    catalog.create_delivery_job(delivery_job_id="deliveryjob:new", run_id=run, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="batch", pricing_snapshot_id="pricing:test", now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id="physical:new", run_id=run, subject_id="subject:" + "1" * 32, delivery_mode="batch", provider_request_id="physical-request:new", model_task_ids=(task,), reservation_id=None, now=NOW)
    fresh = catalog.create_provider_request_attempt(delivery_attempt_id="deliveryattempt:new", provider_request_item_id=item, physical_attempt_id="physical:new", delivery_job_id="deliveryjob:new", attempt_ordinal=2, authorization_id="auth:new", attempt_class="reviewed_transport_correction", predecessor_attempt_id="deliveryattempt:old", now=NOW)
    assert fresh["status"] == "prepared"
    assert [row["delivery_attempt_id"] for row in catalog.list_provider_request_attempts(provider_request_item_id=item)] == ["deliveryattempt:old", "deliveryattempt:new"]
    assert catalog.get_provider_request_attempt("deliveryattempt:old")["status"] == "failed"
    assert catalog.list_provider_request_items(run)[0]["provider_request_item_id"] == item


class _UploadCapture:
    def __init__(self):
        self.payloads = []

    def upload_batch_file(self, content, *, purpose):
        self.payloads.append((content, purpose))
        return "file:test"

    def create_batch(self, **kwargs):
        return "batch:test"


def test_authorized_payload_mismatch_fails_before_upload(tmp_path):
    catalog, run, task, item = _catalogue(tmp_path)
    client = _UploadCapture()
    good = canonical_batch_jsonl_bytes(({"custom_id": item},), expected_custom_ids=(item,))
    auth = BatchAuthorization(run, "plan:a", "packet:b", "pricing:test", "gpt-5.6-luna", Decimal("0.01"), Decimal("0.02"), Decimal("0.10"), Decimal("0.20"), real_provider_enabled=True, payload_sha256=hashlib.sha256(good).hexdigest(), payload_bytes=len(good), authorized_custom_ids=(item,))
    bad = b'{"custom_id":"requestitem:wire","text":"Caf\xe9"}\n'
    with pytest.raises(BatchTransportError):
        OpenAIBatchTransport(client).submit_batch(catalog, delivery_job_id="deliveryjob:old", request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna", "delivery_job_id": "deliveryjob:old", "physical_attempt_id": "physical:old"}], jsonl=bad, authorization=auth, now=NOW)
    assert client.payloads == []


def test_upload_boundary_receives_authorized_bytes_unchanged(tmp_path):
    catalog, run, task, item = _catalogue(tmp_path)
    client = _UploadCapture()
    payload = canonical_batch_jsonl_bytes(({"custom_id": item, "body": {"text": "Café"}},), expected_custom_ids=(item,))
    auth = BatchAuthorization(run, "plan:a", "packet:b", "pricing:test", "gpt-5.6-luna", Decimal("0.01"), Decimal("0.02"), Decimal("0.10"), Decimal("0.20"), real_provider_enabled=True, payload_sha256=hashlib.sha256(payload).hexdigest(), payload_bytes=len(payload), authorized_custom_ids=(item,))
    OpenAIBatchTransport(client).submit_batch(catalog, delivery_job_id="deliveryjob:old", request_items=[{"provider_request_item_id": item, "status": "prepared", "model": "gpt-5.6-luna", "delivery_job_id": "deliveryjob:old", "physical_attempt_id": "physical:old"}], jsonl=payload, authorization=auth, now=NOW)
    assert client.payloads == [(payload, "batch")]
