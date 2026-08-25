from decimal import Decimal

import pytest

from charitygraph.reality_slice1 import (
    BoundedPublicAcquirer, HoldoutFirewallError, OpenAIProviderAdapter,
    assert_development_member, development_members, load_classie_reference,
    project_costs, run_development_preflight, source_opportunities,
)


def test_manifest_has_seven_development_members_and_three_sealed_holdouts():
    members = development_members()
    assert len(members) == 7
    assert {member.cohort_membership for member in members} == {"development"}
    with pytest.raises(HoldoutFirewallError):
        assert_development_member(abn="67 649 417 658")
    with pytest.raises(HoldoutFirewallError):
        assert_development_member(name="Life Without Barriers")


def test_source_plan_is_allow_listed_and_page_bounded():
    members = development_members()
    opportunities = source_opportunities(members[0])
    assert len(opportunities) == 6
    assert all(item.member_abn == members[0].abn for item in opportunities)
    assert all(item.url.startswith("https://") for item in opportunities)
    assert not any("landscape" in item.url for item in opportunities)


def test_private_acquisition_produces_content_addressed_metadata_without_holdout(tmp_path):
    def transport(url):
        return (b"bounded public fixture", url, 200, "text/html")
    acquirer = BoundedPublicAcquirer(tmp_path, transport=transport)
    outcome = acquirer.acquire(source_opportunities(development_members()[0])[0], allow_network=True)
    assert outcome.status == "available"
    assert outcome.content_hash and len(outcome.content_hash) == 64
    assert outcome.artifact_id and outcome.artifact_id.startswith("srcblob:")
    with pytest.raises(HoldoutFirewallError):
        acquirer.acquire(type(source_opportunities(development_members()[0])[0])(
            member_abn="67649417658", family="official-website", role="sealed", url="https://landscaperecovery.com.au", proposition="sealed", publisher="sealed"
        ), allow_network=True)


def test_preflight_is_deterministic_review_only_and_under_budget(tmp_path):
    first = run_development_preflight(runtime_root=tmp_path / "runtime", allow_network=False)
    second = run_development_preflight(runtime_root=tmp_path / "runtime2", allow_network=False)
    assert len(first["development_members"]) == 7
    assert len(first["task_plan"]) == 42
    assert first["holdout_firewall"]["enforced"] is True
    assert first["economics"]["within_cap"] is True
    assert first["economics"]["paid_calls_executed"] is False
    assert first["taxonomy"]["classie"]["status"].startswith("blocked")
    assert first["source_opportunities"] == second["source_opportunities"] == 42
    assert all(not scope["source_families_assessed"] for scope in first["assessment_scopes"])
    assert all(scope["semantic_outcome"] is None and scope["blockers"] for scope in first["assessment_scopes"])


def test_classie_import_requires_native_ids_and_preserves_rights():
    imported = load_classie_reference(
        [{"external_concept_id": "S01", "preferred_label": "Education", "definition": "native"}],
        source_locator="private://classie-4.2",
        content_hash="a" * 64,
        rights_policy="modified-cc-terms-review",
    )
    assert imported["version"] == "4.2"
    assert imported["rights_policy"] == "modified-cc-terms-review"
    with pytest.raises(ValueError):
        load_classie_reference([{"preferred_label": "missing id"}], source_locator="private://x", content_hash="b" * 64, rights_policy="review")


def test_provider_adapter_is_real_boundary_but_paid_execution_is_gated():
    adapter = OpenAIProviderAdapter()
    assert adapter.validate_configuration()["provider_id"] == "openai"
    assert adapter.validate_configuration()["paid_execution_enabled"] is False


def test_cost_projection_is_decimal_and_bounded():
    projection = project_costs(development_members())
    assert Decimal(projection["total_estimated_aud"]) < Decimal("25")
    assert all(row["cache_misses"] == row["task_count"] for row in projection["rows"])
