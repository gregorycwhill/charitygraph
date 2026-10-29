import json
from pathlib import Path

from charitygraph.phase5_governed_source_binding import (
    SELECTED_ROWS,
    SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    SOURCE_EVIDENCE_PROVENANCE_REVISION,
    ExclusionEvidence,
    build_selected_binding_manifest,
)


ARCHIVE_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects")
EXECUTION_CONTEXT = {
    "bridge_fence": "v47",
    "branch": "gate3-cg406-remediation",
    "head": "9e4c36cdc5f7383eca58b81fdc6f23238f7cae17",
}


def _copy_selected_archive(destination: Path, *, tampered_ordinal: int | None = None) -> Path:
    for row in SELECTED_ROWS:
        source = ARCHIVE_ROOT / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        assert source.is_file(), f"retained test object missing: {source}"
        target = destination / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered") if row.ordinal == tampered_ordinal else target.write_bytes(source.read_bytes())
    return destination


def _build(tmp_path: Path, *, exclusions=None, archive_root: Path = ARCHIVE_ROOT):
    return build_selected_binding_manifest(
        source_archive_root=archive_root,
        work_root=tmp_path / "work",
        execution_context=EXECUTION_CONTEXT,
        exclusions=exclusions,
    )


def test_fixed_cohort_binds_exact_rows_without_source_bytes_or_downstream_work(tmp_path):
    result = _build(tmp_path)
    manifest = result.manifest

    assert len(manifest["rows"]) == 10
    assert manifest["source_bytes_included"] is False
    assert result.preflight_task_count == 10
    assert result.downstream_task_count == 0
    assert manifest["rights_policy"]["id"] == "CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1"
    assert manifest["rights_policy"]["version"] == "1.0.0"
    assert manifest["rights_policy"]["applicable_operation"] == "local_private_retention_and_processing"
    assert manifest["rights_policy"]["source_families"] == [
        "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
        "annual_report", "wikipedia_wikimedia", "pfra",
    ]
    assert manifest["summary"] == {
        "candidate_rows": 10,
        "bound_rows": 10,
        "eligible_private_local_retention_rows": 10,
        "bound_not_task_eligible_rows": 0,
        "excluded_rows": 0,
        "preflight_authority_tasks": 10,
        "downstream_tasks": 0,
        "provider_requests": 0,
        "aud_spend": "0.00",
    }

    for candidate, row in zip(SELECTED_ROWS, manifest["rows"]):
        assert row["source_record_id"] == candidate.source_record_id
        assert row["acquisition_receipt_id"] == candidate.acquisition_receipt_id
        assert row["source_artifact_id"] == candidate.source_artifact_id
        assert row["source_sha256"] == candidate.source_sha256
        assert row["representation_artifact_id"].startswith("artifact:")
        assert row["representation_artifact_id"] != row["source_artifact_id"]
        assert row["representation_sha256"] == candidate.source_sha256
        assert row["scope_id"].startswith("scope:")
        assert len(row["rights_record_id"]) == 64
        assert row["status"] == "eligible_private_local_retention"
        assert row["rights_policy_id"] == "CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1"
        assert row["rights_policy_version"] == "1.0.0"
        assert row["provider_processing_status"] == "blocked_provider_contract_not_bound"
        assert row["public_redistribution_status"] == "not_assessed"
        assert row["downstream_tasks"] == 0
        assert row["technical_gaps"] == ("provider_contract_identity_and_version",)

    encoded = json.dumps(manifest, sort_keys=True).encode()
    assert b"source_body" not in encoded
    assert b"raw_bytes" not in encoded


def test_replay_is_byte_and_projection_deterministic(tmp_path):
    first = build_selected_binding_manifest(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path / "first",
        execution_context=EXECUTION_CONTEXT,
    )
    second = build_selected_binding_manifest(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path / "second",
        execution_context=EXECUTION_CONTEXT,
    )

    assert first.manifest_bytes == second.manifest_bytes
    assert first.projection_snapshot_hash == second.projection_snapshot_hash
    assert first.manifest["manifest_identity_sha256"] == second.manifest["manifest_identity_sha256"]


def test_explicit_exclusion_lowers_only_that_row_to_zero_work(tmp_path):
    result = _build(
        tmp_path,
        exclusions={
            4: ExclusionEvidence(
                material="the retained ACNC AIS object",
                authority="Product Owner direction 2026-10-29",
                wording="concrete exclusion evidence supplied for test",
                affected_operation="provider transmission",
            )
        },
    )

    rows = {row["ordinal"]: row for row in result.manifest["rows"]}
    assert rows[4]["status"] == "excluded"
    assert rows[4]["rights_record_id"] is None
    assert rows[4]["downstream_tasks"] == 0
    assert rows[4]["exclusion_evidence"]["affected_operation"] == "provider transmission"
    assert result.manifest["summary"]["excluded_rows"] == 1
    assert result.manifest["summary"]["downstream_tasks"] == 0


def test_hash_mismatch_fails_closed_for_one_candidate_without_substitution(tmp_path):
    archive = _copy_selected_archive(tmp_path / "archive", tampered_ordinal=2)
    result = _build(tmp_path, archive_root=archive)

    rows = {row["ordinal"]: row for row in result.manifest["rows"]}
    assert rows[2]["status"] == "mismatched"
    assert rows[2]["rights_record_id"] is None
    assert rows[2]["representation_artifact_id"] is None
    assert rows[2]["downstream_tasks"] == 0
    assert result.manifest["summary"]["bound_rows"] == 9
    assert result.manifest["summary"]["downstream_tasks"] == 0


def test_bridge_execution_fence_cannot_be_claimed_as_source_provenance_epoch(tmp_path):
    result = _build(tmp_path)
    manifest = result.manifest

    assert "fence" not in manifest
    assert manifest["schema"] == "charitygraph.gate4.t3.selected-binding-manifest/v2"
    assert manifest["source_evidence_provenance"] == {
        "epoch": SOURCE_EVIDENCE_PROVENANCE_EPOCH,
        "producer_revision": SOURCE_EVIDENCE_PROVENANCE_REVISION,
        "target": "gate3-cg406-remediation@cef0e792d8826697db735216be9b3f918c7e44ff",
        "selected_manifest_sha256": "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9",
    }
    assert manifest["bridge_execution_context"] == EXECUTION_CONTEXT
    assert manifest["source_evidence_provenance"]["epoch"] != manifest["bridge_execution_context"]["bridge_fence"]
