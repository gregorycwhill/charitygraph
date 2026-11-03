"""Create the append-only v3 continuation ticket after the completed canary."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parent)]

from charitygraph.phase5_execution_tickets import create_completed_canary_ticket, sha256
from continue_phase5_direct_service_v12_amendment3 import (
    CURRENT_TICKET, V2_TICKET, V2_TICKET_SHA, ROOT, DB, corrected_canary_interpretation,
    preflight,
)
from charitygraph.runtime import SQLiteCatalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", type=Path, default=DB)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--preflight-only", action="store_true", help="validate current exact-row authority without writing a ticket")
    args = parser.parse_args()
    if not args.catalogue.is_file():
        raise SystemExit("expected-existing authoritative catalogue is missing")
    catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    _, readiness = preflight(catalog, args.root, require_ticket=False)
    if args.preflight_only:
        print(json.dumps({"status": readiness["status"], "preflight": readiness,
                          "ticket_write": "not_performed", "provider_operations": 0}, sort_keys=True))
        return 0
    evidence = readiness["completed_canary_evidence"]
    interpretation_path = args.root / "amendment3-canary-v12-corrected-interpretation.json"
    interpretation_bytes = corrected_canary_interpretation(args.root, evidence)
    if sha256(interpretation_bytes) != evidence["corrected_interpretation_report_sha256"]:
        raise RuntimeError("deterministic canary correction report hash differs from certified evidence")
    if interpretation_path.exists() and interpretation_path.read_bytes() != interpretation_bytes:
        raise RuntimeError("append-only corrected canary interpretation path conflicts")
    if not interpretation_path.exists():
        interpretation_path.write_bytes(interpretation_bytes)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    prep = (args.root / "preparation.json").read_bytes()
    jsonl = (args.root / "requests.jsonl").read_bytes()
    prior = V2_TICKET.read_bytes()
    value, created = create_completed_canary_ticket(
        ticket_path=args.root / CURRENT_TICKET.name,
        predecessor_path=args.root / V2_TICKET.name,
        predecessor_bytes=prior,
        predecessor_sha256=V2_TICKET_SHA,
        builder_commit=commit,
        preparation_bytes=prep,
        jsonl_bytes=jsonl,
        completed_canary=evidence,
    )
    _, final_readiness = preflight(catalog, args.root, require_ticket=True)
    raw = (args.root / CURRENT_TICKET.name).read_bytes()
    print(json.dumps({
        "status": "superseding_ticket_created" if created else "superseding_ticket_replayed_identically",
        "path": str(args.root / CURRENT_TICKET.name), "sha256": sha256(raw), "bytes": len(raw),
        "predecessor_sha256": value["supersedes"]["sha256"], "builder_commit": commit,
        "certification": final_readiness["status"],
        "corrected_interpretation_path": str(interpretation_path),
        "corrected_interpretation_sha256": evidence["corrected_interpretation_report_sha256"],
        "provider_operations": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
