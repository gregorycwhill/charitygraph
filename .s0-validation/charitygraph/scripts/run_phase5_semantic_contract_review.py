"""Generate the private Phase-5 semantic contract review packet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from charitygraph.phase5_semantic_contracts import REGISTRY, provider_request_identity, registry_rows, resolve_contract, resolve_result_adapter


SLICE_IDS = {
    "semtask:2fff1efacea32418a8a0f3ae1c3940ad0d1e537ea2cfb86c043d16bb55eaae2b",
    "semtask:b65381e1e2f4f69fa02d11c07e8efa95ad82d6c3443f894afa6a2225a2012ff3",
    "semtask:040def5281cb21619a0906d056c7f17434a27570f46851780823804eca30f0a8",
    "semtask:086c660423890ca3d84fe629c6020d3f4c1c9ff05a73d78ccc3c453ae649578a",
    "semtask:9fb548df3987dce8248422c3195e659bdbe11c00d561c7ee9fefb2cba6a50c89",
    "semtask:1f45290a8d560e6095f04586fd751435c994c177e742a99e06bf3c1538a0062a",
    "semtask:ce1495a20a83d31d9530a4e72f34e81cee0c871fd2448d423a31839176beff9b",
    "semtask:fd6d42c3c1af8da552294bdca6211022d3faa936253aa3ec90be32fa291f34bd",
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_packet(manifest_path: Path, route_path: Path, output_root: Path) -> dict[str, Any]:
    tasks = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = {row["logical_task_id"]: row for row in json.loads(route_path.read_text(encoding="utf-8"))}
    semantic = [task for task in tasks if task["difficulty"] != "deterministic"]
    families = {}
    resolution_errors = {}
    for task in semantic:
        families.setdefault(task["claim_family_id"], task)
    coverage = []
    for family, task in sorted(families.items()):
        try:
            contract = resolve_contract(task)
            row = contract.as_review_row()
            try:
                adapter = resolve_result_adapter(contract)
                adapter_state = f"resolved:{adapter.__module__}.{adapter.__name__}"
            except (LookupError, ImportError) as exc:
                adapter_state = f"unresolved:{exc}"
            packet_requirement = {
                "program_service_discovery": "materialized retained evidence units; schema evidence enum; deterministic parser",
                "direct_service_semantics": "materialized retained evidence units with governed locator IDs and active governed scopes",
            }.get(task["task_profile"], "draft contract requires human/Sol semantic approval before packet execution")
            readiness = "packet_dependent_production_bound" if contract.executable else "not_execution_ready_draft_for_review"
            row.update({"phase5_family_id": family, "phase5_task_profile": task["task_profile"], "phase5_task_profile_version": task["task_profile_version"], "currently_executable": contract.executable, "execution_packet_requirements": packet_requirement, "adapter_resolution": adapter_state, "execution_readiness": readiness, "deterministic_component": "none_for_semantic_task", "semantic_component": "provider-bound semantic execution" if contract.executable else "not authorised"})
        except Exception as exc:
            resolution_errors[family] = str(exc)
            row = {"phase5_family_id": family, "phase5_task_profile": task["task_profile"], "phase5_task_profile_version": task["task_profile_version"], "authority_state": "blocked", "currently_executable": False, "resolution_error": str(exc)}
        coverage.append(row)

    reassessment = []
    for task in semantic:
        if task["logical_task_id"] not in SLICE_IDS:
            continue
        route = routes[task["logical_task_id"]]
        contract = resolve_contract(task)
        evidence_ids: tuple[str, ...] = ()
        new_id = provider_request_identity(task, contract, model=route["model"], delivery_mode=route["service_tier"], evidence_ids=evidence_ids)
        reassessment.append({
            "logical_task_id": task["logical_task_id"], "claim_family_id": task["claim_family_id"],
            "task_profile": task["task_profile"], "authority_state": contract.authority_state,
            "contract_id": contract.contract_id, "contract_hash": contract.identity_hash(evidence_ids),
            "prompt_sha256": contract.prompt_sha256, "schema_id": contract.schema_id,
            "schema_version": contract.schema_version, "schema_sha256": contract.schema_hash_for_evidence(evidence_ids),
            "adapter_id": contract.adapter_id, "adapter_version": contract.adapter_version,
            "model": route["model"], "reasoning_effort": route["reasoning_effort"],
            "existing_request_item_id": route["provider_request_item_id"], "candidate_contract_request_item_id": new_id,
            "request_identity_changed": route["provider_request_item_id"] != new_id,
        })
    counts = {state: sum(1 for row in coverage if row.get("authority_state") == state) for state in ("production_adopted", "production_bound", "draft_for_review", "blocked")}
    packet = {
        "packet_version": "phase5-semantic-contract-registry-v1",
        "active_semantic_family_count": len(coverage), "coverage": coverage,
        "registry_rows": registry_rows(), "resolution_errors": resolution_errors,
        "authority_counts": counts, "first_paid_slice_reassessment": reassessment,
        "first_paid_slice_approved_count": sum(1 for row in reassessment if row["authority_state"] in {"production_adopted", "production_bound"}),
        "provider_serialization_policy": "production_bound_only; drafts and blocked contracts fail closed",
        "provider_calls": 0, "batch_submissions": 0, "source_acquisition": 0, "semantic_executions": 0, "provider_cost_usd": "0",
    }
    _write(output_root / "phase5-semantic-contract-review-packet.json", packet)
    _write(output_root / "phase5-semantic-contract-registry.json", {"registry": registry_rows(), "authority_counts": counts})
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--routes", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-real-provider-dry-run-v1\route-manifest.json"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-semantic-contract-registry-v1"))
    args = parser.parse_args()
    print(json.dumps(build_packet(args.manifest, args.routes, args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
