"""Compile Phase-5 OpenAI artefacts without any provider or network operation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.phase5_openai_dry_run import compile_workload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--inventory", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\semantic-reuse-inventory.json"))
    parser.add_argument("--corpus-dir", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-real-provider-dry-run-v1"))
    args = parser.parse_args()
    print(json.dumps(compile_workload(args.manifest, args.inventory, args.corpus_dir, args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
