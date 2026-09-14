"""Preflight/apply the provider-free Direct Service evidence-addressing stage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.phase5_evidence_addressing import (
    address_direct_service_material,
    direct_service_material_preflight,
    direct_service_scope_candidates,
    materialize_direct_service_scopes,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora"))
    parser.add_argument("--catalogue", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--store-root", type=Path, action="append", default=[])
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-addressed-v1"))
    parser.add_argument("--apply", action="store_true", help="perform append-only locator/scope registration after preflight")
    args = parser.parse_args()
    roots = tuple(args.store_root) or (
        Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\objects"),
        Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects"),
        Path(r"C:\CharityGraph-runtime\state\objects"),
    )
    rows = direct_service_material_preflight(corpus_dir=args.corpus_dir, catalog_path=args.catalogue, store_roots=roots)
    report = {
        "material_rows": len(rows),
        "eligible_material": sum(row["status"] == "eligible" for row in rows),
        "not_available_material": sum(row["status"] == "not_available" for row in rows),
        "blocked_material": sum(row["status"] == "blocked" for row in rows),
        "scope_candidates": direct_service_scope_candidates(rows),
        "locator_mutations": 0,
        "scope_mutations": 0,
        "provider_operations": 0,
        "source_acquisition": 0,
        "semantic_executions": 0,
    }
    if report["blocked_material"]:
        raise RuntimeError(json.dumps(report, sort_keys=True))
    if args.apply:
        projection = address_direct_service_material(corpus_dir=args.corpus_dir, catalog_path=args.catalogue, store_roots=roots, output_root=args.output_root)
        scopes = materialize_direct_service_scopes(candidates=report["scope_candidates"], catalog_path=args.catalogue)
        report.update({"locator_mutations": len(projection["members"]), "projection_hash": projection["projection_hash"], "scope_mutations": len(scopes), "scopes": scopes})
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
