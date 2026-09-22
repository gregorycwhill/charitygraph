"""Bounded S0 public-web locator discovery.

Search output is deliberately discovery metadata.  This module cannot create
source records, evidence locators, observations, cards, or semantic packets.
Acquisition remains separately governed by ``GovernedSourceTransport`` and
``GovernedAcquisition`` after identity authentication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

from charitygraph.scale_s0 import ScalePreflightError

MAX_SEARCH_QUERIES_PER_SUBJECT = 5
MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY = 10
MAX_AUTHENTICATED_LOCATOR_FETCHES_PER_SUBJECT = 5


def _hash(value: object) -> str:
    return sha256(json.dumps(value, default=lambda x: asdict(x), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class LocatorSearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    rank: int | None = None
    source_metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class LocatorSearchResponse:
    provider_call_id: str
    results: tuple[LocatorSearchResult, ...]


class LocatorSearchProvider(Protocol):
    """Provider-neutral, public-identity-only locator search boundary."""
    provider_id: str

    def search(self, *, query: str, subject_abn: str, request_identity: str) -> LocatorSearchResponse: ...


@dataclass
class LocatorDiscoveryBudget:
    """Per-subject operational bounds; authentication is recorded externally."""
    authenticated_locator_fetches: int = 0
    sufficient_useful_sources: bool = False

    def may_fetch(self) -> bool:
        return not self.sufficient_useful_sources and self.authenticated_locator_fetches < MAX_AUTHENTICATED_LOCATOR_FETCHES_PER_SUBJECT

    def record_authenticated_fetch(self, *, useful: bool) -> None:
        if not self.may_fetch():
            raise ScalePreflightError("authenticated locator fetch bound is exhausted or sufficient sources already acquired")
        self.authenticated_locator_fetches += 1
        self.sufficient_useful_sources = self.sufficient_useful_sources or useful


@dataclass(frozen=True)
class PublicEntityIdentity:
    subject_abn: str
    legal_or_trading_name: str
    acn_or_acnc_identifier: str = ""
    governed_identity_anchors: tuple[str, ...] = ()

    def queries(self) -> tuple[str, ...]:
        """Generate at most five mechanical combinations of approved fields."""
        fields = tuple(x for x in (self.legal_or_trading_name, self.subject_abn, self.acn_or_acnc_identifier, *self.governed_identity_anchors) if x)
        if not self.subject_abn or not self.legal_or_trading_name:
            raise ScalePreflightError("locator discovery requires governed ABN and legal or trading name")
        base = (f'"{self.legal_or_trading_name}" "{self.subject_abn}"', f'"{self.legal_or_trading_name}"')
        combinations = list(base)
        for value in fields[2:]:
            combinations.append(f'"{self.legal_or_trading_name}" "{value}"')
        return tuple(dict.fromkeys(combinations))[:MAX_SEARCH_QUERIES_PER_SUBJECT]


STRONG_ANCHORS = frozenset({"exact_abn", "exact_acn", "exact_acnc", "authoritative_locator_link"})
SOFT_ANCHORS = frozenset({"organisation_name", "address_or_location", "officer_or_director", "phone_or_email", "program_name", "authenticated_cross_link", "other_governed_specific"})


@dataclass(frozen=True)
class IdentityAuthentication:
    """Structured findings from subsequent acquisition, never search snippets."""
    anchors: tuple[str, ...]

    def decision(self) -> tuple[bool, str]:
        anchors = frozenset(self.anchors)
        strong = anchors & STRONG_ANCHORS
        if strong:
            return True, "strong_anchor:" + sorted(strong)[0]
        soft = anchors & SOFT_ANCHORS
        if len(soft) >= 2:
            return True, "two_independent_soft_anchors:" + ",".join(sorted(soft))
        return False, "insufficient_authenticated_identity_anchors"


def canonical_locator(locator: str) -> str:
    parsed = urlsplit(locator)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ScalePreflightError("locator must be an HTTP(S) URL")
    host = parsed.hostname.lower() if parsed.hostname else ""
    if host.startswith("www."):
        host = host[4:]
    # Canonical identity intentionally excludes a fragment, never changes path/query.
    return urlunsplit((parsed.scheme.lower(), host + (f":{parsed.port}" if parsed.port else ""), parsed.path or "/", parsed.query, ""))


def redirect_authentication(*, requested_locator: str, final_locator: str,
                            final_identity: IdentityAuthentication | None) -> tuple[bool, str]:
    """Accept benign canonicalisation; require independent auth for another host."""
    request = urlsplit(canonical_locator(requested_locator))
    final = urlsplit(canonical_locator(final_locator))
    if request.hostname == final.hostname and (request.scheme == final.scheme or (request.scheme == "http" and final.scheme == "https")):
        return True, "benign_canonical_redirect"
    if final_identity is None:
        return False, "cross_host_redirect_requires_identity_authentication"
    return final_identity.decision()


@dataclass(frozen=True)
class DiscoveryLineage:
    subject_abn: str
    query: str
    provider_id: str
    provider_call_id: str
    candidate_url: str
    title: str
    snippet: str
    rank: int | None
    source_metadata: dict[str, str] | None
    identity_anchors: tuple[str, ...]
    accepted: bool
    decision_reason: str
    resolved_locator: str | None = None
    redirect_chain: tuple[str, ...] = ()
    acquisition_receipt_id: str | None = None

    @property
    def lineage_id(self) -> str:
        return "locator-discovery:" + _hash(asdict(self))


class OpenAIResponsesWebSearchProvider:
    """Production adapter; caller supplies the already-governed Responses client.

    It makes no independent reservation, attestation, or send decision.  The
    supplied ``authorise_provider_call`` must complete the existing S0 durable
    preflight before this adapter invokes the client, and is deliberately
    required even for a real client.
    """
    provider_id = "openai-responses-web-search"

    def __init__(self, client: Any, *, model: str, authorise_provider_call: Any) -> None:
        if client is None or not model or not callable(authorise_provider_call):
            raise ScalePreflightError("locator search requires governed Responses client, model, and S0 call authoriser")
        self.client, self.model, self.authorise_provider_call = client, model, authorise_provider_call

    def search(self, *, query: str, subject_abn: str, request_identity: str) -> LocatorSearchResponse:
        # The authoriser is the existing reservation/attestation/exactly-once
        # gate.  A false result fails closed before a provider boundary.
        if self.authorise_provider_call(request_identity=request_identity, subject_abn=subject_abn, query=query) is not True:
            raise ScalePreflightError("locator search denied by existing S0 provider controls")
        response = self.client.responses.create(
            model=self.model,
            input=query,
            tools=[{"type": "web_search"}],
            store=False,
        )
        response_id = str(getattr(response, "id", ""))
        if not response_id:
            raise ScalePreflightError("Responses web-search result lacks provider call identity")
        results: list[LocatorSearchResult] = []
        # Official API source metadata is not guaranteed to expose snippets or
        # ranking. Preserve only what the response actually returns.
        for output in getattr(response, "output", ()):
            action = getattr(output, "action", None)
            for rank, source in enumerate(getattr(action, "sources", ()) if action else (), start=1):
                url = getattr(source, "url", None) or (source.get("url") if isinstance(source, dict) else None)
                if url:
                    results.append(LocatorSearchResult(url=str(url), rank=rank))
        return LocatorSearchResponse(response_id, tuple(results[:MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY]))


def discover(provider: LocatorSearchProvider, identity: PublicEntityIdentity, *,
             existing_lineage: Sequence[DiscoveryLineage] = ()) -> tuple[DiscoveryLineage, ...]:
    """Call at most five searches; results remain discovery metadata only."""
    lineages: list[DiscoveryLineage] = []
    completed_queries = {(row.subject_abn, row.query) for row in existing_lineage}
    for query_index, query in enumerate(identity.queries()):
        if (identity.subject_abn, query) in completed_queries:
            continue
        request_identity = "locator-search:" + _hash({"subject": identity.subject_abn, "query": query, "index": query_index})
        response = provider.search(query=query, subject_abn=identity.subject_abn, request_identity=request_identity)
        for result in response.results[:MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY]:
            lineages.append(DiscoveryLineage(identity.subject_abn, query, provider.provider_id, response.provider_call_id,
                result.url, result.title, result.snippet, result.rank, result.source_metadata, (), False,
                "pending_identity_authentication"))
    return tuple(lineages)
