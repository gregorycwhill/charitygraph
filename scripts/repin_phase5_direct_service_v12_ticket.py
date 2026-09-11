"""Repin only the private V1.2 future-execution ticket to this reviewed HEAD."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1"))
    ap.add_argument("--preparation-sha", default="69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26")
    ap.add_argument("--jsonl-sha", default="35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a")
    args = ap.parse_args()
    ticket_path = args.root / "future-execution-ticket.json"
    prep = args.root / "preparation.json"
    jsonl = args.root / "requests.jsonl"
    ticket = json.loads(ticket_path.read_bytes())
    if sha(prep.read_bytes()) != args.preparation_sha or sha(jsonl.read_bytes()) != args.jsonl_sha:
        raise SystemExit("immutable V1.2 preparation or JSONL identity mismatch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if ticket.get("builder_commit_required") == head:
        print(json.dumps({"status": "already_pinned", "builder_commit_required": head, "ticket_sha256": sha(ticket_path.read_bytes()), "ticket_bytes": ticket_path.stat().st_size}, sort_keys=True))
        return 0
    ticket["builder_commit_required"] = head
    encoded = canonical(ticket)
    ticket_path.write_bytes(encoded)
    print(json.dumps({"status": "repinned", "builder_commit_required": head, "ticket_sha256": sha(encoded), "ticket_bytes": len(encoded)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
