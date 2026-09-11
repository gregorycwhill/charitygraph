import json

import pytest

from charitygraph.phase5_direct_service_cutover import compile_v12_from_prior_row
from charitygraph.phase5_execution_mandate import proposed_phase5_standard_luna_v1_2_amendment_manifest
from charitygraph.phase5_semantic_contracts import executable_contract_for


def _prior_row():
    user = {
        "logical_task_id": "semtask:test-direct-service-v12",
        "claim_family_id": "direct-service-access-v1",
        "task_profile": "direct_service_semantics",
        "prompt_policy_version": "direct-service-access-v1:prompt-policy:v2",
        "evidence_corpus_hash": "e" * 64,
        "evidence_policy": {"mode": "frozen_packet_locators"},
        "evidence_bindings": [{"evidence_id": "locator:" + "1" * 64, "source_record_id": "srcrec:test", "content_hash": "a" * 64}],
        "semantic_contract": {"contract_version": "1.1"},
    }
    return {
        "logical_task_id": user["logical_task_id"],
        "subject_id": "subject:test",
        "provider_request_item_id": "requestitem:" + "1" * 64,
        "reservation_id": "reservation:old",
        "request_body": {
            "model": "gpt-5.6-luna",
            "input": [
                {"role": "developer", "content": [{"type": "input_text", "text": "old governed prompt"}]},
                {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user)}]},
            ],
        },
    }


def test_v12_candidate_is_provider_shapeable_but_not_executable():
    request = compile_v12_from_prior_row(_prior_row(), delivery_job_id="deliveryjob:test-v12")
    assert request.schema_name == "direct_service_semantics_v2"
    assert request.provider_request_item_id != "requestitem:" + "1" * 64
    assert "service_tier" not in request.body
    assert request.body["text"]["format"]["schema"]["properties"]["participation"]["items"]["properties"]["proposition_type"]["enum"] == ["participation_opportunity", "participation_measure"]
    with pytest.raises(PermissionError, match="not production-bound"):
        executable_contract_for({
            "logical_task_id": "semtask:test-direct-service-v12",
            "claim_family_id": "direct-service-access-v1",
            "task_profile": "direct_service_semantics",
            "task_profile_version": "2",
            "prompt_policy_version": "direct-service-access-v1:prompt-policy:v3-representation",
            "schema_version": "urn:charitygraph:phase5:planned:direct_service_semantics:v2",
            "evidence_corpus_hash": "e" * 64,
        })


def test_v12_mandate_proposal_changes_only_direct_service_allowlist():
    manifest = proposed_phase5_standard_luna_v1_2_amendment_manifest()
    direct = next(item for item in manifest["allowed_contracts"] if item["contract_id"].endswith("direct-service-v1"))
    old = manifest["direct_service_contract_transition"]["superseded_for_future_sends"]
    replacement = manifest["direct_service_contract_transition"]["replacement_candidate"]
    assert manifest["mandate_id"].endswith("amendment-3")
    assert manifest["supersedes_mandate_id"].endswith("amendment-2")
    assert direct["contract_version"] == "1.2"
    assert old["contract_version"] == "1.1"
    assert replacement["contract_version"] == "1.2"
    assert old["contract_identity_hash"] != replacement["contract_identity_hash"]
    assert next(item for item in manifest["allowed_contracts"] if item["contract_id"].endswith("program-service-discovery-v2"))["contract_version"] == "2.1"
