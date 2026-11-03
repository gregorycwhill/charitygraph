import json
from dataclasses import replace
from decimal import Decimal

import pytest

from charitygraph.phase5_openai_dry_run import RealProviderExecutionGate, parse_provider_result, provider_service_tier_for_delivery_mode, serialize_fallback, validate_provider_schema_name, validate_provider_service_tier
from charitygraph.phase5_semantic_contracts import (
    REGISTRY,
    executable_contract_for,
    provider_request_identity,
    provider_wire_fingerprint,
    resolve_contract,
    resolve_result_adapter,
    validate_relationship_output,
    validate_taxonomy_output,
)


def test_real_provider_gate_denies_by_default() -> None:
    with pytest.raises(PermissionError):
        RealProviderExecutionGate().assert_allowed(run_id="run:x", plan_hash="hash", exposure_usd=Decimal("1"))


def test_provider_result_unknown_custom_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_provider_result({"custom_id": "requestitem:unknown"}, {"requestitem:known"})


def _batch_row(*, custom_id: str = "requestitem:known", status_code: int = 200, body: dict | None = None, error=None) -> dict:
    row = {"custom_id": custom_id, "error": error}
    if error is None:
        row["response"] = {"status_code": status_code, "request_id": "req_test", "body": body}
    return row


def test_batch_responses_result_reads_nested_body_and_usage_details() -> None:
    parsed = parse_provider_result(_batch_row(body={
        "id": "resp_test",
        "status": "completed",
        "service_tier": "default",
        "usage": {"input_tokens": 69725, "output_tokens": 1329, "input_tokens_details": {"cached_tokens": 7}, "output_tokens_details": {"reasoning_tokens": 119}},
    }), {"requestitem:known"})
    assert parsed["status"] == "completed"
    assert parsed["batch_item_status"] == "completed"
    assert parsed["http_status"] == 200
    assert parsed["provider_request_id"] == "req_test"
    assert parsed["provider_response_id"] == "resp_test"
    assert parsed["responses_status"] == "completed"
    assert parsed["usage"]["input_tokens_details"]["cached_tokens"] == 7
    assert parsed["usage"]["output_tokens_details"]["reasoning_tokens"] == 119


def test_batch_request_level_http_error_is_definite_failure() -> None:
    parsed = parse_provider_result(_batch_row(status_code=400, body={"error": {"message": "invalid request"}}), {"requestitem:known"})
    assert parsed["status"] == "failed"
    assert parsed["batch_item_status"] == "failed"
    assert parsed["http_status"] == 400
    assert parsed["responses_status"] is None
    assert parsed["error"]["message"] == "invalid request"


def test_batch_top_level_error_is_definite_failure() -> None:
    parsed = parse_provider_result(_batch_row(error={"code": "batch_error", "message": "item rejected"}), {"requestitem:known"})
    assert parsed["status"] == "failed"
    assert parsed["http_status"] is None
    assert parsed["error"]["code"] == "batch_error"


@pytest.mark.parametrize("row", [
    _batch_row(body=None),
    _batch_row(body={"id": "resp_test", "status": "in_progress"}),
])
def test_malformed_or_nonterminal_batch_response_fails_closed(row: dict) -> None:
    if row["response"]["body"] is None:
        with pytest.raises(ValueError, match="Responses body"):
            parse_provider_result(row, {"requestitem:known"})
    else:
        assert parse_provider_result(row, {"requestitem:known"})["responses_status"] == "in_progress"
        assert parse_provider_result(row, {"requestitem:known"})["status"] == "failed"


def test_flex_fallback_uses_responses_service_tier() -> None:
    request = type("Request", (), {"provider_request_item_id": "requestitem:one", "body": {"model": "gpt-5.6-luna"}})()
    assert serialize_fallback(request, "flex")["body"]["service_tier"] == "flex"


def test_delivery_mode_mapping_is_orthogonal_to_provider_service_tier() -> None:
    assert provider_service_tier_for_delivery_mode("batch") is None
    assert provider_service_tier_for_delivery_mode("standard") is None
    assert provider_service_tier_for_delivery_mode("flex") == "flex"
    with pytest.raises(ValueError, match="unsupported internal delivery mode"):
        provider_service_tier_for_delivery_mode("batchish")
    with pytest.raises(ValueError, match="unsupported Responses service_tier"):
        validate_provider_service_tier("batch")


def test_provider_schema_name_validator_matches_openai_pattern_without_provider_calls() -> None:
    for name in ("letters", "v2_0", "program-service_discovery2"):
        assert validate_provider_schema_name(name) == name
    for name in ("2.0", "with space", "slash/name", ""):
        with pytest.raises(ValueError, match="provider structured-output schema name"):
            validate_provider_schema_name(name)


def test_semantic_contract_identity_does_not_use_provider_alias() -> None:
    contract = next(c for c in REGISTRY if c.task_profile == "program_service_discovery")
    assert contract.provider_schema_name == "program_service_discovery_v2"
    assert contract.schema_id == "urn:charitygraph:builder:schema:program-service-discovery-output:2.1"
    assert contract.identity_hash() == replace(contract, provider_schema_name="another_safe_alias").identity_hash()


def test_provider_wire_identity_is_stable_and_tracks_provider_significant_material() -> None:
    contract = next(c for c in REGISTRY if c.task_profile == "program_service_discovery")
    task = _task("program_service_discovery", "program-service-discovery-v2")
    kwargs = dict(model="gpt-5.6-luna", reasoning_effort="low", delivery_mode="batch", provider_service_tier=None, provider_schema_name="program_service_discovery_v2", schema_hash="a" * 64, max_output_tokens=8000)
    first = provider_wire_fingerprint(task, contract, **kwargs)
    assert first == provider_wire_fingerprint(task, contract, **kwargs)
    assert first != provider_wire_fingerprint(task, contract, **{**kwargs, "provider_schema_name": "2.0"})
    assert first != provider_wire_fingerprint(task, contract, **{**kwargs, "max_output_tokens": 4000})
    assert first != provider_wire_fingerprint(task, contract, **{**kwargs, "schema_hash": "b" * 64})
    assert first != provider_wire_fingerprint(task, contract, **{**kwargs, "provider_service_tier": "flex"})
    changed_prompt = replace(contract, prompt_template=contract.prompt_template + "\nchanged")
    assert first != provider_wire_fingerprint(task, changed_prompt, **kwargs)
    request_id = provider_request_identity(task, contract, evidence_ids=(), **kwargs)
    assert request_id == "requestitem:" + first


def _task(profile: str, family: str, version: str = "1") -> dict:
    contract = next(contract for contract in REGISTRY if contract.task_profile == profile and contract.task_profile_version == version)
    return {"logical_task_id": "semtask:test", "task_profile": profile, "task_profile_version": version, "claim_family_id": family, "prompt_policy_version": contract.planner_prompt_policy_version, "schema_version": contract.planner_schema_version, "evidence_corpus_hash": "e" * 64}


def test_registry_covers_all_active_families_and_only_two_are_production_bound() -> None:
    assert len(REGISTRY) == 14
    assert sum(contract.executable for contract in REGISTRY) == 2
    assert {contract.task_profile for contract in REGISTRY if contract.executable} == {"program_service_discovery", "direct_service_semantics"}
    direct = [contract for contract in REGISTRY if contract.task_profile == "direct_service_semantics"]
    assert {contract.task_profile_version for contract in direct} == {"1", "2"}
    assert next(contract for contract in direct if contract.task_profile_version == "2").authority_state == "candidate_for_review"


def test_taxonomy_and_relationship_contracts_are_materially_different() -> None:
    taxonomy = next(contract for contract in REGISTRY if contract.task_profile == "taxonomy_assignment")
    relationship = next(contract for contract in REGISTRY if contract.task_profile == "relationship_role_extraction")
    assert taxonomy.output_schema != relationship.output_schema
    assert taxonomy.prompt_sha256 != relationship.prompt_sha256


def test_drafts_cannot_serialize_for_provider_execution() -> None:
    with pytest.raises(PermissionError):
        executable_contract_for(_task("taxonomy_assignment", "taxonomy-assignment-v1"))


def test_production_contract_adapters_resolve_to_actual_code() -> None:
    discovery = executable_contract_for(_task("program_service_discovery", "program-service-discovery-v2"))
    direct = executable_contract_for(_task("direct_service_semantics", "direct-service-access-v1"))
    assert resolve_result_adapter(discovery).__name__ == "_parse_discovery_output"
    assert resolve_result_adapter(direct).__name__ == "wire_to_domain"


def test_draft_adapter_is_not_accidentally_resolved() -> None:
    draft = resolve_contract(_task("taxonomy_assignment", "taxonomy-assignment-v1"))
    with pytest.raises(LookupError):
        resolve_result_adapter(draft)


def test_missing_prompt_schema_and_adapter_fail_closed() -> None:
    contract = next(contract for contract in REGISTRY if contract.task_profile == "taxonomy_assignment")
    with pytest.raises(ValueError):
        replace(contract, prompt_template="").assert_complete()
    with pytest.raises(ValueError):
        replace(contract, output_schema=None, schema_factory=None).assert_complete()
    with pytest.raises(ValueError):
        replace(contract, adapter_id="", adapter_version="").assert_complete()


def test_contract_hash_changes_with_prompt_or_schema() -> None:
    contract = next(contract for contract in REGISTRY if contract.task_profile == "taxonomy_assignment")
    assert replace(contract, prompt_template=contract.prompt_template + "\nextra").identity_hash() != contract.identity_hash()
    changed_schema = dict(contract.output_schema or {})
    changed_schema["description"] = "changed"
    assert replace(contract, output_schema=changed_schema).identity_hash() != contract.identity_hash()


def test_contract_aware_request_identity_changes_when_contract_changes() -> None:
    task = _task("direct_service_semantics", "direct-service-access-v1")
    contract = resolve_contract(task)
    changed = replace(contract, prompt_template=contract.prompt_template + "\nchanged")
    assert provider_request_identity(task, contract, model="gpt-5.6-luna", delivery_mode="standard") != provider_request_identity(task, changed, model="gpt-5.6-luna", delivery_mode="standard")


def test_taxonomy_concept_and_evidence_boundaries_are_enforced() -> None:
    with pytest.raises(ValueError):
        validate_taxonomy_output({"selections": [{"concept_id": "concept:invented", "evidence_refs": ["e1"]}]}, allowed_concept_ids={"concept:allowed"}, allowed_evidence_ids={"e1"})
    with pytest.raises(ValueError):
        validate_taxonomy_output({"selections": [{"concept_id": "concept:allowed", "evidence_refs": ["e2"]}]}, allowed_concept_ids={"concept:allowed"}, allowed_evidence_ids={"e1"})


def test_relationship_endpoints_and_evidence_are_bound_or_explicitly_unresolved() -> None:
    with pytest.raises(ValueError):
        validate_relationship_output({"relationships": [{"source_scope_id": "scope:one", "target_scope_id": "scope:invented", "evidence_refs": ["e1"], "unresolved_endpoint": False}]}, allowed_scope_ids={"scope:one", "scope:two"}, allowed_evidence_ids={"e1"})
    validate_relationship_output({"relationships": [{"source_scope_id": "scope:one", "target_scope_id": "scope:invented", "evidence_refs": ["e1"], "unresolved_endpoint": True}]}, allowed_scope_ids={"scope:one", "scope:two"}, allowed_evidence_ids={"e1"})
