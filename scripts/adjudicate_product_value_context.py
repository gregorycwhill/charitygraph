"""Materialize Greg's approved private adjudications and experiment projection."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "src"))

from charitygraph.product_value_context_adjudication import adjudicate_context_inventory


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    work = repo / "work" / "product-value-baseline-2026-09-14"
    generated_at = datetime.now(timezone.utc)
    result = adjudicate_context_inventory(work, adjudicated_at=generated_at)
    out = work / "adjudicated-context"
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "adjudications.json", {
        "generated_at": result["generated_at"],
        "adjudicator": result["adjudicator"],
        "reviewer": result["reviewer"],
        "candidate_inventory_sha256": result["candidate_inventory_sha256"],
        "source_candidate_adjudications": result["source_candidate_adjudications"],
        "coverage_adjudications": result["coverage_adjudications"],
    })
    _write_json(out / "governed-items.json", {
        "status": "PRIVATE_EXPERIMENT_ONLY_NOT_CANONICAL_OR_PUBLIC",
        "namespace_id": "product_value_experiment_2026_09_14",
        "proposition_items": result["proposition_items"],
        "coverage_items": result["coverage_items"],
    })
    _write_json(out / "coverage-contracts.json", result["coverage_contracts"])
    _write_json(out / "private-projection.json", result["private_projection"])
    _write_json(out / "readiness-and-reconciliation.json", {
        key: result[key] for key in (
            "generated_at", "integrity", "dispositions", "original_candidates",
            "corrected_governed_atoms", "rejected_candidate_count", "unresolved_candidate_count",
            "governed_counts", "per_subject", "readiness", "readiness_reason", "provider_gate",
            "provider_calls", "source_acquisitions", "human_adjudications", "candidate_promotions",
            "canonical_public_promotions", "viewer_changes", "public_v0_5_changes", "capacity_execution",
        )
    })
    print(f"Materialized {result['governed_counts']['total_experiment_governed_items']} private governed items at {out}")


if __name__ == "__main__":
    main()
