"""Run the real v1.4 frozen-demand packet validator on frozen first outputs."""
from __future__ import annotations

import json
from pathlib import Path

from charitygraph.frozen_experiment import demand_propositions, demand_requirements, load_frozen_instances, validate_evidence_selection

RUNTIME = Path(r"C:\CharityGraph-runtime\cg406-v14-final-development-replay-run01")
FROZEN = Path(r"C:\CharityGraph-runtime\cg406-fresh-governed-quality-holdout-a1")
PACKET = Path(__file__).resolve().parent


def main() -> None:
    _, demand_manifest, instances = load_frozen_instances(
        subject_manifest=FROZEN / "frozen-subject-manifest.json",
        demand_manifest=FROZEN / "frozen-demand-instance-manifest.json",
    )
    demands = {item["instance_id"]: item for item in instances}
    prepared = json.loads((RUNTIME / "prepared-run.json").read_text(encoding="utf-8"))
    prepared_rows = {row["instance_id"]: row for row in prepared["rows"]}
    ledger = json.loads((PACKET / "terminal-result-ledger.json").read_text(encoding="utf-8"))
    results = []
    valid_count = invalid_count = 0
    outcome_counts: dict[str, int] = {}
    for row in ledger["rows"]:
        instance_id = row["instance_id"]
        signature = demands[instance_id]["semantic_signature"]
        raw_output = json.loads(row["final_answer"])
        outcome = raw_output.get("conclusion", {}).get("outcome", "missing")
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        error = None
        try:
            output = validate_evidence_selection(
                raw_output,
                allowed_evidence_ids=set(prepared_rows[instance_id]["evidence_ids"]),
                demand_signature=signature,
            )
            status = "valid"
            valid_count += 1
        except Exception as exc:  # preserve the validator's exact first error
            status = "invalid"
            error = f"{type(exc).__name__}: {exc}"
            invalid_count += 1
        propositions = raw_output.get("proposition_support", [])
        requirements = raw_output.get("demand_requirement_support", [])
        required_propositions = demand_propositions(signature)
        required_requirements = demand_requirements(signature)
        results.append({
            "instance_id": instance_id,
            "demand_id": row["demand_id"],
            "status": status,
            "error": error,
            "raw_outcome": outcome,
            "derived_category": (
                "contract_admissible_positive" if status == "valid" and outcome in {"supported", "resolved"}
                else "partial_or_insufficient_no_semantic_adjudication"
            ),
            "exact_packet_evidence_refs": status == "valid",
            "required_proposition_count": len(required_propositions),
            "returned_proposition_count": len(propositions),
            "proposition_ids_exactly_once": len({x.get("proposition_id") for x in propositions}) == len(propositions) and {x.get("proposition_id") for x in propositions} == {x["proposition_id"] for x in required_propositions},
            "proposition_support": propositions,
            "required_requirement_count": len(required_requirements),
            "returned_requirement_count": len(requirements),
            "requirement_ids_exactly_once": len({x.get("requirement_id") for x in requirements}) == len(requirements) and {x.get("requirement_id") for x in requirements} == {x["requirement_id"] for x in required_requirements},
            "requirement_support": requirements,
            "selected_evidence_ids": raw_output.get("selected_evidence_ids", []),
            "rejected_evidence_ids": raw_output.get("rejected_evidence_ids", []),
            "conclusion_evidence_ids": [x.get("evidence_id") for x in raw_output.get("conclusion", {}).get("evidence", [])],
            "conclusion_qualification": raw_output.get("conclusion", {}).get("rationale"),
        })
    if len(results) != 12:
        raise RuntimeError("expected exactly 12 terminal validation rows")
    value = {
        "schema": "charitygraph.cg406-v14-validation-results/v1",
        "frozen_result_manifest_sha256": json.loads((PACKET / "frozen-result-manifest.json").read_text(encoding="utf-8"))["result_manifest_sha256"],
        "counts": {"valid": valid_count, "invalid": invalid_count},
        "raw_outcome_counts": outcome_counts,
        "limits": "Mechanical contract validation only. It confirms schema, exact frozen identity coverage, packet-local evidence references, and typed guard rules; semantic entailment is for Sol and is not adjudicated here.",
        "rows": results,
    }
    destination = PACKET / "validation-results.json"
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite validation results: {destination}")
    destination.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
