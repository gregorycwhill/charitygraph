import hashlib
import json
from datetime import datetime, timezone

from charitygraph.contracts import SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.frozen_experiment import execute_prepared_standard, prepare_frozen_experiment
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
    pricing = tmp_path / "pricing.json"
    subject_manifest.write_text(json.dumps({"selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION", "subjects": [{"subject_id": subject}]}), encoding="utf-8")
    demand_manifest.write_text(json.dumps({"selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION", "instances": [{"instance_id": "instance:fixture", "subject_id": subject, "demand_id": "demand:fixture", "semantic_signature": "fixture demand"}]}), encoding="utf-8")
    corpus.write_text(json.dumps({"corpora": [{"subject_id": subject, "material_members": [{"source_family": "acnc_register", "source_record_ids": [record_id], "artifact_ids": [artifact.artifact_id]}]}]}), encoding="utf-8")
    rights.write_text(json.dumps({"decisions": [{"decision_id": "rights:fixture", "source_artifact_id": artifact.artifact_id, "source_record_id": record_id, "source_origin_url": "fixture:source", "source_role": "identity", "acquisition_lineage_ids": ["acq:fixture"], "transmitted_representation_sha256": hashlib.sha256(content).hexdigest(), "rights_policy_id": "PUBLIC_FACTS_ONLY_V1", "provider_processing_policy_id": "openai-responses-private-processing-v1", "rights_basis": "public_facts_only", "evidence_locator": "fixture:rights", "evidence_sha256": "a" * 64, "assessed_on": "2026-10-16", "assessment_scope": "private bounded analytical processing", "local_retention_allowed": False, "provider_transmission_allowed": True, "public_redistribution_allowed": False, "representation_class": "structured_factual", "publicly_accessible_without_circumvention": True, "access_controls_bypassed": False, "lawfully_acquired": True, "analytical_purpose": "semantic_analysis", "provider_no_training_default": True, "provider_data_sharing_opt_in": False, "factual_representation_only": True}]}), encoding="utf-8")
    pricing.write_text(json.dumps({"provider": "openai", "model": "gpt-5.6-luna", "requests": [{"instance_id": "instance:fixture", "hard_max_usd": "0.01", "hard_max_aud": "0.02"}]}), encoding="utf-8")
    prepared = prepare_frozen_experiment(subject_manifest=subject_manifest, demand_manifest=demand_manifest, corpus_manifest=corpus, rights_decisions=rights, pricing_snapshot=pricing, runtime_root=runtime, catalog_path=catalog_path, authorization_catalog_path=authority, authorization_text_hash="b" * 64, now=now)
    provider = _Provider()
    result = execute_prepared_standard(prepared=prepared, catalog_path=catalog_path, authorization_catalog_path=authority, runtime_root=runtime, provider=provider, now=now)
    assert result["counts"] == {"completed": 1}, result
    assert provider.posts == 1
