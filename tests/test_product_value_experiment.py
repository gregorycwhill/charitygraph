from datetime import date, datetime, timezone
from hashlib import sha256

import pytest
from pydantic import ValidationError

from charitygraph.product_value_experiment import (
    ExperimentCandidate,
    PropositionAdjudication,
    create_experiment_governed_item,
    project_experiment_items,
    verify_candidate_bytes,
)
from charitygraph.source_rights import BoundedLocalRetentionDecision


def candidate(**overrides):
    raw = b'{"candidate":"immutable fixture"}'
    values = {
        "candidate_id": "candidate:fixture-1",
        "candidate_content_sha256": sha256(raw).hexdigest(),
        "subject_id": "subject:fixture-1",
        "scope_id": "scope:fixture-1",
        "scope_kind": "organisation",
        "source_artifact_id": "srcblob:fixture-1",
        "source_record_id": "srcrec:fixture-1",
        "representation_sha256": "b" * 64,
        "retention_decision_id": "retention:fixture-1",
        "proposition_type": "stated_commitment",
        "proposition": {"statement": "source-reported commitment"},
        "evidence_locator_ids": ("evidence:fixture-1",),
        "source_carrier_role": "first_party_claim",
        "epistemic_status": "source_claimed",
        "reviewed_evidence_universe_id": "universe:fixture-1",
        "coverage_state": None,
        "source_period_start": date(2025, 1, 1),
        "source_period_end": date(2025, 12, 31),
        "candidate_producer_id": "model-task:fixture-1",
    }
    values.update(overrides)
    return ExperimentCandidate(**values), raw


def decision(cand, **overrides):
    values = {
        "adjudication_id": "adjudication:fixture-1",
        "candidate_id": cand.candidate_id,
        "candidate_content_sha256": cand.candidate_content_sha256,
        "disposition": "ACCEPT",
        "adjudicator_id": "human:reviewer-1",
        "adjudicator_role": "independent_human_proposition_adjudicator",
        "adjudicated_at": datetime(2026, 9, 14, tzinfo=timezone.utc),
        "adjudication_version": "1.0",
        "rationale": "Exact source and scope reviewed.",
        "independent_of_candidate_producer": True,
    }
    values.update(overrides)
    return PropositionAdjudication(**values)


def test_experiment_item_requires_exact_candidate_and_independent_human_acceptance():
    cand, raw = candidate()
    verify_candidate_bytes(cand, raw)
    item = create_experiment_governed_item(cand, decision(cand))
    assert item is not None
    projection = project_experiment_items((item,))
    assert projection.items == (item,)
    assert item.canonical_public is False
    assert item.candidate_content_sha256 == cand.candidate_content_sha256
    assert item.source_artifact_id == cand.source_artifact_id
    assert item.source_record_id == cand.source_record_id
    assert item.representation_sha256 == cand.representation_sha256

    with pytest.raises(ValueError, match="hash"):
        verify_candidate_bytes(cand, b"changed candidate")
    with pytest.raises(ValueError, match="exact immutable candidate"):
        create_experiment_governed_item(cand, decision(cand, candidate_content_sha256="0" * 64))
    with pytest.raises(ValueError, match="cannot adjudicate"):
        create_experiment_governed_item(cand, decision(cand, adjudicator_id=cand.candidate_producer_id))


def test_rejected_candidate_never_enters_governed_namespace_and_minor_fix_is_separate():
    cand, _ = candidate()
    rejected = decision(cand, disposition="REJECT_SCOPE")
    assert create_experiment_governed_item(cand, rejected) is None

    fixed = {"statement": "corrected, source-bounded commitment"}
    accepted = decision(
        cand,
        disposition="ACCEPT_MINOR_CORRECTION",
        corrected_governed_representation=fixed,
    )
    item = create_experiment_governed_item(cand, accepted)
    assert item is not None
    assert item.governed_representation == fixed
    assert cand.proposition == {"statement": "source-reported commitment"}

    with pytest.raises(ValidationError, match="corrected governed representation"):
        decision(cand, disposition="ACCEPT_MINOR_CORRECTION")


def test_local_retention_is_orthogonal_and_fails_closed():
    valid = BoundedLocalRetentionDecision(
        decision_id="retention:fixture-1",
        source_artifact_id="srcblob:fixture-1",
        source_record_id="srcrec:fixture-1",
        source_role="financial_report",
        acquisition_lineage_ids=("acq:fixture-1",),
        representation_sha256="a" * 64,
        rights_basis="statutory_exception",
        representation_class="bounded_excerpt",
        purpose="adjudication",
        scope="One bounded report excerpt for a private proposition review.",
        selected_page_count=4,
        source_page_count=40,
        lawful_access_confirmed=True,
        circumvention_used=False,
        explicit_prohibition_found=False,
        retention_status="authorized",
        lifecycle_status="active_until_review",
        review_due_on=date(2027, 9, 14),
        provider_transmission_status="not_assessed",
    )
    assert valid.public_redistribution_status == "not_authorized"

    with pytest.raises(ValidationError, match="lawful access"):
        BoundedLocalRetentionDecision(**{
            **valid.model_dump(), "lawful_access_confirmed": False,
        })
    with pytest.raises(ValidationError, match="separate provider-rights"):
        BoundedLocalRetentionDecision(**{
            **valid.model_dump(), "provider_transmission_status": "authorized",
        })
    with pytest.raises(ValidationError, match="own separate rights decision"):
        BoundedLocalRetentionDecision(**{
            **valid.model_dump(), "public_redistribution_status": "authorized_under_separate_basis",
        })
    separately_authorized = BoundedLocalRetentionDecision(**{
        **valid.model_dump(),
        "public_redistribution_status": "authorized_under_separate_basis",
        "public_redistribution_decision_id": "rightsdecision:public-separate",
    })
    assert separately_authorized.retention_status == "authorized"
    with pytest.raises(ValidationError, match="five selected pages and 20 percent"):
        BoundedLocalRetentionDecision(**{
            **valid.model_dump(), "selected_page_count": 6, "source_page_count": 40,
        })
    with pytest.raises(ValidationError, match="five selected pages and 20 percent"):
        BoundedLocalRetentionDecision(**{
            **valid.model_dump(), "selected_page_count": 5, "source_page_count": 20,
        })
