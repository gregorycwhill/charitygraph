"""Execute the private, provider-free Phase-5 Top-100 baseline corpus freeze."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.phase5_baseline_corpus import run_baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1"))
    parser.add_argument("--historical-root", type=Path, default=Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829"))
    parser.add_argument("--identity-map", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json"))
    parser.add_argument("--catalog", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--deliberate-interruption-after", type=int)
    args = parser.parse_args()
    result = run_baseline(runtime_root=args.runtime_root, historical_root=args.historical_root, identity_path=args.identity_map, catalog_path=args.catalog, interruption_after=args.deliberate_interruption_after)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
