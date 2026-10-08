from datetime import datetime, timezone

import pytest

from charitygraph.contracts import ArtifactRef, EvidenceFragment, SchemaRef, SourceRecord, deterministic_id
from charitygraph.retained_capture import RetainedCapture, RetainedCaptureUniverse, build_ethos_notability_packet


NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:retained-capture-test:1.0", schema_version="1.0")
SOURCE_HASH = "a" * 64
REP_HASH = "b" * 64
FRAGMENT_HASH = "c" * 64
SOURCE_BLOB = "srcblob:" + SOURCE_HASH
REPRESENTATION = "artifact:" + REP_HASH


def capture(*, source_blob=SOURCE_BLOB, fragment_content_ref=REPRESENTATION):
    source_identity = {"source_family": "fixture", "source_version": "1", "source_locator": "fixture:retained", "payload_hash": SOURCE_HASH}
    source = SourceRecord(
        record_id=deterministic_id("srcrec:", source_identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_family="fixture", source_role="fixture", source_version="1", source_locator="fixture:retained",
        retrieved_at=NOW, observed_at=NOW, payload_ref=SOURCE_BLOB, payload_hash=SOURCE_HASH,
    )
    fragment_identity = {"source_record_id": source.record_id, "locator": "p1:1", "fragment_hash": FRAGMENT_HASH,
                         "selection_method": "central-preparation", "selection_policy_version": "1"}
    fragment = EvidenceFragment(
        record_id=deterministic_id("evidence:", fragment_identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_record=ArtifactRef(artifact_id=source.record_id, content_hash="d" * 64, schema=SCHEMA),
        fragment_kind="text", locator="p1:1", content_ref=fragment_content_ref, fragment_hash=FRAGMENT_HASH,
        selection_method="central-preparation", selection_policy_version="1", observed_at=NOW,
    )
    return RetainedCapture(
        source_record=source, source_blob=ArtifactRef(artifact_id=source_blob, content_hash=SOURCE_HASH, schema=SCHEMA),
        representation=ArtifactRef(artifact_id=REPRESENTATION, content_hash=REP_HASH, schema=SCHEMA),
        representation_input_artifact_ids=(SOURCE_BLOB,), evidence_fragment=fragment,
        text="A centrally retained bounded statement.", source_role="supporting",
    )


def test_retained_capture_builds_existing_347_packet_with_continuous_lineage():
    retained = capture()
    packet = build_ethos_notability_packet(RetainedCaptureUniverse(
        subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained,)
    ))
    assert packet.packet_id == "packet:" + packet.packet_hash
    assert packet.evidence[0].evidence_id == retained.evidence_fragment.record_id
    assert packet.evidence[0].source_record_id == retained.source_record.record_id
    assert packet.evidence[0].lineage_id == retained.lineage_id
    assert packet.evidence[0].text == retained.text


def test_packet_identity_changes_with_retained_capture_content_and_never_acquires():
    retained = capture()
    universe = RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained,))
    first = build_ethos_notability_packet(universe)
    changed = retained.model_copy(update={"text": "A changed retained bounded statement."})
    second = build_ethos_notability_packet(universe.model_copy(update={"captures": (changed,)}))
    assert first.packet_hash != second.packet_hash
    # The module has no acquisition boundary: packet construction works with no provider or network fixture.
    assert build_ethos_notability_packet(universe).packet_hash == first.packet_hash


@pytest.mark.parametrize("change, message", [
    ("source_blob", "payload_ref"),
    ("fragment_content_ref", "content_ref"),
])
def test_retained_capture_rejects_broken_source_representation_fragment_lineage(change, message):
    kwargs = {change: "srcblob:" + "e" * 64 if change == "source_blob" else "artifact:" + "e" * 64}
    with pytest.raises(ValueError, match=message):
        capture(**kwargs)
