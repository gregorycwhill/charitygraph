"""Cross-section invariants for review-only fundraising observations.

The fundraising profile specialises shared evidence, relationship, scope and
finance primitives.  It must not create a second organisation or relationship
truth merely because an observation is convenient to project for review.
"""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from charitygraph.models import (
    CauseBaseCard,
    EvidenceRef,
    FundraisingObservationScope,
    FundraisingPracticeObservation,
    FundraisingProviderRelationship,
    SubjectRelationship,
)
from charitygraph.north_star_projection import project_fundraising


def evidence(evidence_id="ev:fundraising"):
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type="organisation_self_report",
        title="Fundraising disclosure",
        observed_at=date(2026, 10, 5),
    )


def scope(subject_id="charity:one"):
    return FundraisingObservationScope(
        scope_kind="subject",
        scope_subject_causebase_id=subject_id,
        observed_at=date(2026, 10, 5),
    )


def practice(subject_id="charity:one", **changes):
    values = {
        "observation_id": "fp_f2f",
        "source_native_phrase": "Face-to-face fundraising",
        "canonical_facets": ("fundraising.face_to_face",),
        "scope": scope(subject_id),
        "lifecycle": "current",
        "source_role": "direct_assertion",
        "evidence_ids": ["ev:fundraising"],
    }
    values.update(changes)
    return FundraisingPracticeObservation(**values)


def card(**changes):
    values = {
        "causebase_id": "charity:one",
        "legal_name": "Charity One",
        "display_name": "Charity One",
        "entity_status": "registered",
        "causebase_summary": "Test subject.",
        "dataset_version": "test",
        "built_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "evidence": [evidence()],
    }
    values.update(changes)
    return CauseBaseCard(**values)


def test_subject_scoped_fundraising_observation_cannot_cross_organisation_identity():
    with pytest.raises(ValidationError, match="subject scope must match card causebase_id"):
        card(fundraising_practice_observed=[practice("charity:other")])


def test_provider_wrapper_uses_shared_relationship_evidence_and_not_a_second_evidence_ledger():
    provider = FundraisingProviderRelationship(
        relationship_id="fpr_provider",
        relationship=SubjectRelationship(
            relationship_type="fundraising_service_provider",
            target_causebase_id="provider:one",
            evidence_ids=["ev:relationship"],
        ),
        subject_role="client",
        provider_role="fundraising_service_provider",
        scope=scope(),
        lifecycle="current",
        source_role="direct_assertion",
        evidence_ids=["ev:fundraising"],
    )
    with pytest.raises(ValidationError, match="provider relationship evidence IDs missing"):
        card(fundraising_provider_relationships=[provider])

    result = card(
        evidence=[evidence(), evidence("ev:relationship")],
        fundraising_provider_relationships=[provider],
    )
    projection = project_fundraising(result)
    assert projection.provider_relationships[0].relationship.target_causebase_id == "provider:one"
    assert projection.provider_relationships[0].relationship.evidence_ids == ["ev:relationship"]


def test_missing_practice_remains_a_coverage_state_without_finance_or_relationship_promotion():
    missing = practice(
        observation_id="fp_missing",
        source_native_phrase="No practice found in scoped source",
        canonical_facets=(),
        lifecycle="unknown",
        coverage_status="not_yet_processed",
        evidence_ids=[],
    )
    result = project_fundraising(card(fundraising_practice_observed=[missing]))
    assert result.practices[0].coverage_status == "not_yet_processed"
    assert result.campaigns == ()
    assert result.provider_relationships == ()
