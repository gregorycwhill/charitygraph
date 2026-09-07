from decimal import Decimal

from charitygraph.phase5_delivery import PricingSnapshot, application_bundle_compatible, build_delivery_plan, select_delivery_mode


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
