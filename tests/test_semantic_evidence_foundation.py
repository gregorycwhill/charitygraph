import hashlib

import pytest

from charitygraph.semantic_evidence_foundation import (DurableRepresentationStore, EvidenceFoundationError,
    REQUIRED_READINESS_CHECKS, build_readiness_artifact, require_ready_readiness, write_readiness_artifact)


def test_offline_replay_survives_temporary_copy_removal_and_preserves_provenance(tmp_path):
    store = DurableRepresentationStore(tmp_path / "private-archive")
    source_a = store.objects.put(b"source-a")
    source_b = store.objects.put(b"source-b")
    first = store.put(b"ACNC retained text", source_artifact_id=source_a.artifact_id, source_record_id="srcrec:a", source_version="v1", subject_id="subject:a", source_family="acnc_register", source_role="regulatory", retrieved_at="2026-10-09T00:00:00Z", provenance_ids=("acq:a", "srcdef:a"), locator={"kind": "native_text"})
    second = store.put(b"annual report retained text", source_artifact_id=source_b.artifact_id, source_record_id="srcrec:b", source_version="fy25", subject_id="subject:b", source_family="annual_report", source_role="organisation_report", retrieved_at="2026-10-09T00:00:00Z", provenance_ids=("acq:b", "srcdef:b"), locator={"kind": "native_text", "page": 1})
    view = store.freeze_view((first.representation_id, second.representation_id), view_kind="semantic_packet")
    temporary = tmp_path / "temporary-packet.txt"; temporary.write_text("discarded")
    temporary.unlink()
    replay = store.replay_view(view["view_id"])
    assert replay["view_hash"] == view["view_hash"]
    assert {hashlib.sha256(row["content"]).hexdigest() for row in replay["members"]} == {first.content_hash, second.content_hash}
    assert {tuple(row["provenance_ids"]) for row in replay["members"]} == {("acq:a", "srcdef:a"), ("acq:b", "srcdef:b")}


def test_tampered_representation_fails_closed(tmp_path):
    store = DurableRepresentationStore(tmp_path / "private-archive")
    source = store.objects.put(b"source")
    rep = store.put(b"derived", source_artifact_id=source.artifact_id, source_record_id="srcrec:a", source_version="v1", subject_id="subject:a", source_family="acnc_register", source_role="regulatory", retrieved_at="2026-10-09T00:00:00Z", provenance_ids=("acq:a",), locator={"kind": "native_text"})
    path = store._path(rep.representation_hash)
    path.write_text("{}")
    with pytest.raises(EvidenceFoundationError):
        store.read(rep.representation_id)


def test_readiness_is_hashable_and_blocks_provider_when_any_prerequisite_fails(tmp_path):
    checks = {key: {"passed": True, "detail": "verified"} for key in REQUIRED_READINESS_CHECKS}
    checks["ethos_reference_evaluable"] = {"passed": False, "detail": "no source-only reference"}
    artifact = write_readiness_artifact(tmp_path / "readiness.json", checks, context={"provider_calls": 0})
    assert artifact["state"] == "NOT_READY"
    with pytest.raises(EvidenceFoundationError, match="blocked"):
        require_ready_readiness(tmp_path / "readiness.json")
    assert build_readiness_artifact(checks, context={"provider_calls": 0}) == artifact
