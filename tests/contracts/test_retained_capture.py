from datetime import datetime, timezone
import json

import pytest

from charitygraph.contracts import ArtifactRef, EvidenceFragment, SchemaRef, SourceRecord, canonical_sha256, deterministic_id
from charitygraph.ethos_history import EthosObservation, NotableEvent, notable_event_candidate_id, project_ethos_observation, project_notable_event
from charitygraph.ethos_notability_extraction import ProviderResponse, run_ethos_extraction, run_history_extraction, validate_bundle
from charitygraph.retained_capture import RetainedCapture, RetainedCaptureUniverse, RetainedSubjectBinding, build_ethos_notability_packet
from charitygraph.s0_ethos_notability_routing import route_domain


NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:retained-capture-test:1.0", schema_version="1.0")
SOURCE_HASH = "a" * 64
REP_HASH = "b" * 64
FRAGMENT_HASH = "c" * 64
SOURCE_BLOB = "srcblob:" + SOURCE_HASH
REPRESENTATION = "artifact:" + REP_HASH


def capture(*, source_blob=SOURCE_BLOB, fragment_content_ref=REPRESENTATION, locator="p1:1", fragment_hash=FRAGMENT_HASH, subject_id="subject:one"):
    source_identity = {"source_family": "fixture", "source_version": "1", "source_locator": "fixture:retained", "payload_hash": SOURCE_HASH}
    source = SourceRecord(
        record_id=deterministic_id("srcrec:", source_identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_family="fixture", source_role="fixture", source_version="1", source_locator="fixture:retained",
        retrieved_at=NOW, observed_at=NOW, payload_ref=SOURCE_BLOB, payload_hash=SOURCE_HASH,
    )
    fragment_identity = {"source_record_id": source.record_id, "locator": locator, "fragment_hash": fragment_hash,
                         "selection_method": "central-preparation", "selection_policy_version": "1"}
    fragment = EvidenceFragment(
        record_id=deterministic_id("evidence:", fragment_identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_record=ArtifactRef(artifact_id=source.record_id, content_hash="d" * 64, schema=SCHEMA),
        fragment_kind="text", locator=locator, content_ref=fragment_content_ref, fragment_hash=fragment_hash,
        selection_method="central-preparation", selection_policy_version="1", observed_at=NOW,
    )
    return RetainedCapture(
        source_record=source,
        subject_binding=RetainedSubjectBinding(
            binding_id="binding:" + canonical_sha256({
                "source_record_id": source.record_id, "subject_id": subject_id, "state": "resolved", "policy_version": "fixture-v1",
            }),
            source_record_id=source.record_id, subject_id=subject_id, policy_version="fixture-v1",
        ),
        source_blob=ArtifactRef(artifact_id=source_blob, content_hash=SOURCE_HASH, schema=SCHEMA),
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
    assert packet.evidence[0].source_blob_hash == SOURCE_HASH
    assert packet.evidence[0].fragment_locator == "p1:1"
    assert packet.evidence[0].subject_binding_id == retained.subject_binding.binding_id


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


def test_universe_fail_closes_on_conflicting_subject_binding_or_capture_identity():
    retained = capture()
    with pytest.raises(ValueError, match="subject binding"):
        RetainedCaptureUniverse(subject_id="subject:other", permitted_scope_ids=("scope:one",), captures=(retained,))
    conflicting = capture(locator="p2:1", fragment_hash="e" * 64).model_copy(update={"representation": ArtifactRef(artifact_id=REPRESENTATION, content_hash="e" * 64, schema=SCHEMA)})
    with pytest.raises(ValueError, match="conflicting representation"):
        RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained, conflicting))


def test_one_retained_source_can_feed_distinct_selection_versions_without_copying_capture():
    retained = capture()
    section_15 = build_ethos_notability_packet(RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained,), packet_selection_version="section-15-v1"))
    section_17 = build_ethos_notability_packet(RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained,), packet_selection_version="section-17-v1"))
    assert section_15.evidence[0].source_blob_hash == section_17.evidence[0].source_blob_hash == SOURCE_HASH
    assert section_15.packet_hash != section_17.packet_hash


def test_ethos_and_notable_history_reuse_one_capture_with_network_denied(monkeypatch):
    """Both semantic domains consume one retained capture; neither acquires."""
    import urllib.request

    retained = capture()
    universe = RetainedCaptureUniverse(
        subject_id="subject:one", permitted_scope_ids=("scope:one",), captures=(retained,)
    )
    packets = []

    class OfflineProvider:
        def extract(self, *, packet, **_):
            packets.append(packet)
            return ProviderResponse(
                '{"outcome":"abstain","ethos_candidates":[],"history_candidates":[],"reason":"offline fixture"}',
                "offline-fixture", "none",
            )

    def denied(*_, **__):
        raise AssertionError("semantic execution attempted network acquisition")

    monkeypatch.setattr(urllib.request, "urlopen", denied)
    import socket
    monkeypatch.setattr(socket, "create_connection", denied)
    ethos = run_ethos_extraction(universe, OfflineProvider())
    history = run_history_extraction(universe, OfflineProvider())
    assert ethos["validation"]["accepted"] and history["validation"]["accepted"]
    assert len(packets) == 2
    assert packets[0].evidence[0].source_blob_id == packets[1].evidence[0].source_blob_id == retained.source_blob.artifact_id
    assert packets[0].evidence[0].source_version == packets[1].evidence[0].source_version == "1"
    assert packets[0].evidence[0].lineage_id == packets[1].evidence[0].lineage_id == retained.lineage_id

    class DeliberateNetworkProvider:
        def extract(self, **_):
            urllib.request.urlopen("https://example.invalid/acquire")
            raise AssertionError("unreachable")

    with pytest.raises(AssertionError, match="network acquisition"):
        run_ethos_extraction(universe, DeliberateNetworkProvider())


def test_capture_once_provider_free_path_reaches_review_and_private_v03_projection(monkeypatch):
    """Fixture-only adjudication proves the real boundaries, not auto-admission."""
    import urllib.request

    subject, scope = "subject:" + "a" * 64, "scope:" + "b" * 64
    retained = capture(subject_id=subject)
    shared = RetainedCaptureUniverse(
        subject_id=subject, permitted_scope_ids=(scope,), captures=(retained,)
    )
    section_15 = shared.model_copy(update={"packet_selection_version": "section-15-v1"})
    section_17 = shared.model_copy(update={"packet_selection_version": "section-17-v1"})
    seen = []

    class FixtureProvider:
        def extract(self, *, packet, **_):
            seen.append(packet)
            if packet.packet_selection_version == "section-15-v1":
                raw = {
                    "outcome": "candidates",
                    "ethos_candidates": [{
                        "subject_id": subject, "scope_id": scope,
                        "epistemic_role": "self_described",
                        "descriptor": "A centrally retained bounded statement.",
                        "source_role": "supporting", "evidence_ids": [packet.evidence[0].evidence_id],
                    }],
                    "history_candidates": [],
                }
            else:
                raw = {
                    "outcome": "candidates", "ethos_candidates": [],
                    "history_candidates": [{
                        "subject_id": subject, "scope_id": scope,
                        "event_family": "founding",
                        "statement": "A centrally retained bounded statement.",
                        "evidence_ids": [packet.evidence[0].evidence_id],
                        "source_roles": ["supporting"], "event_date": "2000-01-01",
                    }],
                }
            return ProviderResponse(json.dumps(raw), "offline-fixture", "none")

    def denied(*_, **__):
        raise AssertionError("semantic execution attempted network acquisition")

    monkeypatch.setattr(urllib.request, "urlopen", denied)
    import socket
    monkeypatch.setattr(socket, "create_connection", denied)
    ethos_run = run_ethos_extraction(section_15, FixtureProvider())
    history_run = run_history_extraction(section_17, FixtureProvider())
    assert ethos_run["handoff"]["state"] == history_run["handoff"]["state"] == "REVIEW_REQUIRED"
    assert ethos_run["handoff"]["entries"][0]["route"]["disposition"] == "REVIEW_REQUIRED"
    assert history_run["handoff"]["entries"][0]["route"]["disposition"] == "REVIEW_REQUIRED"

    # A test fixture may adjudicate reviewed candidates; production extraction cannot.
    ethos_packet, history_packet = seen
    ethos_candidate = validate_bundle(ethos_packet, json.loads(ethos_run["raw_provider_response"])).bundle.ethos_candidates[0]
    history_candidate = validate_bundle(history_packet, json.loads(history_run["raw_provider_response"])).bundle.history_candidates[0]
    ethos_evidence, history_evidence = ethos_packet.evidence[0], history_packet.evidence[0]
    admitted_ethos = EthosObservation(
        subject_id=ethos_candidate.subject_id, scope_id=ethos_candidate.scope_id,
        epistemic_role=ethos_candidate.epistemic_role, descriptor=ethos_candidate.descriptor,
        source_role=ethos_candidate.source_role, evidence_locator_ids=(ethos_evidence.evidence_id,),
        source_record_ids=(ethos_evidence.source_record_id,), lineage_ids=(ethos_evidence.lineage_id,),
        observation_time={"observed_at": NOW},
    )
    admitted_history = NotableEvent(
        candidate_id=notable_event_candidate_id(
            subject_id=history_candidate.subject_id, scope_id=history_candidate.scope_id,
            event_family=history_candidate.event_family, event_date=datetime.fromisoformat(history_candidate.event_date),
            statement=history_candidate.statement, related_subject_id=None,
        ),
        subject_id=history_candidate.subject_id, scope_id=history_candidate.scope_id,
        event_family=history_candidate.event_family, statement=history_candidate.statement,
        event_date=datetime.fromisoformat(history_candidate.event_date), source_roles=history_candidate.source_roles,
        evidence_locator_ids=(history_evidence.evidence_id,), source_record_ids=(history_evidence.source_record_id,),
        lineage_ids=(history_evidence.lineage_id,), observation_time={"observed_at": NOW},
    )
    ethos_projection = project_ethos_observation(admitted_ethos, record_id="observation:" + "1" * 64, created_at=NOW, producer={"kind": "code", "producer_id": "fixture-adjudicator"})
    history_projection = project_notable_event(admitted_history, record_id="observation:" + "2" * 64, created_at=NOW, producer={"kind": "code", "producer_id": "fixture-adjudicator"})
    assert route_domain(section_id=15, risk_family="source_native", source_native=True).disposition == "PRIVATE_PROJECTION"
    assert route_domain(section_id=17, risk_family="source_native", source_native=True).disposition == "PRIVATE_PROJECTION"
    assert ethos_projection.evidence_locator_ids == (retained.evidence_fragment.record_id,)
    assert history_projection.source_record_ids == (retained.source_record.record_id,)
    assert ethos_projection.lineage[0].target_artifact_id == history_projection.lineage[0].target_artifact_id == retained.lineage_id
    assert ethos_projection.predicate.startswith("north_star_v03.section15.")
    assert history_projection.predicate.startswith("north_star_v03.section17.")
    assert "finding" not in history_projection.value and "sanction" not in history_projection.value
    with pytest.raises(ValueError, match="section 16"):
        route_domain(section_id=16, risk_family="finding")


@pytest.mark.parametrize("runner, section_id", [(run_ethos_extraction, 15), (run_history_extraction, 17)])
def test_capture_once_empty_views_route_to_central_planning_without_provider(runner, section_id):
    class ExplodingProvider:
        def extract(self, **_):
            raise AssertionError("coverage gaps must not invoke semantic providers")

    output = runner(
        RetainedCaptureUniverse(subject_id="subject:one", permitted_scope_ids=("scope:one",)), ExplodingProvider()
    )
    assert output["handoff"]["state"] == "ABSTAINED"
    assert output["handoff"]["source_opportunity"]["section_id"] == section_id
