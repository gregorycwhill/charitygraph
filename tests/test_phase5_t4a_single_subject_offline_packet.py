from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from charitygraph import phase5_t4a_single_subject_offline_packet as packet_module
from charitygraph.phase5_governed_source_binding import SELECTED_ROWS
from charitygraph.phase5_t4a_single_subject_offline_packet import build_single_subject_offline_packet


ARCHIVE_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects")
SUBJECT_ID = SELECTED_ROWS[0].subject_id
EXECUTION_CONTEXT = {
    "bridge_fence": "v51",
    "branch": "gate3-cg406-remediation",
    "head": "372ca4183ee9511d99e3c06bab1a5c17bf0aa4b5",
}


def _build(tmp_path: Path, **kwargs):
    return build_single_subject_offline_packet(
        source_archive_root=kwargs.pop("archive", ARCHIVE_ROOT),
        work_root=tmp_path / "work",
        execution_context=kwargs.pop("execution_context", EXECUTION_CONTEXT),
        subject_id=kwargs.pop("subject_id", SUBJECT_ID),
        **kwargs,
    )


def _copy_archive(destination: Path, *, tamper: int | None = None) -> Path:
    for row in SELECTED_ROWS:
        source = ARCHIVE_ROOT / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target = destination / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered" if row.ordinal == tamper else source.read_bytes())
    return destination


def test_real_subject_two_records_are_deterministic_and_no_send(tmp_path):
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")
    assert first.document == second.document
    assert first.packet_sha256 == second.packet_sha256
    assert first.document["status"] == "ready"
    assert first.document["subject"]["subject_id"] == SUBJECT_ID
    assert len(first.document["source_records"]) == 2
    assert {row["source_family"] for row in first.document["source_records"]} == {"acnc_register", "acnc_ais_bundle"}
    assert first.document["contracts"]["t3_manifest"]["schema"].endswith("/v2")
    assert first.document["contracts"]["rights_projection"]["migration_version"] == 29
    assert first.document["provider_processing"]["send_authorization"] == "not_authorized_for_send"
    assert first.document["side_effects"] == {
        "provider_calls": 0, "transport_requests": 0, "budget_reservations": 0,
        "cost_entries": 0, "source_acquisitions": 0, "publications": 0,
    }
    assert "source_body" not in str(first.document)


def test_wrong_schema_version_is_typed_and_fail_closed(tmp_path, monkeypatch):
    def reject(_task):
        raise ValueError("schema-version binding mismatch")

    monkeypatch.setattr(packet_module, "resolve_contract", reject)
    result = _build(tmp_path)
    assert result.document["status"] == "blocked"
    assert any(item.code == "schema_version_mismatch" for item in result.diagnostics)
    assert result.document["provider_processing"]["send_authorization"] == "not_authorized_for_send"


@pytest.mark.parametrize("case", ("subject", "representation"))
def test_subject_and_representation_drift_are_rejected(tmp_path, case):
    if case == "subject":
        result = _build(tmp_path, subject_id="subject:not-in-retained-t3-cohort")
    else:
        result = _build(tmp_path, archive=_copy_archive(tmp_path / "archive", tamper=2))
    assert result.document["status"] == "blocked"
    codes = {item.code for item in result.diagnostics}
    assert "subject_binding_unavailable" in codes if case == "subject" else "evidence_unavailable" in codes
    assert result.document["side_effects"]["provider_calls"] == 0


def test_catalog_has_no_factory_or_budget_side_effects(tmp_path):
    result = _build(tmp_path)
    assert result.document["side_effects"]["transport_requests"] == 0
    catalog = tmp_path / "work" / "catalog.sqlite3"
    with sqlite3.connect(catalog) as connection:
        counts = tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            "tasks", "task_attempts", "physical_attempts", "budget_reservations", "provider_receipts", "cost_entries",
        ))
    assert counts == (0, 0, 0, 0, 0, 0)
