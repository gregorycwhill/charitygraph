from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_factory_integration import (
    GovernedReference,
    preflight_governed_references,
)
from charitygraph.phase5_real_five_charity_factory_v2 import (
    load_real_five_charity_evidence,
    preflight_real_five_charity_references,
    replay_real_five_charity_factory_v2,
)


_fixture_path = Path(__file__).with_name("test_phase5_governed_factory_integration.py")
_fixture_spec = importlib.util.spec_from_file_location("g4_o1c_integration_fixture", _fixture_path)
assert _fixture_spec is not None and _fixture_spec.loader is not None
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_module)
NOW = _fixture_module.NOW
_fixture = _fixture_module._fixture
_run = _fixture_module._run


def _work_counts(catalog) -> dict[str, int]:
    with catalog._connection() as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "tasks",
                "physical_attempts",
                "provider_receipts",
                "budget_reservations",
                "cost_entries",
                "provider_request_attempts",
            )
        }


def _assert_no_factory_or_provider_work(catalog, reference) -> list[dict]:
    try:
        result = preflight_governed_references(
            [reference],
            catalog=catalog,
            retained_bytes=lambda _: b"represented source 1",
            planned_processing_at=NOW,
        )
        assert result.accepted_count == 0
        assert result.diagnostics[0].state == "rights_missing"

        cohort_id, run_id = _run(catalog, "empty", "empty")
        runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
        assert runner.seed(NOW) == ()
        assert runner.run(NOW) == 0
        assert _work_counts(catalog) == {
            "tasks": 0,
            "physical_attempts": 0,
            "provider_receipts": 0,
            "budget_reservations": 0,
            "cost_entries": 0,
            "provider_request_attempts": 0,
        }
        return catalog.get_provider_rights_diagnostics(reference.reference_id)
    finally:
        catalog.close()


@pytest.mark.parametrize("reference_form", ["empty", "omitted"])
def test_empty_or_missing_rights_decision_reference_is_missing_and_no_work(tmp_path, reference_form):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    payload = reference.model_dump()
    payload["reference_id"] = f"rights-{reference_form}"
    if reference_form == "empty":
        payload["rights_decision_ids"] = ()
    else:
        payload.pop("rights_decision_ids")
    variant = GovernedReference.model_validate(payload)

    diagnostics = _assert_no_factory_or_provider_work(catalog, variant)
    assert diagnostics[-1]["state"] == "rights_missing"


def test_affirmative_rights_preserve_same_scope_factory_task(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    try:
        result = preflight_governed_references(
            [reference],
            catalog=catalog,
            retained_bytes=lambda _: b"represented source 1",
            planned_processing_at=NOW,
        )
        assert result.accepted_count == 1
        assert not result.diagnostics
        assert result.tasks[0]["subject_id"] == reference.subject_id
        assert result.tasks[0]["scope_id"] == reference.scope_id
        assert result.tasks[0]["_model_task"].parameters["rights_decision_ids"] == [
            reference.rights_decision_ids[0]
        ]

        cohort_id, run_id = _run(catalog, "affirmative", "affirmative")
        runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
        seeded = runner.seed(NOW)
        assert len(seeded) == 1
        task = catalog.get_task(seeded[0]["record_id"])
        assert task["subject_id"] == reference.subject_id
        assert task["scope_id"] == reference.scope_id
    finally:
        catalog.close()


def test_committed_five_charity_replay_is_deterministic_and_scope_isolated(tmp_path):
    replay = replay_real_five_charity_factory_v2(work_root=tmp_path / "replay")
    assert replay["replay"]["stable"]["identities_and_diagnostics_stable"] is True
    assert replay["factory"]["executed_tasks"] == 5
    assert replay["factory"]["second_run_executed_tasks"] == 0
    assert replay["factory"]["provider_calls"] == 0

    evidence = load_real_five_charity_evidence()
    other_scope = evidence.references[1].scope_id
    isolated = evidence.references[0].model_copy(update={"scope_id": other_scope})
    result = preflight_real_five_charity_references(
        evidence,
        (isolated, *evidence.references[1:]),
    )
    assert any(
        item.state == "mismatched" and item.reason == "scope is owned by a different subject"
        for item in result.diagnostics
    )
