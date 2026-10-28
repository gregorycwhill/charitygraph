from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from charitygraph.phase5_factory import (
    AmbiguousSendError,
    FactoryPlan,
    ReferenceFactory,
)
from charitygraph.phase5_governed_cohort_rehearsal import (
    CountingFakeProvider,
    NOW,
    build_test_fixture,
    persisted_diagnostic,
    register_test_run,
    table_counts,
)
from charitygraph.phase5_governed_rights_preflight import preflight_governed_rights
from charitygraph.phase5_delivery import DeliveryPolicy
from charitygraph.runtime import SQLiteCatalog


def _preflight(fixture, references=None):
    references = references or tuple(material.request for material in fixture.materials)
    retained = {
        material.representation_artifact_id: material.representation_bytes
        for material in fixture.materials
    }
    return preflight_governed_rights(
        references,
        store=fixture.rights_store,
        projection=fixture.projection,
        catalog=fixture.catalog,
        as_of=fixture.now.date(),
        retained_bytes=retained.__getitem__,
    )


def _physical_id(runner: ReferenceFactory, tasks: tuple[dict, ...]) -> str:
    package_id = __import__(
        "charitygraph.contracts.ids", fromlist=["deterministic_id"]
    ).deterministic_id(
        "taskrun:",
        {"members": [task["record_id"] for task in tasks], "mode": runner.delivery_mode},
    )
    return "physical:" + package_id.split(":", 1)[1]


def test_clean_import_has_no_dirty_rights_seam(tmp_path):
    fixture = build_test_fixture(tmp_path)
    try:
        from charitygraph.phase5_governed_factory_integration import GovernedReference

        assert "rights_decision_ids" not in GovernedReference.model_fields
        assert not hasattr(SQLiteCatalog, "get_artifact_rights_decisions")
        with fixture.catalog._connection() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert not any(name.startswith("artifact_rights_") for name in tables)
        assert "rights_projection_current" in tables
    finally:
        fixture.close()


def test_authority_current_row_lowers_deterministically_to_factory_and_replays(tmp_path):
    fixture = build_test_fixture(tmp_path)
    try:
        material = fixture.materials[0]
        current = fixture.projection.current_record(
            record_id=material.rights_record.content_hash,
            subject_id=material.subject_id,
            scope=material.scope_id,
            as_of=fixture.now.date(),
        )
        assert current["record_id"] == material.rights_record.content_hash
        first = _preflight(fixture)
        second = _preflight(fixture)
        assert first.accepted_count == second.accepted_count == 1
        assert not first.diagnostics
        assert first.tasks[0]["logical_task_id"] == second.tasks[0]["logical_task_id"]
        assert first.tasks[0]["rights_policy_ids"] == ("CC_BY_4_0_V1",)
        assert first.tasks[0]["representation_hashes"] == (
            (material.representation_artifact_id, material.rights_record.representation_sha256),
        )

        cohort_id, run_id = register_test_run(fixture.catalog)
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            fixture.catalog,
            first.factory_plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
        )
        tasks = runner.seed(NOW)
        assert runner.run(NOW) == 1
        first_diagnostic = persisted_diagnostic(fixture.catalog, run_id)
        assert first_diagnostic.document["summary"]["provider_posts"] == 1
        assert first_diagnostic.document["ledger"]["reconciliation"]["state"] == "RECONCILED"
        counts_before_replay = table_counts(fixture.catalog)
        assert runner.run(NOW) == 0
        second_diagnostic = persisted_diagnostic(fixture.catalog, run_id)
        assert provider.send_calls == 1
        assert second_diagnostic.sha256 == first_diagnostic.sha256
        assert table_counts(fixture.catalog) == counts_before_replay == (1, 1, 1, 1, 1, 2)
        assert fixture.catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")
        with fixture.catalog._connection() as conn:
            attempt = conn.execute("SELECT * FROM task_attempts").fetchone()
            receipt = conn.execute("SELECT * FROM provider_receipts").fetchone()
            costs = conn.execute("SELECT entry_key, entry_type FROM cost_entries ORDER BY entry_key").fetchall()
        assert attempt["task_run_id"].startswith("taskrun:")
        assert receipt["provider_receipt_id"].startswith("fake-receipt:")
        assert [row[1] for row in costs] == ["actual", "reservation_release"]
    finally:
        fixture.close()


def test_denial_and_projection_mismatch_create_no_runtime_side_effects(tmp_path):
    fixture = build_test_fixture(tmp_path)
    try:
        material = fixture.materials[0]
        before = table_counts(fixture.catalog)
        denied = material.request.model_copy(update={"rights_record_id": "f" * 64})
        result = _preflight(fixture, (denied,))
        assert result.accepted_count == 0
        assert result.diagnostics[0].state == "blocked"
        assert table_counts(fixture.catalog) == before == (0, 0, 0, 0, 0, 0)

        with fixture.projection._catalog._connection(immediate=True) as conn:
            conn.execute(
                "UPDATE rights_projection_records SET source_role='tampered-role' WHERE record_id=?",
                (material.rights_record.content_hash,),
            )
            fixture.projection._catalog._commit(conn)
        mismatched = _preflight(fixture)
        assert mismatched.accepted_count == 0
        assert mismatched.diagnostics[0].state == "mismatched"
        assert table_counts(fixture.catalog) == before
    finally:
        fixture.close()


def test_standard_item_failure_is_isolated_to_that_subject(tmp_path):
    fixture = build_test_fixture(tmp_path, ("one", "two"))
    try:
        result = _preflight(fixture)
        cohort_id, run_id = register_test_run(fixture.catalog, suffix="failure")
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            fixture.catalog,
            result.factory_plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
        )
        tasks = runner.seed(NOW)
        failed = _physical_id(runner, (tasks[0],))
        assert runner.run(NOW, failures={failed: "structural"}) == 2
        statuses = {
            task["subject_id"]: fixture.catalog.get_task(task["record_id"])["status"]
            for task in tasks
        }
        assert set(statuses.values()) == {"failed_terminal", "succeeded"}
        assert provider.send_calls == 2
        assert runner.run(NOW) == 0
        assert provider.send_calls == 2
    finally:
        fixture.close()


def test_batch_is_planned_without_a_batch_send(tmp_path):
    fixture = build_test_fixture(tmp_path)
    try:
        reference = fixture.materials[0].request
        second = reference.model_copy(update={
            "reference_id": reference.reference_id + ":second",
            "claim_family_id": "g4-t2-test-second-claim",
            "task_profile": "g4_t2_test_second_task",
        })
        result = _preflight(fixture, (reference, second))
        assert result.accepted_count == 2
        assert len(result.factory_plan.physical_packages(delivery_mode="batch")) == 1
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            object(),
            result.factory_plan,
            cohort_id="cohort:test",
            run_id="run:test",
            provider=provider,
            delivery_mode="batch",
            delivery_policy=DeliveryPolicy.build(reviewed_batch_override=True),
        )
        assert runner.delivery_mode == "batch"
        assert provider.send_calls == 0
    finally:
        fixture.close()


def test_ambiguous_crossing_is_held_and_reconciled_without_resend(tmp_path):
    fixture = build_test_fixture(tmp_path)
    try:
        result = _preflight(fixture)
        cohort_id, run_id = register_test_run(fixture.catalog, suffix="ambiguous")
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            fixture.catalog,
            result.factory_plan,
            cohort_id=cohort_id,
            run_id=run_id,
            provider=provider,
        )
        tasks = runner.seed(NOW)
        physical_id = _physical_id(runner, tasks)
        with pytest.raises(AmbiguousSendError):
            runner.run(NOW, interruptions={physical_id: "send_ambiguous"})
        package_id = "taskrun:" + physical_id.split(":", 1)[1]
        assert provider.send_calls == 1
        assert fixture.catalog.get_physical_attempt(physical_id)["status"] == "send_started"
        runner.reconcile_ambiguous_package(package_id, now=NOW)
        assert provider.reconciliation_calls == 1
        assert runner.run(NOW) == 1
        assert runner.run(NOW) == 0
        assert provider.send_calls == 1
        assert fixture.catalog.get_physical_attempt(physical_id)["status"] == "validated"
    finally:
        fixture.close()

