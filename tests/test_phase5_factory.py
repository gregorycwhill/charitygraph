from charitygraph.phase5_factory import FactoryPlan
from charitygraph.runtime import SQLiteCatalog
from datetime import datetime, timezone
from decimal import Decimal


def test_factory_plan_keeps_logical_identity_and_never_crosses_subjects() -> None:
    plan = FactoryPlan.from_manifest([
        {"logical_task_id": "a", "subject_id": "subject:one", "physical_bundle_opportunity": "bundle:x"},
        {"logical_task_id": "b", "subject_id": "subject:one", "physical_bundle_opportunity": "bundle:x"},
        {"logical_task_id": "c", "subject_id": "subject:two", "physical_bundle_opportunity": "bundle:x"},
    ])
    assert [len(x) for x in plan.packages()] == [2, 1]
    assert len(plan.manifest_hash) == 64


def test_rehearsal_provider_is_deterministic_and_has_no_output_payload() -> None:
    from charitygraph.phase5_factory import RehearsalFakeProvider
    task={"cache_key":"a"*64}
    first=RehearsalFakeProvider().execute(task); second=RehearsalFakeProvider().execute(task)
    assert first == second and first.raw_result_ref.startswith("rehearsal-result:")


def test_reference_runner_is_durable_and_noops_after_terminal_run(tmp_path) -> None:
    now=datetime(2026,1,1,tzinfo=timezone.utc); cohort="cohort:"+"a"*32; run="run:"+"b"*32
    catalog=SQLiteCatalog(tmp_path/'factory.sqlite3').open(initialize=True)
    catalog.register_cohort({"record_id":cohort,"cohort_code":"REHEARSAL","definition_version":"1","membership_hash":"c"*64,"budget_cap":{"amount":"100","currency":"AUD"},"created_at":now})
    catalog.register_run({"record_id":run,"cohort_id":cohort,"run_kind":"phase5_factory_rehearsal","status":"planned","configuration_hash":"d"*64,"created_at":now})
    from charitygraph.phase5_factory import ReferenceFactory
    plan=FactoryPlan.from_manifest([{"logical_task_id":"x","subject_id":"subject:"+"1"*32,"physical_bundle_opportunity":None,"difficulty":"deterministic"}])
    runner=ReferenceFactory(catalog,plan,cohort_id=cohort,run_id=run); runner.seed(now)
    assert runner.run(now)==1 and runner.run(now)==0


def test_fake_semantic_path_reconciles_its_synthetic_reservation(tmp_path) -> None:
    now=datetime(2026,1,1,tzinfo=timezone.utc); cohort="cohort:"+"a"*32; run="run:"+"c"*32
    catalog=SQLiteCatalog(tmp_path/'factory.sqlite3').open(initialize=True)
    catalog.register_cohort({"record_id":cohort,"cohort_code":"REHEARSAL","definition_version":"1","membership_hash":"c"*64,"budget_cap":{"amount":"100","currency":"AUD"},"created_at":now})
    catalog.register_run({"record_id":run,"cohort_id":cohort,"run_kind":"phase5_factory_rehearsal","status":"planned","configuration_hash":"d"*64,"created_at":now})
    from charitygraph.phase5_factory import ReferenceFactory
    plan=FactoryPlan.from_manifest([{"logical_task_id":"x","subject_id":"subject:"+"1"*32,"physical_bundle_opportunity":None,"difficulty":"lower_cost_constrained_semantic"}])
    runner=ReferenceFactory(catalog,plan,cohort_id=cohort,run_id=run); runner.seed(now); assert runner.run(now)==1
    assert catalog.budget_position(cohort).actual_spend_aud == Decimal("0.001")


def test_physical_attempt_persists_send_then_receipt(tmp_path) -> None:
    now=datetime(2026,1,1,tzinfo=timezone.utc); cohort="cohort:"+"a"*32; run="run:"+"d"*32
    catalog=SQLiteCatalog(tmp_path/'factory.sqlite3').open(initialize=True)
    catalog.register_cohort({"record_id":cohort,"cohort_code":"REHEARSAL","definition_version":"1","membership_hash":"c"*64,"budget_cap":{"amount":"100","currency":"AUD"},"created_at":now}); catalog.register_run({"record_id":run,"cohort_id":cohort,"run_kind":"phase5_factory_rehearsal","status":"planned","configuration_hash":"d"*64,"created_at":now})
    plan=FactoryPlan.from_manifest([{"logical_task_id":"x","subject_id":"subject:"+"1"*32,"physical_bundle_opportunity":None,"difficulty":"deterministic"}]); task=plan.runtime_tasks(cohort_id=cohort)[0]; catalog.register_task(task,run_id=run,now=now)
    attempt="physical:one"; catalog.prepare_physical_attempt(physical_attempt_id=attempt,run_id=run,subject_id=task['subject_id'],delivery_mode='batch',provider_request_id='fake-request:x',model_task_ids=(task['record_id'],),reservation_id=None,now=now)
    assert catalog.mark_physical_send_started(attempt,now=now)['status']=='send_started'
    assert catalog.persist_provider_receipt(physical_attempt_id=attempt,provider_receipt_id='fake-receipt:x',raw_result_ref='rehearsal:x',usage={},now=now)['physical_attempt_id']==attempt
