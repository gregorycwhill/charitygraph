from datetime import datetime, timezone

import pytest

from charitygraph.runtime.catalog import SQLiteCatalog
from charitygraph.s0_locator_discovery import (
    DiscoveryLineage, IdentityAuthentication, LocatorSearchResponse,
    LocatorSearchResult, LocatorSearchExecutionGate, OpenAIResponsesWebSearchProvider, PublicEntityIdentity,
    LocatorDiscoveryBudget, canonical_locator, discover, redirect_authentication,
)
from charitygraph.s0_product_owner_policy import concrete_first_party_source_definition_id
from charitygraph.scale_s0 import ScalePreflightError
from charitygraph.phase5_standard_transport import (
    OpenAIHTTPStandardClient, OpenAIResponsesWebSearchTransport,
    StandardAmbiguous, StandardProviderResponse,
)


NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


class FakeSearch:
    provider_id = "fake-search"
    def __init__(self, results): self.results, self.calls = results, []
    def search(self, *, query, subject_abn, request_identity):
        self.calls.append((query, subject_abn, request_identity))
        return LocatorSearchResponse("search-call:" + str(len(self.calls)), tuple(self.results))


def authenticate(lineage, anchors, resolved=None):
    accepted, reason = IdentityAuthentication(tuple(anchors)).decision()
    return DiscoveryLineage(**{**lineage.__dict__, "identity_anchors": tuple(anchors), "accepted": accepted,
                               "decision_reason": reason, "resolved_locator": resolved})


def test_sunrise_search_candidate_is_discovery_only_then_authenticated():
    provider = FakeSearch((LocatorSearchResult("https://sunrise.foundation/", "Sunrise", "official Sunrise web site", 1),))
    rows = discover(provider, PublicEntityIdentity("11111111111", "Sunrise Foundation"))
    accepted = authenticate(rows[0], ("exact_abn",), "https://sunrise.foundation/")
    assert accepted.accepted and accepted.snippet == "official Sunrise web site"
    # There is deliberately no conversion from search result to source/evidence.
    assert "evidence" not in accepted.__dict__ and "source_record" not in accepted.__dict__


def test_noongar_stale_locator_is_not_authoritative_when_candidate_authenticates():
    provider = FakeSearch((LocatorSearchResult("https://www.noongarboodjatrust.info/", rank=1),))
    row = discover(provider, PublicEntityIdentity("22222222222", "Noongar Boodja Trust"))[0]
    accepted = authenticate(row, ("organisation_name", "address_or_location"), "https://www.noongarboodjatrust.info/")
    assert accepted.accepted and accepted.resolved_locator == "https://www.noongarboodjatrust.info/"


def test_msf_benign_www_redirect_is_accepted_and_canonicalised():
    accepted, reason = redirect_authentication(requested_locator="https://www.msf.org.au/", final_locator="https://msf.org.au/", final_identity=None)
    assert accepted and reason == "benign_canonical_redirect"
    assert canonical_locator("https://www.msf.org.au/") == "https://msf.org.au/"


def test_distinct_subject_locator_source_definitions_do_not_collide():
    pairs = (("Smith Family", "33333333333", "https://www.thesmithfamily.com.au/"),
             ("Australian Red Cross", "44444444444", "https://www.redcross.org.au/"),
             ("Bush Heritage", "55555555555", "https://www.bushheritage.org.au/"),
             ("Greenpeace", "66666666666", "https://www.greenpeace.org.au/"))
    ids = {concrete_first_party_source_definition_id(subject_abn=abn, canonical_locator=canonical_locator(url)) for _, abn, url in pairs}
    assert len(ids) == len(pairs)


def test_ambiguous_same_name_and_unauthenticated_cross_host_redirect_are_rejected():
    assert not IdentityAuthentication(("organisation_name",)).decision()[0]
    assert redirect_authentication(requested_locator="https://old.example/", final_locator="https://other.example/", final_identity=None) == (False, "cross_host_redirect_requires_identity_authentication")


def test_responses_adapter_fails_closed_without_existing_gate():
    class Client(OpenAIHTTPStandardClient): pass
    with pytest.raises(ScalePreflightError):
        OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(Client()), model="gpt-5.6-luna", execution_gate=lambda **_kwargs: True)


class StubStandardClient(OpenAIHTTPStandardClient):
    def __init__(self, body): self.body, self.calls = body, []
    def create_response_once(self, body, *, client_request_id, request_started_at=None):
        self.calls.append((body, client_request_id))
        return StandardProviderResponse(200, self.body.get("id", "transport-id"), self.body, __import__("json").dumps(self.body).encode(), client_request_id=client_request_id)


class RecordingGate(LocatorSearchExecutionGate):
    client_request_id = "locator-test-client"
    def __init__(self): self.events = []
    def begin(self, *, request_identity, subject_abn, query): self.events.append(("begin", request_identity, subject_abn, query))
    def complete(self, *, provider_receipt_id, result_ref, usage=None, response_facts=None): self.events.append(("complete", provider_receipt_id, result_ref, usage, response_facts))
    def fail(self, *, failure_class, message, ambiguous=False): self.events.append(("fail", failure_class, ambiguous))


def test_authorised_search_is_framed_by_durable_gate_before_and_after_network():
    client = StubStandardClient({"id": "resp_locator_1", "usage": {"total_tokens": 1}, "output": []})
    gate = RecordingGate()
    result = OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=gate).search(
        query='"Sunrise"', subject_abn="11111111111", request_identity="req:1")
    assert result.provider_call_id == "resp_locator_1"
    assert [event[0] for event in gate.events] == ["begin", "complete"]


def test_standard_adapter_emits_exact_luna_web_search_body_and_normalizes_real_sources():
    body = {"id": "resp_locator_sources", "usage": {"input_tokens": 4, "output_tokens": 6},
            "output": [{"type": "web_search_call", "action": {"sources": [
                {"url": "https://example.org/", "title": "Example", "type": "source"},
            ]}}]}
    client = StubStandardClient(body)
    result = OpenAIResponsesWebSearchProvider(
        OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=RecordingGate(),
    ).search(query='"Sunrise"', subject_abn="11111111111", request_identity="req:body")
    sent = __import__("json").loads(client.calls[0][0])
    assert sent == {"model": "gpt-5.6-luna", "input": '"Sunrise"', "tools": [{"type": "web_search"}], "tool_choice": {"type": "web_search"}, "store": False, "include": ["web_search_call.action.sources"]}
    assert result.provider_call_id == "resp_locator_sources"
    assert result.usage == body["usage"]
    assert result.results == (LocatorSearchResult("https://example.org/", title="Example", source_metadata={"title": "Example", "type": "source"}),)
    assert result.results[0].snippet == "" and result.results[0].rank is None


def test_pricing_facts_count_source_bearing_web_search_without_action_type():
    body = {"id": "resp_locator_pricing", "model": "gpt-5.6-luna",
            "usage": {"input_tokens": 4, "output_tokens": 6},
            "output": [{"type": "web_search_call", "action": {"sources": []}}]}
    gate = RecordingGate()
    OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(StubStandardClient(body)),
                                     model="gpt-5.6-luna", execution_gate=gate).search(
        query='"Sunrise"', subject_abn="11111111111", request_identity="req:pricing")
    assert gate.events[1][4] == {"model": "gpt-5.6-luna", "web_search_calls": 1}


@pytest.mark.parametrize("body", [
    {"id": 7, "usage": {"input_tokens": 1, "output_tokens": 1}, "output": []},
    {"id": "resp_incomplete", "model": "gpt-5.6-luna", "status": "incomplete",
     "usage": {"input_tokens": 1, "output_tokens": 1}, "output": []},
])
def test_invalid_identity_or_explicitly_incomplete_response_never_yields_discovery(body):
    gate = RecordingGate()
    with pytest.raises(ScalePreflightError):
        OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(StubStandardClient(body)),
                                         model="gpt-5.6-luna", execution_gate=gate).search(
            query='"Sunrise"', subject_abn="11111111111", request_identity="req:invalid")
    assert gate.events[-1][0] == "fail"


@pytest.mark.parametrize("response_body", [{"usage": {"total_tokens": 1}, "output": []}, {"id": "resp", "output": {}}])
def test_missing_identity_or_source_structure_fails_without_fabricated_locator_metadata(response_body):
    client = StubStandardClient({"id": response_body.get("id", "missing"), **response_body})
    if "id" not in response_body:
        client.body.pop("id")
    gate = RecordingGate()
    with pytest.raises(ScalePreflightError):
        OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=gate).search(
            query='"Sunrise"', subject_abn="11111111111", request_identity="req:malformed")
    assert [event[0] for event in gate.events] == (["begin", "fail"] if "id" not in response_body else ["begin", "complete", "fail"])


def test_standard_ambiguous_evidence_is_not_downgraded_to_definite_failure():
    class FailingClient(OpenAIHTTPStandardClient):
        def create_response_once(self, *_args, **_kwargs):
            raise StandardAmbiguous("socket outcome unknown", client_request_id="locator-test-client")
    gate = RecordingGate()
    with pytest.raises(StandardAmbiguous):
        OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(FailingClient()), model="gpt-5.6-luna", execution_gate=gate).search(
            query='"Sunrise"', subject_abn="11111111111", request_identity="req:ambiguous")
    assert gate.events[-1] == ("fail", "provider_ambiguous_transport", True)


def test_gate_rejects_mock_only_preflight_without_a_frozen_operational_packet():
    from unittest.mock import Mock
    from charitygraph.scale_s0 import ScaleS0Preflight, SendRequest, RoutingClass
    preflight = ScaleS0Preflight.__new__(ScaleS0Preflight)
    preflight.provider_send = Mock()
    catalog = Mock()
    from charitygraph.s0_locator_discovery import S0LocatorSearchExecutionGate
    with pytest.raises(ScalePreflightError, match="constructed S0 preflight"):
        S0LocatorSearchExecutionGate(preflight=preflight,
            request=SendRequest("physical:1", "task", "1", "11111111111", "scope:organisation", "packet:1", True, RoutingClass.DETERMINISTIC, "reservation:1", (), False),
            catalog=catalog, delivery_attempt_id="delivery:1", client_request_id="request:1", request_identity="req:1")


@pytest.mark.parametrize("control_failure", [
    "no_valid_attestation_window",
    "expired_attestation_window",
    "mismatched_attestation_window",
    "revoked_attestation_window",
    "insufficient_budget_or_reservation",
])
def test_existing_preflight_denials_never_reach_network(control_failure):
    from unittest.mock import Mock
    preflight = Mock()
    preflight.provider_send = Mock(side_effect=ScalePreflightError(control_failure))
    class PreflightGate(RecordingGate):
        def begin(self, **kwargs):
            preflight.provider_send()
            super().begin(**kwargs)
    gate = PreflightGate()
    client = StubStandardClient({"id": "never", "output": []})
    adapter = OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=gate)
    with pytest.raises(ScalePreflightError):
        adapter.search(query='"Sunrise"', subject_abn="11111111111", request_identity="req:denied")
    assert client.calls == []


def test_replay_gate_denial_prevents_second_physical_search():
    class ReplayGate(RecordingGate):
        def begin(self, **kwargs):
            if self.events:
                raise ScalePreflightError("duplicate durable provider request identity")
            super().begin(**kwargs)
    client = StubStandardClient({"id": "resp_once", "output": []})
    adapter = OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=ReplayGate())
    adapter.search(query='"Sunrise"', subject_abn="11111111111", request_identity="req:once")
    with pytest.raises(ScalePreflightError):
        adapter.search(query='"Sunrise"', subject_abn="11111111111", request_identity="req:once")
    assert len(client.calls) == 1


def test_discovery_lineage_is_durable_and_idempotent_without_duplicate_provider_calls(tmp_path):
    provider = FakeSearch((LocatorSearchResult("https://sunrise.foundation/", snippet="metadata only", rank=1),))
    identity = PublicEntityIdentity("11111111111", "Sunrise Foundation")
    first = discover(provider, identity)
    # Resume persists/reuses the same deterministic lineage; callers do not re-search.
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    for row in first:
        catalog.register_scale_s0_locator_discovery({**row.__dict__, "lineage_id": row.lineage_id}, created_at=NOW)
        catalog.register_scale_s0_locator_discovery({**row.__dict__, "lineage_id": row.lineage_id}, created_at=NOW)
    stored = catalog.list_scale_s0_locator_discoveries(subject_abn="11111111111")
    resumed = discover(provider, identity, existing_lineage=first)
    assert len(stored) == len(first) and not resumed and len(provider.calls) == len(identity.queries())
    catalog.close()


def test_fetch_bound_and_early_stop_are_explicit():
    budget = LocatorDiscoveryBudget()
    budget.record_authenticated_fetch(useful=True)
    assert not budget.may_fetch()
