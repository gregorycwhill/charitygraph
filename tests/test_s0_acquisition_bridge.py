from dataclasses import replace
from datetime import datetime, timezone

import pytest

from charitygraph.s0_acquisition_bridge import (
    GovernedAcquisition, MandatePopulation, OfflineResponse, SourcePlanner,
    bundle_packets, certified_preflight, freeze_corpus, frozen_packets, persist_bridge, represent_document, task_applicability,
)
from charitygraph.runtime import SQLiteCatalog
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.scale_s0 import (
    DocumentRepresentation, HaltController, PolicyArtifact, RoutingClass,
    RoutingPolicy, ScaleMandate, ScalePreflightError, SourceAuthorisation,
    default_s0_registry,
)


NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)
SUBJECTS = ("28004778081", "28000030179", "74068758654", "37646526132", "50169561394", "47613674461", "78053639115", "61002643852")


def mandate() -> ScaleMandate:
    registry = default_s0_registry()
    hashes = {name: name[0] * 64 for name in ("sampling", "review", "promotion", "halt", "reservation", "source_universe", "specialist_source", "rights_transmission")}
    routing = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {})
    return ScaleMandate("mandate:test", "1", "slice:test", NOW.isoformat(), "actor:test", "population:test", SUBJECTS,
        "2026-09-18", "ranking:test", "group:test", "source-universe:test", "1", ("acnc_register", "acnc_ais"),
        ("acnc_register", "acnc_ais", "official_website", "latest_authorised_annual_report", "specialist"), "specialist:test",
        "rights:test", registry.version, tuple(t.task_id for t in registry.contracts), (), routing.policy_id, routing.version,
        "1", "1", 1, "reservation:test", "AUD", "review:test", "1", "promotion:test", "1", "sampling:test", "1",
        "halt:test", "1", ("governed_observations",), policy_hashes={**hashes, "routing": routing.immutable_hash, "logical_task_registry": registry.immutable_hash})


def open_web(plan):
    return SourceAuthorisation("source:fixture", plan.source_family, plan.locator, "first_party", "permitted_open_web_policy",
        "planned", "not_processed", "", ("program_service",), "", "rights:test", access_classification="OPEN_WEB_PUBLIC", technical_access_state="accessible")


def policies(value, routing):
    ids = {"sampling": ("sampling:test", "1"), "review": ("review:test", "1"), "promotion": ("promotion:test", "1"),
        "halt": ("halt:test", "1"), "reservation": ("reservation:test", "1"), "source_universe": ("source-universe:test", "1"),
        "specialist_source": ("specialist:test", "1"), "rights_transmission": ("rights:test", "1")}
    answer = {name: PolicyArtifact(policy_id, version, value.policy_hashes[name]) for name, (policy_id, version) in ids.items()}
    answer["routing"] = PolicyArtifact(routing.policy_id, routing.version, routing.immutable_hash)
    return answer


def test_exact_eight_population_is_order_independent_and_injections_fail_closed():
    value = mandate()
    assert MandatePopulation.from_mandate(value, reversed(SUBJECTS)).subject_ids == tuple(sorted(SUBJECTS))
    with pytest.raises(ScalePreflightError):
        MandatePopulation.from_mandate(value, SUBJECTS[:-1])
    with pytest.raises(ScalePreflightError):
        MandatePopulation.from_mandate(value, (*SUBJECTS, "99999999999"))
    with pytest.raises(ScalePreflightError):
        MandatePopulation.from_mandate(value, (*SUBJECTS[:-1], "99999999999"))


def test_fixture_source_to_corpus_to_packet_never_crosses_provider_boundary():
    value, registry = mandate(), default_s0_registry()
    plan = SourcePlanner(value).plan(subject_id=SUBJECTS[0], scope_id="scope:organisation", source_family="official_website",
        acquisition_mechanism="fixture", policy_classification="OPEN_WEB_PUBLIC", source_role="first_party", authority_role="publisher",
        requirement="conditional", locator="https://fixture.invalid/smith-family", created_at=NOW)
    snapshot = GovernedAcquisition(value).acquire(plan, open_web(plan), OfflineResponse(b"<html>public fixture</html>", "text/html", plan.locator),
        representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW)
    corpus = freeze_corpus(value, SUBJECTS[0], (snapshot,), now=NOW)
    applicability = task_applicability(registry, value, corpus, scope_id="scope:organisation")
    packets = frozen_packets(value, registry, corpus, (snapshot,), applicability, now=NOW)
    assert packets and all(packet.mandate_id == value.mandate_id for packet in packets)
    assert all(packet.corpus_id == corpus.corpus_id for packet in packets)
    assert all(packet.provider_request_identity.startswith("provider-request:") for packet in packets)


@pytest.mark.parametrize("technical", ["login_required", "paywalled", "challenge_blocked"])
def test_technical_withholding_fails_before_fixture_acquisition(technical):
    value = mandate()
    plan = SourcePlanner(value).plan(subject_id=SUBJECTS[0], scope_id="scope:organisation", source_family="official_website",
        acquisition_mechanism="fixture", policy_classification="OPEN_WEB_PUBLIC", source_role="first_party", authority_role="publisher",
        requirement="conditional", locator="https://fixture.invalid/blocked", created_at=NOW)
    with pytest.raises(ScalePreflightError):
        GovernedAcquisition(value).acquire(plan, replace(open_web(plan), technical_access_state=technical), OfflineResponse(b"no", "text/html", plan.locator),
            representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW)


def test_durable_bridge_records_restart_idempotently_and_constructs_preflight(tmp_path):
    value, registry = mandate(), default_s0_registry()
    routing = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {})
    catalog = SQLiteCatalog(tmp_path / "bridge.sqlite3").open(initialize=True)
    plan = SourcePlanner(value).plan(subject_id=SUBJECTS[0], scope_id="scope:organisation", source_family="official_website",
        acquisition_mechanism="fixture", policy_classification="OPEN_WEB_PUBLIC", source_role="first_party", authority_role="publisher",
        requirement="conditional", locator="https://fixture.invalid/public", created_at=NOW)
    snapshot = GovernedAcquisition(value).acquire(plan, open_web(plan), OfflineResponse(b"fixture", "text/html", plan.locator),
        representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW, catalog=catalog,
        artifact_store=ContentAddressedArtifactStore(tmp_path / "objects", allowed_roots=(tmp_path,), catalog=catalog))
    corpus = freeze_corpus(value, SUBJECTS[0], (snapshot,), now=NOW)
    applicable = task_applicability(registry, value, corpus, scope_id="scope:organisation")
    packets = frozen_packets(value, registry, corpus, (snapshot,), applicable, now=NOW)
    bundles = bundle_packets(value, packets, now=NOW)
    from charitygraph.scale_s0 import ScaleS0Preflight
    ScaleS0Preflight.register_durable_mandate(catalog, value, registry, routing, policies(value, routing), {})
    persist_bridge(catalog, value, plans=(plan,), snapshots=(snapshot,), corpora=(corpus,), bundles=bundles, offline=True)
    persist_bridge(catalog, value, plans=(plan,), snapshots=(snapshot,), corpora=(corpus,), bundles=bundles, offline=True)
    for packet in packets:
        ScaleS0Preflight.register_durable_packet(catalog, value, packet, offline=True)
    with catalog._connection() as connection:
        assert connection.execute("SELECT count(*) FROM scale_s0_source_plans").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM scale_s0_frozen_corpora").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM source_records").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM acquisition_receipts").fetchone()[0] == 1
    handoff = certified_preflight(value, registry, routing, policies(value, routing), (snapshot,), {plan.plan_id: plan}, packets)
    assert handoff.mandate.identity_hash == value.identity_hash
    assert bundles and sum(len(item.packet_ids) for item in bundles) == len(packets)


def test_eight_subject_offline_fixture_matrix_and_false_absence_states():
    value, planner = mandate(), None
    planner = SourcePlanner(value)
    cases = (
        (SUBJECTS[0], "acnc_register", "OPEN_WEB_PUBLIC", DocumentRepresentation.NATIVE_STRUCTURED, "structured_source_native_data"),
        (SUBJECTS[1], "acnc_ais", "OPEN_WEB_PUBLIC", DocumentRepresentation.NATIVE_STRUCTURED, "structured_source_native_data"),
        (SUBJECTS[2], "official_website", "OPEN_WEB_PUBLIC", DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only"),
        (SUBJECTS[4], "latest_authorised_annual_report", "OPEN_WEB_PUBLIC", DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only"),
        (SUBJECTS[5], "latest_authorised_annual_report", "OPEN_WEB_PUBLIC", DocumentRepresentation.VISUALLY_MATERIAL_PDF, "page_rendered_visual"),
        (SUBJECTS[6], "latest_authorised_annual_report", "OPEN_WEB_PUBLIC", DocumentRepresentation.PARSING_FAILURE, "not_processable"),
        (SUBJECTS[7], "specialist", "SEPARATELY_LICENSED_OR_CONTROLLED", DocumentRepresentation.NATIVE_STRUCTURED, "structured_source_native_data"),
    )
    snapshots = []
    for subject, family, access, representation, mode in cases:
        plan = planner.plan(subject_id=subject, scope_id="scope:organisation", source_family=family, acquisition_mechanism="fixture",
            policy_classification=access, source_role="fixture", authority_role="fixture-authority", requirement="specialist" if family == "specialist" else "conditional",
            locator=f"https://fixture.invalid/{subject}", created_at=NOW)
        auth = SourceAuthorisation("source:" + subject, family, plan.locator, "fixture-authority", "permitted_open_web_policy" if access == "OPEN_WEB_PUBLIC" else "permitted",
            "planned", "not_processed", "", ("program_service",), access_classification=access, technical_access_state="accessible",
            specialist_authorisation_id="specialist:test" if family == "specialist" else None)
        snapshots.append(GovernedAcquisition(value).acquire(plan, auth, OfflineResponse(subject.encode(), "application/pdf" if "report" in family else "application/json", plan.locator),
            representation=representation, representation_mode=mode, now=NOW))
    assert len(snapshots) == 7
    blocked = planner.plan(subject_id=SUBJECTS[3], scope_id="scope:organisation", source_family="official_website", acquisition_mechanism="fixture",
        policy_classification="TECHNICALLY_WITHHELD", source_role="fixture", authority_role="fixture", requirement="conditional", locator="https://fixture.invalid/login", created_at=NOW)
    with pytest.raises(ScalePreflightError):
        GovernedAcquisition(value).acquire(blocked, replace(open_web(blocked), access_classification="TECHNICALLY_WITHHELD", technical_access_state="login_required"),
            OfflineResponse(b"blocked", "text/html", blocked.locator), representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW)
    unavailable = planner.plan(subject_id=SUBJECTS[3], scope_id="scope:organisation", source_family="official_website", acquisition_mechanism="fixture",
        policy_classification="OPEN_WEB_PUBLIC", source_role="fixture", authority_role="fixture", requirement="conditional", locator="https://fixture.invalid/unavailable", created_at=NOW)
    with pytest.raises(ScalePreflightError):
        GovernedAcquisition(value).acquire(unavailable, open_web(unavailable), OfflineResponse(b"", "text/html", unavailable.locator, status=503),
            representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW)
    corpus = freeze_corpus(value, SUBJECTS[6], (snapshots[5],), exclusions=("optional source not acquired",), now=NOW)
    states = task_applicability(default_s0_registry(), value, corpus, scope_id="scope:organisation")
    assert "REPRESENTATION_FAILED" in {item.state for item in states}
    assert not {"observed_absent", "not_found"} & {item.state for item in states}


def test_document_v2_pdf_representations_are_snapshot_bound_and_rendered(tmp_path):
    from PIL import Image, ImageDraw
    value = mandate()
    store = ContentAddressedArtifactStore(tmp_path / "objects", allowed_roots=(tmp_path,))
    planner = SourcePlanner(value)
    plans, snapshots = [], []
    files = []
    for name, text in (("reliable", "Annual report: revenue 100"), ("visual", "Visual annual report page")):
        image = Image.new("RGB", (480, 200), "white")
        ImageDraw.Draw(image).text((20, 20), text, fill="black")
        path = tmp_path / f"{name}.pdf"; image.save(path, "PDF"); files.append(path)
    representations = []
    for index, (path, visual) in enumerate(zip(files, (False, True), strict=True)):
        plan = planner.plan(subject_id=SUBJECTS[4 + index], scope_id="scope:organisation", source_family="latest_authorised_annual_report",
            acquisition_mechanism="fixture", policy_classification="OPEN_WEB_PUBLIC", source_role="annual_report", authority_role="first_party",
            requirement="conditional", locator=f"https://fixture.invalid/{path.name}", created_at=NOW)
        snapshot = GovernedAcquisition(value).acquire(plan, open_web(plan), OfflineResponse(path.read_bytes(), "application/pdf", plan.locator),
            representation=DocumentRepresentation.VISUALLY_MATERIAL_PDF if visual else DocumentRepresentation.RELIABLE_TEXT,
            representation_mode="page_rendered_visual" if visual else "text_extraction_only", artifact_store=store, now=NOW)
        representation = represent_document(snapshot, path, visually_material=visual, artifact_store=store, cache_root=tmp_path / "cache", now=NOW)
        assert representation.snapshot_hash == snapshot.snapshot_hash
        assert representation.document_hash == snapshot.snapshot_hash
        if visual:
            assert representation.selected_pages == (1,) and representation.rendered_page_artifact_ids
        else:
            assert representation.representation_kind == DocumentRepresentation.RELIABLE_TEXT.value
        representations.append(representation)
        plans.append(plan); snapshots.append(snapshot)
    assert len(representations) == 2
    routing = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {})
    catalog = SQLiteCatalog(tmp_path / "pdf-bridge.sqlite3").open(initialize=True)
    from charitygraph.scale_s0 import ScaleS0Preflight
    ScaleS0Preflight.register_durable_mandate(catalog, value, default_s0_registry(), routing, policies(value, routing), {})
    corpora = tuple(freeze_corpus(value, plan.subject_id, (snapshot,), now=NOW) for plan, snapshot in zip(plans, snapshots, strict=True))
    persist_bridge(catalog, value, plans=plans, snapshots=snapshots, representations=representations, corpora=corpora, bundles=(), offline=True)
    with catalog._connection() as connection:
        assert connection.execute("SELECT count(*) FROM scale_s0_representations").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM scale_s0_frozen_corpora").fetchone()[0] == 2
