from dataclasses import replace
from datetime import datetime, timezone

import pytest

from charitygraph.s0_acquisition_bridge import (
    GovernedAcquisition, MandatePopulation, OfflineResponse, SourcePlanner,
    freeze_corpus, frozen_packets, task_applicability,
)
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
