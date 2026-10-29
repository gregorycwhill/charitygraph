from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from charitygraph.phase5_t4b_source_answer_projection import build_source_answer_projection
from charitygraph.phase5_t4c_private_answer_brief import (
    BriefCompositionError,
    compose_private_answer_brief,
)


MANIFEST = Path(__file__).parents[1] / "evidence" / "gate4-t3-five-subject-v1" / "selected-binding-manifest.json"
REPRESENTATION_ROOT = Path(r"C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations")

LABELS = {
    "subject:02649cdcb42049bb8dedd30f2333e150": "Guide Dogs NSW/ACT",
    "subject:0889b4decb854e71ab4784479ca95c03": "Human Appeal International Australia",
    "subject:16fba76fde2242d5870835b18b4e8b8d": "Peter & Lyndy White Foundation",
    "subject:1823309bdd06417c9928033603cb6e39": "OzHarvest",
    "subject:1a9ec5de3fc043ff9226fb95a6cae31b": "Islamic Relief Australia",
}


def _projection():
    return build_source_answer_projection(
        manifest_path=MANIFEST,
        representation_root=REPRESENTATION_ROOT,
    )


def test_composes_five_subjects_fifteen_slots_and_ten_hash_bindings():
    brief = compose_private_answer_brief(_projection(), subject_labels=LABELS)

    assert len(brief.subjects) == 5
    assert len(brief.answer_slots) == 15
    assert len(brief.source_hash_bindings) == 10
    assert {subject.display_name for subject in brief.subjects} == set(LABELS.values())
    assert len({digest for _source_record_id, digest in brief.source_hash_bindings}) == 10
    assert len(brief.north_star_coverage) == 20
    assert brief.north_star_coverage[-1].section_id == 20


def test_supported_comparison_values_keep_provenance_and_period_basis():
    brief = compose_private_answer_brief(_projection(), subject_labels=LABELS)

    for subject in brief.subjects:
        values = subject.comparison.__dict__.values()
        cited_values = [value for value in values if hasattr(value, "field_basis")]
        assert len(cited_values) == 13
        assert all(value.subject_id == subject.subject_id for value in cited_values)
        assert all(value.scope_id == subject.scope_id for value in cited_values)
        assert all(value.fact_vs_source_statement_vs_inference == "fact" for value in cited_values)
        assert all(value.source_record_id.startswith("srcrec:") for value in cited_values)
        assert all(len(value.representation_sha256) == 64 for value in cited_values)
        assert all(value.field_basis for value in cited_values)
        assert subject.comparison.reporting_period.reporting_period is not None
        assert subject.comparison.reporting_period.source_family == "acnc_ais_bundle"


def test_currentness_missingness_is_preserved_and_not_negative():
    brief = compose_private_answer_brief(_projection(), subject_labels=LABELS)

    for subject in brief.subjects:
        currentness = subject.currentness
        assert currentness.answer_state == "unanswered"
        assert currentness.answer is None
        assert currentness.missingness is not None
        assert currentness.missingness["source_silence_is_not_absence"] is True
        assert set(currentness.missingness["dimensions"]) == {
            "current_giving_terms",
            "current_service_capacity",
            "outcomes_or_effectiveness",
            "governance",
            "conduct_or_adverse_history",
        }


def test_deterministic_replay_and_zero_side_effects():
    first = compose_private_answer_brief(_projection(), subject_labels=LABELS)
    second = compose_private_answer_brief(_projection(), subject_labels=dict(reversed(list(LABELS.items()))))

    assert first.document == second.document
    assert first.side_effects == {
        "provider_calls": 0,
        "transport_requests": 0,
        "budget_reservations": 0,
        "source_acquisitions": 0,
        "publications": 0,
        "sqlite_opens": 0,
    }


def test_tampered_answer_hash_binding_is_rejected():
    projection = _projection()
    first = projection.records[0]
    citation = replace(first.source_references[0], representation_sha256="0" * 64)
    tampered_record = replace(
        first,
        representation_sha256="0" * 64,
        source_references=(citation,),
    )
    tampered = replace(projection, records=(tampered_record,) + projection.records[1:])

    with pytest.raises(BriefCompositionError, match="hash inventory"):
        compose_private_answer_brief(tampered, subject_labels=LABELS)


def test_nonzero_projection_side_effect_is_rejected():
    projection = _projection()
    tampered = replace(projection, side_effects={**projection.side_effects, "publications": 1})

    with pytest.raises(BriefCompositionError, match="side effect"):
        compose_private_answer_brief(tampered, subject_labels=LABELS)


def test_display_labels_cannot_introduce_an_unknown_subject():
    with pytest.raises(BriefCompositionError, match="unknown subject"):
        compose_private_answer_brief(
            _projection(),
            subject_labels={**LABELS, "subject:not-in-cohort": "Invented"},
        )
