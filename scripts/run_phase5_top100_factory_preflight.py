"""Generate the private, provider-free Phase 5 Top-100 Factory work order."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from charitygraph.phase5_preflight import (
    BUILD_ID, COHORT_HASH, IDENTITY_MAP_HASH, SECTIONS, build_planned_tasks,
    build_planning_matrix, build_reuse_inventory, build_source_inventory,
    implemented_claim_families, preflight_interruption_safety, proposed_claim_families,
    summarize, workload_summary,
)


ROOT = Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829")
DEFAULT_OUT = Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-v1")
DEFAULT_CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
IDENTITY_REPORT = Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--historical-root", type=Path, default=ROOT)
    parser.add_argument("--identity-report", type=Path, default=IDENTITY_REPORT)
    args = parser.parse_args()
    root = args.historical_root
    cohort_manifest = json.loads((root / "top100-cohort-manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256((root / "top100-cohort-manifest.json").read_bytes()).hexdigest() != COHORT_HASH:
        raise RuntimeError("exact Top-100 cohort manifest hash changed")
    cohort = cohort_manifest["selected"]
    if len(cohort) != 100 or {row["donation_rank_2024_public"] for row in cohort} != set(range(1, 101)) or len({row["abn"] for row in cohort}) != 100:
        raise RuntimeError("cohort is not exactly unique ranks 1-100")
    subject_ids = __import__("charitygraph.phase5_preflight", fromlist=["_subject_map"])._subject_map(args.catalog, cohort, args.identity_report)
    bundles = json.loads((root / "evidence-bundles.json").read_text(encoding="utf-8"))["bundles"]
    run_manifest = json.loads((root / "semantic-run-manifest.json").read_text(encoding="utf-8"))
    results = json.loads((root / "call-results-partial.json").read_text(encoding="utf-8"))
    closeout = json.loads((root / "semantic-run-closeout.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    try:
        source_rows = conn.execute("SELECT e.identifier_value, e.material_json FROM external_identifiers e WHERE e.scheme='ABN' AND e.status='active'").fetchall()
        subject_count_before = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        task_count_before = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    finally:
        conn.close()
    source_records = {}
    for abn, material_json in source_rows:
        if abn in subject_ids:
            source_records[abn] = tuple(json.loads(material_json).get("source_record_ids") or ())
    coverage = build_source_inventory(cohort, subject_ids, bundles, source_records)
    reuse = build_reuse_inventory(cohort, subject_ids, run_manifest, results, closeout, bundles)
    canonical = implemented_claim_families(); proposed = proposed_claim_families()
    policies = canonical + proposed
    matrix = build_planning_matrix(cohort, subject_ids, canonical, reuse, coverage)
    # build_planning_matrix appends the private proposed catalogue itself.
    tasks = build_planned_tasks(matrix)
    out = args.runtime_root; out.mkdir(parents=True, exist_ok=True)
    write_json(out / "identity-checkpoint.json", {"builder_main": "3b0794e9dac1c40ea68f290110ad7645b3661bc2", "cohort_manifest_sha256": COHORT_HASH, "identity_map_sha256": IDENTITY_MAP_HASH, "subject_count": len(subject_ids), "subject_ids": subject_ids})
    write_json(out / "source-family-coverage.json", [item.model_dump(mode="json") for item in coverage])
    write_json(out / "semantic-reuse-inventory.json", [item.model_dump(mode="json") for item in reuse])
    write_json(out / "claim-family-registry.json", [item.model_dump(mode="json") for item in canonical])
    write_json(out / "proposed-claim-family-catalogue.json", [item.model_dump(mode="json") for item in proposed])
    write_json(out / "planning-matrix.json", [item.model_dump(mode="json") for item in matrix])
    write_json(out / "planned-logical-tasks.json", [item.model_dump(mode="json") for item in tasks])
    blocked = [item.model_dump(mode="json") for item in reuse if item.exact_reuse_status == "blocked_ambiguous_transmission"]
    write_json(out / "unresolved-block-register.json", {"rank62": blocked, "proposed_policy_decisions": [item.family_id for item in proposed if item.maturity in {"proposed", "high_risk_depth_deferred"}]})
    write_json(out / "risk-deferred-register.json", {"high_risk_or_deferred_families": [item.model_dump(mode="json") for item in proposed if item.method_class in {"human_reviewed", "deferred"}]})
    source_summary = {}
    for family in sorted({item.source_family for item in coverage}):
        source_summary[family] = {state: sum(item.source_family == family and item.state == state for item in coverage) for state in sorted({item.state for item in coverage if item.source_family == family})}
    reuse_summary = {status: sum(item.exact_reuse_status == status for item in reuse) for status in sorted({item.exact_reuse_status for item in reuse})}
    bundle_opportunities = [{"bundle_key": key, "logical_task_count": sum(task.physical_bundle_opportunity == key for task in tasks), "independent_task_ids": [task.logical_task_id for task in tasks if task.physical_bundle_opportunity == key]} for key in sorted({task.physical_bundle_opportunity for task in tasks if task.physical_bundle_opportunity})]
    write_json(out / "preflight-summary.json", {"build_id": BUILD_ID, "north_star_sections": SECTIONS, "cohort_manifest_sha256": COHORT_HASH, "identity_map_sha256": IDENTITY_MAP_HASH, "canonical_claim_family_ids": [item.family_id for item in canonical], "proposed_claim_family_count": len(proposed), "planning_unit_count": len(matrix), "planning_state_counts": summarize(matrix), "future_work_by_method": workload_summary(matrix), "planned_logical_task_count": len(tasks), "physical_bundling_opportunities": bundle_opportunities, "source_coverage_summary": source_summary, "reuse_summary": reuse_summary, "historical_closeout": closeout, "interruption_safety": preflight_interruption_safety(), "subject_count_before": subject_count_before, "task_count_before": task_count_before, "subject_count_after": subject_count_before, "task_count_after": task_count_before, "provider_calls": 0, "source_acquisition": 0, "semantic_executions": 0, "canonical_observations_created": 0})
    report_hash = hashlib.sha256((out / "preflight-summary.json").read_bytes()).hexdigest()
    (out / "preflight-summary.json.sha256").write_text(report_hash + "\n", encoding="ascii")
    print(json.dumps({"output_root": str(out), "planning_units": len(matrix), "planned_tasks": len(tasks), "provider_calls": 0, "source_acquisition": 0, "summary_sha256": report_hash}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
