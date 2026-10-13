"""Provider-free, exact-ACNC identity binding for a frozen benchmark.

Display labels and ABNs are lookup inputs only.  A binding exists only after
the exact ABN resolves to one ACNC entity and its immutable response is stored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from charitygraph.contracts import AcquisitionReceipt, ArtifactRef, ExternalIdentifier, SchemaRef, SourceRecord, SubjectRecord
from charitygraph.contracts.ids import deterministic_id, new_opaque_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.identity_bootstrap import POLICY, SOURCE_VERSION, _source_definition, _source_record_hash, fetch_register_record
from charitygraph.runtime import SQLiteCatalog


def bootstrap_benchmark_subjects(*, catalog_path: Path, runtime_root: Path, bindings: Iterable[dict[str, str]]) -> list[dict[str, Any]]:
    """Create/reuse opaque subjects from exact ACNC evidence for benchmark keys."""
    rows = list(bindings)
    if not rows or any(set(("binding_key", "abn", "label")) - set(row) for row in rows):
        raise ValueError("each benchmark binding needs binding_key, abn and label")
    if len({row["binding_key"] for row in rows}) != len(rows) or len({row["abn"] for row in rows}) != len(rows):
        raise ValueError("benchmark binding keys and ABNs must be unique")
    catalog = SQLiteCatalog(catalog_path).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,), catalog=catalog)
    definition = _source_definition()
    if catalog.get_source_definition(definition.record_id) is None:
        catalog.register_source_definition(definition)
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    try:
        for row in rows:
            abn = row["abn"]
            locator, body, registered_name = fetch_register_record(abn)
            artifact = store.put(body, created_at=now)
            source_id = deterministic_id("srcrec:", {"source_family":"acnc_register", "source_version":SOURCE_VERSION, "source_locator":locator, "payload_hash":artifact.content_hash})
            record = SourceRecord(record_id=source_id, created_at=now, producer={"kind":"code", "producer_id":"benchmark-identity-bootstrap", "version":"1"}, source_family="acnc_register", source_role="register_identity", source_version=SOURCE_VERSION, source_locator=locator, retrieved_at=now, observed_at=now, media_type="application/json", payload_ref=artifact.artifact_id, payload_hash=artifact.content_hash, attribution="Australian Charities and Not-for-profits Commission")
            catalog.register_source_record(record)
            catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=deterministic_id("acq:", {"source_definition_id":definition.record_id, "artifact_id":artifact.artifact_id, "locator":locator}), created_at=now, producer={"kind":"code", "producer_id":"benchmark-identity-bootstrap", "version":"1"}, source_definition_id=definition.record_id, requested_locator=locator, resolved_locator=locator, retrieved_at=now, outcome="available", response_status=200, media_type="application/json", content_hash=artifact.content_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib", material_parameters={"identity_policy_id":POLICY, "lookup_abn":abn}))
            subject_id = new_opaque_id("subject:")
            subject = SubjectRecord(record_id=new_opaque_id("subjectrecord:"), created_at=now, producer={"kind":"code", "producer_id":"benchmark-identity-bootstrap", "version":"1"}, subject_id=subject_id, subject_kind="unknown", lifecycle_status="active", display_name=registered_name, external_identifiers=(ExternalIdentifier(scheme="ABN", value=abn, issuing_authority="Australian Business Register", source_record_ids=(source_id,)),), identity_authority_refs=(ArtifactRef(artifact_id=source_id, content_hash=_source_record_hash(catalog, source_id), schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),), identity_policy_id=POLICY)
            catalog.register_subject(subject)
            result.append({"binding_key":row["binding_key"], "label":row["label"], "lookup_abn":abn, "subject_id":subject_id, "registered_name":registered_name, "identity_source_record_id":source_id, "identity_source_sha256":artifact.content_hash, "resolved_locator":locator, "identity_policy_id":POLICY})
        return result
    finally:
        catalog.close()
