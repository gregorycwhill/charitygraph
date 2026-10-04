from datetime import date, datetime, timezone

import pytest

from charitygraph.models import (
    CauseBaseCard,
    EvidenceRef,
    FundingSourceObservation,
    FundraisingCampaignObservation,
    FundraisingObservationScope,
    FundraisingPracticeObservation,
    FundraisingProviderRelationship,
    SubjectRelationship,
)
from charitygraph.north_star_projection import FundraisingProjection, project_fundraising


SCOPE = FundraisingObservationScope(
    scope_kind="subject", scope_subject_causebase_id="cb_example",
    geography=["AU"], valid_from=date(2026, 1, 1), observed_at=date(2026, 2, 1),
)
PROVIDER_LINK = SubjectRelationship(
    relationship_type="fundraising_service_provider", target_causebase_id="cb_provider",
    evidence_ids=["ev_fundraising"],
)


def evidence():
    return EvidenceRef(
        evidence_id="ev_fundraising", source_type="organisation_self_report",
        title="Fundraising disclosure", observed_at=date(2026, 2, 1),
    )


def practice(**overrides):
    payload = dict(
        observation_id="fp_f2f_regular", source_native_phrase="F2F regular giving recruitment",
        canonical_facets=(
            "fundraising.face_to_face", "fundraising.regular_giving",
            "fundraising.private_site", "fundraising.recurring",
            "fundraising.direct_debit", "fundraising.acquisition",
        ),
        scope=SCOPE, lifecycle="current", source_role="direct_assertion",
        evidence_ids=["ev_fundraising"],
    )
    payload.update(overrides)
    return FundraisingPracticeObservation(**payload)


def card(**overrides):
    payload = dict(
        causebase_id="cb_example", legal_name="Example", display_name="Example",
        entity_status="registered", causebase_summary="Example", dataset_version="test",
        built_at=datetime(2026, 2, 2, tzinfo=timezone.utc), evidence=[evidence()],
    )
    payload.update(overrides)
    return CauseBaseCard(**payload)


def test_practice_campaign_funding_source_and_expenditure_are_distinct_contracts():
    standing = practice()
    campaign = FundraisingCampaignObservation(
        observation_id="fc_flood_appeal", campaign_name="Flood Appeal 2026",
        source_native_phrase="Flood appeal", canonical_facets=("fundraising.emergency_appeal",),
        scope=SCOPE, lifecycle="active", source_role="direct_assertion",
        evidence_ids=["ev_fundraising"],
    )
    source = FundingSourceObservation(source_type="individual_donations", source_label="Donations")
    result = card(
        funding_sources=[source], fundraising_practice_observed=[standing],
        fundraising_campaign_observed=[campaign],
    )

    assert result.fundraising_expenditure is None
    assert result.funding_sources[0].source_type == "individual_donations"
    assert result.fundraising_practice_observed[0].observation_id.startswith("fp_")
    assert result.fundraising_campaign_observed[0].observation_id.startswith("fc_")


def test_orthogonal_facets_coexist_but_same_axis_assignments_fail_closed():
    assert set(practice().canonical_facets) >= {"fundraising.face_to_face", "fundraising.direct_debit"}
    with pytest.raises(ValueError, match="same facet"):
        practice(canonical_facets=("fundraising.face_to_face", "fundraising.telephone"))
    with pytest.raises(ValueError, match="unknown fundraising facets"):
        practice(canonical_facets=("fundraising.not_a_real_term",))


def test_provider_relationship_is_directed_and_requires_evidence():
    relation = FundraisingProviderRelationship(
        relationship_id="fpr_provider", relationship=PROVIDER_LINK,
        subject_role="commissioner", provider_role="fundraising_service_provider",
        scope=SCOPE, lifecycle="current", source_role="direct_assertion",
        evidence_ids=["ev_fundraising"],
    )
    assert card(fundraising_provider_relationships=[relation]).fundraising_provider_relationships[0].relationship.target_causebase_id == "cb_provider"
    with pytest.raises(ValueError, match="requires evidence"):
        FundraisingProviderRelationship(
            relationship_id="fpr_unproven", relationship=SubjectRelationship(
                relationship_type="fundraising_platform_provider", target_causebase_id="cb_provider"
            ), subject_role="client", provider_role="fundraising_platform_provider", scope=SCOPE,
        )


def test_projection_is_lossless_for_currentness_and_missingness_and_ignores_legacy_flat_input():
    current = practice()
    missing = practice(
        observation_id="fp_missing", source_native_phrase="No practice data",
        canonical_facets=(), lifecycle="unknown", coverage_status="not_yet_processed",
        evidence_ids=[],
    )
    result = project_fundraising(card(fundraising_practice_observed=[current, missing]))
    assert result.practices[0].lifecycle == "current"
    assert result.practices[1].coverage_status == "not_yet_processed"
    assert CauseBaseCard.model_json_schema()["properties"]["fundraising_methods"]["deprecated"] is True


def test_existing_fundraising_projection_shape_remains_constructible_without_optional_section_data():
    result = FundraisingProjection(practices=(), campaigns=(), provider_relationships=())
    assert result.money == ()
    assert result.coverage == ()
    assert result.evidence == ()


def test_duplicate_typed_assignments_fail_closed_on_the_card():
    with pytest.raises(ValueError, match="duplicate fundraising practice IDs"):
        card(fundraising_practice_observed=[practice(), practice()])
