"""Mechanical verifier for the fresh Gate-3 holdout preparation packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((ROOT / "frozen-selected-holdout-manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "eligibility-audit.json").read_text(encoding="utf-8"))
    inventory = json.loads((ROOT / "artifact-inventory.json").read_text(encoding="utf-8"))["artifacts"]
    handoff = json.loads((ROOT / "handoff.json").read_text(encoding="utf-8"))
    rows = manifest["instances"]
    assert manifest["selection_state"] == "FROZEN_BEFORE_EVIDENCE_EVALUATION_AND_ORACLE_CONSTRUCTION"
    assert len(rows) == 36 == len({row["instance_id"] for row in rows}) == len({row["subject"]["subject_id"] for row in rows})
    assert {str(domain): 2 for domain in range(1, 19)} == manifest["domain_distribution"]
    assert audit["result"] == "PASS" and not audit["cg405_subject_name_overlap"] and not audit["cg406_instance_overlap"]
    assert all(row["semantic_signature_sha256"] == row["semantic_signature"]["semantic_signature_sha256"] for row in rows)
    for name, item in inventory.items():
        path = ROOT / name
        assert path.is_file() and item["sha256"] == sha(path) and item["bytes"] == path.stat().st_size
    assert handoff["selection_manifest_sha256"] == sha(ROOT / "frozen-selected-holdout-manifest.json")
    assert handoff["content_artifact_inventory_sha256"] == sha(ROOT / "content-artifact-inventory.json")
    assert {"handoff.json", "verify_holdout_packet.py", "content-artifact-inventory.json"}.issubset(inventory)
    print(json.dumps({"status": "PASS", "selected_instances": 36, "provider_calls": 0, "source_acquisition": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
