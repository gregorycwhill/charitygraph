from decimal import Decimal
from datetime import datetime, timezone

from charitygraph.phase5_delivery import DeliveryJob, FakeDeliveryAdapter, PricingSnapshot, application_bundle_compatible, build_delivery_plan, delivery_chaos_populations, select_delivery_mode
from charitygraph.contracts.ids import deterministic_id
from charitygraph.runtime import SQLiteCatalog


def _task(task_id: str, **extra):
    return {"logical_task_id": task_id, "subject_id": "subject:" + "1" * 32, "difficulty": "lower_cost_constrained_semantic", "physical_bundle_opportunity": "opportunity", **extra}


def test_opportunity_is_not_bundle_authorisation_without_multiplex_contract() -> None:
    tasks = [_task("a"), _task("b")]
    assert not application_bundle_compatible(tasks)
    plan = build_delivery_plan(tasks)
    assert len(plan.request_items) == 2


def test_explicit_common_multiplex_contract_allows_application_bundle() -> None:
    tasks = [_task("a", multiplex_contract="schema:composite", reasoning_settings="r", tool_policy="none", response_envelope="json"), _task("b", multiplex_contract="schema:composite", reasoning_settings="r", tool_policy="none", response_envelope="json")]
    assert application_bundle_compatible(tasks)
    assert len(build_delivery_plan(tasks).request_items) == 1


def test_delivery_policy_prefers_batch_then_flex_then_standard() -> None:
    assert select_delivery_mode(_task("a")) == "batch"
    assert select_delivery_mode(_task("b", batch_supported=False)) == "flex"
    assert select_delivery_mode(_task("c", latency_required=True)) == "standard"


def test_batch_is_many_independent_items_and_exact_economics() -> None:
    plan = build_delivery_plan([_task(str(index)) for index in range(3)], pricing=PricingSnapshot())
    assert len(plan.delivery_jobs) == 1 and len(plan.delivery_jobs[0].request_item_ids) == 3
    assert plan.economics()["all_standard"] == Decimal("0.006000")
    assert plan.economics()["selected"] == Decimal("0.001500")


def test_delivery_chaos_selection_returns_full_deterministic_populations() -> None:
    plan=build_delivery_plan([_task(str(index)) for index in range(200)])
    first=delivery_chaos_populations(plan); second=delivery_chaos_populations(plan)
    assert first == second and sum(len(items) for items in first.values()) > 1


def _catalogue(tmp_path):
    now=datetime(2026, 1, 1, tzinfo=timezone.utc); cohort="cohort:"+"a"*32; run="run:"+"b"*32
    catalog=SQLiteCatalog(tmp_path/'delivery.sqlite3').open(initialize=True)
    catalog.register_cohort({"record_id":cohort,"cohort_code":"DELIVERY","definition_version":"1","membership_hash":"c"*64,"budget_cap":{"amount":"100","currency":"AUD"},"created_at":now})
    catalog.register_run({"record_id":run,"cohort_id":cohort,"run_kind":"delivery","status":"planned","configuration_hash":"d"*64,"created_at":now})
    task="modeltask:"+"e"*64
    catalog.register_task({"record_id":task,"subject_id":"subject:"+"1"*32,"cohort_id":cohort,"task_type":"structured_extraction","task_schema":{"schema_id":"urn:test"},"cache_key":"f"*64,"provider_id":"fake","model_snapshot":"test"},run_id=run,now=now)
    return catalog,run,task,now


def test_batch_recovery_states_are_durable_and_no_duplicate_submission(tmp_path) -> None:
    catalog,run,task,now=_catalogue(tmp_path); job="deliveryjob:"+"1"*64; item="requestitem:"+"2"*64
    catalog.create_delivery_job(delivery_job_id=job,run_id=run,provider_id="fake",model_route="test",delivery_mode="batch",pricing_snapshot_id="pricing:test",now=now)
    catalog.create_provider_request_item(provider_request_item_id=item,run_id=run,model_task_id=task,provider_id="fake",model_route="test",requested_delivery_mode="batch",effective_service_tier="batch",delivery_job_id=job,now=now)
    # B1: prepared state survives a restart without any submission identity.
    assert SQLiteCatalog(tmp_path/'delivery.sqlite3').open(initialize=False).get_delivery_job(job)["status"] == "prepared"
    # B2/B3: a single submission ID persists; in-progress recovery does not create another job.
    catalog.transition_delivery_job(job,"submitted",now=now,provider_batch_id="fake-batch:one")
    catalog.transition_delivery_job(job,"in_progress",now=now)
    catalog.transition_provider_request_item(item,"submitted",now=now,provider_request_id="fake-request:one")
    catalog.transition_provider_request_item(item,"send_ambiguous",now=now)
    assert SQLiteCatalog(tmp_path/'delivery.sqlite3').open(initialize=False).get_delivery_job(job)["provider_batch_id"] == "fake-batch:one"
    assert catalog.list_provider_request_items(run)[0]["status"] == "send_ambiguous"
    reconciled=FakeDeliveryAdapter().reconcile_batch(catalog, DeliveryJob(job,"batch","fake","test",(item,)))
    assert reconciled["provider_batch_id"] == "fake-batch:one" and reconciled["items"][0]["status"] == "send_ambiguous"


def test_batch_partial_expiry_and_duplicate_result_replay(tmp_path) -> None:
    catalog,run,task,now=_catalogue(tmp_path); job="deliveryjob:"+"3"*64; item="requestitem:"+"4"*64
    second_task="modeltask:"+"9"*64
    catalog.register_task({"record_id":second_task,"subject_id":"subject:"+"1"*32,"cohort_id":"cohort:"+"a"*32,"task_type":"structured_extraction","task_schema":{"schema_id":"urn:test"},"cache_key":"a"*64,"provider_id":"fake","model_snapshot":"test"},run_id=run,now=now)
    catalog.create_delivery_job(delivery_job_id=job,run_id=run,provider_id="fake",model_route="test",delivery_mode="batch",pricing_snapshot_id="pricing:test",now=now)
    catalog.create_provider_request_item(provider_request_item_id=item,run_id=run,model_task_id=task,provider_id="fake",model_route="test",requested_delivery_mode="batch",effective_service_tier="batch",delivery_job_id=job,now=now)
    second_item="requestitem:"+"b"*64
    catalog.create_provider_request_item(provider_request_item_id=second_item,run_id=run,model_task_id=second_task,provider_id="fake",model_route="test",requested_delivery_mode="batch",effective_service_tier="batch",delivery_job_id=job,now=now)
    catalog.transition_delivery_job(job,"submitted",now=now,provider_batch_id="fake-batch:two"); catalog.transition_delivery_job(job,"in_progress",now=now)
    catalog.transition_provider_request_item(item,"submitted",now=now,provider_request_id="fake-request:two"); catalog.transition_provider_request_item(item,"in_progress",now=now)
    first=catalog.transition_provider_request_item(item,"completed",now=now,provider_receipt_id="fake-receipt:two",result_ref="fake-result",usage={"input_tokens":1})
    replay=catalog.transition_provider_request_item(item,"completed",now=now,provider_receipt_id="fake-receipt:two",result_ref="fake-result",usage={"input_tokens":1})
    assert first["provider_receipt_id"] == replay["provider_receipt_id"] == "fake-receipt:two"
    catalog.transition_provider_request_item(second_item,"submitted",now=now,provider_request_id="fake-request:expired"); catalog.transition_provider_request_item(second_item,"in_progress",now=now); catalog.transition_provider_request_item(second_item,"expired",now=now)
    catalog.transition_delivery_job(job,"expired",now=now)
    states={row["provider_request_item_id"]:row["status"] for row in catalog.list_provider_request_items(run)}
    assert states[item] == "completed" and states[second_item] == "expired" and catalog.get_delivery_job(job)["status"] == "expired"


def test_flex_and_standard_remain_individual_delivery_jobs(tmp_path) -> None:
    for mode, suffix in (("flex","5"),("standard","6")):
        catalog,run,task,now=_catalogue(tmp_path / mode)
        job="deliveryjob:"+suffix*64; item="requestitem:"+("7" if mode=="flex" else "8")*64
        catalog.create_delivery_job(delivery_job_id=job,run_id=run,provider_id="fake",model_route="test",delivery_mode=mode,pricing_snapshot_id="pricing:test",now=now)
        catalog.create_provider_request_item(provider_request_item_id=item,run_id=run,model_task_id=task,provider_id="fake",model_route="test",requested_delivery_mode=mode,effective_service_tier=mode,delivery_job_id=job,now=now)
        assert catalog.get_delivery_job(job)["delivery_mode"] == mode
