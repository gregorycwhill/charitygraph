"""Execute the six full-workload, fake-only Factory recovery rehearsals."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_factory import AmbiguousSendError, FactoryInterrupted, FactoryPlan, ReferenceFactory
from charitygraph.phase5_factory_chaos import CHAOS_POLICY_VERSION, scenario_for
from charitygraph.runtime import SQLiteCatalog

SCENARIOS = {
    "C1_pre_send": "pre_send",
    "C2_send_ambiguous": "send_ambiguous",
    "C3_receipt_restart": "receipt_restart",
    "C4_structural": "structural",
    "C5_grounding": "grounding",
    "C6_partial_bundle": "partial",
}


def _package_id(tasks: tuple[dict[str, object], ...]) -> str:
    return deterministic_id("taskrun:", {"members": [str(task["record_id"]) for task in tasks], "mode": "batch"})


def _select(plan: FactoryPlan, scenario: str, cohort_id: str) -> tuple[tuple[str, tuple[dict[str, object], ...]], ...]:
    runtime = {task["logical_task_id"]: task for task in plan.runtime_tasks(cohort_id=cohort_id)}
    candidates = []
    for package in plan.physical_packages(delivery_mode="batch"):
        tasks = tuple(runtime[item["logical_task_id"]] for item in package)
        physical = "physical:" + _package_id(tasks).split(":", 1)[1]
        # Chaos transports apply only to chargeable provider request packages;
        # deterministic work never crosses a provider send boundary.
        if all(task["difficulty"] != "deterministic" for task in tasks) and scenario_for(physical) == scenario and (scenario != "C6_partial_bundle" or len(tasks) > 1):
            candidates.append((physical, tasks))
    if not candidates:
        raise RuntimeError(f"no eligible full-workload package for {scenario}")
    return tuple(sorted(candidates, key=lambda item: item[0]))


def _run_disposition(task_states: dict[str, int], *, unresolved_ambiguities: int) -> str:
    if unresolved_ambiguities or task_states.get("held", 0):
        return "held"
    if task_states.get("failed_terminal", 0):
        return "failed"
    if sum(task_states.values()) == task_states.get("succeeded", 0):
        return "succeeded"
    return "cancelled"


def _open_run(root: Path, plan: FactoryPlan, scenario: str) -> tuple[SQLiteCatalog, str, str, datetime]:
    root.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    catalog = SQLiteCatalog(root / "factory.sqlite3").open(initialize=True)
    cohort = deterministic_id("cohort:", {"rehearsal": "phase5-core-chaos", "scenario": scenario})
    run = deterministic_id("run:", {"rehearsal": "phase5-core-chaos", "scenario": scenario})
    catalog.register_cohort({"record_id": cohort, "cohort_code": "P5_CHAOS", "definition_version": "1", "membership_hash": plan.manifest_hash, "budget_cap": {"amount": "10000", "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "phase5_factory_core_chaos", "status": "planned", "configuration_hash": plan.manifest_hash, "created_at": now})
    catalog.transition_run(run, "running", now=now)
    return catalog, cohort, run, now


def _counts(db: Path) -> dict[str, object]:
    with sqlite3.connect(db) as conn:
        return {
            "task_states": dict(conn.execute("SELECT status, count(*) FROM tasks GROUP BY status ORDER BY status")),
            "physical_states": dict(conn.execute("SELECT status, count(*) FROM physical_attempts GROUP BY status ORDER BY status")),
            "receipts": conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0],
            "actual_cost_entries": conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0],
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_key_violations": conn.execute("PRAGMA foreign_key_check").fetchall(),
        }


def run_scenario(plan: FactoryPlan, root: Path, scenario: str) -> dict[str, object]:
    catalog, cohort, run, now = _open_run(root, plan, scenario)
    runner = ReferenceFactory(catalog, plan, cohort_id=cohort, run_id=run)
    runner.seed(now)
    selected = _select(plan, scenario, cohort)
    selected_ids = tuple(physical for physical, _ in selected)
    selected_tasks = {physical: tasks for physical, tasks in selected}
    interruptions = {physical: SCENARIOS[scenario] for physical in selected_ids}
    if scenario in {"C1_pre_send", "C2_send_ambiguous", "C3_receipt_restart"}:
        runner.run(now, interruptions=interruptions, continue_interruptions=True)
    else:
        runner.run(now, failures=interruptions)
    # A fresh catalog/runner object is the real close/reopen restart boundary.
    restarted = SQLiteCatalog(root / "factory.sqlite3").open(initialize=False)
    recovered = ReferenceFactory(restarted, plan, cohort_id=cohort, run_id=run)
    explicit_reconciliation = False
    if scenario == "C2_send_ambiguous":
        try:
            recovered.run(now)
        except AmbiguousSendError:
            explicit_reconciliation = True
        else:
            raise AssertionError("ambiguous send was incorrectly auto-resubmitted")
        for physical in selected_ids:
            recovered.reconcile_ambiguous_package(_package_id(selected_tasks[physical]), now=now)
    completed_after_restart = recovered.run(now)
    noop = recovered.run(now)
    state_counts = _counts(root / "factory.sqlite3")["task_states"]
    disposition = _run_disposition(state_counts, unresolved_ambiguities=0)
    restarted.transition_run(run, disposition, now=now)
    result = {
        "scenario": scenario,
        "policy_version": CHAOS_POLICY_VERSION,
        "selected_physical_attempt_ids": selected_ids,
        "selected_count": len(selected_ids),
        "selected_package_sizes": {physical: len(selected_tasks[physical]) for physical in selected_ids},
        "interruption_observed": len(runner.interruptions_observed),
        "explicit_reconciliation_observed": explicit_reconciliation,
        "run_disposition": disposition,
        "completed_after_restart": completed_after_restart,
        "terminal_noop": noop,
        "network_calls": 0,
        "provider_calls": 0,
        "semantic_knowledge_production": 0,
        **_counts(root / "factory.sqlite3"),
    }
    (root / "scenario-summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-factory-core-chaos-v1"))
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), help="run one full-workload scenario for isolated diagnosis")
    args = parser.parse_args()
    plan = FactoryPlan.from_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    if len(plan.logical_tasks) != 1331:
        raise RuntimeError("authoritative Phase-5 task count changed")
    selected = (args.scenario,) if args.scenario else tuple(SCENARIOS)
    results = [run_scenario(plan, args.runtime_root / scenario, scenario) for scenario in selected]
    report = {"logical_tasks": len(plan.logical_tasks), "scenarios": results, "network_calls": 0, "provider_calls": 0, "semantic_knowledge_production": 0}
    (args.runtime_root / "core-chaos-summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"scenarios": len(results), "network_calls": 0, "provider_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
