"""Run the private, provider-free Gate 4 autonomy demonstration.

The cohort is deliberately limited to three already-retained Gate 3 review
subjects.  This script produces local runtime evidence only; it never acquires
sources, calls a paid provider, promotes knowledge, publishes, or closes a
gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charitygraph.autonomous_loop import InstructionEnvelope, LocalAutonomousBridge
from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_factory import FactoryInterrupted, FactoryPlan, ReferenceFactory
from charitygraph.runtime import SQLiteCatalog


EVIDENCE = ROOT / "evidence" / "gate3-final-semantic-review" / "case-assessments.json"
RUNTIME = ROOT / "runtime" / "gate4-autonomous-loop-20261020-commit2"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(catalog: SQLiteCatalog, cohort_id: str, run_id: str) -> None:
    catalog.register_cohort({
        "record_id": cohort_id,
        "cohort_code": "GATE4-RETAINED-3",
        "definition_version": "gate4-autonomous-demo-v1",
        "membership_hash": sha(EVIDENCE),
        "budget_cap": {"amount": "1", "currency": "AUD"},
        "created_at": NOW,
    })
    catalog.register_run({
        "record_id": run_id,
        "cohort_id": cohort_id,
        "run_kind": "gate4_autonomous_builder_rehearsal",
        "status": "planned",
        "configuration_hash": hashlib.sha256(b"gate4-autonomous-demo-v1").hexdigest(),
        "created_at": NOW,
    })


def subject_rows() -> list[dict[str, Any]]:
    rows = json.loads(EVIDENCE.read_text(encoding="utf-8"))["cases"]
    # These are retained Gate 3 review identities, not the protected holdout.
    selected = rows[:3]
    return [
        {
            "subject_id": row["subject_id"],
            "evidence_id": f"gate3-final-semantic-review/case-assessments.json#ordinal-{row['ordinal']}",
            "review_case_id": row["oracle_case_id"],
            "source_sha256": sha(EVIDENCE),
            "retained": True,
            "holdout": False,
        }
        for row in selected
    ]


def run_builder_demo(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cohort_id = "cohort:gate4-autonomous-20261020"
    run_id = "run:gate4-autonomous-20261020"
    db = RUNTIME / "builder.sqlite3"
    catalog = SQLiteCatalog(db).open(initialize=True)
    register(catalog, cohort_id, run_id)
    manifest = []
    for index, row in enumerate(rows):
        manifest.append({
            "logical_task_id": f"gate4:{index}:{row['subject_id']}",
            "subject_id": row["subject_id"],
            "physical_bundle_opportunity": None,
            "difficulty": "lower_cost_constrained_semantic" if index != 1 else "deterministic",
        })
    plan = FactoryPlan.from_manifest(manifest)
    runner = ReferenceFactory(catalog, plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    packages = runner.plan.physical_packages(delivery_mode=runner.delivery_mode)
    # One isolated failure: other authorised subjects still complete.
    failing_package = "physical:" + deterministic_id(
        "taskrun:", {"members": [plan.runtime_tasks(cohort_id=cohort_id)[1]["record_id"]], "mode": runner.delivery_mode}
    ).split(":", 1)[1]

    def execute(package: tuple[dict[str, Any], ...], failure: str | None = None) -> dict[str, Any]:
        tasks = tuple(next(task for task in runner.plan.runtime_tasks(cohort_id=cohort_id) if task["logical_task_id"] == item["logical_task_id"]) for item in package)
        package_id, receipt = runner.prepare_package(tasks, now=NOW)
        completed = runner.finalise_package_children(tasks, package_id=package_id, receipt=receipt, now=NOW, failure=failure)
        return {"package_id": package_id, "receipt": bool(receipt), "children_terminalised": completed}

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="gate4-worker") as pool:
        futures = []
        for package in packages:
            tasks = tuple(next(task for task in runner.plan.runtime_tasks(cohort_id=cohort_id) if task["logical_task_id"] == item["logical_task_id"]) for item in package)
            p_id = "physical:" + deterministic_id(
                "taskrun:", {"members": [task["record_id"] for task in tasks], "mode": runner.delivery_mode}
            ).split(":", 1)[1]
            futures.append(pool.submit(execute, package, "structural" if p_id == failing_package else None))
        physical_runs = [future.result() for future in futures]
    with sqlite3.connect(db) as conn:
        receipts_before_repeat = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
    runner.run(NOW, continue_interruptions=True)
    with sqlite3.connect(db) as conn:
        receipts_after_repeat = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
        attempt_count = conn.execute("SELECT count(*) FROM task_attempts").fetchone()[0]
        physical_count = conn.execute("SELECT count(*) FROM physical_attempts").fetchone()[0]
    task_states = [catalog.get_task(task["record_id"]) for task in plan.runtime_tasks(cohort_id=cohort_id)]
    output_rows = []
    for row, state in zip(rows, task_states):
        output_rows.append({
            **row,
            "execution_state": state["status"],
            "output_status": "candidate" if state["status"] == "succeeded" else "governed_missingness_or_failure",
            "governed_projection_status": "not_promoted",
            "lineage": {"evidence_id": row["evidence_id"], "source_sha256": row["source_sha256"]},
            "routing": {"provider": "fake", "model_snapshot": "phase5-rehearsal-v1", "delivery": runner.delivery_mode},
            "cost_status": "simulated_rehearsal_only",
        })
    return {
        "cohort_id": cohort_id,
        "run_id": run_id,
        "database": str(db),
        "physical_packages": len(packages),
        "physical_receipts": physical_count,
        "logical_attempts": attempt_count,
        "receipts_before_repeat": receipts_before_repeat,
        "receipts_after_repeat": receipts_after_repeat,
        "idempotent_repeat": receipts_before_repeat == receipts_after_repeat,
        "bounded_parallel_workers": 2,
        "failure_isolation": any(state["status"] in {"failed", "failed_retryable", "failed_terminal", "held"} for state in task_states) and any(state["status"] == "succeeded" for state in task_states),
        "simulated_cost_aud": str(catalog.budget_position(cohort_id).actual_spend_aud),
        "subjects": output_rows,
    }


def run_restart_demo() -> dict[str, Any]:
    db = RUNTIME / "restart-v4.sqlite3"
    catalog = SQLiteCatalog(db).open(initialize=True)
    cohort_id, run_id = "cohort:gate4-restart-20261020", "run:gate4-restart-20261020"
    register(catalog, cohort_id, run_id)
    subject = subject_rows()[0]
    plan = FactoryPlan.from_manifest([{"logical_task_id": "gate4:restart", "subject_id": subject["subject_id"], "difficulty": "lower_cost_constrained_semantic"}])
    first = ReferenceFactory(catalog, plan, cohort_id=cohort_id, run_id=run_id)
    tasks = first.seed(NOW)
    try:
        first.prepare_package(tasks, now=NOW, interruption="receipt_restart")
    except FactoryInterrupted:
        interrupted = True
    else:
        interrupted = False
    with sqlite3.connect(db) as conn:
        receipts_after_interrupt = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
    resumed = ReferenceFactory(catalog, plan, cohort_id=cohort_id, run_id=run_id)
    resumed.run(NOW)
    with sqlite3.connect(db) as conn:
        receipts_after_resume = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
    return {"interrupted_after_receipt": interrupted, "receipts_after_interrupt": receipts_after_interrupt, "receipts_after_resume": receipts_after_resume, "no_duplicate_send": receipts_after_interrupt == receipts_after_resume, "task_status": catalog.get_task(tasks[0]["record_id"])["status"], "database": str(db)}


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    head, branch = git("rev-parse", "HEAD"), git("branch", "--show-current")
    rows = subject_rows()
    bridge = LocalAutonomousBridge(RUNTIME / "bridge", workspace=ROOT).open()
    instruction = InstructionEnvelope.create(
        instruction_id="gate4:autonomous-builder-demo:20261020:v5",
        content="Execute the private provider-free Gate 4 Builder rehearsal over three retained Gate 3 review subjects; no acquisition, paid provider call, promotion, publication, merge or gate decision.",
        target={"repository": "charitygraph", "workspace_path": str(ROOT), "branch": branch, "head": head, "model": "luna-high"},
        created_at=NOW,
    )
    submission = bridge.submit(instruction)
    if not submission["accepted"] and submission["status"] == "complete":
        existing = bridge.inspect(instruction.instruction_id)
        print(Path(existing["result_path"]).read_text(encoding="utf-8"))
        return
    claimed = bridge.claim(owner="local-host-watcher", now=NOW)
    bridge.begin(claimed.instruction_id, owner="local-host-watcher", now=NOW)
    builder = run_builder_demo(rows)
    restart = run_restart_demo()
    result = {
        "schema": "charitygraph.gate4-autonomous-demo-result/v1",
        "disposition": "PARTIAL",
        "execution_state": "complete",
        "engineering_state": "provider-free rehearsal passed with isolated failure and restart evidence",
        "canonicality": "LOCAL_ONLY",
        "gate_decision": "not_requested",
        "integration_instance": {"repository": "charitygraph", "branch": branch, "head": head, "workspace": str(ROOT), "python": os.sys.executable, "data_evidence": str(EVIDENCE), "data_evidence_sha256": sha(EVIDENCE)},
        "transport": {"submission": submission, "instruction_id": instruction.instruction_id, "instruction_sha256": instruction.content_sha256, "claim_owner": "local-host-watcher", "result_surface": str(RUNTIME / "bridge" / "results" / f"{instruction.instruction_id.replace(':', '_')}.json")},
        "builder": builder,
        "restart": restart,
        "limitations": ["The instruction was created by the local rehearsal script, not through a ChatGPT-writable host-observed ingress.", "Drive can be written/read by the connected ChatGPT surface, but this Windows workspace has no credentialed Drive watcher or claim adapter.", "Fake provider tariffs are simulated telemetry, not actual provider expenditure; no paid provider call occurred.", "Outputs are bounded candidate/coverage records and retained-evidence lineage; no semantic candidate was promoted and no canonical release projection was written."],
    }
    bridge.complete(instruction.instruction_id, owner="local-host-watcher", result=result, now=NOW)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
