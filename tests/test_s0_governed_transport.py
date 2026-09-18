from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from charitygraph.s0_acquisition_bridge import OfflineResponse, SourcePlanner
from charitygraph.s0_governed_transport import GovernedSourceTransport, GovernedTransportError, TransportResult
from charitygraph.scale_s0 import HaltController, ScalePreflightError
from test_s0_acquisition_bridge import mandate, open_web, SUBJECTS


NOW = datetime(2026, 9, 18, tzinfo=timezone.utc)


def plan_and_auth():
    value = mandate()
    plan = SourcePlanner(value).plan(subject_id=SUBJECTS[0], scope_id="scope:organisation", source_family="official_website", acquisition_mechanism="governed_http", policy_classification="OPEN_WEB_PUBLIC", source_role="first_party", authority_role="publisher", requirement="conditional", locator="http://example.test/public", created_at=NOW)
    return value, plan, open_web(plan)


def test_preflight_rejects_before_opener_for_unsafe_sources(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport()
    opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth.__class__(**{**auth.__dict__, "technical_access_state": "login_required"}), value)
    opener.open.assert_not_called()


def test_open_web_fetch_is_bounded_and_returns_transport_metadata(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(max_response_bytes=20)
    response = Mock(); response.status = 200; response.getcode.return_value = 200; response.headers = {"Content-Type": "text/html"}; response.read.side_effect = [b"public", b""]
    transport._opener = Mock(); transport._opener.open.return_value = response
    result = transport.fetch(plan, auth, value, now=NOW)
    assert result.content == b"public" and result.requested_locator == plan.locator and result.tool_id == "charitygraph-governed-http"


def test_non_http_and_controlled_without_authority_are_rejected_before_open():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError): transport.fetch(plan.__class__(**{**plan.__dict__, "locator": "file:///tmp/no"}), auth, value)
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth.__class__(**{**auth.__dict__, "access_classification": "SEPARATELY_LICENSED_OR_CONTROLLED", "rights_transmission_status": "permitted", "specialist_authorisation_id": None}), value)
    opener.open.assert_not_called()


def test_transport_result_flows_into_existing_governed_acquisition(monkeypatch):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport()
    response = Mock(); response.status = 200; response.getcode.return_value = 200; response.headers = {"Content-Type": "text/html"}; response.read.side_effect = [b"public", b""]
    transport._opener = Mock(); transport._opener.open.return_value = response
    from charitygraph.s0_acquisition_bridge import GovernedAcquisition
    snapshot = GovernedAcquisition(value).acquire_transport(plan, auth, transport, representation=__import__("charitygraph.scale_s0", fromlist=["DocumentRepresentation"]).DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", now=NOW)
    assert snapshot.snapshot_hash


@pytest.mark.parametrize("state", ["login_required", "paywalled", "challenge_blocked"])
def test_technical_states_never_open_socket(state):
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    with pytest.raises(GovernedTransportError):
        transport.fetch(plan, auth.__class__(**{**auth.__dict__, "technical_access_state": state}), value)
    opener.open.assert_not_called()


def test_active_halt_is_checked_before_socket():
    value, plan, auth = plan_and_auth(); transport = GovernedSourceTransport(); opener = Mock(); transport._opener = opener
    from charitygraph.scale_s0 import HaltController, HaltRecord, HaltReason, HaltScope
    halts = HaltController([HaltRecord("h", HaltReason.RIGHTS_TRANSMISSION_VIOLATION, HaltScope.SUBJECT, value.slice_id, "source-acquisition", plan.subject_id, NOW.isoformat())])
    with pytest.raises(GovernedTransportError): transport.fetch(plan, auth, value, halts=halts)
    opener.open.assert_not_called()
