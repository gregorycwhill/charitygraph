from __future__ import annotations

from datetime import datetime, timezone

from charitygraph.phase5_governed_factory_integration import GovernedFactoryPreflight
from charitygraph.phase5_integrated_offline_recovery_rehearsal import (
    NOT_OBSERVED,
    RecoveryFaultPlan,
    run_integrated_offline_recovery_rehearsal,
)


NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _preflight(*, reversed_input: bool = False) -> GovernedFactoryPreflight:
    rows = []
    for label in ("terminal", "retryable", "ambiguous", "healthy"):
        rows.append(
            {
                "logical_task_id": f"semtask:offline-{label}",
                "record_id": f"modeltask:offline-{label}",
                "subject_id": f"subject:offline-{label}",
                "scope_id": f"scope:offline-{label}",
                "difficulty": "stronger_semantic_judgement",
                "physical_bundle_opportunity": None,
                "source_definition_ids": (f"srcdef:offline-{label}",),
                "acquisition_receipt_ids": (f"acq:offline-{label}",),
                "source_record_ids": (f"srcrec:offline-{label}",),
                "evidence_locator_ids": (f"evidence:offline-{label}",),
                "representation_artifact_ids": (f"artifact:offline-{label}",),
                "representation_hashes": {f"artifact:offline-{label}": "a" * 64},
                "rights_policy_ids": ("rights-policy:offline",),
                "rights_roles": ("source-native",),
                "governed_reference_hash": f"hash:offline-{label}",
            }
        )
    if reversed_input:
        rows.reverse()
    return GovernedFactoryPreflight(tasks=tuple(rows), diagnostics=())


def _faults() -> RecoveryFaultPlan:
    return RecoveryFaultPlan(
        terminal_task_id="semtask:offline-terminal",
        retryable_pre_send_task_id="semtask:offline-retryable",
        ambiguous_task_id="semtask:offline-ambiguous",
    )


def test_integrated_rehearsal_runs_real_factory_faults_restart_and_health(tmp_path):
    result = run_integrated_offline_recovery_rehearsal(
        _preflight(),
        database_path=tmp_path / "rehearsal.sqlite3",
        cohort_id="cohort:offline-recovery",
        run_id="run:offline-recovery",
        now=NOW,
        faults=_faults(),
    )

    by_id = {outcome.logical_task_id: outcome for outcome in result.outcomes}
    assert result.task_count == 4
    assert result.healthy_task_ids == ("semtask:offline-healthy",)
    assert by_id["semtask:offline-terminal"].outcome == "terminal_failure"
    assert by_id["semtask:offline-terminal"].result_state == NOT_OBSERVED
    assert by_id["semtask:offline-ambiguous"].provider_receipt_id is None
    assert by_id["semtask:offline-ambiguous"].usage_state == NOT_OBSERVED
    assert by_id["semtask:offline-retryable"].result_state == "succeeded"
    assert by_id["semtask:offline-retryable"].task_attempt_count == 1
    assert all(outcome.source_record_ids for outcome in result.outcomes)
    assert all(outcome.scope_id for outcome in result.outcomes)

    assert result.no_duplicate_accepted_logical_effects is True
    assert result.no_cross_subject_contamination is True
    assert result.deterministic_replay is True
    assert result.restart_recovered_retryable is True
    assert result.ambiguous_failed_closed is True
    assert result.provider_call_count == 4
    assert result.operator_health_document["schema"] == "charitygraph.phase5.operator-health/v1"
    assert result.operator_health_document["provider_usage"]["state"] == "observed"
    assert any(
        event.get("fault") == "ambiguous_provider_boundary"
        and "fail_closed" in event.get("outcome", "")
        for event in result.event_trace
    )


def test_reversed_input_has_same_schedule_trace_and_diagnostic(tmp_path):
    first = run_integrated_offline_recovery_rehearsal(
        _preflight(),
        database_path=tmp_path / "first.sqlite3",
        cohort_id="cohort:offline-recovery",
        run_id="run:offline-recovery",
        now=NOW,
        faults=_faults(),
    )
    second = run_integrated_offline_recovery_rehearsal(
        _preflight(reversed_input=True),
        database_path=tmp_path / "second.sqlite3",
        cohort_id="cohort:offline-recovery",
        run_id="run:offline-recovery",
        now=NOW,
        faults=_faults(),
    )

    assert first.plan_manifest_hash == second.plan_manifest_hash
    assert first.schedule_trace == second.schedule_trace
    assert first.event_trace == second.event_trace
    assert first.provider_call_ids == second.provider_call_ids
    assert first.operator_health_sha256 == second.operator_health_sha256


def test_fault_plan_requires_three_distinct_known_tasks(tmp_path):
    bad = RecoveryFaultPlan(
        terminal_task_id="semtask:offline-terminal",
        retryable_pre_send_task_id="semtask:offline-terminal",
        ambiguous_task_id="semtask:offline-ambiguous",
    )
    try:
        run_integrated_offline_recovery_rehearsal(
            _preflight(),
            database_path=tmp_path / "invalid.sqlite3",
            cohort_id="cohort:offline-recovery",
            run_id="run:offline-recovery",
            now=NOW,
            faults=bad,
        )
    except ValueError as exc:
        assert "three distinct" in str(exc)
    else:
        raise AssertionError("invalid fault plan must fail closed")
