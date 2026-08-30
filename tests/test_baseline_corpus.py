import json
from decimal import Decimal
from pathlib import Path

import pytest

from charitygraph.baseline_corpus import (
    AcquisitionState,
    BindingState,
    CorpusMember,
    CorpusBindingContext,
    DiscoveryState,
    MaterialOrigin,
    RepresentationReadiness,
    build_corpus_manifest,
    enumerate_site_candidates,
    load_v05_cards,
    normalise_host,
    normalise_v05_subject,
    extract_pfra_members, partition_site_candidates, provider_budget_allows, resolve_wikipedia_candidate, resolve_wikipedia_candidate_with_luna, select_filing_documents,
)


def member(**changes):
    values = dict(
        source_family="acnc_register", source_definition_id="srcdef:acnc",
        acquisition_receipt_ids=("acq:one",), artifact_ids=("srcblob:" + "a" * 64,),
        source_record_ids=("src:acnc",), discovery=DiscoveryState.RESOLVED,
        acquisition=AcquisitionState.AVAILABLE, subject_binding=BindingState.BOUND,
        material_origin=MaterialOrigin.REUSED_EXISTING,
    )
    values.update(changes)
    return CorpusMember(**values)


def test_nested_v05_identity_and_website_normalisation(tmp_path: Path):
    path = tmp_path / "card.json"
    path.write_text(json.dumps({"causebase_id": "cb_test", "contract_version": "0.5", "subject_kind": "charity", "identity": {"display_name": "Example", "legal_name": "Example Ltd", "operating_names": ["Example"], "website": "HTTPS://WWW.Example.org.au/about", "external_identifiers": [{"scheme": "abn", "value": "12"}]}, "evidence": [{"evidence_id": "ev:1"}]}), encoding="utf-8")
    row = normalise_v05_subject(load_v05_cards(tmp_path)[0])
    assert row["subject_id"] == "cb_test"
    assert row["website_domain"] == "example.org.au"
    assert row["legal_name"] == "Example Ltd"
    assert row["external_identifiers"][0]["scheme"] == "abn"


def test_host_normalisation_strips_path_case_and_www():
    assert normalise_host("https://WWW.Example.org/path?q=1") == "example.org"


def test_site_enumeration_is_mechanical_and_same_origin_only():
    html = '<a href="/about">About</a><a href="/x">X</a><a href="https://other.example/no">Other</a>'
    rows = enumerate_site_candidates(html, "https://example.org")
    assert [row["url"] for row in rows] == ["https://example.org", "https://example.org/about", "https://example.org/x"]
    assert [row["ordinal"] for row in rows] == [0, 1, 2]


def test_site_enumeration_includes_sitemap_candidates():
    rows = enumerate_site_candidates("", "https://example.org", sitemap_xml="<urlset xmlns='x'><url><loc>https://example.org/a</loc></url></urlset>")
    assert rows[-1]["url"] == "https://example.org/a"


def test_available_member_requires_immutable_artifact():
    with pytest.raises(ValueError):
        member(artifact_ids=())


def test_bound_member_requires_source_lineage():
    with pytest.raises(ValueError):
        member(source_record_ids=(), evidence_locator_ids=())


def test_ready_representation_requires_derived_artifact():
    with pytest.raises(ValueError):
        member(representation_readiness=RepresentationReadiness.READY)


def test_manifest_material_identity_excludes_provenance():
    first = build_corpus_manifest(subject_id="cb:test", profile_version="baseline-v1", members=[member()], cohort_id="cohort:a", run_id="run:a", retrieval_timestamps=("2026-08-29T00:00:00Z",), builder_commit="a" * 40)
    second = build_corpus_manifest(subject_id="cb:test", profile_version="baseline-v1", members=[member()], cohort_id="cohort:b", run_id="run:b", retrieval_timestamps=("2026-08-30T00:00:00Z",), builder_commit="b" * 40)
    assert first.material_identity_hash == second.material_identity_hash
    assert first.provenance_hash != second.provenance_hash


def test_manifest_member_change_changes_material_identity():
    first = build_corpus_manifest(subject_id="cb:test", profile_version="baseline-v1", members=[member()], cohort_id="cohort:a")
    second = build_corpus_manifest(subject_id="cb:test", profile_version="baseline-v1", members=[member(source_family="official_website")], cohort_id="cohort:a")
    assert first.material_identity_hash != second.material_identity_hash


def test_reporting_scope_binding_context_is_material_identity():
    context = CorpusBindingContext(basis="acnc_reporting_group", acnc_entity_id="group-1", source_native_group_name="Group Name")
    first = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member(binding_context=context)])
    second = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member()])
    assert first.material_identity_hash != second.material_identity_hash


def test_coverage_states_are_separate_and_no_boolean_complete():
    item = member(discovery=DiscoveryState.NOT_ATTEMPTED, acquisition=AcquisitionState.UNAVAILABLE, subject_binding=BindingState.NONE, material_origin=MaterialOrigin.NONE)
    assert item.discovery.value == "not_attempted"
    assert item.acquisition.value == "unavailable"
    assert not hasattr(item, "corpus_complete")
def test_material_identity_ignores_receipts_operational_state_and_representation():
    first = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member()])
    second = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member(acquisition_receipt_ids=("acq:other",), material_origin=MaterialOrigin.NEWLY_ACQUIRED, acquisition=AcquisitionState.PARTIAL, representation_readiness=RepresentationReadiness.PARTIAL, representation_artifact_ids=("artifact:" + "b" * 64,), representation_gaps=("page-2",))])
    assert first.material_identity_hash == second.material_identity_hash


def test_material_identity_changes_source_revision_and_record_selection():
    first = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member()])
    changed = build_corpus_manifest(subject_id="subject:abc", profile_version="baseline-v1", members=[member(source_revision="rev-2")])
    assert first.material_identity_hash != changed.material_identity_hash

def test_official_website_bound_material_is_not_empty():
    manifest = build_corpus_manifest(subject_id="subject:website", profile_version="baseline-v1", members=[member(source_family="official_website", source_record_ids=("srcrec:homepage",), artifact_ids=("srcblob:" + "h" * 64,))])
    assert len(manifest.material_members) == 1
    assert manifest.material_members[0].source_family == "official_website"


def test_filing_bundle_selects_ais_and_same_period_attachments_by_metadata():
    rows = select_filing_documents([{ "type": "Annual Information Statement", "Year": "2025", "Url": "https://acnc.example/ais" }, { "type": "Annual Report", "Year": "2025", "Url": "https://acnc.example/report" }, { "type": "Financial Report", "Year": "2024", "Url": "https://acnc.example/old" }], "2025")
    assert [row["role"] for row in rows] == ["annual_information_statement", "annual_report"]


def test_provider_budget_guard_blocks_over_cap():
    assert provider_budget_allows(Decimal("0.10"), Decimal("0.20"), Decimal("0.19"))
    assert not provider_budget_allows(Decimal("0.40"), Decimal("0.00"), Decimal("0.11"))


def test_wikipedia_binding_uses_names_not_abn_title_equality():
    assert resolve_wikipedia_candidate(["The Smith Family"], [{"title": "The Smith Family"}])["status"] == "bound"
    assert resolve_wikipedia_candidate(["The Smith Family"], [{"title": "28000030179"}])["status"] == "no_bound_record"


def test_pfra_member_parser_is_role_specific_and_preserves_domain():
    rows = extract_pfra_members("<h4 class=\"card-title\">Mission Australia</h4><p><a href=\"https://www.missionaustralia.com.au\">site</a></p>", page_role="current_charity_membership")
    assert rows[0]["member_role"] == "current_charity_membership"
    assert rows[0]["label"] == "Mission Australia"
    assert rows[0]["linked_domains"] == ["missionaustralia.com.au"]


def test_large_site_partition_is_budget_derived_not_fixed_url_count():
    rows = [{"ordinal": i, "url": f"https://example.org/{i}", "label": "x" * 80} for i in range(1200)]
    batches = partition_site_candidates(rows, max_request_tokens=4000)
    assert len(batches) > 1
    assert [item["ordinal"] for batch in batches for item in batch] == list(range(1200))


def test_site_partition_enforces_output_token_bound_with_short_candidates():
    rows = [{"ordinal": i, "url": "u", "label": ""} for i in range(10)]
    batches = partition_site_candidates(rows, max_output_tokens=8, max_request_tokens=100000)
    assert all(len(batch) * 4 <= 8 for batch in batches)


def test_abr_dgr_prose_is_not_semantically_interpreted():
    import importlib.util
    script = Path(__file__).parents[1] / "scripts" / "run_baseline_charity_corpus_v1.py"
    spec = importlib.util.spec_from_file_location("baseline_runner", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    result = module.extract_abr_dgr_fields(b"DGR endorsed: yes; Item 1; 1/1/2025")
    assert result["status"] is None
    assert result["source_native"] is False
    assert result["extraction"] == "deferred"


def test_wikipedia_identity_resolution_uses_bounded_model_only_for_residual_candidates():
    class Usage:
        input_tokens = 10
        output_tokens = 5
        total_tokens = 15
    class Result:
        model = "gpt-5.6-luna"
        output_text = '{"status":"bound","candidate_index":0}'
        usage = Usage()
        transport_requests = 1
    result = resolve_wikipedia_candidate_with_luna(
        ["Example Charity"],
        [{"title": "Example Charity", "snippet": "registered organisation"}],
        subject_context={"abn": "12"},
        request_fn=lambda **kwargs: Result(),
    )
    assert result["status"] == "bound"
    assert result["candidate_index"] == 0
