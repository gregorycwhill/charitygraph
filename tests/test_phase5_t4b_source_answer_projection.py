from __future__ import annotations

import json
from pathlib import Path

import pytest

from charitygraph.contracts.canonical import canonical_sha256
from charitygraph.phase5_t4b_source_answer_projection import (
    QUESTION_ACTIVITY,
    QUESTION_CURRENTNESS,
    QUESTION_SCALE,
    ProjectionValidationError,
    build_source_answer_projection,
)


MANIFEST = Path(__file__).parents[1] / "evidence" / "gate4-t3-five-subject-v1" / "selected-binding-manifest.json"
REPRESENTATION_ROOT = Path(r"C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations")


def _copy_representations(destination: Path, *, tamper: str | None = None) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for row in manifest["rows"]:
        digest = row["representation_sha256"]
        source = REPRESENTATION_ROOT / "objects" / "sha256" / digest[:2] / digest
        target = destination / "objects" / "sha256" / digest[:2] / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered" if digest == tamper else source.read_bytes())
    return destination


def _copy_manifest(destination: Path, *, row_update: dict[str, object]) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["rows"][0].update(row_update)
    manifest["manifest_identity_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_identity_sha256"}
    )
    path = destination / "selected-binding-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _copy_manifest_with_update(destination: Path, *, update: dict[str, object]) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest.update(update)
    path = destination / "selected-binding-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def test_real_cohort_emits_fifteen_slots_and_cites_all_ten_representations():
    projection = build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)

    assert len(projection.records) == 15
    assert len(set(projection.representation_hashes)) == 10
    assert {record.subject_id for record in projection.records}.__len__() == 5
    assert {record.question_id for record in projection.records} == {
        QUESTION_ACTIVITY,
        QUESTION_SCALE,
        QUESTION_CURRENTNESS,
    }
    assert all(record.source_record_id.startswith("srcrec:") for record in projection.records)
    assert all(record.representation_locator.endswith(record.representation_sha256) for record in projection.records)
    assert projection.side_effects == {
        "provider_calls": 0,
        "transport_requests": 0,
        "budget_reservations": 0,
        "source_acquisitions": 0,
        "publications": 0,
        "sqlite_opens": 0,
    }


def test_projection_is_deterministic_and_separates_structured_answers():
    first = build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)
    second = build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)

    assert first.document == second.document
    assert all(record.fact_vs_source_statement_vs_inference == "fact" for record in first.records if record.answer_state == "supported")
    assert not any("SummaryOfActivities" in field for record in first.records for field in record.field_basis)


def test_hash_tampering_is_rejected(tmp_path: Path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tampered_digest = manifest["rows"][0]["representation_sha256"]
    representations = _copy_representations(tmp_path / "representations", tamper=tampered_digest)

    with pytest.raises(ProjectionValidationError, match="hash mismatch"):
        build_source_answer_projection(manifest_path=MANIFEST, representation_root=representations)


@pytest.mark.parametrize(
    "update",
    [
        {"selected_manifest_sha256": "0" * 64},
        {"manifest_identity_sha256": "0" * 64},
    ],
)
def test_manifest_identity_metadata_tampering_is_rejected(tmp_path: Path, update: dict[str, object]):
    manifest = _copy_manifest_with_update(tmp_path, update=update)

    with pytest.raises(ProjectionValidationError, match="manifest identity"):
        build_source_answer_projection(manifest_path=manifest, representation_root=REPRESENTATION_ROOT)


@pytest.mark.parametrize(
    "row_update",
    [
        {"source_record_id": "srcrec:" + "0" * 64},
        {"rights_record_id": "0" * 64},
    ],
)
def test_t3_source_record_and_rights_binding_tampering_is_rejected(tmp_path: Path, row_update: dict[str, object]):
    manifest = _copy_manifest(tmp_path, row_update=row_update)

    with pytest.raises(ProjectionValidationError, match="source-record/rights binding"):
        build_source_answer_projection(manifest_path=manifest, representation_root=REPRESENTATION_ROOT)


@pytest.mark.parametrize("row_update", [{"subject_id": "subject:wrong"}, {"scope_id": "scope:wrong"}])
def test_cross_subject_or_scope_manifest_drift_is_rejected(tmp_path: Path, row_update: dict[str, object]):
    manifest = _copy_manifest(tmp_path, row_update=row_update)

    with pytest.raises(ProjectionValidationError, match="binding mismatch"):
        build_source_answer_projection(manifest_path=manifest, representation_root=REPRESENTATION_ROOT)


def test_reporting_period_and_provenance_are_retained():
    projection = build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)
    scale = [record for record in projection.records if record.question_id == QUESTION_SCALE]

    assert len(scale) == 5
    assert all(record.answer_state == "supported" for record in scale)
    assert all(record.reporting_period == record.answer["reporting_period"] for record in scale)
    assert all(any(field.endswith("FinReportFrom") for field in record.field_basis) for record in scale)
    assert all(any(field.endswith("FinReportTo") for field in record.field_basis) for record in scale)
    assert all(record.source_family == "acnc_ais_bundle" for record in scale)


def test_currentness_missingness_is_explicit_not_negative():
    projection = build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)
    unanswered = [record for record in projection.records if record.question_id == QUESTION_CURRENTNESS]

    assert len(unanswered) == 5
    assert all(record.answer_state == "unanswered" and record.answer is None for record in unanswered)
    assert all(record.missingness["source_silence_is_not_absence"] is True for record in unanswered)
    assert all(
        set(record.missingness["dimensions"])
        == {"current_giving_terms", "current_service_capacity", "outcomes_or_effectiveness", "governance", "conduct_or_adverse_history"}
        for record in unanswered
    )


def test_read_only_call_creates_no_files(tmp_path: Path):
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    build_source_answer_projection(manifest_path=MANIFEST, representation_root=REPRESENTATION_ROOT)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert before == after == []
