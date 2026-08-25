from decimal import Decimal

import pytest

from charitygraph.reality_slice1 import (
    BoundedPublicAcquirer, HoldoutFirewallError, OpenAIProviderAdapter,
    assess_acquisition, assert_development_member, development_members,
    load_classie_reference, project_costs, run_development_preflight,
    source_opportunities,
)


def test_manifest_has_seven_development_members_and_three_sealed_holdouts():
    members = development_members()
    assert len(members) == 7
    assert {member.cohort_membership for member in members} == {"development"}
    with pytest.raises(HoldoutFirewallError):
        assert_development_member(abn="67 649 417 658")
    with pytest.raises(HoldoutFirewallError):
        assert_development_member(name="Life Without Barriers")


def test_source_plan_uses_subject_specific_locators_and_discovery_only():
    member = development_members()[0]
    opportunities = source_opportunities(member)
    assert {item.family for item in opportunities} == {"acnc", "abr"}
    assert all(item.subject_binding == member.abn for item in opportunities)
    assert all("/ABN/View?abn=" in item.url or "charity-details?charity=" in item.url for item in opportunities)
    html = b'<a href="/what-we-do">What we do</a><a href="/annual-reports">Reports</a>'
    resolved = source_opportunities(member, page_fetcher=lambda _: html)
    assert {item.family for item in resolved} == {"acnc", "abr", "official-website", "annual-report"}
    assert all(not item.url.endswith("/annual-report") for item in resolved)


def test_acquisition_success_does_not_equal_usable_evidence():
    member = development_members()[0]
    homepage = source_opportunities(member)[0]
    assert assess_acquisition(homepage, body=member.abn.encode()).status == "usable_evidence"
    generic = homepage.__class__(member.abn, "official-website", "homepage", "https://example.test", "program", "publisher", subject_binding=member.abn)
    assert assess_acquisition(generic, body=b"200 OK").status == "generic_landing_page"


def test_private_acquisition_stores_metadata_and_never_holdout(tmp_path):
    def transport(url):
        return (b"bounded public fixture 28000030179", url, 200, "text/html")
    acquirer = BoundedPublicAcquirer(tmp_path, transport=transport)
    outcome = acquirer.acquire(source_opportunities(development_members()[0])[0], allow_network=True)
    assert outcome.status == "available"
    assert outcome.evidence_status == "usable_evidence"
    assert outcome.content_hash and len(outcome.content_hash) == 64
    with pytest.raises(HoldoutFirewallError):
        acquirer.acquire(source_opportunities(development_members()[0])[0].__class__(
            member_abn="67649417658", family="official-website", role="sealed",
            url="https://landscaperecovery.com.au", proposition="sealed", publisher="sealed",
            subject_binding="67649417658"), allow_network=True)


def test_preflight_is_acquisition_only_and_does_not_claim_semantic_gold(tmp_path):
    first = run_development_preflight(runtime_root=tmp_path / "runtime", allow_network=False)
    second = run_development_preflight(runtime_root=tmp_path / "runtime2", allow_network=False)
    assert len(first["development_members"]) == 7
    assert first["holdout_firewall"]["enforced"] is True
    assert first["economics_demo"]["within_cap"] is True
    assert first["economics_demo"]["paid_calls_executed"] is False
    assert first["taxonomy"]["classie"]["status"].startswith("blocked")
    assert first["source_opportunities"] == second["source_opportunities"] == 14
    assert first["task_plan"] == []
    assert first["candidate_observations"] == []
    assert "proposed_reference_set" not in first
    assert all(not scope["source_families_assessed"] for scope in first["assessment_scopes"])
    assert all(scope["semantic_outcome"] is None and scope["blockers"] for scope in first["assessment_scopes"])
    assert first["taxonomy"]["charitygraph_activity"]["concept_count"] == 8

def test_classie_import_requires_native_ids_and_preserves_rights():
    imported = load_classie_reference(
        [{"external_concept_id": "S01", "preferred_label": "Education", "definition": "native"}],
        source_locator="private://classie-4.2", content_hash="a" * 64,
        rights_policy="modified-cc-terms-review",
    )
    assert imported["version"] == "4.2"
    assert imported["rights_policy"] == "modified-cc-terms-review"
    with pytest.raises(ValueError):
        load_classie_reference([{"preferred_label": "missing id"}], source_locator="private://x", content_hash="b" * 64, rights_policy="review")


def test_provider_adapter_is_real_boundary_and_paid_execution_is_gated():
    adapter = OpenAIProviderAdapter()
    assert adapter.validate_configuration()["provider_id"] == "openai"
    assert adapter.validate_configuration()["paid_execution_enabled"] is False


def test_cost_projection_uses_decimal_and_budget_cap():
    projection = project_costs(development_members())
    assert Decimal(projection["total_estimated_aud"]) < Decimal("25")
    assert all(row["cache_misses"] == row["task_count"] for row in projection["rows"])

def test_cold_replay_reuses_source_hashes_and_reservation_identity(tmp_path):
    first = run_development_preflight(runtime_root=tmp_path / "replay", allow_network=False)
    second = run_development_preflight(runtime_root=tmp_path / "replay", allow_network=False)
    assert first["replay_mode"] == "fresh_bounded_acquisition"
    assert second["replay_mode"] == "source_hash_replay"
    assert [row["content_hash"] for row in first["acquisition_outcomes"]] == [row["content_hash"] for row in second["acquisition_outcomes"]]
    assert first["reservation_demo"]["status"] == second["reservation_demo"]["status"] == "not_applicable"