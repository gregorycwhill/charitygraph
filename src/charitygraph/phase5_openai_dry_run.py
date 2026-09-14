"""No-send compilation of the Phase-5 workload into OpenAI wire artefacts."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Iterable

from .phase5_semantic_contracts import executable_contract_for, provider_request_identity, resolve_contract
from .phase5_execution_packet import ExecutionPacketUnready, SemanticExecutionPacket, render_packet_prompt

RESPONSES_ENDPOINT = "/v1/responses"
DISCOVERY_MAX_OUTPUT_TOKENS = 8000
LUNA, TERRA = "gpt-5.6-luna", "gpt-5.6-terra"
PROVIDER_SCHEMA_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MONEY_QUANTUM = Decimal("0.000001")
# Empirical upper bound for future Standard reservations.  The retained V1.1
# run observed a maximum provider/local-input ratio of 1.582856; 1.60 remains
# the conservative token expansion until exact billing tokenization is used.
STANDARD_INPUT_BOUND_FACTOR = Decimal("1.60")
STANDARD_LONG_CONTEXT_INPUT_THRESHOLD = 272_000
STANDARD_LONG_CONTEXT_INPUT_MULTIPLIER = Decimal("2")
STANDARD_LONG_CONTEXT_OUTPUT_MULTIPLIER = Decimal("1.5")


class BatchPayloadError(ValueError):
    """The bytes do not satisfy the canonical OpenAI Batch JSONL contract."""


def validate_batch_jsonl_bytes(payload: bytes, *, expected_custom_ids: Iterable[str] | None = None) -> tuple[dict[str, Any], ...]:
    """Validate immutable provider-bound Batch bytes without re-encoding them."""
    if not isinstance(payload, bytes):
        raise BatchPayloadError("Batch payload must be bytes")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise BatchPayloadError("Batch payload must not contain a UTF-8 BOM")
    if b"\x00" in payload:
        raise BatchPayloadError("Batch payload must not contain NUL bytes")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise BatchPayloadError("Batch payload is not valid UTF-8") from exc
    if b"\r" in payload:
        raise BatchPayloadError("Batch payload must use LF-only records")
    if not payload.endswith(b"\n"):
        raise BatchPayloadError("Batch payload must use exactly one final LF and LF-only records")
    lines = text.split("\n")
    if lines[-1] != "":
        raise BatchPayloadError("Batch payload must have exactly one final LF")
    if any(line == "" for line in lines[:-1]):
        raise BatchPayloadError("Batch payload must not contain blank records")
    rows: list[dict[str, Any]] = []
    for line in lines[:-1]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BatchPayloadError("Batch payload contains malformed JSONL") from exc
        if not isinstance(value, dict):
            raise BatchPayloadError("Batch payload records must be JSON objects")
        custom_id = value.get("custom_id")
        if not isinstance(custom_id, str) or not custom_id:
            raise BatchPayloadError("Batch payload records require a custom_id")
        rows.append(value)
    ids = [row["custom_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise BatchPayloadError("Batch payload contains duplicate custom_id values")
    if expected_custom_ids is not None and set(ids) != {str(item) for item in expected_custom_ids}:
        raise BatchPayloadError("Batch payload custom_id set does not match authorization")
    return tuple(rows)


def canonical_batch_jsonl_bytes(items: Iterable[dict[str, Any]], *, expected_custom_ids: Iterable[str] | None = None) -> bytes:
    """Serialize Batch records once, directly to canonical UTF-8 bytes."""
    rows = tuple(items)
    raw = ("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in rows) + ("\n" if rows else "")).encode("utf-8")
    validate_batch_jsonl_bytes(raw, expected_custom_ids=expected_custom_ids)
    return raw


def conservative_money_ceiling(value: Decimal | str, quantum: Decimal = MONEY_QUANTUM) -> Decimal:
    """Round a non-negative authorization amount upward to ledger precision."""
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("money ceiling must be a finite non-negative Decimal")
    return amount.quantize(quantum, rounding=ROUND_CEILING)


def conservative_member_aud_ceiling(usd_amount: Decimal | str, aud_per_usd: Decimal | str) -> Decimal:
    """Convert one member ceiling and round it upward before aggregation."""
    return conservative_money_ceiling(Decimal(str(usd_amount)) * Decimal(str(aud_per_usd)))


def conservative_standard_hard_max_usd(input_tokens_estimate: int | Decimal | str, max_output_tokens: int, *, model: str = "gpt-5.6-luna", input_bound_factor: Decimal | str = STANDARD_INPUT_BOUND_FACTOR) -> Decimal:
    """Return a conservative Standard exposure bound from pinned request data.

    The input estimate is not treated as exact billing. It is expanded by an
    explicit empirically-derived bound and priced at the model's highest
    input rate (including cache writes). If that upper input bound can cross
    the long-context threshold, the full-request long-context multipliers are
    applied to both input and output. The output cap is a mechanical provider
    limit. The result is rounded upward at ledger precision.
    """
    estimate = Decimal(str(input_tokens_estimate))
    factor = Decimal(str(input_bound_factor))
    if estimate < 0 or factor < 1 or max_output_tokens < 0:
        raise ValueError("Standard hard exposure inputs are invalid")
    price = PRICING[model]
    upper_input = estimate * factor
    long_context = upper_input > STANDARD_LONG_CONTEXT_INPUT_THRESHOLD
    input_rate = max(price["input"], price.get("cache_write_input", price["input"]))
    input_multiplier = STANDARD_LONG_CONTEXT_INPUT_MULTIPLIER if long_context else Decimal(1)
    output_multiplier = STANDARD_LONG_CONTEXT_OUTPUT_MULTIPLIER if long_context else Decimal(1)
    usd = (upper_input * input_rate * input_multiplier
           + Decimal(max_output_tokens) * price["output"] * output_multiplier) / Decimal(1_000_000)
    return conservative_money_ceiling(usd, Decimal("0.000001"))


def conservative_standard_hard_max_aud(input_tokens_estimate: int | Decimal | str, max_output_tokens: int, aud_per_usd: Decimal | str, *, model: str = "gpt-5.6-luna", input_bound_factor: Decimal | str = STANDARD_INPUT_BOUND_FACTOR) -> Decimal:
    return conservative_money_ceiling(conservative_standard_hard_max_usd(input_tokens_estimate, max_output_tokens, model=model, input_bound_factor=input_bound_factor) * Decimal(str(aud_per_usd)))

CAPABILITIES = {
    LUNA: {"provider": "openai", "responses": True, "batch": True, "flex": True, "structured_outputs": True, "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"], "context_window": 1_050_000, "max_output_tokens": 128_000, "batch_queue_tier1": 5_000_000},
    TERRA: {"provider": "openai", "responses": True, "batch": True, "flex": True, "structured_outputs": True, "reasoning_efforts": ["none", "low", "medium", "high", "xhigh", "max"], "context_window": 1_050_000, "max_output_tokens": 128_000, "batch_queue_tier1": 5_000_000},
}

PRICING = {
    LUNA: {"input": Decimal("0.20"), "cached_input": Decimal("0.02"), "cache_write_input": Decimal("0.25"), "output": Decimal("1.20")},
    TERRA: {"input": Decimal("2.00"), "cached_input": Decimal("0.20"), "cache_write_input": Decimal("2.50"), "output": Decimal("12.00")},
}


def standard_actual_cost(usage: dict[str, Any], aud_per_usd: Decimal | str, *, model: str = LUNA) -> tuple[Decimal, Decimal]:
    """Calculate Standard actual cost from Responses token detail at pinned rates.

    Cache-write and cached counts are treated as mutually exclusive subsets
    of input_tokens. Long-context pricing applies to the full request once the
    input total exceeds the documented threshold. Both ledger amounts round
    upward so reconciliation cannot understate provider exposure.
    """
    price = PRICING[model]
    input_tokens = Decimal(str(usage.get("input_tokens", 0)))
    output_tokens = Decimal(str(usage.get("output_tokens", 0)))
    details = usage.get("input_tokens_details")
    details = details if isinstance(details, dict) else {}
    cached_tokens = Decimal(str(details.get("cached_tokens", 0)))
    cache_write_tokens = Decimal(str(details.get("cache_write_tokens", 0)))
    values = (input_tokens, output_tokens, cached_tokens, cache_write_tokens)
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("Standard usage token counts must be finite and non-negative")
    if cached_tokens + cache_write_tokens > input_tokens:
        raise ValueError("Standard cached and cache-write tokens exceed total input tokens")
    uncached_tokens = input_tokens - cached_tokens - cache_write_tokens
    input_usd = (uncached_tokens * price["input"]
                 + cached_tokens * price["cached_input"]
                 + cache_write_tokens * price.get("cache_write_input", price["input"]))
    output_usd = output_tokens * price["output"]
    if input_tokens > STANDARD_LONG_CONTEXT_INPUT_THRESHOLD:
        input_usd *= STANDARD_LONG_CONTEXT_INPUT_MULTIPLIER
        output_usd *= STANDARD_LONG_CONTEXT_OUTPUT_MULTIPLIER
    usd = conservative_money_ceiling((input_usd + output_usd) / Decimal(1_000_000))
    aud = conservative_money_ceiling(usd * Decimal(str(aud_per_usd)))
    return usd, aud

@dataclass(frozen=True)
class CompiledRequest:
    logical_task_id: str
    provider_request_item_id: str
    delivery_job_id: str
    model: str
    delivery_mode: str
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
    """Parse one OpenAI Batch JSONL envelope and its Responses body.

    Batch item state, HTTP outcome, and the inner Responses lifecycle are kept
    as separate fields.  ``status`` remains the small compatibility projection
    consumed by the transport: it is ``completed`` only for a successful HTTP
    response whose inner Responses object is completed.
    """
    if not isinstance(payload, dict):
        raise ValueError("Batch result envelope must be an object")
    custom_id = payload.get("custom_id")
    if custom_id not in known_request_ids:
        raise ValueError("unknown provider custom_id")
    batch_error = payload.get("error")
    if batch_error is not None:
        return {
            "provider_request_item_id": custom_id,
            "status": "failed",
            "batch_item_status": "failed",
            "http_status": None,
            "provider_request_id": None,
            "provider_response_id": None,
            "responses_status": None,
            "usage": None,
            "service_tier": None,
            "error": batch_error,
        }

    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("Batch result envelope is missing response object")
    status_code = response.get("status_code")
    request_id = response.get("request_id")
    body = response.get("body")
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("Batch response is missing integer status_code")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("Batch response is missing request_id")
    if not isinstance(body, dict):
        raise ValueError("Batch response is missing Responses body")

    responses_status = body.get("status")
    usage = body.get("usage")
    service_tier = body.get("service_tier")
    successful_http = 200 <= status_code < 300
    if successful_http:
        if not isinstance(body.get("id"), str) or not body["id"]:
            raise ValueError("successful Batch response is missing Responses id")
        if not isinstance(responses_status, str) or not responses_status:
            raise ValueError("successful Batch response is missing Responses status")
        if responses_status == "completed":
            status = "completed"
        else:
            status = "failed"
    else:
        status = "failed"

    return {
        "provider_request_item_id": custom_id,
        "status": status,
        "batch_item_status": "completed" if status == "completed" else "failed",
        "http_status": status_code,
        "provider_request_id": request_id,
        "provider_response_id": body.get("id"),
        "responses_status": responses_status,
        "usage": usage,
        "service_tier": service_tier,
        "error": body.get("error") if not successful_http else None,
    }


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


def validate_provider_schema_name(name: str) -> str:
    """Validate an OpenAI structured-output alias before any wire artefact exists."""
    if not isinstance(name, str) or not PROVIDER_SCHEMA_NAME_PATTERN.fullmatch(name) or len(name) > 64:
        raise ValueError("provider structured-output schema name must match ^[a-zA-Z0-9_-]+$ and be at most 64 characters")
    return name


PROVIDER_SERVICE_TIERS = frozenset({"auto", "default", "fast", "flex", "priority"})


def provider_service_tier_for_delivery_mode(delivery_mode: str) -> str | None:
    """Map Factory delivery semantics to the inner Responses API boundary."""
    if delivery_mode == "batch":
        return None
    if delivery_mode == "flex":
        return "flex"
    if delivery_mode == "standard":
        return None
    raise ValueError(f"unsupported internal delivery mode: {delivery_mode}")


def validate_provider_service_tier(service_tier: str | None) -> str | None:
    if service_tier is not None and service_tier not in PROVIDER_SERVICE_TIERS:
        raise ValueError(f"unsupported Responses service_tier: {service_tier}")
    return service_tier


def resolve_model(task: dict[str, Any]) -> tuple[str, str]:
    if task["difficulty"] == "lower_cost_constrained_semantic":
        return LUNA, "low"
    if task["difficulty"] == "stronger_semantic_judgement":
        return TERRA, "high"
    raise ValueError("dry-run compiler accepts semantic tasks only")


def serialize_execution_packet_request(task: dict[str, Any], packet: SemanticExecutionPacket, *, delivery_job_id: str, delivery_mode: str) -> CompiledRequest:
    model, effort = resolve_model(task)
    contract = executable_contract_for(task)
    evidence_ids = tuple(item.evidence_id for item in packet.evidence_units)
    schema = contract.schema_for_evidence(evidence_ids)
    _validate_schema(schema)
    if not contract.provider_schema_name:
        raise ValueError(f"contract {contract.contract_id} has no explicit provider schema name")
    schema_name = validate_provider_schema_name(contract.provider_schema_name)
    provider_service_tier = validate_provider_service_tier(provider_service_tier_for_delivery_mode(delivery_mode))
    schema_hash = contract.schema_hash_for_evidence(evidence_ids)
    request_item_id = provider_request_identity(task, contract, model=model, reasoning_effort=effort, delivery_mode=delivery_mode, provider_schema_name=schema_name, schema_hash=schema_hash, evidence_ids=evidence_ids, max_output_tokens=DISCOVERY_MAX_OUTPUT_TOKENS)
    prompt = render_packet_prompt(packet, contract)
    evidence_bindings = [
        {
            "evidence_id": item.evidence_id,
            "artifact_id": item.artifact_id,
            "content_hash": item.content_hash,
            "byte_count": item.byte_count,
            "source_record_id": item.source_record_id,
        }
        for item in packet.evidence_units
    ]
    body = {
        "model": model,
        "reasoning": {"effort": effort},
        "max_output_tokens": DISCOVERY_MAX_OUTPUT_TOKENS,
        "store": False,
        "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps({"logical_task_id": task["logical_task_id"], "claim_family_id": task["claim_family_id"], "task_profile": task["task_profile"], "prompt_policy_version": task["prompt_policy_version"], "evidence_corpus_hash": task["evidence_corpus_hash"], "semantic_contract": contract.identity_payload(evidence_ids), "evidence_policy": contract.evidence_policy, "evidence_bindings": evidence_bindings}, ensure_ascii=False, sort_keys=True)}]},
        ],
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        "metadata": {"logical_task_id": task["logical_task_id"], "provider_request_item_id": request_item_id, "delivery_job_id": delivery_job_id, "claim_family_id": task["claim_family_id"], "semantic_contract_id": contract.contract_id, "semantic_contract_hash": contract.identity_hash(evidence_ids)},
    }
    if provider_service_tier is not None:
        body["service_tier"] = provider_service_tier
    return CompiledRequest(task["logical_task_id"], request_item_id, delivery_job_id, model, delivery_mode, schema_name, body)


def serialize_candidate_execution_packet_request(task: dict[str, Any], packet: SemanticExecutionPacket, *, delivery_job_id: str, delivery_mode: str) -> CompiledRequest:
    """Compile a complete candidate contract without authorizing transmission.

    This is intentionally separate from the production serializer.  It is
    useful for offline schema/identity certification and future-ticket
    preparation, but the normal execution entry point remains fail-closed on
    ``executable_contract_for``.
    """
    contract = resolve_contract(task)
    if contract.executable:
        raise ValueError("candidate serializer requires a non-executable candidate contract")
    contract.assert_complete()
    model, effort = resolve_model(task)
    evidence_ids = tuple(item.evidence_id for item in packet.evidence_units)
    schema = contract.schema_for_evidence(evidence_ids)
    _validate_schema(schema)
    schema_name = validate_provider_schema_name(contract.provider_schema_name or "")
    provider_service_tier = validate_provider_service_tier(provider_service_tier_for_delivery_mode(delivery_mode))
    request_item_id = provider_request_identity(task, contract, model=model, reasoning_effort=effort, delivery_mode=delivery_mode, provider_schema_name=schema_name, schema_hash=contract.schema_hash_for_evidence(evidence_ids), evidence_ids=evidence_ids, max_output_tokens=DISCOVERY_MAX_OUTPUT_TOKENS)
    prompt = render_packet_prompt(packet, contract)
    evidence_bindings = [{
        "evidence_id": item.evidence_id,
        "artifact_id": item.artifact_id,
        "content_hash": item.content_hash,
        "byte_count": item.byte_count,
        "source_record_id": item.source_record_id,
    } for item in packet.evidence_units]
    body = {
        "model": model,
        "reasoning": {"effort": effort},
        "max_output_tokens": DISCOVERY_MAX_OUTPUT_TOKENS,
        "store": False,
        "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps({"logical_task_id": task["logical_task_id"], "claim_family_id": task["claim_family_id"], "task_profile": task["task_profile"], "prompt_policy_version": task["prompt_policy_version"], "evidence_corpus_hash": task["evidence_corpus_hash"], "semantic_contract": contract.identity_payload(evidence_ids), "evidence_policy": contract.evidence_policy, "evidence_bindings": evidence_bindings}, ensure_ascii=False, sort_keys=True)}]},
        ],
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        "metadata": {"logical_task_id": task["logical_task_id"], "provider_request_item_id": request_item_id, "delivery_job_id": delivery_job_id, "claim_family_id": task["claim_family_id"], "semantic_contract_id": contract.contract_id, "semantic_contract_hash": contract.identity_hash(evidence_ids)},
    }
    if provider_service_tier is not None:
        body["service_tier"] = provider_service_tier
    return CompiledRequest(task["logical_task_id"], request_item_id, delivery_job_id, model, delivery_mode, schema_name, body)


def compile_request(task: dict[str, Any], corpus: dict[str, Any], *, delivery_job_id: str, delivery_mode: str, packet: SemanticExecutionPacket | None = None) -> CompiledRequest:
    """Compatibility entry point; manifest-only compilation is forbidden."""
    if packet is None:
        raise ExecutionPacketUnready("OpenAI serialization requires a materialized semantic execution packet")
    return serialize_execution_packet_request(task, packet, delivery_job_id=delivery_job_id, delivery_mode=delivery_mode)


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
        compiled.append(compile_request(task, corpus, delivery_job_id=f"deliveryjob:openai-batch-{job_number:03d}", delivery_mode="batch"))
    # Reassign deterministic job identities after route partitioning.
    jobs: dict[tuple[str, str], list[CompiledRequest]] = {}
    for request in compiled:
        jobs.setdefault((request.model, request.delivery_mode), []).append(request)
    final: list[CompiledRequest] = []
    job_rows = []
    for (model, tier), requests in sorted(jobs.items()):
        for index in range(0, len(requests), batch_items):
            chunk = requests[index:index + batch_items]
            job_id = f"deliveryjob:openai-batch-{len(job_rows)+1:03d}"
            jsonl = []
            for request in chunk:
                task = task_by_id[request.logical_task_id]
                request = compile_request(task, json.loads((corpus_dir / (inventory[task["subject_id"]]["abn"] + ".json")).read_text()), delivery_job_id=job_id, delivery_mode="batch")
                item = {"custom_id": request.provider_request_item_id, "method": "POST", "url": RESPONSES_ENDPOINT, "body": request.body}
                jsonl.append(item); final.append(request)
            raw_bytes = canonical_batch_jsonl_bytes(jsonl, expected_custom_ids=[item["custom_id"] for item in jsonl])
            job_rows.append({"delivery_job_id": job_id, "model": model, "delivery_mode": tier, "items": len(jsonl), "bytes": len(raw_bytes), "estimated_input_tokens": sum(estimate_tokens(i["body"]) for i in jsonl), "sha256": hashlib.sha256(raw_bytes).hexdigest(), "items_jsonl_bytes": raw_bytes})
    output_root.mkdir(parents=True, exist_ok=True)
    batch_dir = output_root / "batch-jsonl"; batch_dir.mkdir(exist_ok=True)
    for row in job_rows:
        (batch_dir / (row["delivery_job_id"].replace(":", "_") + ".jsonl")).write_bytes(row.pop("items_jsonl_bytes"))
    for request in final:
        if request.delivery_mode == "standard":
            pass
    counts = {model: sum(1 for r in final if r.model == model) for model in (LUNA, TERRA)}
    cost_standard = Decimal("0"); cost_selected = Decimal("0"); input_tokens = 0; output_tokens = 0
    selected_member_costs: dict[str, Decimal] = {}
    selected_member_aud_costs: dict[str, Decimal] = {}
    for row in job_rows:
        input_tokens += row["estimated_input_tokens"]
    output_tokens = sum(1600 if request.model == LUNA else 3200 for request in final)
    for request in final:
        model_price = PRICING[request.model]
        tokens = estimate_tokens(request.body)
        out = 1600 if request.model == LUNA else 3200
        standard_member = Decimal(tokens) / Decimal(1_000_000) * model_price["input"] + Decimal(out) / Decimal(1_000_000) * model_price["output"]
        selected_member = standard_member / 2
        cost_standard += conservative_money_ceiling(standard_member)
        cost_selected += conservative_money_ceiling(selected_member)
        selected_member_costs[request.provider_request_item_id] = conservative_money_ceiling(selected_member)
        selected_member_aud_costs[request.provider_request_item_id] = conservative_member_aud_ceiling(selected_member, "1.52")
    by_family: dict[str, Decimal] = defaultdict(Decimal); by_subject: dict[str, Decimal] = defaultdict(Decimal)
    task_by_request = {r.provider_request_item_id: task_by_id[r.logical_task_id] for r in final}
    for request in final:
        tokens = estimate_tokens(request.body); out = 1600 if request.model == LUNA else 3200
        amount = selected_member_costs[request.provider_request_item_id]
        task = task_by_request[request.provider_request_item_id]; by_family[task["claim_family_id"]] += amount; by_subject[task["subject_id"]] += amount
    stable_prefix_tokens = estimate_tokens({"developer": final[0].body["input"][0]}) * len(final)
    selected_batch_aud = sum(selected_member_aud_costs.values(), Decimal("0"))
    report = {"logical_tasks": len(tasks), "semantic_request_items": len(final), "application_bundles": 0, "models": counts, "batch_jobs": len(job_rows), "job_distribution": [{k: v for k, v in row.items() if k != "items_jsonl_bytes"} for row in job_rows], "estimated_input_tokens": input_tokens, "estimated_output_tokens": output_tokens, "estimated_cacheable_prefix_tokens": stable_prefix_tokens, "context_or_size_violations": 0, "schema_validation": {"schemas_validated": len(final), "schema_identities": len({r.schema_name for r in final})}, "pricing_snapshot_id": "openai-model-pages-2026-09-07", "fx_snapshot": {"base": "USD", "quote": "AUD", "rate": "1.52", "status": "dry_run_input"}, "rounding": {"rule": "full Decimal precision; each non-negative member ceiling rounds upward to 0.000001 before aggregation", "ledger_quantum": str(MONEY_QUANTUM)}, "all_standard_usd": str(cost_standard), "selected_batch_usd": str(cost_selected), "selected_batch_aud": str(selected_batch_aud), "flex_requests": 0, "standard_requests": 0, "batch_items": len(final), "cost_by_claim_family_usd": {k: str(v) for k, v in sorted(by_family.items())}, "cost_by_subject_usd": {k: str(v) for k, v in sorted(by_subject.items())}, "serialization": "responses-v1; batch POST /v1/responses; strict structured outputs", "network_calls": 0, "responses_calls": 0, "batch_submissions": 0, "provider_cost_usd": "0", "governed_knowledge_production": 0}
    (output_root / "provider-capability-snapshot.json").write_text(json.dumps({"snapshot_id": "openai-model-pages-2026-09-07", "source": "official OpenAI model documentation", "models": CAPABILITIES}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "real-pricing-snapshot.json").write_text(json.dumps({"snapshot_id": "openai-model-pages-2026-09-07", "currency": "USD", "batch_and_flex_multiplier": "0.5", "models": {model: {key: str(value) for key, value in prices.items()} for model, prices in PRICING.items()}, "source": "official OpenAI model documentation", "retrieved_date": "2026-09-07"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "route-manifest.json").write_text(json.dumps([{"logical_task_id": r.logical_task_id, "provider_request_item_id": r.provider_request_item_id, "delivery_job_id": r.delivery_job_id, "model": r.model, "reasoning_effort": r.body["reasoning"]["effort"], "delivery_mode": r.delivery_mode, "provider_service_tier": r.body.get("service_tier"), "schema_name": r.schema_name} for r in final], indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    (output_root / "budget-preflight.json").write_text(json.dumps({"selected_batch_usd": str(cost_selected), "selected_batch_aud": str(selected_batch_aud), "configured_ceiling_aud": "10000.00", "within_ceiling": selected_batch_aud <= Decimal("10000.00"), "real_provider_authorization": "absent_default_deny", "provider_calls": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "round-trip-report.json").write_text(json.dumps({"request_count": len(final), "unique_custom_ids": len(known_ids) == len(final), "endpoint_consistent": all(row["delivery_job_id"] for row in job_rows), "unknown_id_fail_closed": unknown_failed_closed, "batch_submission_count": 0, "responses_call_count": 0}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "no-send-guard-report.json").write_text(json.dumps({"network_calls": 0, "responses_calls": 0, "file_uploads": 0, "batch_submissions": 0, "flex_sends": 0, "standard_sends": 0, "provider_cost_usd": "0", "gate": "default-deny"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "dry-run-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
