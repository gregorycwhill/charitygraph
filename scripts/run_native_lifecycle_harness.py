"""Run the provider-free synthetic Native lifecycle verification."""
from __future__ import annotations
import argparse
from pathlib import Path
from charitygraph.native_lifecycle_harness import run_synthetic_lifecycle

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = run_synthetic_lifecycle(args.output)
    print(f"synthetic lifecycle assertions: {report['passed']}/{report['total']}")
    return 0 if report["passed"] == report["total"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
