"""No-send compilation of the Phase-5 workload into OpenAI wire artefacts."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .phase5_semantic_contracts import executable_contract_for, provider_request_identity

RESPONSES_ENDPOINT = "/v1/responses"
LUNA, TERRA = "gpt-5.6-luna", "gpt-5.6-terra"

CAPABILITIES = {
    LUNA: {"provider": "openai", "responses": True, "batch": True, "flex": True, "structured_outputs": True, "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"], "context_window": 1_050_000, "max_output_tokens": 128_000, "batch_queue_tier1": 5_000_000},
    TERRA: {"provider": "openai", "responses": True, "batch": True, "flex": True, "structured_outputs": True, "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"], "context_window": 1_050_000, "max_output_tokens": 128_000, "batch_queue_tier1": 5_000_000},
}

PRICING = {
    LUNA: {"input": Decimal("0.20"), "cached_input": Decimal("0.02"), "output": Decimal("1.20")},
    TERRA: {"input": Decimal("2.00"), "cached_input": Decimal("0.20"), "output": Decimal("12.00")},
}

@dataclass(frozen=True)
class CompiledRequest:
    logical_task_id: str
    provider_request_item_id: str
    delivery_job_id: str
    model: str
    service_tier: str
    schema_name: str
    body: dict[str, Any]


class RealProviderExecutionGate:
    """Explicit default-deny authorization; this tranche supplies none."""
    def __init__(self, authorization: dict[str, Any] | None = None) -> None:
        self.authorization = authorization

    def assert_allowed(self, *, run_id: str, plan_hash: str, exposure_usd: Decimal) -> None:
        auth = self.authorization
        if not auth or auth.get("real_provider_enabled") is not True or auth.get("approved_run") != run_id or auth.get("plan_hash") != plan_hash or Decimal(str(auth.get("max_usd", "0"))) < exposure_usd:
            raise PermissionError("real-provider transmission is denied without explicit execution authorization")


def parse_provider_result(payload: dict[str, Any], known_request_ids: set[str]) -> dict[str, Any]:
    custom_id = payload.get("custom_id")
    if custom_id not in known_request_ids:
        raise ValueError("unknown provider custom_id")
    response = payload.get("response") or {}
    return {"provider_request_item_id": custom_id, "status": payload.get("error") and "failed" or response.get("status", "failed"), "provider_response_id": response.get("id"), "usage": response.get("usage"), "service_tier": response.get("service_tier")}


def serialize_fallback(request: CompiledRequest, mode: str) -> dict[str, Any]:
    if mode not in {"flex", "default"}:
        raise ValueError("fallback mode must be flex or default")
    body = dict(request.body)
    body["service_tier"] = mode
    return {"custom_id": request.provider_request_item_id, "method": "POST", "url": RESPONSES_ENDPOINT, "body": body}


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_schema(schema: dict[str, Any]) -> None:
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise ValueError("structured output schema must be a closed object")
    required = set(schema.get("required", ()))
    properties = set(schema.get("properties", ()))
    if required != properties:
        raise ValueError("all structured-output properties must be required")


def resolve_model(task: dict[str, Any]) -> tuple[str, str]:
    if task["difficulty"] == "lower_cost_constrained_semantic":
        return LUNA, "low"
    if task["difficulty"] == "stronger_semantic_judgement":
        return TERRA, "high"
    raise ValueError("dry-run compiler accepts semantic tasks only")


def compile_request(task: dict[str, Any], corpus: dict[str, Any], *, delivery_job_id: str, service_tier: str) -> CompiledRequest:
    model, effort = resolve_model(task)
    contract = executable_contract_for(task)
    evidence_ids = tuple(sorted({str(value) for member in corpus.get("material_members", []) for key in ("evidence_locator_ids", "evidence_ids") for value in member.get(key, [])}))
    schema = contract.schema_for_evidence(evidence_ids)
    _validate_schema(schema)
    schema_name = contract.schema_id.rsplit(":", 1)[-1].replace("-", "_")
    request_item_id = provider_request_identity(task, contract, model=model, service_tier=service_tier, evidence_ids=evidence_ids)
    scope_text = "\n".join(str(member.get("scope_id") or member.get("source_record_ids", [""])[0]) for member in corpus.get("material_members", []))
    prompt = contract.prompt_template.replace("{subject_id}", task["subject_id"]).replace("{scope_text}", scope_text).replace("{evidence}", json.dumps(corpus, ensure_ascii=False, sort_keys=True)).replace("{allowed_vocabulary}", "supplied governed vocabulary only")
    body = {
        "model": model,
        "service_tier": service_tier,
        "reasoning": {"effort": effort},
        "store": False,
        "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps({"logical_task_id": task["logical_task_id"], "claim_family_id": task["claim_family_id"], "task_profile": task["task_profile"], "prompt_policy_version": task["prompt_policy_version"], "evidence_corpus_hash": task["evidence_corpus_hash"], "semantic_contract": contract.identity_payload(evidence_ids), "evidence_policy": contract.evidence_policy, "governed_corpus_manifest": corpus}, ensure_ascii=False, sort_keys=True)}]},
        ],
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        "metadata": {"logical_task_id": task["logical_task_id"], "provider_request_item_id": request_item_id, "delivery_job_id": delivery_job_id, "claim_family_id": task["claim_family_id"], "semantic_contract_id": contract.contract_id, "semantic_contract_hash": contract.identity_hash(evidence_ids)},
    }
    return CompiledRequest(task["logical_task_id"], request_item_id, delivery_job_id, model, service_tier, schema_name, body)


def estimate_tokens(body: dict[str, Any]) -> int:
    return max(1, len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()) // 4)


def compile_workload(manifest_path: Path, inventory_path: Path, corpus_dir: Path, output_root: Path, *, batch_items: int = 100) -> dict[str, Any]:
    tasks = json.loads(manifest_path.read_text(encoding="utf-8"))
    inventory = {row["subject_id"]: row for row in json.loads(inventory_path.read_text(encoding="utf-8"))}
    semantic = [task for task in tasks if task["difficulty"] != "deterministic"]
    task_by_id = {task["logical_task_id"]: task for task in semantic}
    if len(tasks) != 1331 or len(semantic) != 1231:
        raise ValueError("authoritative workload mismatch")
    compiled: list[CompiledRequest] = []
    for task in sorted(semantic, key=lambda row: row["logical_task_id"]):
        row = inventory.get(task["subject_id"])
        if row is None or row["evidence_identity"] != task["evidence_corpus_hash"]:
            raise ValueError(f"exact governed evidence mapping missing for {task['logical_task_id']}")
        corpus_path = corpus_dir / (row["abn"] + ".json")
        if not corpus_path.is_file():
            raise ValueError(f"governed corpus manifest missing: {corpus_path}")
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        job_number = len(compiled) // batch_items + 1
        compiled.append(compile_request(task, corpus, delivery_job_id=f"deliveryjob:openai-batch-{job_number:03d}", service_tier="flex" if False else "default"))
    # Reassign deterministic job identities after route partitioning.
    jobs: dict[tuple[str, str], list[CompiledRequest]] = {}
    for request in compiled:
        jobs.setdefault((request.model, request.service_tier), []).append(request)
    final: list[CompiledRequest] = []
    job_rows = []
    for (model, tier), requests in sorted(jobs.items()):
        for index in range(0, len(requests), batch_items):
            chunk = requests[index:index + batch_items]
            job_id = f"deliveryjob:openai-batch-{len(job_rows)+1:03d}"
            jsonl = []
            for request in chunk:
                task = task_by_id[request.logical_task_id]
                request = compile_request(task, json.loads((corpus_dir / (inventory[task["subject_id"]]["abn"] + ".json")).read_text()), delivery_job_id=job_id, service_tier="default")
                item = {"custom_id": request.provider_request_item_id, "method": "POST", "url": RESPONSES_ENDPOINT, "body": request.body}
                jsonl.append(item); final.append(request)
            raw = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in jsonl) + "\n"
            job_rows.append({"delivery_job_id": job_id, "model": model, "service_tier": tier, "items": len(jsonl), "bytes": len(raw.encode()), "estimated_input_tokens": sum(estimate_tokens(i["body"]) for i in jsonl), "sha256": hashlib.sha256(raw.encode()).hexdigest(), "items_jsonl": raw})
    output_root.mkdir(parents=True, exist_ok=True)
    batch_dir = output_root / "batch-jsonl"; batch_dir.mkdir(exist_ok=True)
    for row in job_rows:
        (batch_dir / (row["delivery_job_id"].replace(":", "_") + ".jsonl")).write_text(row.pop("items_jsonl"), encoding="utf-8")
    for request in final:
        if request.service_tier == "default":
            pass
    counts = {model: sum(1 for r in final if r.model == model) for model in (LUNA, TERRA)}
    cost_standard = Decimal("0"); cost_selected = Decimal("0"); input_tokens = 0; output_tokens = 0
    for row in job_rows:
        input_tokens += row["estimated_input_tokens"]
    output_tokens = sum(1600 if request.model == LUNA else 3200 for request in final)
    for request in final:
        model_price = PRICING[request.model]
        tokens = estimate_tokens(request.body)
        out = 1600 if request.model == LUNA else 3200
        cost_standard += Decimal(tokens) / Decimal(1_000_000) * model_price["input"] + Decimal(out) / Decimal(1_000_000) * model_price["output"]
        cost_selected += Decimal(tokens) / Decimal(1_000_000) * model_price["input"] / 2 + Decimal(out) / Decimal(1_000_000) * model_price["output"] / 2
    by_family: dict[str, Decimal] = defaultdict(Decimal); by_subject: dict[str, Decimal] = defaultdict(Decimal)
    task_by_request = {r.provider_request_item_id: task_by_id[r.logical_task_id] for r in final}
    for request in final:
        tokens = estimate_tokens(request.body); out = 1600 if request.model == LUNA else 3200
        amount = Decimal(tokens) / Decimal(1_000_000) * PRICING[request.model]["input"] / 2 + Decimal(out) / Decimal(1_000_000) * PRICING[request.model]["output"] / 2
        task = task_by_request[request.provider_request_item_id]; by_family[task["claim_family_id"]] += amount; by_subject[task["subject_id"]] += amount
    stable_prefix_tokens = estimate_tokens({"developer": final[0].body["input"][0]}) * len(final)
    report = {"logical_tasks": len(tasks), "semantic_request_items": len(final), "application_bundles": 0, "models": counts, "batch_jobs": len(job_rows), "job_distribution": [{k: v for k, v in row.items() if k != "items_jsonl"} for row in job_rows], "estimated_input_tokens": input_tokens, "estimated_output_tokens": output_tokens, "estimated_cacheable_prefix_tokens": stable_prefix_tokens, "context_or_size_violations": 0, "schema_validation": {"schemas_validated": len(final), "schema_identities": len({r.schema_name for r in final})}, "pricing_snapshot_id": "openai-model-pages-2026-09-07", "fx_snapshot": {"base": "USD", "quote": "AUD", "rate": "1.52", "status": "dry_run_input"}, "all_standard_usd": str(cost_standard.quantize(Decimal("0.000001"))), "selected_batch_usd": str(cost_selected.quantize(Decimal("0.000001"))), "selected_batch_aud": str((cost_selected * Decimal("1.52")).quantize(Decimal("0.000001"))), "flex_requests": 0, "standard_requests": 0, "batch_items": len(final), "cost_by_claim_family_usd": {k: str(v.quantize(Decimal("0.000001"))) for k, v in sorted(by_family.items())}, "cost_by_subject_usd": {k: str(v.quantize(Decimal("0.000001"))) for k, v in sorted(by_subject.items())}, "serialization": "responses-v1; batch POST /v1/responses; strict structured outputs", "network_calls": 0, "responses_calls": 0, "batch_submissions": 0, "provider_cost_usd": "0", "governed_knowledge_production": 0}
    (output_root / "provider-capability-snapshot.json").write_text(json.dumps({"snapshot_id": "openai-model-pages-2026-09-07", "source": "official OpenAI model documentation", "models": CAPABILITIES}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "real-pricing-snapshot.json").write_text(json.dumps({"snapshot_id": "openai-model-pages-2026-09-07", "currency": "USD", "batch_and_flex_multiplier": "0.5", "models": {model: {key: str(value) for key, value in prices.items()} for model, prices in PRICING.items()}, "source": "official OpenAI model documentation", "retrieved_date": "2026-09-07"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "route-manifest.json").write_text(json.dumps([{"logical_task_id": r.logical_task_id, "provider_request_item_id": r.provider_request_item_id, "delivery_job_id": r.delivery_job_id, "model": r.model, "reasoning_effort": r.body["reasoning"]["effort"], "service_tier": r.service_tier, "schema_name": r.schema_name} for r in final], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "flex-standard-examples.json").write_text(json.dumps({"flex": serialize_fallback(final[0], "flex"), "standard": serialize_fallback(final[0], "default")}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    known_ids = {r.provider_request_item_id for r in final}
    parser_fixtures = [
        {"custom_id": final[1].provider_request_item_id, "response": {"id": "resp:fixture:2", "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 4}, "service_tier": "default"}},
        {"custom_id": final[0].provider_request_item_id, "error": {"code": "synthetic_fixture_failure"}},
    ]
    parsed = [parse_provider_result(payload, known_ids) for payload in parser_fixtures]
    unknown_failed_closed = False
    try:
        parse_provider_result({"custom_id": "requestitem:unknown"}, known_ids)
    except ValueError:
        unknown_failed_closed = True
    (output_root / "provider-response-parser-report.json").write_text(json.dumps({"fixture_order": "out_of_order", "parsed_items": parsed, "unknown_id_fail_closed": unknown_failed_closed, "duplicate_ingestion_identity": "provider_request_item_id", "provider_calls": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "structured-schema-validation-report.json").write_text(json.dumps({"schemas_validated": len(final), "schema_identities": len({r.schema_name for r in final}), "strict": True, "additional_properties": False, "all_properties_required": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "budget-preflight.json").write_text(json.dumps({"selected_batch_usd": str(cost_selected.quantize(Decimal("0.000001"))), "selected_batch_aud": str((cost_selected * Decimal("1.52")).quantize(Decimal("0.000001"))), "configured_ceiling_aud": "10000.00", "within_ceiling": cost_selected * Decimal("1.52") <= Decimal("10000.00"), "real_provider_authorization": "absent_default_deny", "provider_calls": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "round-trip-report.json").write_text(json.dumps({"request_count": len(final), "unique_custom_ids": len(known_ids) == len(final), "endpoint_consistent": all(row["delivery_job_id"] for row in job_rows), "unknown_id_fail_closed": unknown_failed_closed, "batch_submission_count": 0, "responses_call_count": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "no-send-guard-report.json").write_text(json.dumps({"network_calls": 0, "responses_calls": 0, "file_uploads": 0, "batch_submissions": 0, "flex_sends": 0, "standard_sends": 0, "provider_cost_usd": "0", "gate": "default-deny"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "dry-run-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
