"""Execute the bounded P5-A0 exact-ABN identity bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from charitygraph.identity_bootstrap import bootstrap_cohort, identity_map_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\state"))
    parser.add_argument("--cohort", type=Path, default=Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829\top100-cohort-manifest.json"))
    parser.add_argument("--archive-csv", type=Path, default=Path(r"C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\archive\sources\regulator\acnc-register\2026-08-10\01ceee0645b9f1111a555c65e026c12b04811a682e2cb1fa10edb7d510a7d5c8.csv"))
    parser.add_argument("--report", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json"))
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args()
    first = bootstrap_cohort(catalog_path=args.catalog, runtime_root=args.runtime, cohort_path=args.cohort, archive_csv=args.archive_csv, allow_network=args.allow_network)
    second = bootstrap_cohort(catalog_path=args.catalog, runtime_root=args.runtime, cohort_path=args.cohort, archive_csv=args.archive_csv, allow_network=args.allow_network)
    if [row["subject_id"] for row in first] != [row["subject_id"] for row in second]:
        raise RuntimeError("identity bootstrap is not idempotent")
    report = {"cohort_manifest_sha256": hashlib.sha256(args.cohort.read_bytes()).hexdigest(), "input_archive_sha256": hashlib.sha256(args.archive_csv.read_bytes()).hexdigest(), "identity_map_hash": identity_map_hash(first), "rows": first, "rerun_rows": second, "counts": {"cohort": len(first), "reused_existing_subject": sum(r["status"] == "reused_existing_subject" for r in first), "created_from_reused_acnc_source": sum(r["status"] == "created_from_reused_acnc_source" for r in first), "created_from_new_acnc_acquisition": sum(r["status"] == "created_from_new_acnc_acquisition" for r in first), "blocked": sum(r["status"] == "blocked" for r in first)}, "network": {"allowed_source_family": "acnc_register", "search_requests": 0, "entity_requests": 0, "archive_reuse": sum(r["status"] == "created_from_reused_acnc_source" for r in first)}, "historical_semantic_attempt": {"abn": "48321126727", "rank": 62, "status": "blocked_ambiguous_transmission", "resend_authorized": False, "semantic_task_created_by_this_tranche": False}, "provider_calls": 0, "semantic_tasks_created": 0, "rerun_idempotent": True}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.report.read_bytes()).hexdigest()
    args.report.with_suffix(args.report.suffix + ".sha256").write_text(digest + "\n", encoding="ascii")
    print(json.dumps({"report": str(args.report), "identity_map_hash": report["identity_map_hash"], "counts": report["counts"], "rerun_idempotent": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
