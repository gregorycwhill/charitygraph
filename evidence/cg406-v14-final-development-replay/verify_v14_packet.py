"""Read-only integrity check for the final local CG406 v1.4 evidence packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> list[str]:
    failures = []
    inventory = read(ROOT / "artifact-inventory.json")
    for item in inventory["local_artifacts"]:
        path = ROOT / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            failures.append(f"local hash mismatch: {item['path']}")
    for item in inventory["referenced_frozen_inputs_and_comparison_sources"]:
        path = Path(item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            failures.append(f"referenced hash mismatch: {item['name']}")
    manifest = read(ROOT / "frozen-result-manifest.json")
    embedded = manifest["result_manifest_sha256"]
    manifest_payload = dict(manifest)
    manifest_payload.pop("result_manifest_sha256")
    if hashlib.sha256(canonical(manifest_payload)).hexdigest() != embedded:
        failures.append("embedded result-manifest identity mismatch")
    ledger = read(ROOT / "terminal-result-ledger.json")
    if len(ledger["rows"]) != 12 or ledger["provider_posts"] != 12:
        failures.append("terminal row/post count mismatch")
    if sha(ROOT / "terminal-result-ledger.json") != manifest["terminal_result_ledger_sha256"]:
        failures.append("frozen terminal ledger hash mismatch")
    if manifest["result_manifest_sha256"] != embedded:
        failures.append("manifest identity mismatch")
    responses = ROOT / "first-terminal-responses"
    files = list(responses.glob("requestitem_*.json"))
    if len(files) != 12:
        failures.append("first terminal response archive count mismatch")
    for row in ledger["rows"]:
        path = ROOT / row["response_archive"]
        if not path.is_file() or sha(path) != row["response_sha256"]:
            failures.append(f"response archive mismatch: {row['provider_request_item_id']}")
        if manifest["response_sha256_by_request_item"].get(row["provider_request_item_id"]) != row["response_sha256"]:
            failures.append(f"manifest response identity mismatch: {row['provider_request_item_id']}")
    identity = read(ROOT / "prepared-run-identity.json")
    prepared_path = Path(r"C:\CharityGraph-runtime\cg406-v14-final-development-replay-run01\prepared-run.json")
    prepared = read(prepared_path)
    if identity["prepared_run_hash"] != prepared["prepared_run_hash"] or sha(prepared_path).lower() != identity["serialized_prepared_run_sha256"].lower():
        failures.append("prepared run identity mismatch")
    if len(identity["prepared_rows"]) != 12 or len(prepared["rows"]) != 12:
        failures.append("prepared row count mismatch")
    actual_rows = {row["instance_id"]: row for row in prepared["rows"]}
    for row in identity["prepared_rows"]:
        actual = actual_rows.get(row["instance_id"])
        if not actual or actual["packet_hash"] != row["packet_hash"] or actual["provider_request_item_id"] != row["request_id"] or actual["request_body_sha256"] != row["body_sha256"]:
            failures.append(f"prepared row identity mismatch: {row['instance_id']}")
    return failures


if __name__ == "__main__":
    errors = verify()
    if errors:
        raise SystemExit("\n".join(errors))
    print("PASS: local inventory, referenced assets, prepared identity, frozen ledger, result manifest, and all 12 first terminal response hashes verified")
