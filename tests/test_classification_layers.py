from datetime import datetime, timezone
import hashlib
import json

import pytest

from charitygraph.contracts.knowledge import ScopeRecord
from charitygraph.llm_semantic_economics import (
    ClassieAssignment,
    EvidenceBundle,
    RichSemanticOutput,
    SemanticAssertion,
    SemanticProposal,
    SourceDocument,
    build_evidence_bundle,
    parse_document,
    semantic_prompt,
    validate_output,
)
from charitygraph.private_classie import PrivateClassieLoadError, load_private_classie_payload, public_classification_projection
from charitygraph.phase1 import seed_phase1_taxonomies


def _doc() -> SourceDocument:
    text = "A documented program delivers service."
    digest = hashlib.sha256(text.encode()).hexdigest()
    return SourceDocument(
        url="https://example.test/report",
        retrieved_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        publisher="Fixture",
        content_hash=digest,
        artifact_id="srcblob:" + digest,
        media_type="text/html",
        byte_size=len(text),
        text=text,
    )


def _output(evidence_id: str, *, concept: str = "classie.program") -> RichSemanticOutput:
    proposal = SemanticProposal(
        proposal_id="program-1",
        label="Documented program",
        kind="program",
        durable=True,
        parent_proposal_id=None,
        description=None,
        evidence_refs=(evidence_id,),
        aliases=(),
        confidence="medium",
        competing_interpretation=None,
        model_review_recommendation="required",
    )
    assertion = SemanticAssertion(
        proposition="delivers service",
        subject_proposal_id="program-1",
        scope_kind="proposal",
        evidence_refs=(evidence_id,),
        confidence="medium",
        competing_interpretation=None,
    )
    assignment = ClassieAssignment(
        subject_proposal_id="program-1",
        scope_kind="proposal",
        external_concept_id=concept,
        role="primary",
        evidence_refs=(evidence_id,),
        confidence="medium",
        rationale="Fixture evidence",
        competing_interpretation=None,
        model_review_recommendation="required",
    )
    return RichSemanticOutput(
        programs=(proposal,),
        services=(),
        projects=(),
        campaigns=(),
        organisational_units=(),
        activities=(assertion,),
        populations=(),
        geographies=(),
        sdg_alignments=(),
        assertions=(),
        classie_assignments=(assignment,),
        semantic_outcome="supported",
        blockers=(),
    )


def test_seed_profiles_keep_acnc_facets_and_classie_versions_distinct(tmp_path):
    from charitygraph.runtime import SQLiteCatalog
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    seeded = seed_phase1_taxonomies(catalog, classie_concepts=({"external_concept_id": "classie.program", "preferred_label": "Program"},))
    assert seeded["acnc-registration-purpose"][1]["id"] != seeded["acnc-registration-beneficiary"][1]["id"]
    assert catalog.get_taxonomy_version(seeded["acnc-ais-classie"][1]["id"])["version"] == "AIS-2025"
    assert catalog.get_taxonomy_version(seeded["classie"][1]["id"])["version"] == "4.2"


def test_private_classie_loader_hashes_and_fails_closed(tmp_path):
    path = tmp_path / "classie.json"
    payload = {"scheme_id": "charitygraph-classie", "version": "4.2-private", "source_locator": "private://classie", "concepts": [{"external_concept_id": "classie.program", "preferred_label": "Program", "definition": "Fixture"}]}
    raw = json.dumps(payload, sort_keys=True).encode()
    path.write_bytes(raw)
    loaded = load_private_classie_payload(path)
    assert loaded["content_hash"] == hashlib.sha256(raw).hexdigest()
    assert loaded["publication_eligibility"] == "withheld"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(PrivateClassieLoadError):
        load_private_classie_payload(path)


def test_scoped_classie_output_is_strict_and_independent_of_acnc_label():
    bundle = build_evidence_bundle("subject:" + "1" * 32, "lean", (_doc(),))
    evidence_id = bundle.source_segments[0].evidence_id
    output = _output(evidence_id)
    validate_output(output, bundle, classie_concept_ids={"classie.program"})
    prompt = semantic_prompt(bundle, "Fixture", classie_concepts=({"external_concept_id": "classie.program", "preferred_label": "Program", "definition": "Fixture"},))
    assert "ACNC classified this as" not in prompt
    assert "classie.program" in prompt
    with pytest.raises(ValueError, match="unknown CLASSIE concept"):
        validate_output(output, bundle, classie_concept_ids={"classie.other"})


def test_reporting_group_scope_does_not_propagate_to_member_or_program():
    common = {"created_at": datetime(2026, 8, 1, tzinfo=timezone.utc), "producer": {"kind": "human", "producer_id": "fixture"}}
    group = ScopeRecord(record_id="scope:" + "1" * 32, subject_id="subject:" + "1" * 32, scope_kind="reporting_group", label="Group", **common)
    legal = ScopeRecord(record_id="scope:" + "2" * 32, subject_id="subject:" + "2" * 32, scope_kind="organisation", label="Legal member", **common)
    program = ScopeRecord(record_id="scope:" + "3" * 32, subject_id="subject:" + "3" * 32, scope_kind="program", label="Program", **common)
    assert group.scope_kind == "reporting_group"
    assert legal.scope_kind == "organisation"
    assert program.scope_kind == "program"
    assert {group.record_id, legal.record_id, program.record_id} == {"scope:" + "1" * 32, "scope:" + "2" * 32, "scope:" + "3" * 32}

def test_classie_public_projection_is_withheld_when_disabled():
    rows = ({"scheme_id": "charitygraph-classie", "classie": True}, {"scheme_id": "ato-dgr", "status": "endorsed"})
    assert public_classification_projection(rows) == (rows[1],)
    assert public_classification_projection(rows, classie_enabled=True) == rows