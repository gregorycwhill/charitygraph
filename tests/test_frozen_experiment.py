import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

from charitygraph.contracts import SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.baseline_corpus import AcquisitionState, BindingState, CorpusMember, DiscoveryState, MaterialOrigin, build_corpus_manifest, compile_provider_evidence_corpus
from charitygraph.evidence_store import ContentAddressedArtifactStore
import pytest

from charitygraph.frozen_experiment import demand_propositions, demand_requirements, execute_prepared_standard, prepare_frozen_experiment, validate_evidence_selection
from charitygraph.phase5_semantic_contracts import executable_contract_for
from charitygraph.phase5_standard_transport import StandardProviderResponse
from charitygraph.runtime import SQLiteCatalog


class _Provider:
    def __init__(self):
        self.posts = 0

    def create_response_once(self, body, *, client_request_id, request_started_at=None):
        self.posts += 1
        result = {"id": "resp_fixture", "status": "completed", "incomplete_details": None, "usage": {"input_tokens": 2, "output_tokens": 1}}
        raw = json.dumps(result, separators=(",", ":")).encode()
        return StandardProviderResponse(200, "req_fixture", result, raw, client_request_id, "req_fixture", "fixture", request_started_at, True)


def _requirement_support(signature, *, state="unresolved"):
    return [
        {"requirement_id": item["requirement_id"], "support_state": state, "evidence_ids": ["evidence:one"], "qualification": "fixture requirement assessment"}
        for item in demand_requirements(signature)
    ]


def _signature(propositions):
    return json.dumps({
        "propositions": propositions,
        "subjects": ["fixture subject"],
        "joins": ["fixture relation"],
        "operations": ["screen"],
        "forbidden": ["fixture non-inference"],
        "evidence": "fixture evidence standard",
        "intent": "fixture intent",
        "temporal": "fixture temporal obligation",
    })


def test_evidence_selection_schema_binds_all_evidence_reference_fields_and_requires_scope_accounting():
    contract = executable_contract_for({"task_profile": "evidence_selection", "task_profile_version": "2", "claim_family_id": "evidence-selection-v1", "prompt_policy_version": "evidence-selection-v1:prompt-policy:v4-demand-integrity", "schema_version": "urn:charitygraph:frozen-experiment:evidence-selection:v4"})
    signature = _signature(["claim-a", "claim-b"])
    proposition_ids = tuple(item["proposition_id"] for item in demand_propositions(signature))
    schema = contract.schema_for_packet(("evidence:one", "evidence:two"), proposition_ids)
    rendered = json.dumps(schema)
    assert "evidence:one" in rendered and "evidence:two" in rendered and all(item in rendered for item in proposition_ids)
    output = {"selected_evidence_ids": ["evidence:one"], "rejected_evidence_ids": ["evidence:two"], "demand_requirement_support": _requirement_support(signature), "proposition_support": [{"proposition_id": proposition_ids[0], "support_state": "supported", "evidence_ids": ["evidence:one"], "scope_status": "subject", "temporal_status": "satisfied", "scope_basis": "not_applicable"}, {"proposition_id": proposition_ids[1], "support_state": "unresolved", "evidence_ids": ["evidence:two"], "scope_status": "unresolved", "temporal_status": "unresolved", "scope_basis": "unresolved", "qualification": "packet does not establish the required scope"}], "conclusion": {"outcome": "insufficient_evidence", "evidence": [{"evidence_id": "evidence:one", "role": "supporting"}]}}
    parsed = validate_evidence_selection(output, allowed_evidence_ids={"evidence:one", "evidence:two"}, demand_signature=signature)
    assert parsed.proposition_support[1].proposition_id == proposition_ids[1]
    output["conclusion"]["evidence"][0]["evidence_id"] = "evidence:other"
    with pytest.raises(ValueError, match="outside its packet"):
        validate_evidence_selection(output, allowed_evidence_ids={"evidence:one", "evidence:two"}, demand_signature=signature)


def test_packet_proposition_identities_fail_closed_for_generic_noncanonical_patterns():
    signature = _signature(["one frozen proposition", "another frozen proposition"])
    ids = [item["proposition_id"] for item in demand_propositions(signature)]
    valid = {
        "selected_evidence_ids": ["evidence:one"],
        "rejected_evidence_ids": [],
        "demand_requirement_support": _requirement_support(signature),
        "proposition_support": [
            {"proposition_id": ids[0], "support_state": "supported", "evidence_ids": ["evidence:one"], "scope_status": "subject", "temporal_status": "satisfied", "scope_basis": "not_applicable"},
            {"proposition_id": ids[1], "support_state": "not_established", "evidence_ids": [], "scope_status": "unresolved", "temporal_status": "unresolved", "scope_basis": "unresolved", "qualification": "not shown in the packet"},
        ],
        "conclusion": {"outcome": "insufficient_evidence", "evidence": [{"evidence_id": "evidence:one", "role": "supporting"}]},
    }
    # These cover label paraphrase, raw demand text, case/punctuation drift,
    # a foreign identifier, duplicate coverage, omission, and substitution.
    mutations = (
        lambda value: value["proposition_support"][0].update({"proposition_id": "proposition:paraphrased"}),
        lambda value: value["proposition_support"][0].update({"proposition_id": "one frozen proposition"}),
        lambda value: value["proposition_support"][0].update({"proposition_id": ids[0].upper()}),
        lambda value: value["proposition_support"][0].update({"proposition_id": ids[0] + " "}),
        lambda value: value["proposition_support"][0].update({"proposition_id": "proposition:" + "0" * 64}),
        lambda value: value["proposition_support"].__setitem__(1, {**value["proposition_support"][1], "proposition_id": ids[0]}),
        lambda value: value["proposition_support"].pop(),
        lambda value: value["proposition_support"].reverse(),
    )
    for mutate in mutations[:-1]:
        candidate = deepcopy(valid)
        mutate(candidate)
        with pytest.raises(ValueError):
            validate_evidence_selection(candidate, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)
    # Reordering itself is harmless: exact identity coverage, not response order,
    # is the contract.
    reordered = deepcopy(valid)
    mutations[-1](reordered)
    assert validate_evidence_selection(reordered, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)


def test_typed_demand_requirements_fail_closed_before_a_strong_conclusion():
    signature = _signature(["past-record proposition", "future-decision proposition"])
    proposition_ids = [item["proposition_id"] for item in demand_propositions(signature)]
    requirements = _requirement_support(signature, state="supported")
    output = {
        "selected_evidence_ids": ["evidence:one"], "rejected_evidence_ids": [],
        "demand_requirement_support": requirements,
        "proposition_support": [
            {"proposition_id": item, "support_state": "supported", "evidence_ids": ["evidence:one"], "scope_status": "subject", "temporal_status": "satisfied", "scope_basis": "not_applicable"}
            for item in proposition_ids
        ],
        "conclusion": {"outcome": "supported", "rationale": "fixture", "evidence": [{"evidence_id": "evidence:one", "role": "supporting"}]},
    }
    assert validate_evidence_selection(output, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)
    # The structural counterexample represents a missing demanded relation,
    # scope, time, evidence-standard, or non-inference obligation.  The
    # validator does not infer English; it fail-closes on the exact frozen ID.
    missing = deepcopy(output)
    missing["demand_requirement_support"][0]["support_state"] = "unresolved"
    missing["demand_requirement_support"][0]["qualification"] = "not established by this packet"
    with pytest.raises(ValueError, match="unresolved frozen demand requirements"):
        validate_evidence_selection(missing, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)
    substituted = deepcopy(output)
    substituted["demand_requirement_support"][0]["requirement_id"] = "requirement:" + "0" * 64
    with pytest.raises(ValueError, match="every frozen demand requirement"):
        validate_evidence_selection(substituted, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)


def test_partial_support_and_service_scope_boundaries_remain_explicit():
    signature = _signature(["service cohort proposition", "time proposition"])
    ids = [item["proposition_id"] for item in demand_propositions(signature)]
    partial = {
        "selected_evidence_ids": ["evidence:one"], "rejected_evidence_ids": [],
        "demand_requirement_support": _requirement_support(signature),
        "proposition_support": [
            {"proposition_id": ids[0], "support_state": "unresolved", "evidence_ids": ["evidence:one"], "scope_status": "unresolved", "temporal_status": "satisfied", "scope_basis": "program_location", "qualification": "program location does not establish eligible service cohort"},
            {"proposition_id": ids[1], "support_state": "supported", "evidence_ids": ["evidence:one"], "scope_status": "subject", "temporal_status": "satisfied", "scope_basis": "not_applicable"},
        ],
        "conclusion": {"outcome": "insufficient_evidence", "evidence": [{"evidence_id": "evidence:one", "role": "supporting"}]},
    }
    assert validate_evidence_selection(partial, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)
    positive = deepcopy(partial)
    positive["conclusion"]["outcome"] = "supported"
    positive["conclusion"]["rationale"] = "one proposition is asserted as supported"
    with pytest.raises(ValueError, match="unresolved material proposition scope"):
        validate_evidence_selection(positive, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)
    weak_positive = deepcopy(partial)
    weak_positive["proposition_support"][0].update({"support_state": "supported", "scope_status": "subject", "scope_basis": "beneficiary_category"})
    with pytest.raises(ValueError, match="cannot alone establish"):
        validate_evidence_selection(weak_positive, allowed_evidence_ids={"evidence:one"}, demand_signature=signature)


def test_prepare_and_provider_free_standard_rehearsal_uses_durable_lifecycle(tmp_path):
    now = datetime(2026, 10, 16, tzinfo=timezone.utc)
    runtime, catalog_path = tmp_path / "runtime", tmp_path / "catalog.sqlite3"
    content = b'{"governed":"fixture evidence"}'
    artifact = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,)).put(content)
    record_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": "1", "source_locator": "fixture:source", "payload_hash": hashlib.sha256(content).hexdigest()})
    authority = tmp_path / "authority.sqlite3"
    catalog = SQLiteCatalog(catalog_path, authorization_path=authority).open(initialize=True)
    catalog.register_source_record(SourceRecord(record_id=record_id, created_at=now, producer={"kind": "code", "producer_id": "test", "version": "1"}, source_family="acnc_register", source_role="identity", source_version="1", source_locator="fixture:source", observed_at=now, payload_ref=artifact.artifact_id, payload_hash=hashlib.sha256(content).hexdigest()))
    catalog.close()
    subject = "subject:fixture"
    subject_manifest = tmp_path / "subjects.json"
    demand_manifest = tmp_path / "demands.json"
    corpus = tmp_path / "corpus.json"
    rights = tmp_path / "rights.json"
    pricing = runtime / "frozen-pricing-snapshot.json"
    subject_manifest.write_text(json.dumps({"selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION", "subjects": [{"subject_id": subject}]}), encoding="utf-8")
    demand_manifest.write_text(json.dumps({"selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION", "instances": [{"instance_id": "instance:fixture", "subject_id": subject, "demand_id": "demand:fixture", "semantic_signature": _signature(["fixture proposition"])}]}), encoding="utf-8")
    governed = compile_provider_evidence_corpus([build_corpus_manifest(
        subject_id=subject, profile_version="baseline-v1", members=[CorpusMember(
            source_family="acnc_register", source_definition_id="srcdef:fixture",
            acquisition_receipt_ids=("acq:fixture",), artifact_ids=(artifact.artifact_id,),
            source_record_ids=(record_id,), discovery=DiscoveryState.RESOLVED,
            acquisition=AcquisitionState.AVAILABLE, subject_binding=BindingState.BOUND,
            material_origin=MaterialOrigin.REUSED_EXISTING,
        )],
    )])
    corpus.write_text(json.dumps(governed), encoding="utf-8")
    rights.write_text(json.dumps({"decisions": [{"decision_id": "rights:fixture", "source_artifact_id": artifact.artifact_id, "source_record_id": record_id, "source_origin_url": "fixture:source", "source_role": "identity", "acquisition_lineage_ids": ["acq:fixture"], "transmitted_representation_sha256": hashlib.sha256(content).hexdigest(), "rights_policy_id": "PUBLIC_FACTS_ONLY_V1", "provider_processing_policy_id": "openai-responses-private-processing-v1", "rights_basis": "public_facts_only", "evidence_locator": "fixture:rights", "evidence_sha256": "a" * 64, "assessed_on": "2026-10-16", "assessment_scope": "private bounded analytical processing", "local_retention_allowed": False, "provider_transmission_allowed": True, "public_redistribution_allowed": False, "representation_class": "structured_factual", "publicly_accessible_without_circumvention": True, "access_controls_bypassed": False, "lawfully_acquired": True, "analytical_purpose": "semantic_analysis", "provider_no_training_default": True, "provider_data_sharing_opt_in": False, "factual_representation_only": True}]}), encoding="utf-8")
    pricing.write_text(json.dumps({"provider": "openai", "model": "gpt-5.6-luna", "snapshot_id": "fixture-pricing-v1", "aud_per_usd": "1.52", "provider_rates_usd_per_million_tokens": {"input": "0.20", "cached_input": "0.02", "cache_write_input": "0.25", "output": "1.20"}, "requests": [{"instance_id": "instance:fixture", "hard_max_usd": "0.01", "hard_max_aud": "0.02"}]}), encoding="utf-8")
    prepared = prepare_frozen_experiment(subject_manifest=subject_manifest, demand_manifest=demand_manifest, corpus_manifest=corpus, rights_decisions=rights, pricing_snapshot=pricing, runtime_root=runtime, catalog_path=catalog_path, authorization_catalog_path=authority, authorization_text_hash="b" * 64, provider_account_project="proj_fixture", now=now)
    provider = _Provider()
    provider.provider_account_project = "proj_fixture"
    result = execute_prepared_standard(prepared=prepared, catalog_path=catalog_path, authorization_catalog_path=authority, runtime_root=runtime, provider=provider, now=now)
    assert result["counts"] == {"completed": 1}, result
    assert provider.posts == 1
    assert prepared["provider_account_project"] == "proj_fixture"
    assert prepared["rows"][0]["provider_account_project"] == "proj_fixture"
    assert prepared["rows"][0]["request_body_sha256"] == hashlib.sha256(json.dumps(prepared["rows"][0]["request_body"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    catalog = SQLiteCatalog(catalog_path, authorization_path=authority).open()
    try:
        assert catalog.get_cost_entry("actual:frozen:" + prepared["rows"][0]["provider_request_item_id"]) is not None
        assert catalog.get_cost_entry("release:frozen:" + prepared["rows"][0]["provider_request_item_id"]) is not None
    finally:
        catalog.close()
