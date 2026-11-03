from __future__ import annotations

from pathlib import Path

from charitygraph.phase5_governed_source_binding import SELECTED_ROWS, ExclusionEvidence
from charitygraph.contracts.canonical import canonical_sha256
from charitygraph.phase5_t4a_pilot_packet import build_t4a_pilot_packet


ARCHIVE_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects")
EXECUTION_CONTEXT = {
    "bridge_fence": "v48",
    "branch": "gate3-cg406-remediation",
    "head": "18668e7b197086ab95e1faf6ba5aa665377164dd",
}


def _copy_archive(destination: Path, *, omit: int | None = None, tamper: int | None = None) -> Path:
    for row in SELECTED_ROWS:
        if row.ordinal == omit:
            continue
        source = ARCHIVE_ROOT / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target = destination / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered" if row.ordinal == tamper else source.read_bytes())
    return destination


def _build(tmp_path: Path, **kwargs):
    return build_t4a_pilot_packet(
        source_archive_root=kwargs.pop("archive", ARCHIVE_ROOT),
        work_root=tmp_path / "work",
        execution_context=kwargs.pop("execution_context", EXECUTION_CONTEXT),
        **kwargs,
    )


def test_packet_hash_and_replay_are_stable_and_no_send(tmp_path):
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")

    assert first.packet_sha256 == second.packet_sha256
    assert first.packet_id == second.packet_id
    assert first.as_dict() == second.as_dict()
    assert first.packet_sha256 == canonical_sha256({key: value for key, value in first.as_dict().items() if key != "packet_identity_sha256"})
    assert len(first.task_keys) == 10
    assert first.as_dict()["preflight"]["status"] == "blocked"
    assert first.as_dict()["preflight"]["send"]["status"] == "blocked"


def test_packet_binds_five_subjects_and_ten_sources_with_provenance_split(tmp_path):
    packet = _build(tmp_path)
    document = packet.as_dict()
    assert len(packet.subject_ids) == 5
    assert len(packet.source_bindings) == 10
    assert len(packet.task_keys) == 10
    assert packet.provenance.source_epoch == "v45"
    assert packet.provenance.bridge_fence == EXECUTION_CONTEXT["bridge_fence"]
    assert packet.provenance.source_epoch != packet.provenance.bridge_fence
    assert document["rights"]["status"] == "accepted"
    assert document["semantic_contract"]["prompt_sha256"]
    assert "prompt_template" not in document["semantic_contract"]
    assert document["provider_processing"]["status"] == "blocked"
    assert document["provider_contract"] == {
        "status": "unbound", "contract_id": None, "project_id": None,
        "service": None, "model": None, "version": None,
    }
    assert all(item["idempotency_key"].startswith("idempotency:") for item in document["task_keys"])


def test_excluded_source_is_retained_as_exclusion_and_blocks_packet(tmp_path):
    packet = _build(tmp_path, exclusions={
        4: ExclusionEvidence(
            material="retained ACNC AIS object",
            authority="bounded negative-path test",
            wording="excluded for packet preflight verification",
            affected_operation="provider transmission",
        )
    })
    row = next(row for row in packet.source_bindings if row.ordinal == 4)
    assert row.status == "excluded"
    assert packet.tasks == ()
    assert packet.as_dict()["preflight"]["status"] == "blocked"


def test_altered_content_digest_blocks_without_task_lowering(tmp_path):
    packet = _build(tmp_path, archive=_copy_archive(tmp_path / "tampered", tamper=2))
    row = next(row for row in packet.source_bindings if row.ordinal == 2)
    assert row.status == "mismatched"
    assert packet.tasks == ()
    assert packet.as_dict()["preflight"]["side_effects"]["provider_calls"] == 0


def test_epoch_confusion_is_fail_closed(tmp_path):
    packet = _build(tmp_path, source_evidence_epoch="v44")
    assert packet.tasks == ()
    assert packet.provenance.source_epoch == "v45"
    assert packet.provenance.requested_source_epoch == "v44"
    assert packet.provenance.bridge_fence == EXECUTION_CONTEXT["bridge_fence"]
    assert any("source evidence epoch" in reason for reason in packet.blocked_reasons)


def test_missing_provider_contract_is_explicit_and_has_zero_side_effects(tmp_path):
    packet = _build(tmp_path)
    document = packet.as_dict()
    assert document["provider_contract"]["contract_id"] is None
    assert document["provider_processing"]["eligibility"] == "not_eligible_without_bound_contract"
    assert document["preflight"]["side_effects"] == {
        "provider_calls": 0, "model_outputs": 0, "reservations": 0,
        "cost_entries": 0, "acquisitions": 0, "publications": 0,
    }
    catalog = tmp_path / "work" / "catalog.sqlite3"
    assert catalog.is_file()
    import sqlite3
    with sqlite3.connect(catalog) as connection:
        counts = tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            "tasks", "task_attempts", "physical_attempts", "budget_reservations", "provider_receipts", "cost_entries",
        ))
    assert counts == (0, 0, 0, 0, 0, 0)
