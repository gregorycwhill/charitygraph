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
    build_model_task,
    request_specific_rich_semantic_output_schema,
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
    payload = {"scheme_id": "classie", "version": "4.2-private", "source_locator": "private://classie", "concepts": [{"external_concept_id": "classie.program", "preferred_label": "Program", "definition": "Fixture"}]}
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

def test_public_projection_uses_explicit_metadata_not_scheme_names():
    rows = (
        {"scheme_id": "charitygraph-classie", "publication_eligibility": "withheld"},
        {"scheme_id": "foo-classie-looking-name", "publication_eligibility": "eligible", "publication_policy_id": "release-vnext"},
        {"scheme_id": "ato-dgr", "publication_eligibility": "ineligible"},
        {"scheme_id": "native", "publication_eligibility": "review_required"},
    )
    assert public_classification_projection(rows) == (rows[1],)
    assert public_classification_projection(rows, classie_enabled=True) == (rows[1],)
    assert public_classification_projection(rows, publication_policy_id="other") == ()


def test_public_projection_accepts_only_explicitly_eligible_assignments():
    row = {"scheme_id": "arbitrary", "publication_eligibility": "eligible", "publication_policy_id": "release-vnext"}
    assert public_classification_projection((row,), publication_policy_id="release-vnext") == (row,)

def test_request_specific_schema_enumerates_evidence_and_private_concepts(tmp_path):
    bundle = build_evidence_bundle("subject:" + "2" * 32, "lean", (_doc(),))
    evidence_id = bundle.source_segments[0].evidence_id
    schema = request_specific_rich_semantic_output_schema(
        permitted_evidence_ids=(evidence_id,),
        classie_concept_ids=("classie.program",),
        classie_enabled=True,
    )
    for definition in ("SemanticProposal", "SemanticAssertion", "ClassieAssignment"):
        assert schema["$defs"][definition]["properties"]["evidence_refs"]["items"]["enum"] == [evidence_id]
    assert schema["$defs"]["ClassieAssignment"]["properties"]["external_concept_id"]["enum"] == ["classie.program"]
    assert "classie.unknown" not in schema["$defs"]["ClassieAssignment"]["properties"]["external_concept_id"]["enum"]
    disabled = request_specific_rich_semantic_output_schema(permitted_evidence_ids=(evidence_id,))
    assert disabled["properties"]["classie_assignments"]["maxItems"] == 0


def test_private_classie_wiring_changes_prompt_provenance_and_reuse_identity(tmp_path):
    path = tmp_path / "classie.json"
    payload = {"scheme_id": "classie", "version": "4.2-private", "source_locator": "private://classie", "concepts": [{"external_concept_id": "classie.program", "preferred_label": "Program", "definition": "Fixture"}]}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    loaded = load_private_classie_payload(path)
    bundle = build_evidence_bundle("subject:" + "3" * 32, "lean", (_doc(),))
    task = build_model_task(bundle.subject_id, bundle, provider_id="fake", model_snapshot="fake", classie_runtime=loaded)
    prompt = semantic_prompt(bundle, "Fixture", classie_concepts=loaded["concepts"])
    assert "classie.program" in prompt
    assert loaded["version"] == task.parameters["classie_runtime"]["version"]
    assert loaded["content_hash"] == task.parameters["classie_runtime"]["content_hash"]
    assert task.parameters["classie_runtime"]["content_hash"] == loaded["content_hash"]
    changed = dict(loaded, version="4.3-private", content_hash="f" * 64)
    assert task.cache_key != build_model_task(bundle.subject_id, bundle, provider_id="fake", model_snapshot="fake", classie_runtime=changed).cache_key
    disabled_prompt = semantic_prompt(bundle, "Fixture")
    assert "disabled/not-configured" in disabled_prompt
    assert "classie.program" not in disabled_prompt
    assert build_model_task(bundle.subject_id, bundle, provider_id="fake", model_snapshot="fake").cache_key != task.cache_key


def test_configured_private_classie_flows_through_spike_without_provider(tmp_path):
    path = tmp_path / "classie.json"
    payload = {"scheme_id": "classie", "version": "4.2-private", "source_locator": "private://classie", "concepts": [{"external_concept_id": "classie.program", "preferred_label": "Program", "definition": "Fixture"}]}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    loaded = load_private_classie_payload(path)
    from charitygraph.llm_semantic_economics import run_spike, SpikeRunConfig
    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime"), classie_payload_path=str(path), classie_expected_version="4.2-private"), transport=lambda url: (b"<p>evidence</p>", "text/html"))
    assert report["classie_runtime"] == {"status": "private_runtime_loaded", "scheme_id": "classie", "version": "4.2-private", "content_hash": loaded["content_hash"], "external_scheme_id": None, "publication_eligibility": "withheld"}

def test_exact_reuse_identity_ignores_tier_but_changes_evidence():
    subject = "subject:" + "4" * 32
    docs = (_doc(),)
    lean = build_evidence_bundle(subject, "lean", docs)
    broad = build_evidence_bundle(subject, "broad", docs)
    assert build_model_task(subject, lean, provider_id="fake", model_snapshot="fake").cache_key == build_model_task(subject, broad, provider_id="fake", model_snapshot="fake").cache_key
    other = SourceDocument(**{**_doc().model_dump(), "text": "different evidence", "content_hash": hashlib.sha256(b"different evidence").hexdigest(), "artifact_id": "srcblob:" + hashlib.sha256(b"different evidence").hexdigest()})
    changed = build_evidence_bundle(subject, "lean", (other,))
    assert build_model_task(subject, lean, provider_id="fake", model_snapshot="fake").cache_key != build_model_task(subject, changed, provider_id="fake", model_snapshot="fake").cache_key

def test_disabled_classie_output_is_rejected_and_run_reports_explicit_state(tmp_path):
    bundle = build_evidence_bundle("subject:" + "5" * 32, "lean", (_doc(),))
    with pytest.raises(ValueError, match="unknown CLASSIE concept"):
        validate_output(_output(bundle.source_segments[0].evidence_id), bundle, classie_concept_ids=set())
    from charitygraph.llm_semantic_economics import run_spike, SpikeRunConfig
    report = run_spike(SpikeRunConfig(runtime_root=str(tmp_path / "runtime")), transport=lambda url: (b"<p>evidence</p>", "text/html"))
    assert report["classie_runtime"]["status"] == "disabled_not_configured"


def test_dynamic_schema_retains_recursive_strict_contract():
    bundle = build_evidence_bundle("subject:" + "6" * 32, "lean", (_doc(),))
    schema = request_specific_rich_semantic_output_schema(permitted_evidence_ids=(bundle.source_segments[0].evidence_id,), classie_concept_ids=("classie.program",), classie_enabled=True)
    def walk(node):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    for node in walk(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])