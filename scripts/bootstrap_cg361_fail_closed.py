"""Create a durable CG361 preflight record without manufacturing completeness.

This recovery intentionally stops before corpus freeze and provider execution when
the historical acquisition ledger cannot evidence every required category cell.
It only copies identity/provenance metadata and never reads source prose.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


COHORT_SHA256 = "fa77ab9141ddc5621713c9f487294cadb59fdcdf6d001fc5b4deb2d1e050e5ad"
CATEGORIES = (
    "annual_or_financial_reports", "about", "mission_values", "history",
    "programs_services", "impact_results", "governance_leadership",
    "policies_codes_safeguarding_inclusion", "affiliations_accreditations",
    "strategy", "news_campaigns", "research_evaluation_publications",
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(r"C:\CharityGraph-runtime\cg361-bounded-builder-endtoend-361-terra")
    historical = Path(r"C:\CharityGraph-runtime\cg359-t01\cg359-t01-freeze-and-authorised-source-inventory.json")
    if root.exists():
        raise SystemExit(f"refusing to overwrite durable experiment root: {root}")
    inventory = json.loads(historical.read_text(encoding="utf-8"))
    recovered = [
        {"case_id": item["case_id"], "subject_id": item["subject_id"], "display_name": item["display_name"]}
        for item in inventory["per_charity_inventory"]
    ]
    if len(recovered) != 15 or inventory["freeze"]["cohort_sha256"] != COHORT_SHA256:
        raise SystemExit("historical identity recovery is not the fixed 15-charity cohort")

    identity = {
        "contract": "cg361-fixed-cohort-recovery-v1",
        "fixed_cohort_sha256": COHORT_SHA256,
        "historical_inventory_path": str(historical),
        "historical_inventory_sha256": hashlib.sha256(historical.read_bytes()).hexdigest(),
        "subjects": recovered,
        "warning": "The original canonical cohort bytes were not retained at an accessible path; this is a recovered identity table, not a substitute cohort artifact.",
    }
    identity_sha = write(root / "cohort-recovery.json", identity)

    # The historical ledger is source-class oriented, not category-cell oriented.
    # Record each missing disposition explicitly; do not turn it into absence.
    matrix = []
    for subject in recovered:
        for category in CATEGORIES:
            matrix.append({
                "case_id": subject["case_id"], "subject_id": subject["subject_id"],
                "category": category,
                "state": "BLOCKED_MISSING_EVIDENCED_ATTEMPT",
                "reason": "Historical CG359 source-family attempts do not bind a locator-discovery/acquisition disposition to this category cell.",
                "attempt_ids": [],
            })
    matrix_artifact = {
        "contract": "bounded-first-party-completeness-v1-preflight",
        "fixed_cohort_sha256": COHORT_SHA256,
        "categories": list(CATEGORIES), "coverage_matrix": matrix,
        "terminal_cells": 0, "required_cells": len(matrix),
        "gate": "FAIL_CLOSED", "provider_calls": 0,
        "reason": "No new authorised corpus may be frozen: all category cells lack evidenced terminal attempts.",
    }
    matrix_sha = write(root / "discovery-acquisition-matrix.json", matrix_artifact)
    root_manifest = {
        "format": "charitygraph.cg361.experiment-root.v1",
        "experiment_id": "CG-BOUNDED-BUILDER-ENDTOEND-361-TERRA",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "FAILED_PRECONDITION",
        "fixed_cohort_sha256": COHORT_SHA256,
        "artifacts": {
            "cohort_recovery": {"path": "cohort-recovery.json", "sha256": identity_sha},
            "discovery_acquisition_matrix": {"path": "discovery-acquisition-matrix.json", "sha256": matrix_sha},
        },
        "stage_manifests": [],
        "provider": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": "0.00"},
        "failure": {
            "code": "CG361_COMPLETENESS_EVIDENCE_UNAVAILABLE",
            "message": "Fail-closed completeness gate cannot pass from the available historical source-family ledger; successor corpus, packetisation, canary and extraction were not run.",
            "nonzero_required": True,
        },
    }
    root_manifest["root_manifest_sha256"] = digest(root_manifest)
    write(root / "experiment-root-manifest.json", root_manifest)
    print(json.dumps({"root": str(root), "status": root_manifest["status"], "root_manifest_sha256": root_manifest["root_manifest_sha256"], "required_cells": len(matrix)}, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
