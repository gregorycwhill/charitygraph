from __future__ import annotations

import json
from pathlib import Path

import pytest

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_factory import AmbiguousSendError, ReferenceFactory
from charitygraph.phase5_governed_cohort_rehearsal import (
    CountingFakeProvider,
    build_test_fixture,
    persisted_diagnostic,
    register_test_run,
)
from charitygraph.phase5_governed_real_cohort_rehearsal import (
    build_real_evidence_factory_plan,
    execute_real_evidence_factory_plan,
)
from charitygraph.phase5_governed_rights_preflight import preflight_governed_rights
from charitygraph.phase5_delivery import DeliveryPolicy


ARCHIVE_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects")
EXECUTION_CONTEXT = {
    "bridge_fence": "v48",
    "branch": "gate3-cg406-remediation",
    "head": "18668e7b197086ab95e1faf6ba5aa665377164dd",
}


def _copy_selected_archive(destination: Path, *, omit_ordinal: int | None = None, tampered_ordinal: int | None = None) -> Path:
    from charitygraph.phase5_governed_source_binding import SELECTED_ROWS

    for row in SELECTED_ROWS:
        if row.ordinal == omit_ordinal:
            continue
        source = ARCHIVE_ROOT / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target = destination / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered") if row.ordinal == tampered_ordinal else target.write_bytes(source.read_bytes())
    return destination


def _real_plan(tmp_path: Path, **kwargs):
    return build_real_evidence_factory_plan(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path / "real-work",
        execution_context=EXECUTION_CONTEXT,
        **kwargs,
    )


def test_real_five_subject_ten_source_binding_lowers_to_clean_factory_and_replays(tmp_path):
    first = _real_plan(tmp_path / "first")
    second = _real_plan(tmp_path / "second")

    assert first.blocked_reason is None
    assert first.manifest["schema"] == "charitygraph.gate4.t3.selected-binding-manifest/v2"
    assert first.manifest["source_evidence_provenance"]["epoch"] == "v45"
    assert first.manifest["bridge_execution_context"] == EXECUTION_CONTEXT
    assert first.manifest["source_evidence_provenance"]["epoch"] != EXECUTION_CONTEXT["bridge_fence"]
    assert len({row["subject_id"] for row in first.manifest["rows"]}) == 5
    assert len(first.manifest["rows"]) == 10
    assert first.preflight.accepted_count == 10
    assert len(first.task_ids) == 10
    assert first.task_ids == second.task_ids
    assert first.cohort_plan_sha256 == second.cohort_plan_sha256
    assert first.cohort_id == second.cohort_id
    assert first.cohort_plan["coverage"] == {
        "candidate_rows": 10,
        "admitted_subject_count": 5,
        "admitted_source_count": 10,
        "eligible_rows": 10,
        "task_count": 10,
        "missingness": {
            "missing": 0,
            "mismatched": 0,
            "excluded": 0,
            "not_task_eligible": 0,
            "other_statuses": [],
        },
    }
    assert first.cohort_plan_sha256 == __import__("hashlib").sha256(
        json.dumps(first.cohort_plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    provider = CountingFakeProvider()
    execution = execute_real_evidence_factory_plan(
        first,
        work_root=tmp_path / "first" / "real-work",
        provider=provider,
    )
    replay = execute_real_evidence_factory_plan(
        first,
        work_root=tmp_path / "first" / "real-work",
        provider=provider,
    )
    assert execution.task_count == execution.completed_tasks == 10
    assert execution.attempt_count == 10
    assert execution.fake_send_calls == 0
    assert provider.send_calls == 0
    assert execution.aud_actual == execution.aud_released == "0"
    assert replay.diagnostic_sha256 == execution.diagnostic_sha256
    assert replay.completed_tasks == 0
    assert provider.send_calls == 0


@pytest.mark.parametrize("case", ("missing", "mismatched", "hash_tampered", "excluded", "source_epoch"))
def test_real_negative_inputs_fail_closed_before_factory_work(tmp_path, case):
    work = tmp_path / case
    if case == "missing":
        archive = _copy_selected_archive(work / "archive", omit_ordinal=2)
        plan = build_real_evidence_factory_plan(
            source_archive_root=archive,
            work_root=work / "real-work",
            execution_context=EXECUTION_CONTEXT,
        )
    elif case == "hash_tampered":
        archive = _copy_selected_archive(work / "archive", tampered_ordinal=2)
        plan = build_real_evidence_factory_plan(
            source_archive_root=archive,
            work_root=work / "real-work",
            execution_context=EXECUTION_CONTEXT,
        )
    elif case == "excluded":
        from charitygraph.phase5_governed_source_binding import ExclusionEvidence

        plan = _real_plan(work, exclusions={
            4: ExclusionEvidence(
                material="retained ACNC AIS row",
                authority="bounded test authority",
                wording="excluded for provider-free negative-path verification",
                affected_operation="Factory lowering",
            )
        })
    elif case == "source_epoch":
        plan = _real_plan(work, source_evidence_epoch="v44")
    else:
        plan = _real_plan(work, selected_manifest_sha256="0" * 64)

    assert plan.blocked_reason is not None
    assert plan.factory_plan.logical_tasks == ()
    assert plan.preflight.accepted_count == 0
    assert plan.task_ids == ()
    if plan.manifest is not None:
        assert plan.manifest["summary"]["downstream_tasks"] == 0
    if (work / "real-work" / "catalog.sqlite3").is_file():
        from charitygraph.runtime import SQLiteCatalog

        catalog = SQLiteCatalog(work / "real-work" / "catalog.sqlite3").open(initialize=True)
        try:
            with catalog._connection() as conn:
                counts = tuple(int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in (
                    "tasks", "task_attempts", "physical_attempts", "budget_reservations", "provider_receipts", "cost_entries",
                ))
            assert counts == (0, 0, 0, 0, 0, 0)
        finally:
            catalog.close()


def test_existing_standard_fake_provider_mechanics_are_fixture_only(tmp_path):
    fixture = build_test_fixture(tmp_path / "synthetic", ("one", "two"))
    try:
        result = preflight_governed_rights(
            tuple(material.request for material in fixture.materials),
            store=fixture.rights_store,
            projection=fixture.projection,
            catalog=fixture.catalog,
            as_of=fixture.now.date(),
            retained_bytes=fixture.artifacts.read,
        )
        cohort_id, run_id = register_test_run(fixture.catalog, suffix="real-integration-mechanics")
        provider = CountingFakeProvider()
        runner = ReferenceFactory(
            fixture.catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id, provider=provider,
        )
        tasks = runner.seed(fixture.now)
        failed_physical = "physical:" + deterministic_id(
            "taskrun:", {"members": [tasks[0]["record_id"]], "mode": "standard"}
        ).split(":", 1)[1]
        assert runner.run(fixture.now, failures={failed_physical: "structural"}) == 2
        assert provider.send_calls == 2
        assert runner.run(fixture.now) == 0
        assert provider.send_calls == 2
        diagnostic = persisted_diagnostic(fixture.catalog, run_id)
        assert diagnostic.document["summary"]["provider_posts"] == 2

        batch_result = preflight_governed_rights(
            (fixture.materials[0].request, fixture.materials[0].request.model_copy(update={
                "reference_id": "governed-rights-ref:g4-t2-batch-second",
                "claim_family_id": "g4-t2-batch-second",
                "task_profile": "g4_t2_batch_second",
            })),
            store=fixture.rights_store,
            projection=fixture.projection,
            catalog=fixture.catalog,
            as_of=fixture.now.date(),
            retained_bytes=fixture.artifacts.read,
        )
        batch_provider = CountingFakeProvider()
        batch_runner = ReferenceFactory(
            object(), batch_result.factory_plan, cohort_id="cohort:batch-plan", run_id="run:batch-plan",
            provider=batch_provider, delivery_mode="batch",
            delivery_policy=DeliveryPolicy.build(reviewed_batch_override=True),
        )
        assert len(batch_runner.plan.physical_packages(delivery_mode="batch")) == 1
        assert batch_provider.send_calls == 0
    finally:
        fixture.close()


def test_ambiguous_crossing_reconciles_without_resend_and_ledger_is_exact(tmp_path):
    fixture = build_test_fixture(tmp_path / "synthetic", ("one",))
    try:
        result = preflight_governed_rights(
            (fixture.materials[0].request,),
            store=fixture.rights_store,
            projection=fixture.projection,
            catalog=fixture.catalog,
            as_of=fixture.now.date(),
            retained_bytes=fixture.artifacts.read,
        )
        cohort_id, run_id = register_test_run(fixture.catalog, suffix="real-integration-ambiguous")
        provider = CountingFakeProvider()
        runner = ReferenceFactory(fixture.catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id, provider=provider)
        tasks = runner.seed(fixture.now)
        package_id = deterministic_id(
            "taskrun:", {"members": [tasks[0]["record_id"]], "mode": "standard"}
        )
        physical_id = "physical:" + package_id.split(":", 1)[1]
        with pytest.raises(AmbiguousSendError):
            runner.run(fixture.now, interruptions={physical_id: "send_ambiguous"})
        assert provider.send_calls == 1
        runner.reconcile_ambiguous_package(package_id, now=fixture.now)
        assert runner.run(fixture.now) == 1
        assert runner.run(fixture.now) == 0
        assert provider.send_calls == 1
        with fixture.catalog._connection() as conn:
            cost_types = [row[0] for row in conn.execute(
                "SELECT entry_type FROM cost_entries WHERE run_id=? ORDER BY entry_key", (run_id,)
            )]
            actual = conn.execute(
                "SELECT accounting_amount FROM cost_entries WHERE run_id=? AND entry_type='actual'", (run_id,)
            ).fetchone()[0]
            released = conn.execute(
                "SELECT accounting_amount FROM cost_entries WHERE run_id=? AND entry_type='reservation_release'", (run_id,)
            ).fetchone()[0]
        assert cost_types == ["actual", "reservation_release"]
        assert actual == "0.002000"
        assert released == "0.008000"
    finally:
        fixture.close()
