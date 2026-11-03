"""Compile a mechanical, source-lineaged Sol handoff from frozen v1.4 output."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from charitygraph.frozen_experiment import demand_propositions, demand_requirements

ROOT = Path(__file__).resolve().parent
RUNTIME = Path(r"C:\CharityGraph-runtime\cg406-v14-final-development-replay-run01")
FROZEN = Path(r"C:\CharityGraph-runtime\cg406-fresh-governed-quality-holdout-a1")
PREVIOUS = Path(__file__).resolve().parents[1] / "cg406-v13-development-replay"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite handoff artifact: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def source_lookup() -> dict[str, dict]:
    db = RUNTIME / "catalog.sqlite3"
    uri = "file:" + db.as_posix() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        values = conn.execute(
            "SELECT source_record_id, source_family, source_role, source_version, source_locator, payload_hash, material_json FROM source_records"
        ).fetchall()
        result = {}
        for row in values:
            item = dict(row)
            result[item["source_record_id"]] = item
        return result
    finally:
        conn.close()


def evidence_info(evidence_id: str, sources: dict[str, dict]) -> dict:
    item = sources.get(evidence_id)
    if not item:
        return {"evidence_id": evidence_id, "source_record_metadata": "not found in frozen source catalogue"}
    return {
        "evidence_id": evidence_id,
        "source_family": item["source_family"],
        "source_role": item["source_role"],
        "source_version": item["source_version"],
        "source_native_locator": item["source_locator"],
        "source_payload_sha256": item["payload_hash"],
    }


def by_instance(rows: list[dict]) -> dict[str, dict]:
    return {row["instance_id"]: row for row in rows}


def main() -> None:
    subjects = read(FROZEN / "frozen-subject-manifest.json")["subjects"]
    demands = read(FROZEN / "frozen-demand-instance-manifest.json")["instances"]
    subject_by_id = {row["subject_id"]: row for row in subjects}
    demand_by_instance = {row["instance_id"]: row for row in demands}
    prepared = read(RUNTIME / "prepared-run.json")
    prepared_by_instance = by_instance(prepared["rows"])
    current_ledger = read(ROOT / "terminal-result-ledger.json")
    current_validation = read(ROOT / "validation-results.json")
    current_validation_by_id = by_instance(current_validation["rows"])
    previous_ledger = read(PREVIOUS / "terminal-result-ledger.json")
    previous_validation = read(PREVIOUS / "validation-results.json")
    previous_by_id = by_instance(previous_ledger["rows"])
    previous_validation_by_id = by_instance(previous_validation["rows"])
    sources = source_lookup()

    family_row_counts: Counter[str] = Counter()
    family_record_counts: Counter[str] = Counter()
    rows = []
    for instance_id in sorted(demand_by_instance):
        demand = demand_by_instance[instance_id]
        subject = subject_by_id[demand["subject_id"]]
        prepared_row = prepared_by_instance[instance_id]
        current = next(row for row in current_ledger["rows"] if row["instance_id"] == instance_id)
        current_val = current_validation_by_id[instance_id]
        previous = previous_by_id[instance_id]
        previous_val = previous_validation_by_id[instance_id]
        packet_sources = [evidence_info(evidence_id, sources) for evidence_id in prepared_row["evidence_ids"]]
        family_set = {source.get("source_family", "unknown") for source in packet_sources}
        for family in family_set:
            family_row_counts[family] += 1
        for source in packet_sources:
            family_record_counts[source.get("source_family", "unknown")] += 1
        raw = json.loads(current["final_answer"])
        selected_ids = list(raw.get("selected_evidence_ids", []))
        rejected_ids = list(raw.get("rejected_evidence_ids", []))
        rows.append({
            "instance_id": instance_id,
            "organisation": subject["display_name"],
            "subject_id": subject["subject_id"],
            "demand_id": demand["demand_id"],
            "demand": json.loads(demand["semantic_signature"]),
            "v13": {
                "raw_outcome": previous.get("conclusion", {}).get("outcome"),
                "mechanical_status": previous_val.get("status"),
                "exact_failure": previous_val.get("error"),
                "selected_evidence_ids": previous.get("selected_evidence_ids", []),
                "rejected_evidence_ids": previous.get("rejected_evidence_ids", []),
            },
            "v14": {
                "raw_outcome": current.get("final_answer") and raw.get("conclusion", {}).get("outcome"),
                "derived_category": current_val["derived_category"],
                "mechanical_status": current_val["status"],
                "exact_failure": current_val["error"],
                "selected_evidence_ids": selected_ids,
                "rejected_evidence_ids": rejected_ids,
                "selected_evidence_lineage": [evidence_info(evidence_id, sources) for evidence_id in selected_ids],
                "rejected_evidence_lineage": [evidence_info(evidence_id, sources) for evidence_id in rejected_ids],
                "conclusion_evidence_lineage": [evidence_info(evidence_id, sources) for evidence_id in current_val["conclusion_evidence_ids"]],
                "proposition_support": current_val["proposition_support"],
                "requirement_support": current_val["requirement_support"],
                "conclusion_qualification": current_val["conclusion_qualification"],
                "packet_evidence_lineage": packet_sources,
                "packet_hash": prepared_row["packet_hash"],
                "request_body_sha256": prepared_row["request_body_sha256"],
            },
        })

    manifest = read(ROOT / "frozen-result-manifest.json")
    summary = {
        "schema": "charitygraph.cg406-v14-mechanical-comparison/v1",
        "frozen_result_manifest_sha256": manifest["result_manifest_sha256"],
        "oracle_consulted": False,
        "comparison_basis": "frozen v1.3 terminal outputs and mechanical validation versus frozen v1.4 terminal outputs and real contract validation; no semantic agreement scoring",
        "v13_raw_outcome_counts": read(PREVIOUS / "frozen-result-manifest.json")["outcome_counts"],
        "v13_mechanical_validation_counts": read(PREVIOUS / "frozen-result-manifest.json")["mechanical_validation_counts"],
        "v14_raw_outcome_counts": current_validation["raw_outcome_counts"],
        "v14_mechanical_validation_counts": current_validation["counts"],
        "v13_to_v14_improvement_regression_notes": [
            "v1.4 changes remain mechanical-contract and evidence-provenance changes; this file does not score semantic agreement.",
            "Compare raw outcomes independently from derived contract-admissible categories.",
            "The single v1.4 raw supported outcome is not a Sol semantic adjudication.",
            "SDC-0019 remains CANDIDATE_SOURCE_GAP; Source Universe v1 is unchanged.",
        ],
        "provider_family_coverage": {
            family: {"requests_with_family": family_row_counts[family], "packet_evidence_records": family_record_counts[family]}
            for family in sorted(family_row_counts)
        },
        "spend": {
            "v14_actual_usd": manifest["aggregate_actual_usd"],
            "v14_actual_aud": manifest["aggregate_actual_aud"],
            "prior_reconciled_actual_aud": "0.510035",
            "cumulative_actual_aud": str(float(manifest["aggregate_actual_aud"]) + 0.510035),
            "cumulative_hard_ceiling_aud": "1.00",
            "v14_hard_max_aud": manifest["aggregate_hard_max_aud"],
        },
        "rows": rows,
        "process_integrity_note": "A v1.3 result-manifest excerpt and first ledger lines were inspected before the v1.4 manifest was frozen while checking the established artifact shape. No v1.4 responses had yet been observed, and the independent oracle was never opened. This sequencing deviation is disclosed for Sol; the v1.4 first-terminal response set itself was frozen before any further prior-result comparison.",
    }
    write_once(ROOT / "mechanical-v13-v14-comparison.json", summary)
    write_once(ROOT / "sol-handoff.json", {
        "schema": "charitygraph.cg406-v14-sol-handoff/v1",
        "status": "READY_FOR_SOL_CG406_FINAL_DEVELOPMENT_ADJUDICATION",
        "development_cohort_status": "CG406_DEVELOPMENT_COHORT_CLOSED_FOR_TUNING",
        "sol_adjudication_requested": True,
        "gate3_closure_recommendation": None,
        "oracle_consulted": False,
        "rows": rows,
        "mechanical_summary": {
            "raw_outcomes": current_validation["raw_outcome_counts"],
            "mechanical_validity": current_validation["counts"],
            "contract_admissible_positive_count": sum(row["v14"]["derived_category"] == "contract_admissible_positive" for row in rows),
            "spend_actual_usd": manifest["aggregate_actual_usd"],
            "spend_actual_aud": manifest["aggregate_actual_aud"],
            "provider_posts": manifest["provider_posts"],
            "transport_retries": manifest["transport_retries"],
            "token_usage": manifest["token_usage"],
        },
        "process_integrity_note": summary["process_integrity_note"],
        "scope_gap_classification": "CANDIDATE_SOURCE_GAP",
        "source_universe_v1_changed": False,
    })


if __name__ == "__main__":
    main()
