"""Build the two-task Phase-5 execution-packet canary without transmission."""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.phase5_execution_packet import ExecutionPacketUnready, materialize_execution_packet, render_packet_prompt
from charitygraph.phase5_openai_dry_run import PRICING, estimate_tokens, serialize_execution_packet_request
from charitygraph.phase5_semantic_contracts import executable_contract_for, resolve_contract, resolve_result_adapter


CANARY = {
    "semtask:9fb548df3987dce8248422c3195e659bdbe11c00d561c7ee9fefb2cba6a50c89",
    "semtask:b65381e1e2f4f69fa02d11c07e8efa95ad82d6c3443f894afa6a2225a2012ff3",
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(manifest_path: Path, inventory_path: Path, corpus_dir: Path, runtime_root: Path, catalog_path: Path, output_root: Path) -> dict[str, Any]:
    tasks = {task["logical_task_id"]: task for task in json.loads(manifest_path.read_text(encoding="utf-8"))}
    routes = {row["logical_task_id"]: row for row in json.loads((Path(r"C:\CharityGraph-runtime\phase5-real-provider-dry-run-v1") / "route-manifest.json").read_text(encoding="utf-8"))}
    inventory = {row["subject_id"]: row for row in json.loads(inventory_path.read_text(encoding="utf-8"))}
    results: list[dict[str, Any]] = []
    request_items: list[dict[str, Any]] = []
    for task_id in sorted(CANARY):
        task = tasks[task_id]
        route = routes[task_id]
        contract = resolve_contract(task)
        result: dict[str, Any] = {"logical_task_id": task_id, "subject_id": task["subject_id"], "task_profile": task["task_profile"], "contract_id": contract.contract_id, "authority_state": contract.authority_state, "contract_hash_without_evidence": contract.identity_hash()}
        try:
            executable = executable_contract_for(task)
            adapter = resolve_result_adapter(executable)
            result["adapter_resolved"] = f"{adapter.__module__}.{adapter.__name__}"
            corpus = json.loads((corpus_dir / (inventory[task["subject_id"]]["abn"] + ".json")).read_text(encoding="utf-8"))
            packet = materialize_execution_packet(task=task, corpus=corpus, contract=executable, runtime_root=runtime_root, catalog_path=catalog_path, model=route["model"], reasoning_effort=route["reasoning_effort"], service_tier=route["service_tier"])
            request = serialize_execution_packet_request(task, packet, delivery_job_id=f"deliveryjob:canary-{route['model'].replace('.', '-')}", delivery_mode="standard")
            schema = executable.schema_for_evidence(tuple(item.evidence_id for item in packet.evidence_units))
            evidence_ids = [item.evidence_id for item in packet.evidence_units]
            schema_evidence_enum = schema["properties"]["proposals"]["items"]["properties"]["evidence"]["items"]["properties"]["evidence_id"]["enum"]
            result.update({"execution_readiness": "execution_packet_ready", "packet_hash": packet.packet_hash, "evidence_unit_count": len(packet.evidence_units), "evidence_bytes": sum(item.byte_count for item in packet.evidence_units), "evidence_ids": evidence_ids, "evidence_locators": sorted({locator for item in packet.evidence_units for locator in item.locator_ids}), "scope_count": len(packet.scopes), "scope_ids": [scope.scope_id for scope in packet.scopes], "schema_id": executable.schema_id, "schema_version": executable.schema_version, "schema_sha256": executable.schema_hash_for_evidence(tuple(evidence_ids)), "prompt_sha256": executable.prompt_sha256, "prompt_contains_actual_evidence": all(item.content in render_packet_prompt(packet, executable) for item in packet.evidence_units), "schema_evidence_ids_supplied": schema_evidence_enum == evidence_ids, "input_tokens": estimate_tokens(request.body), "output_limit": 8000 if task["task_profile"] == "program_service_discovery" else 24000, "request_item_id": request.provider_request_item_id, "request_body": request.body})
            output_tokens = result["output_limit"]
            price = PRICING[route["model"]]
            standard = Decimal(result["input_tokens"]) / Decimal(1_000_000) * price["input"] + Decimal(output_tokens) / Decimal(1_000_000) * price["output"]
            result["projected_batch_usd"] = str((standard / 2).quantize(Decimal("0.000001")))
            result["projected_standard_usd"] = str(standard.quantize(Decimal("0.000001")))
            request_items.append({"custom_id": request.provider_request_item_id, "method": "POST", "url": "/v1/responses", "body": request.body})
        except ExecutionPacketUnready as exc:
            result.update({"execution_readiness": "execution_packet_unready", "reason": str(exc), "request_item_id": None})
        results.append(result)
    totals = {"ready": sum(row["execution_readiness"] == "execution_packet_ready" for row in results), "unready": sum(row["execution_readiness"] == "execution_packet_unready" for row in results), "input_tokens": sum(row.get("input_tokens", 0) for row in results), "evidence_bytes": sum(row.get("evidence_bytes", 0) for row in results), "projected_batch_usd": str(sum((Decimal(row.get("projected_batch_usd", "0")) for row in results), Decimal("0")).quantize(Decimal("0.000001"))), "projected_standard_usd": str(sum((Decimal(row.get("projected_standard_usd", "0")) for row in results), Decimal("0")).quantize(Decimal("0.000001"))), "provider_calls": 0, "batch_submissions": 0, "semantic_executions": 0, "provider_cost_usd": "0"}
    _write(output_root / "execution-packet-canary-v2.json", {"tasks": results, "totals": totals, "batch_partition": {"ready_items": len(request_items), "model_jobs": sorted({item["body"]["model"] for item in request_items})}})
    (output_root / "request-items.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in request_items) + ("\n" if request_items else ""), encoding="utf-8")
    return {"tasks": results, "totals": totals}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--inventory", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\semantic-reuse-inventory.json"))
    parser.add_argument("--corpus-dir", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora"))
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1"))
    parser.add_argument("--catalog", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-execution-packet-v1"))
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.inventory, args.corpus_dir, args.runtime_root, args.catalog, args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
