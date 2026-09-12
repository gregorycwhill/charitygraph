"""Create the append-only v2 execution ticket for the surviving 17 V1.2 rows."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parent)]

from charitygraph.phase5_execution_tickets import create_superseding_ticket, sha256
from continue_phase5_direct_service_v12_amendment3 import (
    CURRENT_TICKET, FAILED_CANARY, OLD_TICKET, ROOT, SUPERSESSION_REASON, DB,
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
    evidence = readiness["excluded_canary_evidence"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    prep = (args.root / "preparation.json").read_bytes()
    jsonl = (args.root / "requests.jsonl").read_bytes()
    prior = OLD_TICKET.read_bytes()
    value, created = create_superseding_ticket(
        ticket_path=args.root / CURRENT_TICKET.name,
        predecessor_path=args.root / OLD_TICKET.name,
        predecessor_bytes=prior,
        builder_commit=commit,
        preparation_bytes=prep,
        jsonl_bytes=jsonl,
        excluded_request_id=FAILED_CANARY,
        exclusion_evidence=evidence,
        supersession_reason=SUPERSESSION_REASON,
    )
    _, final_readiness = preflight(catalog, args.root, require_ticket=True)
    raw = (args.root / CURRENT_TICKET.name).read_bytes()
    print(json.dumps({
        "status": "superseding_ticket_created" if created else "superseding_ticket_replayed_identically",
        "path": str(args.root / CURRENT_TICKET.name), "sha256": sha256(raw), "bytes": len(raw),
        "predecessor_sha256": value["supersedes"]["sha256"], "builder_commit": commit,
        "certification": final_readiness["status"], "provider_operations": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
