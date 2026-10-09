"""Run the frozen CG353 dedicated arm without widening its evidence boundary.

This runner deliberately treats a missing immutable representation as a packet
failure.  It never substitutes a locator, re-fetches content, or silently
removes an evidence item.  Provider calls occur only after the entire packet is
materialised exactly from the frozen manifest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


EXPECTED_CORPUS_SHA256 = "120e20160adbfd27a53b526b200e85841850ded612a839dd4381110295300644"


def canonical_hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--representation-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus_bytes = args.corpus.read_bytes()
    corpus = json.loads(corpus_bytes)
    # The freezer's content-addressed corpus identity is a declared canonical
    # manifest value; the enclosing JSON also carries operational metadata.
    if corpus.get("corpus_sha256") != EXPECTED_CORPUS_SHA256:
        raise SystemExit("frozen corpus identity mismatch")
    rows = []
    for packet in corpus["packets"]:
        case_number = int(packet["case_id"].split("-")[1])
        if case_number > 10 or packet["section"] != 15:
            continue
        missing = []
        for evidence in packet["evidence"]:
            representation = args.representation_root / evidence["representation_locator"]
            if not representation.is_file():
                missing.append({"evidence_id": evidence.get("evidence_fragment_id"), "representation_locator": evidence["representation_locator"], "representation_sha256": evidence["representation_sha256"]})
        state = "ABSTAINED_COVERAGE_GAP" if not packet["evidence"] else ("PACKET_FAILURE" if missing else "READY_FOR_PROVIDER")
        rows.append({"case_id": packet["case_id"], "section": 15, "packet_id": packet["packet_id"], "packet_hash": packet["packet_hash"], "state": state, "missing_representations": missing, "provider_called": False, "request_hash": None, "response_hash": None, "input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": "0"})
    report = {"experiment_id": "CG-UNIFIED-SEMANTIC-EXTRACTION-353", "arm": "B_dedicated_ethos_notability", "model": "gpt-5.6-luna", "provider_path": "openai.responses", "corpus_sha256": EXPECTED_CORPUS_SHA256, "executed_at": datetime.now(timezone.utc).isoformat(), "rows": rows, "aggregate": {"cases": len(rows), "provider_calls": 0, "cost_usd": "0", "packet_failures": sum(row["state"] == "PACKET_FAILURE" for row in rows), "coverage_abstentions": sum(row["state"] == "ABSTAINED_COVERAGE_GAP" for row in rows)}}
    report["report_sha256"] = canonical_hash(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
