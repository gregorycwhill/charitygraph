import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import charitygraph.product_value_context as context
from charitygraph.product_value_experiment import ExperimentCandidate, project_experiment_items


def _fixture_source(root: Path) -> tuple[Path, str]:
    root.mkdir(parents=True)
    representation_path = "representations/28004778081/acnc-entity-record.txt"
    representation = {
        "Abn": "28004778081",
        "LegalName": "Example Charity Limited",
        "StatementYear": "2025",
        "AdvancementOfEducation": False,
        "AdvancementOfReligion": False,
        "ReliefOfPoverty": True,
        "OtherPurposes": False,
        "ActivityOperating": True,
        "ActivityOperatingOverseas": False,
        "Programs": [{"Name": "Program A", "ProgramClassification": "Housing", "ProgramClassificationID": "168"}],
        "ActivityPersuitPurposesDescription": "The source reports a purpose and a delivered activity.",
    }
    raw = json.dumps(representation, ensure_ascii=False, separators=(",", ":")).encode()
    target = root / representation_path
    target.parent.mkdir(parents=True)
    target.write_bytes(raw)
    representation_hash = hashlib.sha256(raw).hexdigest()
    metadata = {
        "sources": [{
            "abn": "28004778081",
            "subject_name": "Example Charity",
            "subject_id": "subject:fixture",
            "legal_scope": "organisation",
            "source_artifact_id": "srcblob:fixture",
            "source_record_id": "srcrec:fixture",
            "representation_path": representation_path,
            "representation_sha256": representation_hash,
            "evidence_locator_id": "locator:fixture",
            "source_role": "historical_frozen_regulator_material",
            "source_family": "acnc_ais_bundle",
            "source_date": "unknown unless stated in supplied text",
            "retrieved_at": "not recorded in clean corpus manifest",
            "effective_period": None,
            "retention_decision_id": "retention:fixture",
            "provider_transmission_status": "authorized_exact_hash_subject_to_revalidation",
        }]
    }
    (root / "source-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    lock = {
        "lock_timestamp": "2026-09-14T02:44:55+00:00",
        "source_representation_sha256": {representation_path: representation_hash},
    }
    lock_bytes = json.dumps(lock, separators=(",", ":")).encode()
    (root / "source-only-baseline.lock.json").write_bytes(lock_bytes)
    return root, hashlib.sha256(lock_bytes).hexdigest()


def test_exact_structured_values_keep_scope_role_locator_and_unassigned_mixed_text(tmp_path, monkeypatch):
    source_root, lock_hash = _fixture_source(tmp_path / "source")
    monkeypatch.setattr(context, "SUBJECTS", {"28004778081": ("Example Charity", "scope:fixture")})
    generated_at = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    rows = context.derive_context_candidates(source_root, generated_at=generated_at, expected_lock_sha256=lock_hash)

    assert rows
    assert all(row["derivation_method"] == "DETERMINISTIC_STRUCTURED_EXTRACTION" for row in rows)
    assert all(row["scope_kind"] == "organisation" and row["scope_id"] == "scope:fixture" for row in rows)
    assert all(row["source_carrier_role"] == "historical_frozen_regulator_material" for row in rows)
    assert all(row["evidence_locator_ids"][0].startswith("locator:fixture#/") for row in rows)
    purpose = next(row for row in rows if row["proposition_type"] == "acnc_carried_charitable_purpose_field_value" and row["proposition"]["source_field_path"].endswith("ReliefOfPoverty"))
    assert purpose["proposition"]["source_field_value"] is True
    assert purpose["epistemic_status"] == "first_party_report_carried_by_regulator"
    mixed = next(row for row in rows if row["proposition_type"] == "acnc_carried_mixed_purpose_activity_description")
    assert mixed["north_star_section_ids"] == []
    assert mixed["mapping_status"] == "unassigned_mixed_purpose_activity_text_requires_human_atomization"
    program = next(row for row in rows if row["proposition_type"] == "acnc_carried_program_record")
    assert program["proposition"]["source_field_value"] == {
        "Name": "Program A", "ProgramClassification": "Housing", "ProgramClassificationID": "168",
    }


def test_extraction_fails_closed_on_lock_time_or_representation_mutation(tmp_path, monkeypatch):
    source_root, lock_hash = _fixture_source(tmp_path / "source")
    monkeypatch.setattr(context, "SUBJECTS", {"28004778081": ("Example Charity", "scope:fixture")})
    with pytest.raises(ValueError, match="after the accepted baseline lock"):
        context.derive_context_candidates(
            source_root,
            generated_at=datetime(2026, 9, 14, 2, 44, 55, tzinfo=timezone.utc),
            expected_lock_sha256=lock_hash,
        )
    representation = source_root / "representations/28004778081/acnc-entity-record.txt"
    representation.write_text(representation.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="representation hash mismatch"):
        context.derive_context_candidates(
            source_root,
            generated_at=datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
            expected_lock_sha256=lock_hash,
        )


def test_changed_lock_is_rejected_and_missing_structured_field_is_not_absence(tmp_path, monkeypatch):
    source_root, lock_hash = _fixture_source(tmp_path / "source")
    monkeypatch.setattr(context, "SUBJECTS", {"28004778081": ("Example Charity", "scope:fixture")})
    lock_path = source_root / "source-only-baseline.lock.json"
    lock_path.write_text(lock_path.read_text(encoding="utf-8").replace("02:44:55", "02:44:56"), encoding="utf-8")
    with pytest.raises(ValueError, match="locked source-only baseline changed"):
        context.derive_context_candidates(
            source_root,
            generated_at=datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
            expected_lock_sha256=lock_hash,
        )

    representation_path = source_root / "representations/28004778081/acnc-entity-record.txt"
    record = json.loads(representation_path.read_text(encoding="utf-8"))
    del record["ReliefOfPoverty"]
    raw = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode()
    representation_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    metadata_path = source_root / "source-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sources"][0]["representation_sha256"] = digest
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["source_representation_sha256"]["representations/28004778081/acnc-entity-record.txt"] = digest
    lock_bytes = json.dumps(lock, separators=(",", ":")).encode()
    lock_path.write_bytes(lock_bytes)
    new_lock_hash = hashlib.sha256(lock_bytes).hexdigest()
    rows = context.derive_context_candidates(
        source_root,
        generated_at=datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
        expected_lock_sha256=new_lock_hash,
    )
    assert not any(row["proposition"]["source_field_path"].endswith("ReliefOfPoverty") for row in rows)
    assert not any(row.get("coverage_state") == "not_found_in_reviewed_sources" for row in rows)


def test_candidate_only_preview_has_no_governed_or_projected_items(tmp_path, monkeypatch):
    source_root, lock_hash = _fixture_source(tmp_path / "source")
    monkeypatch.setattr(context, "SUBJECTS", {"28004778081": ("Example Charity", "scope:fixture")})
    generated_at = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
    rows = context.derive_context_candidates(source_root, generated_at=generated_at, expected_lock_sha256=lock_hash)
    preview = context.create_projection_preview(rows, generated_at)
    packet = context.create_adjudication_packet(rows, generated_at)

    assert preview["governed_items"] == preview["governed_coverage_states"] == preview["projected_items"] == 0
    subject = preview["subjects"][0]
    assert subject["explicit_coverage"]["retained_annual_report_representation"] == "not_processed"
    assert "not source silence" in subject["explicit_coverage"]["interpretation"]
    assert "leave blank until Greg adjudicates" in packet
    assert "REJECT_MISSINGNESS" in packet
    assert "- Rationale: \n" in packet


def test_experiment_projection_rejects_raw_candidates():
    candidate = ExperimentCandidate(
        candidate_id="candidate:raw-only", candidate_content_sha256="a" * 64,
        subject_id="subject:fixture", scope_id="scope:fixture", scope_kind="organisation",
        source_artifact_id="srcblob:fixture", source_record_id="srcrec:fixture",
        representation_sha256="b" * 64, retention_decision_id="retention:fixture",
        proposition_type="raw_context", proposition={"value": "candidate"},
        evidence_locator_ids=("locator:fixture#/field",), source_carrier_role="regulator",
        epistemic_status="source_claim", reviewed_evidence_universe_id="universe:fixture",
        candidate_producer_id="product-value-deterministic-context-v1",
    )
    with pytest.raises(ValidationError):
        project_experiment_items((candidate,))
