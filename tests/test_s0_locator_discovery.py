from datetime import datetime, timezone

import pytest

from charitygraph.runtime.catalog import SQLiteCatalog
from charitygraph.s0_locator_discovery import (
    DiscoveryLineage, IdentityAuthentication, LocatorSearchResponse,
    LocatorSearchResult, OpenAIResponsesWebSearchProvider, PublicEntityIdentity,
    LocatorDiscoveryBudget, canonical_locator, discover, redirect_authentication,
)
from charitygraph.s0_product_owner_policy import concrete_first_party_source_definition_id
from charitygraph.scale_s0 import ScalePreflightError


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
    class Client:
        class responses:
            @staticmethod
            def create(**_kwargs): raise AssertionError("must not call provider")
    adapter = OpenAIResponsesWebSearchProvider(Client(), model="gpt-5", authorise_provider_call=lambda **_kwargs: False)
    with pytest.raises(ScalePreflightError):
        adapter.search(query='"Sunrise"', subject_abn="11111111111", request_identity="req:1")


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
