from datetime import date, datetime, timezone

import pytest

from charitygraph.contracts import (
    ArtifactRef, EvidenceInput, EvidenceLocator, LineageEdge, ProgramCandidateOutput,
    SchemaRef, SemanticConclusion, SemanticEvidence, SourceRecord, SubjectRecord,
    TaxonomyAssignmentOutput, TaxonomyScheme, TaxonomyConcept, TaxonomyVersion,
    TaxonomySelection,
)
from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase1 import Phase1PreRunEngine, exact_identifier_join, seed_phase1_taxonomies, validate_abn
from charitygraph.runtime import ConflictError, SQLiteCatalog


NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
SUBJECT = "subject:" + "1" * 32
AUTHORITY = ArtifactRef(
    artifact_id="decision:" + "a" * 32,
    content_hash="b" * 64,
    schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:test:1.0", schema_version="1.0"),
)


def make_subject(subject_id=SUBJECT):
    return SubjectRecord(
        record_id="subjectrecord:" + subject_id[-32:],
        created_at=NOW,
        producer={"kind": "human", "producer_id": "fixture"},
        subject_id=subject_id,
        subject_kind="organisation",
        lifecycle_status="active",
        identity_authority_refs=(AUTHORITY,),
        identity_policy_id="exact-v1",
        display_name="Synthetic Organisation",
    )


def open_catalog(tmp_path):
    return SQLiteCatalog(tmp_path / "phase1.sqlite3").open(initialize=True)


def source_record():
    payload_hash = "c" * 64
    record_id = deterministic_id("srcrec:", {
        "source_family": "synthetic-register",
        "source_version": "1",
        "source_locator": "https://example.test/register/1",
        "payload_hash": payload_hash,
    })
    return SourceRecord(
        record_id=record_id,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        source_family="synthetic-register",
        source_role="structured-program-register",
        source_version="1",
        source_locator="https://example.test/register/1",
        observed_at=NOW,
        payload_ref="artifact:" + "d" * 32,
        payload_hash=payload_hash,
    )


def seed_taxonomy(catalog):
    scheme = TaxonomyScheme(
        record_id="scheme:" + "2" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "fixture"},
        scheme_id="sdg",
        owner="United Nations",
        purpose="alignment fixture",
        jurisdiction="global",
        disposition="reference_only",
        licence="official terms",
        reuse_policy="attribution",
        attribution="UN SDG",
        steward="fixture steward",
        review_status="frozen",
    )
    version = TaxonomyVersion(
        record_id="schemever:" + "3" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "fixture"},
        scheme_id=scheme.scheme_id,
        version="fixture-1",
        release_date=date(2026, 1, 1),
        status="frozen",
        licence="official terms",
        reuse_policy="attribution",
        attribution="UN SDG",
    )
    concept = TaxonomyConcept(
        record_id="concept:" + "4" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "fixture"},
        scheme_version_id=version.record_id,
        external_concept_id="SDG-4",
        preferred_label="Quality education",
    )
    catalog.register_taxonomy_scheme(scheme)
    catalog.register_taxonomy_version(version)
    catalog.register_taxonomy_concept(concept)
    return version, concept


def test_abn_checksum_and_exact_identifier_join():
    assert validate_abn("51 824 753 556")
    assert not validate_abn("51 824 753 557")
    assert exact_identifier_join({"ABN": "51824753556"}, [{"ABN": "51824753556", "id": "acnc-1"}])["id"] == "acnc-1"
    assert exact_identifier_join({"name": "same"}, [{"name": "same"}, {"name": "same"}]) is None

def test_seed_portfolio_is_versioned_and_bounded(tmp_path):
    catalog = open_catalog(tmp_path)
    seeded = seed_phase1_taxonomies(catalog)
    assert set(seeded) == {"acnc", "ato-dgr", "classie", "sdg", "charitygraph-activity"}
    assert sum(item["kind"] == "concept" for item in seeded["sdg"]) == 17
    assert any(item.get("external_id") == "SUBJECT-EDU" for item in seeded["classie"])
    assert catalog.get_taxonomy_version(seeded["classie"][1]["id"])["version"] == "4.2"


def test_taxonomy_versions_concepts_assignments_are_idempotent_and_bound(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(make_subject())
    source = source_record()
    catalog.register_source_record(source)
    locator = EvidenceLocator(kind="structured_field", source_record_id=source.record_id, field_path="programs[0]")
    evidence_id = catalog.register_evidence_locator(locator)["evidence_locator_id"]
    version, concept = seed_taxonomy(catalog)
    assignment = {
        "record_id": "assignment:" + "5" * 32,
        "created_at": NOW,
        "producer": {"kind": "human", "producer_id": "reviewer"},
        "subject_id": SUBJECT,
        "scheme_version_id": version.record_id,
        "concept_id": concept.record_id,
        "role": "primary",
        "assignment_method": "source-reported",
        "evidence_ids": (evidence_id,),
        "outcome_state": "supported",
        "lifecycle_status": "accepted",
    }
    first = catalog.register_taxonomy_assignment(assignment)
    assert catalog.register_taxonomy_assignment(assignment)["material_hash"] == first["material_hash"]
    with pytest.raises(ConflictError):
        catalog.register_taxonomy_assignment({**assignment, "confidence": "high"})
    catalog.close()


def test_phase1_vertical_fake_provider_and_lineage(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(make_subject())
    source = source_record()
    catalog.register_source_record(source)
    locator_id = catalog.register_evidence_locator(
        EvidenceLocator(kind="structured_field", source_record_id=source.record_id, field_path="programs[0]")
    )["evidence_locator_id"]
    engine = Phase1PreRunEngine(catalog)
    candidate = engine.create_structured_program_candidate(
        subject_id=SUBJECT,
        source_record_id=source.record_id,
        evidence_ids=(locator_id,),
        label="Reading program",
    )
    assert catalog.get_program_candidate(candidate.record_id)["label"] == "Reading program"
    task = engine.create_task(
        subject_id=SUBJECT,
        evidence=(EvidenceInput(evidence_id=locator_id, content_hash="e" * 64, selection_hash="f" * 64),),
        task_kind="program_decomposition",
    )
    output = ProgramCandidateOutput(
        label=candidate.label,
        decision="material_program",
        subject_kind="program",
        conclusion=SemanticConclusion(
            outcome="supported",
            evidence=(SemanticEvidence(evidence_id=locator_id, role="supporting"),),
            rationale="The structured source labels a bounded programme.",
            confidence="high",
        ),
    )
    execution, validated = engine.execute_task(task, output)
    replay, _ = engine.execute_task(task, output)
    assert replay.task_run.record_id == execution.task_run.record_id
    assert replay.logical_result.record_id == execution.logical_result.record_id
    assert execution.task.record_id == task.record_id
    assert execution.logical_result.validation_status == "valid"
    assert validated.decision == "material_program"

    version, concept = seed_taxonomy(catalog)
    taxonomy_output = TaxonomyAssignmentOutput(
        conclusion=SemanticConclusion(
            outcome="supported",
            evidence=(SemanticEvidence(evidence_id=locator_id, role="supporting"),),
            rationale="The source supports the fixture classification.",
            confidence="medium",
        ),
        selections=(TaxonomySelection(
            concept_id=concept.record_id,
            role="primary",
            evidence=(SemanticEvidence(evidence_id=locator_id, role="supporting"),),
            rationale="Direct source classification.",
            confidence="medium",
        ),),
    )
    rows = engine.persist_taxonomy_output(
        subject_id=SUBJECT,
        scheme_version_id=version.record_id,
        output=taxonomy_output,
        evidence_ids=(locator_id,),
    )
    assert rows[0]["concept_id"] == concept.record_id
    assert catalog.integrity_check() == "ok"
