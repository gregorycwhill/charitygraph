"""Prepare the remaining Direct Service slice under the non-executable V1.2 candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.phase5_direct_service_cutover import compile_v12_from_prior_row
from charitygraph.phase5_execution_mandate import manifest_hash, proposed_phase5_standard_luna_v1_2_amendment_manifest
from charitygraph.phase5_openai_dry_run import conservative_standard_hard_max_aud, conservative_standard_hard_max_usd, estimate_tokens
from charitygraph.phase5_semantic_contracts import resolve_contract


DEFAULT_SOURCE = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.1-preparation-v1\campaign\continuation-18-corrected.json")
DEFAULT_OUTPUT = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")
DEFAULT_PROPOSAL = Path("proposals/phase5-direct-service-v1.2-amendment-3.json")
CAMPAIGN = "phase5-direct-service-v1.2-cutover-v1"
RUN = "run:phase5-direct-service-v1.2-cutover"
JOB = "deliveryjob:phase5-direct-service-v1.2-standard"
MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-3"
FX = Decimal("1.52")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--proposal-path", type=Path, default=DEFAULT_PROPOSAL)
    args = parser.parse_args()
    source_raw = args.source.read_bytes()
    source = json.loads(source_raw.decode("utf-8"))
    prior_rows = source.get("request_items", [])
    if len(prior_rows) != 18:
        raise RuntimeError(f"expected exactly 18 prior rows, found {len(prior_rows)}")
    if source.get("excluded_terminal_429") in {row.get("provider_request_item_id") for row in prior_rows}:
        raise RuntimeError("terminal 429 was included in the cutover source")
    outputs = []
    for prior in sorted(prior_rows, key=lambda row: row["logical_task_id"]):
        request = compile_v12_from_prior_row(prior, delivery_job_id=JOB)
        input_estimate = estimate_tokens(request.body)
        hard_usd = conservative_standard_hard_max_usd(input_estimate, 8000)
        hard_aud = conservative_standard_hard_max_aud(input_estimate, 8000, FX)
        if hard_aud >= Decimal("0.25"):
            raise RuntimeError(f"per-request ceiling exceeded for {request.logical_task_id}: {hard_aud}")
        contract = resolve_contract({
            "logical_task_id": request.logical_task_id,
            "claim_family_id": "direct-service-access-v1",
            "task_profile": "direct_service_semantics",
            "task_profile_version": "2",
            "prompt_policy_version": "direct-service-access-v1:prompt-policy:v3-representation",
            "schema_version": "urn:charitygraph:phase5:planned:direct_service_semantics:v2",
            "evidence_corpus_hash": "retained-prior-row",
        })
        body_raw = canonical_bytes(request.body)
        outputs.append({
            "provider_request_item_id": request.provider_request_item_id,
            "logical_task_id": request.logical_task_id,
            "subject_id": prior["subject_id"],
            "old_v1_1_provider_request_item_id": prior["provider_request_item_id"],
            "old_v1_1_reservation_id": prior.get("reservation_id"),
            "old_v1_1_mandate_reservation_id": prior.get("mandate_reservation_id"),
            "contract_id": contract.contract_id,
            "contract_version": contract.contract_version,
            "contract_identity_hash": contract.identity_hash(tuple(json.loads(request.body["input"][1]["content"][0]["text"])["evidence_bindings"][i]["evidence_id"] for i in range(len(json.loads(request.body["input"][1]["content"][0]["text"])["evidence_bindings"])))),
            "prompt_sha256": contract.prompt_sha256,
            "schema_id": contract.schema_id,
            "schema_version": contract.schema_version,
            "schema_hash": sha_bytes(canonical_bytes(request.body["text"]["format"]["schema"])),
            "provider_schema_name": request.schema_name,
            "model": request.model,
            "reasoning_effort": "low",
            "delivery_mode": request.delivery_mode,
            "provider_service_tier": None,
            "max_output_tokens": 8000,
            "input_tokens_estimate": input_estimate,
            "hard_max_usd": str(hard_usd),
            "hard_max_aud": str(hard_aud),
            "wire_fingerprint": request.provider_request_item_id.removeprefix("requestitem:"),
            "request_body_sha256": sha_bytes(body_raw),
            "request_body": request.body,
            "provider_operations": 0,
            "authorization_state": "pending_amendment_3_activation",
        })
    preparation = {
        "manifest_version": "phase5-direct-service-v1.2-cutover-preparation-v1",
        "campaign": CAMPAIGN,
        "run_id": RUN,
        "delivery_job_id": JOB,
        "mandate_id_required": MANDATE,
        "source_v1_1_continuation_sha256": sha_bytes(source_raw),
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "delivery_mode": "standard",
        "provider_service_tier": "omitted",
        "provider_schema_name": "direct_service_semantics_v2",
        "task_profile": "direct_service_semantics",
        "task_profile_version": "2",
        "prompt_policy_version": "direct-service-access-v1:prompt-policy:v3-representation",
        "planner_schema_version": "urn:charitygraph:phase5:planned:direct_service_semantics:v2",
        "max_output_tokens": 8000,
        "max_concurrency": 4,
        "automatic_retries": 0,
        "semantic_retries": 0,
        "fallbacks": [],
        "provider_operations": 0,
        "semantic_executions": 0,
        "governed_promotions": 0,
        "authorization_state": "pending_amendment_3_activation",
        "old_v1_1_requests_excluded": [row["old_v1_1_provider_request_item_id"] for row in outputs],
        "terminal_429_excluded": source.get("excluded_terminal_429"),
        "request_items": outputs,
        "aggregate": {
            "request_item_count": len(outputs),
            "input_tokens_estimate": sum(row["input_tokens_estimate"] for row in outputs),
            "hard_max_usd": str(sum((Decimal(row["hard_max_usd"]) for row in outputs), Decimal("0"))),
            "hard_max_aud": str(sum((Decimal(row["hard_max_aud"]) for row in outputs), Decimal("0"))),
            "max_per_request_aud": str(max(Decimal(row["hard_max_aud"]) for row in outputs)),
        },
    }
    prep_raw = canonical_bytes(preparation)
    jsonl = b"".join(canonical_bytes({"custom_id": row["provider_request_item_id"], "method": "POST", "url": "/v1/responses", "body": row["request_body"]}) + b"\n" for row in outputs)
    proposal = proposed_phase5_standard_luna_v1_2_amendment_manifest()
    proposal_raw = canonical_bytes(proposal)
    args.proposal_path.parent.mkdir(parents=True, exist_ok=True)
    args.proposal_path.write_bytes(proposal_raw)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "preparation.json").write_bytes(prep_raw)
    (args.output_root / "requests.jsonl").write_bytes(jsonl)
    (args.output_root / "future-execution-ticket.json").write_bytes(canonical_bytes({
        "ticket_version": "phase5-direct-service-v1.2-future-execution-ticket-v1",
        "status": "blocked_pending_explicit_amendment_3_activation",
        "campaign": CAMPAIGN,
        "run_id": RUN,
        "delivery_job_id": JOB,
        "preparation_manifest_sha256": sha_bytes(prep_raw),
        "preparation_manifest_bytes": len(prep_raw),
        "jsonl_sha256": sha_bytes(jsonl),
        "jsonl_bytes": len(jsonl),
        "builder_commit_required": "working-branch-commit-to-be-recorded",
        "mandate_id_required": MANDATE,
        "contract_identity": {"contract_id": contract.contract_id, "contract_version": contract.contract_version, "task_profile": "direct_service_semantics", "task_profile_version": "2", "provider_schema_name": "direct_service_semantics_v2"},
        "model": "gpt-5.6-luna", "reasoning_effort": "low", "delivery_mode": "standard", "max_concurrency": 4, "max_output_tokens": 8000,
        "aggregate_hard_max_usd": preparation["aggregate"]["hard_max_usd"], "aggregate_hard_max_aud": preparation["aggregate"]["hard_max_aud"], "per_request_hard_aud": "0.25",
        "one_transmission_max": True, "automatic_retries": 0, "semantic_retries": 0, "fallbacks": [],
        "excluded_v1_1_requests": [row["old_v1_1_provider_request_item_id"] for row in outputs], "excluded_terminal_429": source.get("excluded_terminal_429"),
    }))
    (args.output_root / "summary.json").write_bytes(canonical_bytes({"status": "18/18 PREPARED_PENDING_MANDATE_AUTHORITY", "provider_operations": 0, "source_operations": 0, "semantic_executions": 0, "preparation_manifest_sha256": sha_bytes(prep_raw), "preparation_manifest_bytes": len(prep_raw), "jsonl_sha256": sha_bytes(jsonl), "jsonl_bytes": len(jsonl), "amendment_3_proposal_sha256": sha_bytes(proposal_raw), "amendment_3_proposal_bytes": len(proposal_raw), "aggregate": preparation["aggregate"]}))
    print(json.dumps({"status": "18/18 PREPARED_PENDING_MANDATE_AUTHORITY", "campaign_path": str(args.output_root), "preparation_manifest_sha256": sha_bytes(prep_raw), "preparation_manifest_bytes": len(prep_raw), "jsonl_sha256": sha_bytes(jsonl), "jsonl_bytes": len(jsonl), "amendment_3_path": str(args.proposal_path), "amendment_3_sha256": sha_bytes(proposal_raw), "amendment_3_bytes": len(proposal_raw), "aggregate": preparation["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
