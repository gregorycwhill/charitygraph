"""Prepare or execute a frozen experiment through the ordinary Standard path.

``prepare`` is provider-free.  ``execute`` is deliberately a separate explicit
operation and is the only mode that constructs the provider client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from charitygraph.frozen_experiment import execute_prepared_standard, prepare_frozen_experiment
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient


def _write_exact(path: Path, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise RuntimeError(f"refusing to overwrite different frozen execution evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--authorization-catalog", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--subject-manifest", type=Path)
    parser.add_argument("--demand-manifest", type=Path)
    parser.add_argument("--corpus-manifest", type=Path)
    parser.add_argument("--rights-decisions", type=Path)
    parser.add_argument("--pricing-snapshot", type=Path)
    parser.add_argument("--authorization-text", type=Path)
    parser.add_argument("--provider-project")
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.mode == "prepare":
        required = ("subject_manifest", "demand_manifest", "corpus_manifest", "rights_decisions", "pricing_snapshot", "authorization_text")
        missing = [name for name in required if getattr(args, name) is None]
        if missing:
            raise SystemExit("prepare requires: " + ", ".join("--" + item.replace("_", "-") for item in missing))
        authorization_hash = hashlib.sha256(args.authorization_text.read_bytes()).hexdigest()
        prepared = prepare_frozen_experiment(
            subject_manifest=args.subject_manifest, demand_manifest=args.demand_manifest,
            corpus_manifest=args.corpus_manifest, rights_decisions=args.rights_decisions,
            pricing_snapshot=args.pricing_snapshot, runtime_root=args.runtime_root,
            catalog_path=args.catalog, authorization_catalog_path=args.authorization_catalog,
            authorization_text_hash=authorization_hash,
        )
        _write_exact(args.prepared, prepared)
        print(json.dumps({key: prepared[key] for key in ("cohort_id", "run_id", "mandate_id", "pricing_snapshot_sha256", "prepared_run_hash")}, sort_keys=True))
        return 0
    if not args.provider_project:
        raise SystemExit("execute requires --provider-project")
    prepared = json.loads(args.prepared.read_text(encoding="utf-8"))
    # This construction is intentionally reachable only in execute mode.
    result = execute_prepared_standard(
        prepared=prepared, catalog_path=args.catalog, authorization_catalog_path=args.authorization_catalog, runtime_root=args.runtime_root,
        provider=OpenAIHTTPStandardClient(provider_project=args.provider_project),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
