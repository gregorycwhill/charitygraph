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
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

from charitygraph.scale_s0 import (
    ExecutionAttemptIdentity, FrozenPacket, LOCATOR_SEARCH_MAX_QUERIES_PER_SUBJECT,
    LOCATOR_SEARCH_OPERATION_KIND,
    RoutingClass, ScalePreflightError, SendRequest, locator_search_request_identity,
)

MAX_SEARCH_QUERIES_PER_SUBJECT = LOCATOR_SEARCH_MAX_QUERIES_PER_SUBJECT
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


class LocatorSearchExecutionGate(ABC):
    """The only execution seam permitted between discovery and a provider.

    Implementations must delegate to the existing S0 preflight and durable
    Standard provider lifecycle.  A boolean callback is intentionally not a
    valid gate.
    """

    @abstractmethod
    def begin(self, *, request_identity: str, subject_abn: str, query: str) -> None: ...

    @abstractmethod
    def complete(self, *, provider_receipt_id: str, result_ref: str, usage: Any = None) -> None: ...

    @abstractmethod
    def fail(self, *, failure_class: str, message: str, ambiguous: bool = False) -> None: ...


@dataclass(frozen=True)
class LocatorSearchPrice:
    """A current provider price snapshot bound before a locator crossing."""
    pricing_snapshot_id: str
    estimated_provider_cost: str
    currency: str


@dataclass(frozen=True)
class LocatorSearchPreparedRequest:
    """Frozen, source-free material for one exact Standard locator request.

    This value neither reserves budget nor starts transport.  It gives the
    caller all identities required to construct the already-governed Standard
    lifecycle immediately after the A3-coupled reservation succeeds.
    """
    packet: FrozenPacket
    request: SendRequest
    delivery_attempt_id: str
    client_request_id: str


def freeze_locator_search_packet(*, mandate: Any, execution_attempt: ExecutionAttemptIdentity,
                                 subject_abn: str, query: str, query_index: int,
                                 pricing: LocatorSearchPrice, frozen_at: str,
                                 scope_id: str = "scope:organisation") -> FrozenPacket:
    """Compile a deterministic operational packet without evidence or a send."""
    if execution_attempt.mandate_id != mandate.mandate_id or execution_attempt.slice_id != mandate.slice_id:
        raise ScalePreflightError("locator search packet execution identity is outside the mandate")
    if pricing.currency != mandate.currency_basis:
        raise ScalePreflightError("locator search price currency must equal the frozen S0 currency")
    request_identity = locator_search_request_identity(subject_id=subject_abn, query=query, query_index=query_index)
    material = {
        "mandate": mandate.identity_hash,
        "execution_attempt": execution_attempt.attempt_id,
        "operation": LOCATOR_SEARCH_OPERATION_KIND,
        "subject": subject_abn,
        "scope": scope_id,
        "query": query,
        "query_index": query_index,
        "provider_request_identity": request_identity,
        "pricing_snapshot_id": pricing.pricing_snapshot_id,
        "estimated_provider_cost": pricing.estimated_provider_cost,
        "currency": pricing.currency,
    }
    content_hash = _hash(material)
    return FrozenPacket(
        "packet:" + _hash({"locator_search_packet": material}),
        "urn:charitygraph:scale-s0:locator_search", "1.0", subject_abn, scope_id,
        (), (), "profile:locator-search:1",
        "urn:charitygraph:builder:schema:locator-search-discovery-metadata:1.0",
        RoutingClass.LOW_COST_SEMANTIC, request_identity, content_hash,
        mandate_id=mandate.mandate_id, slice_id=mandate.slice_id,
        frozen_at=frozen_at, operation_kind=LOCATOR_SEARCH_OPERATION_KIND,
        locator_query=query, locator_query_index=query_index,
        pricing_snapshot_id=pricing.pricing_snapshot_id,
        estimated_provider_cost=pricing.estimated_provider_cost,
    )


def prepare_locator_search_request(*, packet: FrozenPacket, reservation_id: str,
                                   provider_account_project: str,
                                   execution_authority: str) -> LocatorSearchPreparedRequest:
    """Construct the request identities required by the normal Standard lifecycle.

    The generic lifecycle records must be durably prepared by the caller before
    ``S0LocatorSearchExecutionGate.begin`` can cross the provider boundary.
    That ordering is intentional: a packet alone is never send authority.
    """
    if packet.operation_kind != LOCATOR_SEARCH_OPERATION_KIND or not reservation_id:
        raise ScalePreflightError("locator search request requires a frozen locator packet and reservation")
    if not provider_account_project or not execution_authority:
        raise ScalePreflightError("locator search request requires explicit A3 account/project and authority")
    identity = packet.provider_request_identity
    return LocatorSearchPreparedRequest(
        packet,
        SendRequest(
            "physical:" + _hash({"locator_search": identity}), packet.task_id, packet.task_version,
            packet.subject_id, packet.scope_id, packet.binding_hash, True,
            packet.routing_class, reservation_id, (), False,
            provider_account_project=provider_account_project,
            execution_authority=execution_authority,
        ),
        "delivery-attempt:" + _hash({"locator_search": identity}),
        "locator-search-client:" + _hash({"locator_search": identity}),
    )


class S0LocatorSearchExecutionGate(LocatorSearchExecutionGate):
    """Adapter over ``ScaleS0Preflight`` and existing Standard lifecycle APIs."""

    def __init__(self, *, preflight: Any, request: Any, catalog: Any,
                 delivery_attempt_id: str, client_request_id: str,
                 request_identity: str,
                 now: datetime | None = None) -> None:
        # Import lazily to keep the provider-neutral interface independent of
        # the S0 implementation while still making production construction
        # structurally require the real preflight class.
        from charitygraph.scale_s0 import ScaleS0Preflight, SendRequest
        if not isinstance(preflight, ScaleS0Preflight) or not isinstance(request, SendRequest):
            raise ScalePreflightError("locator search requires the existing ScaleS0Preflight SendRequest gate")
        required = (catalog, delivery_attempt_id, client_request_id, request_identity)
        if any(item is None or not str(item) for item in required):
            raise ScalePreflightError("locator search requires durable Standard lifecycle identities")
        packet_map = getattr(preflight, "packets", None)
        if not isinstance(packet_map, Mapping):
            raise ScalePreflightError("locator search gate requires a constructed S0 preflight")
        packet = packet_map.get(request.packet_hash or "")
        if packet is None or packet.operation_kind != LOCATOR_SEARCH_OPERATION_KIND:
            raise ScalePreflightError("locator search gate requires a frozen locator-search packet")
        if (request.task_id, request.task_version, request.subject_id, request.scope_id,
            request.source_ids, request.route, request.packet_frozen) != (
                packet.task_id, packet.task_version, packet.subject_id, packet.scope_id,
                (), packet.routing_class, True):
            raise ScalePreflightError("locator search SendRequest is not bound to its frozen packet")
        if request_identity != packet.provider_request_identity:
            raise ScalePreflightError("locator search gate identity is not bound to its frozen packet")
        self.preflight, self.request, self.catalog = preflight, request, catalog
        self.delivery_attempt_id, self.client_request_id, self.request_identity = delivery_attempt_id, client_request_id, request_identity
        self.now = now or datetime.now(timezone.utc)
        self._started = False

    def begin(self, *, request_identity: str, subject_abn: str, query: str) -> None:
        if request_identity != self.request_identity:
            # The stable request identity is carried by the frozen packet and
            # cannot be substituted by a query caller.
            raise ScalePreflightError("locator search request identity does not match the frozen S0 request")
        if subject_abn != self.request.subject_id:
            raise ScalePreflightError("locator search subject is outside the frozen S0 request")
        packet = self.preflight.packets[self.request.packet_hash or ""]
        if query != packet.locator_query:
            raise ScalePreflightError("locator search query is not bound to the frozen S0 request")
        self.preflight.provider_send(self.request, now=self.now)
        self.catalog.mark_standard_send_started(self.delivery_attempt_id, client_request_id=self.client_request_id, now=self.now)
        self._started = True

    def complete(self, *, provider_receipt_id: str, result_ref: str, usage: Any = None) -> None:
        if not self._started:
            raise ScalePreflightError("locator search completion has no durable send-start")
        self.catalog.record_standard_transport_outcome(
            self.request.physical_attempt_id, status="PROVIDER_RESPONSE_RECEIVED",
            response_headers_received=True, response_identity=provider_receipt_id,
            usage=usage or {}, now=self.now,
        )
        self.catalog.complete_standard_delivery(self.delivery_attempt_id,
            provider_request_id=self.request_identity,
            provider_receipt_id=provider_receipt_id,
            raw_result_ref=result_ref, usage=usage or {}, result_ref=result_ref, now=self.now)
        self.catalog.record_standard_transport_outcome(
            self.request.physical_attempt_id, status="COMPLETED",
            response_headers_received=True, response_identity=provider_receipt_id,
            usage=usage or {}, now=self.now,
        )

    def fail(self, *, failure_class: str, message: str, ambiguous: bool = False) -> None:
        if self._started:
            self.catalog.record_standard_transport_outcome(
                self.request.physical_attempt_id,
                status="PROVIDER_CROSSING_AMBIGUOUS" if ambiguous else "PROVIDER_REJECTED",
                response_headers_received=False, transport_exception=message,
                now=self.now,
            )
            self.catalog.settle_standard_failure(self.delivery_attempt_id, failure_class=failure_class,
                message=message, ambiguous=ambiguous, now=self.now)


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
    """Production adapter over the already-governed Responses client.

    The execution gate is a concrete S0 preflight plus durable Standard
    lifecycle; arbitrary callbacks cannot authorize a provider crossing.
    """
    provider_id = "openai-responses-web-search"

    def __init__(self, client: Any, *, model: str, execution_gate: LocatorSearchExecutionGate) -> None:
        if client is None or not model or not isinstance(execution_gate, LocatorSearchExecutionGate):
            raise ScalePreflightError("locator search requires Responses client, model, and durable S0 execution gate")
        self.client, self.model, self.execution_gate = client, model, execution_gate

    def search(self, *, query: str, subject_abn: str, request_identity: str) -> LocatorSearchResponse:
        self.execution_gate.begin(request_identity=request_identity, subject_abn=subject_abn, query=query)
        try:
            response = self.client.responses.create(model=self.model, input=query,
                tools=[{"type": "web_search"}], store=False)
        except Exception as error:
            self.execution_gate.fail(failure_class="provider_transport_failure", message=str(error), ambiguous=True)
            raise
        response_id = str(getattr(response, "id", ""))
        if not response_id:
            self.execution_gate.fail(failure_class="provider_schema_failure", message="missing provider response identity")
            raise ScalePreflightError("Responses web-search result lacks provider call identity")
        self.execution_gate.complete(provider_receipt_id=response_id, result_ref="provider-response:" + response_id, usage=getattr(response, "usage", None))
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
        request_identity = locator_search_request_identity(subject_id=identity.subject_abn, query=query, query_index=query_index)
        response = provider.search(query=query, subject_abn=identity.subject_abn, request_identity=request_identity)
        for result in response.results[:MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY]:
            lineages.append(DiscoveryLineage(identity.subject_abn, query, provider.provider_id, response.provider_call_id,
                result.url, result.title, result.snippet, result.rank, result.source_metadata, (), False,
                "pending_identity_authentication"))
    return tuple(lineages)
