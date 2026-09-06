"""Write the private, offline Phase-5 blocked-run website admissibility ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from charitygraph.phase5_reconciliation import audit_website_events, summarise_admissibility


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1"))
    parser.add_argument("--historical-root", type=Path, default=Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean"))
    parser.add_argument("--catalog", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    args = parser.parse_args()
    decisions = audit_website_events(runtime_root=args.runtime_root, historical_root=args.historical_root, catalog_path=args.catalog)
    payload = {"decision_layer": "prospective_only", "network_calls": 0, "provider_calls": 0, "semantic_executions": 0, "website_events": decisions, "summary": summarise_admissibility(decisions)}
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    args.output_root.mkdir(parents=True, exist_ok=True)
    target = args.output_root / "blocked-run-website-admissibility-ledger.json"
    target.write_bytes(encoded)
    print(json.dumps({"path": str(target), "sha256": hashlib.sha256(encoded).hexdigest(), "summary": payload["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
