from datetime import datetime, timezone

from charitygraph.contracts import (
    ArtifactRef,
    DirectServiceEvidenceRef,
    DirectServiceProposition,
    EvidenceLocator,
    ScopeRecord,
    SubjectRecord,
    project_observation,
)
from charitygraph.runtime import SQLiteCatalog


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)
SUBJECT = "subject:" + "1" * 32
SOURCE = "srcrec:" + "2" * 32


def _subject() -> SubjectRecord:
    return SubjectRecord(
        record_id="subjectrecord:" + "1" * 32,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        subject_id=SUBJECT,
        subject_kind="organisation",
        lifecycle_status="active",
        identity_authority_refs=(ArtifactRef(
            artifact_id="srcrec:" + "9" * 32,
            content_hash="a" * 64,
            schema={"schema_id": "urn:charitygraph:builder:schema:source-record:1.0", "schema_version": "1.0"},
        ),),
        identity_policy_id="fixture-v1",
        display_name="Direct-service fixture",
    )


def test_direct_service_projection_preserves_scope_evidence_and_missingness(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "direct-service.sqlite3").open(initialize=True)
    catalog.register_subject(_subject())
    scope = ScopeRecord(
        record_id="scope:" + "3" * 32,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        subject_id=SUBJECT,
        scope_kind="service",
        label="Crisis support service",
    )
    catalog.register_scope(scope)
    locator = catalog.register_evidence_locator(
        EvidenceLocator(kind="document", source_record_id=SOURCE, page=1)
    )["evidence_locator_id"]
    proposition = DirectServiceProposition(
        proposition_type="current_availability",
        scope_kind="service",
        scope_label="Crisis support service",
        coverage_state="source_silent",
        evidence=(),
    )
    # A source-silent state is explicit and remains distinct in the value
    # even though the legacy outcome-state column stores it as unknown.
    projected = project_observation(
        proposition.model_copy(update={"evidence": (DirectServiceEvidenceRef(locator=locator, role="context"),)}),
        record_id="observation:" + "4" * 32,
        subject_id=SUBJECT,
        scope_id=scope.record_id,
        source_record_ids=(SOURCE,),
        created_at=NOW,
        producer={"kind": "code", "producer_id": "direct-service-fixture"},
    )
    catalog.record_observation(projected)
    assert catalog.record_observation(projected)["observation_id"] == projected.record_id
    row = catalog.reconstruct_knowledge_history(SUBJECT)["observations"][0]
    assert row["scope_id"] == scope.record_id
    assert row["value"]["coverage_state"] == "source_silent"
    assert row["evidence_locator_ids"] == [locator]
    assert catalog.integrity_check() == "ok"
    catalog.close()
