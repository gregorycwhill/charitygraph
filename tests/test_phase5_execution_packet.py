import hashlib
import json
import sqlite3

import pytest

from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.phase5_execution_packet import ExecutionPacketUnready, materialize_execution_packet, render_packet_prompt
from charitygraph.phase5_openai_dry_run import serialize_execution_packet_request
from charitygraph.phase5_semantic_contracts import executable_contract_for


def _task(contract):
    return {
        "logical_task_id": "semtask:packet-test",
        "subject_id": "subject:packet-test",
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "claim_family_id": contract.claim_families[0],
        "prompt_policy_version": contract.planner_prompt_policy_version,
        "schema_version": contract.planner_schema_version,
        "evidence_corpus_hash": "a" * 64,
        "difficulty": "lower_cost_constrained_semantic",
    }


def _catalog(path, record_id, payload_hash):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE source_records (
            source_record_id TEXT PRIMARY KEY, source_family TEXT, source_role TEXT,
            source_locator TEXT, payload_ref TEXT, payload_hash TEXT
        );
        CREATE TABLE subject_scopes (
            scope_id TEXT, subject_id TEXT, scope_kind TEXT, label TEXT,
            lifecycle_status TEXT
        );
        CREATE TABLE evidence_locators (
            evidence_locator_id TEXT PRIMARY KEY, artifact_id TEXT, source_record_id TEXT,
            kind TEXT, locator_json TEXT, material_hash TEXT
        );
        """
    )
    conn.execute("INSERT INTO source_records VALUES (?, ?, ?, ?, ?, ?)", (record_id, "test", "test", "https://example.test", "", payload_hash))
    conn.execute("INSERT INTO evidence_locators VALUES (?, ?, ?, ?, ?, ?)", ("locator:test", None, record_id, "document", "{}", "selection-hash"))
    conn.commit()
    conn.close()


def test_packet_materializes_bytes_and_prompt_from_content_addressed_store(tmp_path):
    runtime = tmp_path / "runtime"
    store = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,))
    content = b'{"governed":"evidence"}'
    stored = store.put(content)
    record_id = "srcrec:test"
    catalog = tmp_path / "catalog.sqlite3"
    _catalog(catalog, record_id, hashlib.sha256(content).hexdigest())
    contract = executable_contract_for({
        "task_profile": "program_service_discovery", "task_profile_version": "1",
        "claim_family_id": "program-service-discovery-v2",
        "prompt_policy_version": "program-service-discovery-v2:prompt-policy:v1",
        "schema_version": "urn:charitygraph:phase5:planned:program_service_discovery:v1",
    })
    task = _task(contract)
    corpus = {"subject_id": task["subject_id"], "material_members": [{"source_family": "test", "source_record_ids": [record_id], "artifact_ids": [stored.artifact_id], "evidence_locator_ids": ["locator:test"]}]}
    packet = materialize_execution_packet(task=task, corpus=corpus, contract=contract, runtime_root=runtime, catalog_path=catalog, model="gpt-5.6-luna", reasoning_effort="low", service_tier="default")
    assert packet.evidence_units[0].content == content.decode()
    assert json.dumps(corpus) not in packet.evidence_units[0].content
    assert content.decode() in render_packet_prompt(packet, contract)
    request = serialize_execution_packet_request(task, packet, delivery_job_id="deliveryjob:test", delivery_mode="batch")
    developer_text = request.body["input"][0]["content"][0]["text"]
    user_text = request.body["input"][1]["content"][0]["text"]
    assert content.decode() in developer_text
    assert content.decode() not in user_text
    assert "evidence_units" not in user_text
    assert "evidence_bindings" in user_text
    assert request.body["max_output_tokens"] == 8000
    assert request.schema_name == "program_service_discovery_v2"
    assert request.body["text"]["format"]["name"] == "program_service_discovery_v2"
    assert "service_tier" not in request.body
    assert request.provider_request_item_id == "requestitem:58d1288cd8c75b75234ae3c893b146f7c4fb8b97cbbbcadf537073f34ed402e4"
    flex = serialize_execution_packet_request(task, packet, delivery_job_id="deliveryjob:test", delivery_mode="flex")
    assert flex.body["service_tier"] == "flex"
    assert flex.provider_request_item_id != request.provider_request_item_id


def test_packet_fails_closed_for_missing_retained_artifact(tmp_path):
    runtime = tmp_path / "runtime"
    catalog = tmp_path / "catalog.sqlite3"
    record_id = "srcrec:missing"
    _catalog(catalog, record_id, "b" * 64)
    contract = executable_contract_for({
        "task_profile": "program_service_discovery", "task_profile_version": "1",
        "claim_family_id": "program-service-discovery-v2",
        "prompt_policy_version": "program-service-discovery-v2:prompt-policy:v1",
        "schema_version": "urn:charitygraph:phase5:planned:program_service_discovery:v1",
    })
    task = _task(contract)
    corpus = {"subject_id": task["subject_id"], "material_members": [{"source_family": "test", "source_record_ids": [record_id], "artifact_ids": ["srcblob:" + "c" * 64], "evidence_locator_ids": ["locator:test"]}]}
    with pytest.raises(ExecutionPacketUnready, match="hash-verified"):
        materialize_execution_packet(task=task, corpus=corpus, contract=contract, runtime_root=runtime, catalog_path=catalog, model="gpt-5.6-luna", reasoning_effort="low", service_tier="default")


def test_direct_service_packet_requires_governed_scopes_before_serialization(tmp_path):
    contract = executable_contract_for({
        "task_profile": "direct_service_semantics", "task_profile_version": "1",
        "claim_family_id": "direct-service-access-v1",
        "prompt_policy_version": "direct-service-access-v1:prompt-policy:v2",
        "schema_version": "urn:charitygraph:phase5:planned:direct_service_semantics:v1",
    })
    task = _task(contract)
    catalog = tmp_path / "catalog.sqlite3"
    _catalog(catalog, "srcrec:direct", "d" * 64)
    corpus = {"subject_id": task["subject_id"], "material_members": [{"source_family": "test", "source_record_ids": ["srcrec:direct"], "artifact_ids": ["srcblob:" + "d" * 64], "evidence_locator_ids": []}]}
    with pytest.raises(ExecutionPacketUnready, match="governed active scopes"):
        materialize_execution_packet(task=task, corpus=corpus, contract=contract, runtime_root=tmp_path / "runtime", catalog_path=catalog, model="gpt-5.6-terra", reasoning_effort="low", service_tier="default")
