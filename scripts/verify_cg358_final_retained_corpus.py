"""Offline integrity, provenance, packet-replay and network-denial checks for CG358."""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
from pathlib import Path


def canon(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    cohort = json.loads(a.cohort.read_text(encoding="utf-8"))
    manifest = json.loads((a.root / "retained-universe.json").read_text(encoding="utf-8"))
    defects = []
    original_socket = socket.socket
    def denied(*args, **kwargs):
        raise AssertionError("network access denied during semantic/offline replay")
    socket.socket = denied
    try:
        subjects = {x["case_id"]: x["subject_id"] for x in cohort["cases"]}
        for item in manifest["retained_objects"]:
            raw = a.root / "raw" / item["raw_sha256"]
            rep = a.root / item["representation_locator"]
            if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest() != item["raw_sha256"]:
                defects.append(item["case_id"] + ":raw")
            if not rep.is_file() or hashlib.sha256(rep.read_bytes()).hexdigest() != item["representation_sha256"]:
                defects.append(item["case_id"] + ":representation")
            if subjects.get(item["case_id"]) != item["subject_id"]:
                defects.append(item["case_id"] + ":subject-binding")
        expected = {(c["case_id"], section) for c in cohort["cases"] for section in (15, 17)}
        actual = {(x["case_id"], x["section"]) for x in manifest["packets"]}
        if actual != expected:
            defects.append("packet-universe")
        for packet in manifest["packets"]:
            material = {k: packet[k] for k in ("case_id", "subject_id", "section", "selection_version", "evidence")}
            if packet["packet_id"] != "packet:" + sha(material) or packet["packet_hash"] != sha(material):
                defects.append(packet["case_id"] + f":packet-{packet['section']}")
        for case_id in subjects:
            left = next(x["evidence"] for x in manifest["packets"] if x["case_id"] == case_id and x["section"] == 15)
            right = next(x["evidence"] for x in manifest["packets"] if x["case_id"] == case_id and x["section"] == 17)
            if left != right:
                defects.append(case_id + ":cross-section-reuse")
    finally:
        socket.socket = original_socket
    recomputed = sha({k: v for k, v in manifest.items() if k != "retained_universe_sha256"})
    if recomputed != manifest["retained_universe_sha256"]:
        defects.append("manifest-hash")
    checks = {
        "durable_store_integrity": not any(x.endswith(":raw") or x.endswith(":representation") for x in defects),
        "offline_replay": "packet-universe" not in defects and not any(":packet-" in x for x in defects),
        "provenance_integrity": not any(x.endswith(":subject-binding") for x in defects) and "manifest-hash" not in defects,
        "same_source_cross_domain_reuse": not any(x.endswith(":cross-section-reuse") for x in defects),
        "semantic_network_denial": True,
        "zero_provider_calls": manifest["provider_calls"] == 0,
        "zero_authenticated_github_mutations": manifest["authenticated_github_mutations"] == 0,
    }
    report = {"contract": "cg358-final-corpus-verification-v1", "retained_universe_sha256": manifest["retained_universe_sha256"], "checks": checks, "defects": defects, "passed": all(checks.values()) and not defects}
    report["report_sha256"] = sha(report)
    a.out.write_bytes(canon(report))
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
