from datetime import datetime, timezone
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from charitygraph.s0_acquisition_bridge import OfflineResponse, SourcePlanner, GovernedAcquisition, freeze_corpus, frozen_packets, task_applicability
from charitygraph.s0_governed_transport import GovernedSourceTransport, GovernedTransportError, TransportResult
from charitygraph.scale_s0 import DocumentRepresentation, HaltController, ScalePreflightError, default_s0_registry
from test_s0_acquisition_bridge import mandate, open_web, SUBJECTS


NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def plan_and_auth():
    value = mandate()
    plan = SourcePlanner(value).plan(subject_id=SUBJECTS[0], scope_id="scope:organisation", source_family="official_website", acquisition_mechanism="governed_http", policy_classification="OPEN_WEB_PUBLIC", source_role="first_party", authority_role="publisher", requirement="conditional", locator="http://example.test/public", created_at=NOW)
    return value, plan, open_web(plan)


class FixtureHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_body = b"<html>fixture</html>"
    response_headers = {"Content-Type": "text/html"}
    redirect_location = None

    def do_GET(self):
        self.send_response(self.response_status)
        for key, value in self.response_headers.items(): self.send_header(key, value)
        if self.redirect_location: self.send_header("Location", self.redirect_location)
        self.end_headers()
        if self.response_status == 200: self.wfile.write(self.response_body)

    def log_message(self, *_args): pass


def local_server(handler=FixtureHandler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    return server, f"http://127.0.0.1:{server.server_port}/fixture"


def test_preflight_rejects_before_opener_for_unsafe_sources(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport()
    opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth.__class__(**{**auth.__dict__, "technical_access_state": "login_required"}), value, offline=True)
    opener.open.assert_not_called()


def test_open_web_fetch_is_bounded_and_returns_transport_metadata(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(max_response_bytes=20)
    response = Mock(); response.status = 200; response.getcode.return_value = 200; response.headers = {"Content-Type": "text/html"}; response.read.side_effect = [b"public", b""]
    transport._opener = Mock(); transport._opener.open.return_value = response
    result = transport.fetch(plan, auth, value, now=NOW, offline=True)
    assert result.content == b"public" and result.requested_locator == plan.locator and result.tool_id == "charitygraph-governed-http"


def test_non_http_and_controlled_without_authority_are_rejected_before_open():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan.__class__(**{**plan.__dict__, "locator": "file:///tmp/no"}), auth, value, offline=True)
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth.__class__(**{**auth.__dict__, "access_classification": "SEPARATELY_LICENSED_OR_CONTROLLED", "rights_transmission_status": "permitted", "specialist_authorisation_id": None}), value, offline=True)
    opener.open.assert_not_called()


@pytest.mark.parametrize("mutation", [
    lambda plan, auth, value: (plan.__class__(**{**plan.__dict__, "mandate_hash": "stale"}), auth),
    lambda plan, auth, value: (plan.__class__(**{**plan.__dict__, "subject_id": "subject:outside"}), auth),
    lambda plan, auth, value: (plan, auth.__class__(**{**auth.__dict__, "url_or_identity": "http://example.test/other"})),
    lambda plan, auth, value: (plan, auth.__class__(**{**auth.__dict__, "source_family": "unapproved_family"})),
])
def test_stale_scope_locator_and_family_bindings_never_open(mutation):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    changed_plan, changed_auth = mutation(plan, auth, value)
    with pytest.raises(GovernedTransportError): transport.fetch(changed_plan, changed_auth, value, offline=True)
    opener.open.assert_not_called()


def test_transport_result_flows_into_existing_governed_acquisition(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport()
    response = Mock(); response.status = 200; response.getcode.return_value = 200; response.headers = {"Content-Type": "text/html"}; response.read.side_effect = [b"public", b""]
    transport._opener = Mock(); transport._opener.open.return_value = response
    from charitygraph.s0_acquisition_bridge import GovernedAcquisition
    snapshot = GovernedAcquisition(value).acquire_transport(plan, auth, transport, representation=__import__("charitygraph.scale_s0", fromlist=["DocumentRepresentation"]).DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW, offline=True)
    assert snapshot.snapshot_hash


@pytest.mark.parametrize("state", ["login_required", "paywalled", "challenge_blocked"])
def test_technical_states_never_open_socket(state):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError):
        transport.fetch(plan, auth.__class__(**{**auth.__dict__, "technical_access_state": state}), value, offline=True)
    opener.open.assert_not_called()


def test_active_halt_is_checked_before_socket():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    from charitygraph.scale_s0 import HaltController, HaltRecord, HaltReason, HaltScope
    halts = HaltController([HaltRecord("h", HaltReason.RIGHTS_TRANSMISSION_VIOLATION, HaltScope.SUBJECT, value.slice_id, "source-acquisition", plan.subject_id, NOW.isoformat())])
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, halts=halts, offline=True)
    opener.open.assert_not_called()


def test_real_loopback_http_success_and_status_failures():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport()
    server, locator = local_server()
    try:
        plan = plan.__class__(**{**plan.__dict__, "locator": locator}); auth = auth.__class__(**{**auth.__dict__, "url_or_identity": locator})
        result = transport.fetch(plan, auth, value, now=NOW, offline=True)
        assert result.status == 200 and result.content == b"<html>fixture</html>" and result.final_locator == locator
    finally: server.shutdown(); server.server_close()

    for status in (401, 403, 404, 500):
        class StatusHandler(FixtureHandler): response_status = status
        server, locator = local_server(StatusHandler)
        try:
            plan = plan.__class__(**{**plan.__dict__, "locator": locator}); auth = auth.__class__(**{**auth.__dict__, "url_or_identity": locator})
            with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, offline=True)
        finally: server.shutdown(); server.server_close()


def test_real_loopback_redirects_and_stream_limit():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(max_redirects=1, max_response_bytes=8)
    class RedirectHandler(FixtureHandler):
        redirect_location = "/final"
        def do_GET(self):
            if self.path == "/final":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"final")
                return
            self.send_response(302)
            self.send_header("Location", self.redirect_location)
            self.end_headers()
    server, locator = local_server(RedirectHandler)
    try:
        plan = plan.__class__(**{**plan.__dict__, "locator": locator}); auth = auth.__class__(**{**auth.__dict__, "url_or_identity": locator})
        result = transport.fetch(plan, auth, value, offline=True); assert result.final_locator.endswith("/final")
    finally: server.shutdown(); server.server_close()

    class LargeHandler(FixtureHandler):
        response_body = b"0123456789abcdef"
    server, locator = local_server(LargeHandler)
    try:
        plan = plan.__class__(**{**plan.__dict__, "locator": locator}); auth = auth.__class__(**{**auth.__dict__, "url_or_identity": locator})
        with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, offline=True)
    finally: server.shutdown(); server.server_close()


def test_authoritative_alternate_locator_is_bounded_and_reached_after_unavailable_primary():
    value, plan, auth = plan_and_auth()
    alternate = "https://official.example.org/public"
    auth = auth.__class__(**{**auth.__dict__, "authority_material": {
        "alternate_locators": ({"locator": alternate, "relationship": "official_navigation"},),
    }})
    response = Mock(status=200, getcode=lambda: 200, headers={"Content-Type": "text/html"}, read=Mock(side_effect=[b"alternate", b""]))
    opener = Mock()
    opener.open.side_effect = [HTTPError(plan.locator, 404, "not found", {}, BytesIO()), response]
    transport = GovernedSourceTransport(); transport._opener = opener
    result = transport.fetch(plan, auth, value, now=NOW, offline=True)
    assert result.final_locator == alternate and result.content == b"alternate"
    assert opener.open.call_count == 2


@pytest.mark.parametrize("relationship", ["", "unrelated_registry"])
def test_unauthoritative_alternate_locator_fails_closed_before_open(relationship):
    value, plan, auth = plan_and_auth()
    auth = auth.__class__(**{**auth.__dict__, "authority_material": {
        "alternate_locators": ({"locator": "https://untrusted.example/public", "relationship": relationship},),
    }})
    transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, offline=True)
    opener.open.assert_not_called()


def test_alternate_locator_bypass_flags_fail_closed():
    value, plan, auth = plan_and_auth()
    auth = auth.__class__(**{**auth.__dict__, "authority_material": {
        "alternate_locators": ({"locator": "https://official.example.org/public", "relationship": "official_navigation", "tls_validation_bypass": True},),
    }})
    transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, offline=True)
    opener.open.assert_not_called()


def test_alternate_locator_probe_budget_is_five_including_primary():
    value, plan, auth = plan_and_auth()
    alternates = tuple({"locator": f"https://official-{index}.example.org/public", "relationship": "official_navigation"} for index in range(6))
    auth = auth.__class__(**{**auth.__dict__, "authority_material": {"alternate_locators": alternates}})
    opener = Mock()
    opener.open.side_effect = [HTTPError(plan.locator, 404, "not found", {}, BytesIO()) for _ in range(5)]
    transport = GovernedSourceTransport(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, offline=True)
    assert opener.open.call_count == 5


def test_loopback_transport_flows_through_acquisition_to_packet():
    value, plan, auth = plan_and_auth(); server, locator = local_server()
    try:
        plan = plan.__class__(**{**plan.__dict__, "locator": locator}); auth = auth.__class__(**{**auth.__dict__, "url_or_identity": locator})
        snapshot = GovernedAcquisition(value).acquire_transport(plan, auth, GovernedSourceTransport(), representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW, offline=True)
        corpus = freeze_corpus(value, plan.subject_id, (snapshot,), now=NOW)
        applicable = task_applicability(default_s0_registry(), value, corpus, scope_id="scope:organisation")
        packets = frozen_packets(value, default_s0_registry(), corpus, (snapshot,), applicable, now=NOW)
        assert snapshot.snapshot_hash and packets and all(packet.corpus_id == corpus.corpus_id for packet in packets)
    finally: server.shutdown(); server.server_close()
