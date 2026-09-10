from datetime import datetime, timezone

from charitygraph.phase5_standard_transport import StandardCampaignCoordinator
from charitygraph.runtime import SQLiteCatalog

from tests.test_phase5_standard_transport import FakeProvider, _row


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_multi_item_standard_job_stays_open_until_all_items_terminal(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "runtime.sqlite3").open(initialize=True)
    cohort = "cohort:" + "a" * 32
    run = "run:" + "b" * 32
    subject = "subject:" + "c" * 32
    catalog.register_cohort({"record_id": cohort, "cohort_code": "STANDARD", "definition_version": "1", "membership_hash": "d" * 64, "budget_cap": {"amount": "10", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "standard", "status": "planned", "configuration_hash": "e" * 64, "created_at": NOW})
    job = "deliveryjob:" + "f" * 64
    catalog.create_delivery_job(delivery_job_id=job, run_id=run, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id="pricing:test", now=NOW)
    rows = []
    for index in (1, 2):
        row = _row(index)
        row["logical_task_id"] = "modeltask:" + format(index, "064x")
        row["provider_request_item_id"] = "requestitem:" + format(index, "064x")
        row["delivery_attempt_id"] = "deliveryattempt:" + format(index, "064x")
        row["physical_attempt_id"] = "physical:" + format(index, "064x")
        row["request_body"]["metadata"]["logical_task_id"] = row["logical_task_id"]
        row["request_body_sha256"] = __import__("hashlib").sha256(__import__("json").dumps(row["request_body"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        catalog.register_task({"record_id": row["logical_task_id"], "subject_id": subject, "cohort_id": cohort, "task_type": "semantic_interpretation", "task_schema": {"schema_id": "urn:test"}, "cache_key": format(index, "064x"), "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run, now=NOW)
        reservation = "reservation:" + format(index, "064x")
        catalog.reserve_cost({"record_id": reservation, "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": (row["logical_task_id"],)}, now=NOW)
        catalog.prepare_physical_attempt(physical_attempt_id=row["physical_attempt_id"], run_id=run, subject_id=subject, delivery_mode="standard", provider_request_id=row["provider_request_item_id"], model_task_ids=(row["logical_task_id"],), reservation_id=reservation, now=NOW)
        catalog.create_provider_request_item(provider_request_item_id=row["provider_request_item_id"], run_id=run, model_task_id=row["logical_task_id"], provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=job, physical_attempt_id=row["physical_attempt_id"], now=NOW)
        catalog.create_provider_request_attempt(delivery_attempt_id=row["delivery_attempt_id"], provider_request_item_id=row["provider_request_item_id"], physical_attempt_id=row["physical_attempt_id"], delivery_job_id=job, attempt_ordinal=1, authorization_id="mandate:test", attempt_class="initial", predecessor_attempt_id=None, now=NOW)
        row.update({"run_id": run, "reservation_id": reservation, "mandate_reservation_id": reservation, "hard_max_aud": "1", "provider_schema_name": row["provider_schema_name"], "scope_id": None, "evidence_ids": []})
        rows.append(row)
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=1, now=NOW).run(rows)
    assert result["counts"] == {"completed": 2}
    assert provider.posts.__len__() == 2
    assert catalog.get_delivery_job(job)["status"] == "completed"
