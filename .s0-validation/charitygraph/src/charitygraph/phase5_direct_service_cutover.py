"""Provider-free preparation helpers for the Direct Service V1.2 cutover."""
from __future__ import annotations

import copy
import json
from typing import Any

from .phase5_openai_dry_run import (
    DISCOVERY_MAX_OUTPUT_TOKENS,
    CompiledRequest,
    _validate_schema,
    provider_service_tier_for_delivery_mode,
    validate_provider_schema_name,
)
from .phase5_semantic_contracts import provider_request_identity, resolve_contract


V12_TASK_PROFILE_VERSION = "2"
V12_PROMPT_POLICY = "direct-service-access-v1:prompt-policy:v3-representation"
V12_PLANNER_SCHEMA = "urn:charitygraph:phase5:planned:direct_service_semantics:v2"


def compile_v12_from_prior_row(prior_row: dict[str, Any], *, delivery_job_id: str) -> CompiledRequest:
    """Recompile one never-sent V1.1 row as a V1.2 candidate.

    Only the contract/prompt/schema binding changes.  Evidence bindings and
    the logical task identity are copied from the immutable prior preparation;
    no catalogue or reservation is touched by this function.
    """
    old_body = prior_row.get("request_body")
    if not isinstance(old_body, dict):
        raise ValueError("prior request body is not an object")
    body = copy.deepcopy(old_body)
    try:
        user = json.loads(body["input"][1]["content"][0]["text"])
        old_prompt = body["input"][0]["content"][0]["text"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("prior request body lacks the governed two-part input") from exc
    bindings = user.get("evidence_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("prior request has no evidence bindings")
    if any(not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str) for item in bindings):
        raise ValueError("prior request has malformed evidence bindings")
    evidence_ids = tuple(item["evidence_id"] for item in bindings)
    task = {
        "logical_task_id": prior_row["logical_task_id"],
        "claim_family_id": user["claim_family_id"],
        "task_profile": "direct_service_semantics",
        "task_profile_version": V12_TASK_PROFILE_VERSION,
        "prompt_policy_version": V12_PROMPT_POLICY,
        "schema_version": V12_PLANNER_SCHEMA,
        "evidence_corpus_hash": user["evidence_corpus_hash"],
    }
    contract = resolve_contract(task)
    if contract.executable:
        raise ValueError("V1.2 candidate unexpectedly became executable")
    contract.assert_complete()
    schema = contract.schema_for_evidence(evidence_ids)
    _validate_schema(schema)
    schema_name = validate_provider_schema_name(contract.provider_schema_name or "")
    provider_tier = provider_service_tier_for_delivery_mode("standard")
    request_item_id = provider_request_identity(
        task,
        contract,
        model="gpt-5.6-luna",
        reasoning_effort="low",
        delivery_mode="standard",
        provider_service_tier=provider_tier,
        provider_schema_name=schema_name,
        schema_hash=contract.schema_hash_for_evidence(evidence_ids),
        evidence_ids=evidence_ids,
        max_output_tokens=DISCOVERY_MAX_OUTPUT_TOKENS,
    )
    user["task_profile_version"] = V12_TASK_PROFILE_VERSION
    user["prompt_policy_version"] = V12_PROMPT_POLICY
    user["schema_version"] = V12_PLANNER_SCHEMA
    user["semantic_contract"] = contract.identity_payload(evidence_ids)
    user["evidence_policy"] = contract.evidence_policy
    body["input"][0]["content"][0]["text"] = old_prompt + "\n\nV1.2 output rule: emit propositions only in the section-specific array for the selected section; leave the other section arrays empty."
    body["input"][1]["content"][0]["text"] = json.dumps(user, ensure_ascii=False, sort_keys=True)
    body["text"] = {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}}
    body["metadata"] = {
        "logical_task_id": task["logical_task_id"],
        "provider_request_item_id": request_item_id,
        "delivery_job_id": delivery_job_id,
        "claim_family_id": task["claim_family_id"],
        "semantic_contract_id": contract.contract_id,
        "semantic_contract_hash": contract.identity_hash(evidence_ids),
    }
    body.pop("service_tier", None)
    return CompiledRequest(task["logical_task_id"], request_item_id, delivery_job_id, "gpt-5.6-luna", "standard", schema_name, body)


__all__ = ["compile_v12_from_prior_row", "V12_TASK_PROFILE_VERSION", "V12_PROMPT_POLICY", "V12_PLANNER_SCHEMA"]
