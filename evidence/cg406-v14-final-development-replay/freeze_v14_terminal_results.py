"""Freeze terminal CG406 v1.4 response evidence once, without comparisons."""
from __future__ import annotations

import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path

from charitygraph.phase5_openai_dry_run import standard_actual_cost

RUNTIME = Path(r"C:\CharityGraph-runtime\cg406-v14-final-development-replay-run01")
PACKET = Path(__file__).resolve().parent
RESPONSES = RUNTIME / "standard-results"
RAW_OUT = PACKET / "first-terminal-responses"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, value: object) -> bytes:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    if path.exists():
        raise RuntimeError(f"refusing to overwrite frozen evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def main() -> None:
    prepared_path = RUNTIME / "prepared-run.json"
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    if len(prepared["rows"]) != 12:
        raise RuntimeError("expected exactly 12 prepared rows")
    if prepared["aggregate_hard_aud"] != "0.277645":
        raise RuntimeError("prepared cost ceiling changed; stop before freezing")
    if prepared["provider_account_project"] != "proj_vnAuU8uxocL0Rosg3SulgmRI":
        raise RuntimeError("provider project changed")
    pricing = json.loads((RUNTIME / "frozen-pricing-snapshot.json").read_text(encoding="utf-8"))
    if sha(RUNTIME / "frozen-pricing-snapshot.json") != prepared["pricing_snapshot_sha256"]:
        raise RuntimeError("pricing snapshot hash does not match prepared identity")
    if RAW_OUT.exists():
        raise RuntimeError(f"refusing to overwrite terminal responses: {RAW_OUT}")
    RAW_OUT.mkdir(parents=True)

    rows = []
    response_hashes = {}
    in_total = out_total = 0
    actual_usd = actual_aud = Decimal("0")
    for pinned in prepared["rows"]:
        request_id = pinned["provider_request_item_id"]
        response_path = RESPONSES / f"{request_id.replace(':', '_')}.json"
        if not response_path.is_file():
            raise RuntimeError(f"missing first terminal response: {request_id}")
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if response.get("metadata", {}).get("provider_request_item_id") != request_id:
            raise RuntimeError(f"response/request identity mismatch: {request_id}")
        if response.get("status") not in {"completed", "failed", "incomplete", "cancelled"}:
            raise RuntimeError(f"response is not terminal: {request_id}")
        raw_copy = RAW_OUT / response_path.name
        shutil.copyfile(response_path, raw_copy)
        response_hash = sha(raw_copy)
        response_hashes[request_id] = response_hash
        usage = response.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        in_total += input_tokens
        out_total += output_tokens
        usd, aud = standard_actual_cost(usage, Decimal(str(pricing["aud_per_usd"])), model="gpt-5.6-luna")
        actual_usd += usd
        actual_aud += aud
        final_text = ""
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    final_text += content.get("text", "")
        rows.append({
            "instance_id": pinned["instance_id"],
            "demand_id": pinned["instance_id"].rsplit(":", 1)[-1],
            "provider_request_item_id": request_id,
            "packet_hash": pinned["packet_hash"],
            "request_body_sha256": pinned["request_body_sha256"],
            "response_id": response.get("id"),
            "response_sha256": response_hash,
            "response_archive": f"first-terminal-responses/{raw_copy.name}",
            "status": response["status"],
            "error": response.get("error"),
            "parse_status": "valid" if response.get("status") == "completed" else "not_parsed_terminal_failure",
            "final_answer": final_text,
            "model": response.get("model"),
            "service_tier": response.get("service_tier"),
            "usage": usage,
            "actual_usd": str(usd),
            "actual_aud": str(aud),
            "transport_retries": 0,
        })

    if len(rows) != 12 or len(response_hashes) != 12:
        raise RuntimeError("terminal response set is not exactly 12")
    ledger = {
        "schema": "charitygraph.cg406-v14-terminal-result-ledger/v1",
        "campaign": "CG406-final-development-replay-v1.4",
        "prepared_run_hash": prepared["prepared_run_hash"],
        "prepared_file_sha256": sha(prepared_path),
        "provider_project": prepared["provider_account_project"],
        "provider_posts": 12,
        "transport_retries": 0,
        "rows": rows,
    }
    ledger_path = PACKET / "terminal-result-ledger.json"
    ledger_bytes = write_once(ledger_path, ledger)
    result_manifest = {
        "schema": "charitygraph.cg406-v14-development-result-manifest/v1",
        "status": "FROZEN_FIRST_TERMINAL_RESULTS",
        "prepared_run_hash": prepared["prepared_run_hash"],
        "prepared_file_sha256": sha(prepared_path),
        "terminal_result_ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "terminal_row_count": len(rows),
        "provider_posts": 12,
        "transport_retries": 0,
        "outcome_counts": {},
        "mechanical_validation_counts": {},
        "response_sha256_by_request_item": response_hashes,
        "aggregate_actual_usd": str(actual_usd),
        "aggregate_actual_aud": str(actual_aud),
        "aggregate_hard_max_usd": prepared["aggregate_hard_usd"],
        "aggregate_hard_max_aud": prepared["aggregate_hard_aud"],
        "token_usage": {"input_tokens": in_total, "output_tokens": out_total, "total_tokens": in_total + out_total},
        "contract_version": "1.4",
        "schema_version": "1.4-provenance-claim-separation",
    }
    result_manifest["result_manifest_sha256"] = hashlib.sha256(canonical(result_manifest)).hexdigest()
    write_once(PACKET / "frozen-result-manifest.json", result_manifest)


if __name__ == "__main__":
    main()
