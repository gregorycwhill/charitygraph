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
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

from charitygraph.scale_s0 import (
    ExecutionAttemptIdentity, FrozenPacket, LOCATOR_SEARCH_MAX_QUERIES_PER_SUBJECT,
    LOCATOR_SEARCH_OPERATION_KIND,
    RoutingClass, ScalePreflightError, SendRequest, locator_search_request_identity,
    validate_locator_subject_reference,
)
from charitygraph.phase5_standard_transport import (
    OpenAIResponsesWebSearchTransport,
    StandardTransportError,
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
    usage: Mapping[str, Any] | None = None
    response_body: Mapping[str, Any] | None = None


class LocatorSearchProvider(Protocol):
    """Provider-neutral locator search for a governed subject and ABN seed."""
    provider_id: str

    def search(self, *, query: str, locator_subject_ref: str, locator_abn: str,
               request_identity: str) -> LocatorSearchResponse: ...


class LocatorSearchExecutionGate(ABC):
    """The only execution seam permitted between discovery and a provider.

    Implementations must delegate to the existing S0 preflight and durable
    Standard provider lifecycle.  A boolean callback is intentionally not a
    valid gate.
    """

    @abstractmethod
    def begin(self, *, request_identity: str, locator_subject_ref: str,
              locator_abn: str, query: str) -> None: ...

    @abstractmethod
    def complete(self, *, provider_receipt_id: str, result_ref: str, usage: Any = None,
                 response_facts: Any = None) -> None: ...

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
                                 locator_subject_ref: str, locator_abn: str,
                                 query: str, query_index: int,
                                 pricing: LocatorSearchPrice, frozen_at: str,
                                 provider_account_project: str,
                                 execution_authority: str,
                                 structured_authority: Any | None = None,
                                 scope_id: str = "scope:organisation") -> FrozenPacket:
    """Compile a deterministic operational packet without evidence or a send."""
    if execution_attempt.mandate_id != mandate.mandate_id or execution_attempt.slice_id != mandate.slice_id:
        raise ScalePreflightError("locator search packet execution identity is outside the mandate")
    if pricing.currency != mandate.currency_basis:
        raise ScalePreflightError("locator search price currency must equal the frozen S0 currency")
    if not provider_account_project or not execution_authority:
        raise ScalePreflightError("locator search packet requires explicit immutable A3 account/project and authority")
    if structured_authority is not None:
        # New compiler-produced packets carry the digest, never a caller's
        # prose label.  Legacy packets remain readable but cannot be promoted
        # into a structured checkpoint without this validation.
        structured_authority.validate()
        if (structured_authority.hash != execution_authority or query_index != 0
                or structured_authority.provider_project != provider_account_project
                or structured_authority.attempt_id != execution_attempt.attempt_id):
            raise ScalePreflightError("structured authority does not bind this executable locator packet")
        binding = next((x for x in structured_authority.subject_bindings if x.locator_subject_ref == locator_subject_ref), None)
        if binding is None or (binding.identifier_scheme, binding.identifier_value) != ("ABN", locator_abn):
            raise ScalePreflightError("structured authority does not bind this locator subject/identifier")
    request_identity = locator_search_request_identity(
        locator_subject_ref=locator_subject_ref, locator_identifier_scheme="ABN",
        locator_identifier_value=locator_abn, query=query, query_index=query_index,
        execution_attempt_id=execution_attempt.attempt_id,
        provider_account_project=provider_account_project,
        execution_authority=execution_authority,
    )
    material = {
        "mandate": mandate.identity_hash,
        "execution_attempt": execution_attempt.attempt_id,
        "provider_account_project": provider_account_project,
        "execution_authority": execution_authority,
        "operation": LOCATOR_SEARCH_OPERATION_KIND,
        "locator_subject_ref": locator_subject_ref,
        "external_identifier": {"scheme": "ABN", "value": locator_abn},
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
        "urn:charitygraph:scale-s0:locator_search", "1.0", locator_subject_ref, scope_id,
        (), (), "profile:locator-search:1",
        "urn:charitygraph:builder:schema:locator-search-discovery-metadata:1.0",
        RoutingClass.LOW_COST_SEMANTIC, request_identity, content_hash,
        mandate_id=mandate.mandate_id, slice_id=mandate.slice_id,
        frozen_at=frozen_at, operation_kind=LOCATOR_SEARCH_OPERATION_KIND,
        locator_query=query, locator_query_index=query_index,
        pricing_snapshot_id=pricing.pricing_snapshot_id,
        estimated_provider_cost=pricing.estimated_provider_cost,
        locator_execution_attempt_id=execution_attempt.attempt_id,
        provider_account_project=provider_account_project,
        execution_authority=execution_authority,
        locator_identifier_scheme="ABN", locator_identifier_value=locator_abn,
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
    if (provider_account_project != packet.provider_account_project
            or execution_authority != packet.execution_authority):
        raise ScalePreflightError("locator search request A3 binding does not match the frozen packet")
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
                 now: datetime | Callable[[], datetime] | None = None) -> None:
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
        # Do not capture a production clock at gate construction: a fresh A3
        # window can expire while a prepared packet is waiting to send.  Tests
        # may supply a fixed instant or a deterministic clock.
        self._clock = now if callable(now) else (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
        self._started = False
        self._transport_invoked = False
        self._physical_crossing = False
        self._last_send_authorizing_now: datetime | None = None

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise ScalePreflightError("locator execution clock must return a datetime")
        return value

    def _send_authorizing_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ScalePreflightError("locator execution clock must return a timezone-aware datetime")
        prior = self._last_send_authorizing_now
        if prior is not None and value < prior:
            raise ScalePreflightError("locator execution clock moved backwards during send authorization")
        self._last_send_authorizing_now = value
        return value

    @property
    def provider_posts(self) -> int:
        """Count a real or possibly-real transport crossing, never gate entry."""
        return int(self._physical_crossing)

    @property
    def crossing_started(self) -> bool:
        return self._started

    def transport_invoked(self) -> None:
        self._transport_invoked = True

    def transport_outcome(self, *, physical: bool) -> None:
        self._physical_crossing = self._physical_crossing or physical

    def begin(self, *, request_identity: str, locator_subject_ref: str,
              locator_abn: str, query: str) -> None:
        if request_identity != self.request_identity:
            # The stable request identity is carried by the frozen packet and
            # cannot be substituted by a query caller.
            raise ScalePreflightError("locator search request identity does not match the frozen S0 request")
        if locator_subject_ref != self.request.subject_id:
            raise ScalePreflightError("locator search subject is outside the frozen S0 request")
        packet = self.preflight.packets[self.request.packet_hash or ""]
        if packet.locator_identifier_scheme != "ABN" or locator_abn != packet.locator_identifier_value:
            raise ScalePreflightError("locator search ABN is outside the frozen S0 request")
        if query != packet.locator_query:
            raise ScalePreflightError("locator search query is not bound to the frozen S0 request")
        # The pre-POST trace is part of the durable request identity.  It must
        # describe the exact bytes the sole transport owner will serialize;
        # never accept a legacy role/content body as equivalent to this body.
        from .scale_s0 import locator_search_request_body_sha256
        trace = self.catalog.get_standard_transport_trace(self.request.physical_attempt_id)
        if trace is None or trace.get("request_body_sha256") != locator_search_request_body_sha256(query):
            raise ScalePreflightError("locator search transport trace body does not match the canonical request")
        self.preflight.provider_send(self.request, now=self._send_authorizing_now())
        # The first proof reconstructs packet/rights/reservation authority;
        # the second proof is deliberately adjacent to send-started so an A3
        # window expiring during preparation cannot authorize a crossing.
        self.preflight.provider_send(self.request, now=self._send_authorizing_now())
        # Use one final fresh observation both to re-authorise and to stamp the
        # durable crossing.  A new observation must never advance send-started
        # past the last A3 proof: expiry in that final seam otherwise permits a
        # physical POST under an unvalidated clock instant.
        send_started_at = self._send_authorizing_now()
        self.preflight.provider_send(self.request, now=send_started_at)
        self.catalog.mark_standard_send_started(
            self.delivery_attempt_id,
            client_request_id=self.client_request_id,
            now=send_started_at,
        )
        self._started = True

    def complete(self, *, provider_receipt_id: str, result_ref: str, usage: Any = None,
                 response_facts: Any = None) -> None:
        if not self._started:
            raise ScalePreflightError("locator search completion has no durable send-start")
        self._physical_crossing = True
        self.catalog.record_standard_transport_outcome(
            self.request.physical_attempt_id, status="PROVIDER_RESPONSE_RECEIVED",
            response_headers_received=True, response_identity=provider_receipt_id,
            usage=usage or {}, now=self._now(),
        )
        self.catalog.complete_standard_delivery(self.delivery_attempt_id,
            provider_request_id=self.request_identity,
            provider_receipt_id=provider_receipt_id,
            raw_result_ref=result_ref, usage=usage or {}, result_ref=result_ref, now=self._now(),
            response_facts=response_facts)
        self.catalog.record_standard_transport_outcome(
            self.request.physical_attempt_id, status="COMPLETED",
            response_headers_received=True, response_identity=provider_receipt_id,
            usage=usage or {}, now=self._now(),
        )

    def fail(self, *, failure_class: str, message: str, ambiguous: bool = False) -> None:
        if ambiguous:
            self._physical_crossing = True
        if self._started:
            # A response receipt is a completed transport/accounting fact even
            # when discovery-only metadata subsequently fails schema checks.
            # Do not rewrite it into a transport failure or ambiguity.
            physical = self.catalog.get_physical_attempt(self.request.physical_attempt_id)
            if not ambiguous and physical is not None and physical.get("status") == "validated":
                outcome = "provider_schema_failure" if failure_class == "provider_schema_failure" else "provider_validation_failure"
                self.catalog.record_scale_s0_locator_terminal_outcome(
                    self.request.physical_attempt_id, outcome_class=outcome,
                    message=message, now=self._now())
                return
            self.catalog.record_standard_transport_outcome(
                self.request.physical_attempt_id,
                status="PROVIDER_CROSSING_AMBIGUOUS" if ambiguous else "PROVIDER_REJECTED",
                response_headers_received=False, transport_exception=message,
                now=self._now(),
            )
            self.catalog.settle_standard_failure(self.delivery_attempt_id, failure_class=failure_class,
                message=message, ambiguous=ambiguous, now=self._now())


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
    """A governed locator subject plus an authority-scoped ABN lookup seed."""
    locator_subject_ref: str
    legal_or_trading_name: str
    locator_abn: str
    acn_or_acnc_identifier: str = ""
    governed_identity_anchors: tuple[str, ...] = ()

    def queries(self) -> tuple[str, ...]:
        """Generate at most five mechanical combinations of approved fields."""
        fields = tuple(x for x in (self.legal_or_trading_name, self.locator_abn, self.acn_or_acnc_identifier, *self.governed_identity_anchors) if x)
        if not self.locator_subject_ref or not self.locator_abn or not self.legal_or_trading_name:
            raise ScalePreflightError("locator discovery requires a governed subject, external ABN lookup identifier, and legal or trading name")
        validate_locator_subject_reference(
            locator_subject_ref=self.locator_subject_ref,
            locator_identifier_scheme="ABN",
            locator_identifier_value=self.locator_abn,
        )
        base = (f'"{self.legal_or_trading_name}" "{self.locator_abn}"', f'"{self.legal_or_trading_name}"')
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
    locator_subject_ref: str
    locator_abn: str
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
    """Production locator provider over the governed Standard transport.

    The execution gate is a concrete S0 preflight plus durable Standard
    lifecycle; arbitrary callbacks cannot authorize a provider crossing.
    """
    provider_id = "openai-responses-web-search"

    def __init__(self, transport: OpenAIResponsesWebSearchTransport, *, model: str,
                 execution_gate: LocatorSearchExecutionGate) -> None:
        if not isinstance(transport, OpenAIResponsesWebSearchTransport) or model != "gpt-5.6-luna" or not isinstance(execution_gate, LocatorSearchExecutionGate):
            raise ScalePreflightError("locator search requires the authorised Standard transport, Luna model, and durable S0 execution gate")
        self.transport, self.model, self.execution_gate = transport, model, execution_gate

    def search(self, *, query: str, locator_subject_ref: str, locator_abn: str,
               request_identity: str) -> LocatorSearchResponse:
        # A live gate carries the exact A3 project binding.  Refuse a client
        # that is absent, unbound, or bound to another project before the gate
        # can mark send-started.  Lightweight provider-free test gates may not
        # expose a request and are intentionally exempt from this live check.
        gate_request = getattr(self.execution_gate, "request", None)
        if gate_request is not None:
            client_project = getattr(self.transport.client, "provider_account_project", None)
            expected_project = getattr(gate_request, "provider_account_project", None)
            if not client_project or not expected_project or client_project != expected_project:
                raise ScalePreflightError("canonical HTTP client project does not match the durable A3 project")
        self.execution_gate.begin(request_identity=request_identity,
                                  locator_subject_ref=locator_subject_ref,
                                  locator_abn=locator_abn, query=query)
        mark_invoked = getattr(self.execution_gate, "transport_invoked", None)
        if callable(mark_invoked):
            mark_invoked()
        try:
            response = self.transport.create_web_search_once(
                model=self.model, query=query,
                client_request_id=self.execution_gate.client_request_id,
            )
        except StandardTransportError as error:
            record_outcome = getattr(self.execution_gate, "transport_outcome", None)
            if callable(record_outcome):
                record_outcome(physical=error.ambiguous or error.response_headers_received)
            # A response header proves that the POST crossed the provider
            # boundary.  If decoding cannot yield a durable response identity,
            # its cost cannot safely be reconciled or released.
            ambiguous = error.ambiguous or error.response_headers_received
            self.execution_gate.fail(
                failure_class="provider_ambiguous_transport" if ambiguous else "provider_rejected",
                message=str(error), ambiguous=ambiguous,
            )
            raise
        except Exception as error:
            record_outcome = getattr(self.execution_gate, "transport_outcome", None)
            if callable(record_outcome):
                record_outcome(physical=True)
            # Transport was invoked and this unclassified path supplies no
            # evidence that bytes did not leave the process.  Never turn that
            # uncertainty into a release-eligible definite rejection.
            self.execution_gate.fail(failure_class="provider_ambiguous_transport", message=str(error), ambiguous=True)
            raise
        response_id = response.body.get("id") if isinstance(response.body, Mapping) else None
        if not isinstance(response_id, str) or not response_id.strip():
            self.execution_gate.fail(failure_class="provider_ambiguous_transport", message="missing trustworthy provider response identity", ambiguous=True)
            raise ScalePreflightError("Responses web-search result lacks provider call identity")
        usage = response.body.get("usage")
        response_facts = self._pricing_facts(response.body)
        # The receipt boundary comes before all locator-result parsing.  This
        # keeps a definite provider response durable even when requested source
        # metadata is missing or malformed.
        self.execution_gate.complete(provider_receipt_id=response_id,
                                     result_ref="provider-response:" + response_id,
                                     usage=usage, response_facts=response_facts)
        # A decoded response with an explicit non-completed state remains a
        # billable transport/accounting fact, but must never yield discovery
        # metadata.  Older fixture-compatible bodies omit these fields.
        if (response.body.get("status") is not None and response.body.get("status") != "completed") or response.body.get("incomplete_details") is not None:
            self.execution_gate.fail(failure_class="provider_validation_failure", message="provider response was not completed")
            raise ScalePreflightError("Responses web-search result was not completed")
        results: list[LocatorSearchResult] = []
        # Preserve only source fields actually returned by the API.  Locator
        # discovery must not invent snippets, ranks, or usage.
        output = response.body.get("output", ())
        if not isinstance(output, list):
            self.execution_gate.fail(failure_class="provider_schema_failure", message="invalid provider output structure")
            raise ScalePreflightError("Responses web-search result has invalid output structure")
        saw_web_search_call = False
        for item in output:
            if not isinstance(item, Mapping):
                continue
            # Sources are meaningful only on the definitive tool-call output
            # item.  Do not let an unexpected message/reasoning item smuggle
            # discovery metadata across this boundary.
            if item.get("type") != "web_search_call":
                continue
            saw_web_search_call = True
            action = item.get("action")
            sources = action.get("sources") if isinstance(action, Mapping) else None
            if not isinstance(sources, list):
                self.execution_gate.fail(failure_class="provider_schema_failure", message="missing web-search source structure")
                raise ScalePreflightError("Responses web-search result lacks source structure")
            for source in sources:
                if not isinstance(source, Mapping) or not isinstance(source.get("url"), str) or not source["url"]:
                    continue
                metadata = {key: str(source[key]) for key in ("title", "type") if isinstance(source.get(key), (str, int, float, bool))}
                results.append(LocatorSearchResult(url=source["url"], title=metadata.get("title", ""), source_metadata=metadata or None))
        if not saw_web_search_call:
            self.execution_gate.fail(failure_class="provider_schema_failure", message="missing web-search source structure")
            raise ScalePreflightError("Responses web-search result lacks source structure")
        return LocatorSearchResponse(response_id, tuple(results[:MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY]), usage=usage if isinstance(usage, Mapping) else None, response_body=response.body)

    @staticmethod
    def _pricing_facts(body: Mapping[str, Any]) -> dict[str, Any] | None:
        """Extract only deterministic pricing dimensions, never source metadata."""
        model, output = body.get("model"), body.get("output")
        if model != "gpt-5.6-luna" or not isinstance(output, list):
            return None
        count = 0
        for item in output:
            if not isinstance(item, Mapping):
                return None
            if item.get("type") != "web_search_call":
                continue
            count += 1
        return {"model": model, "web_search_calls": count}


def discover(provider: LocatorSearchProvider, identity: PublicEntityIdentity, *,
             existing_lineage: Sequence[DiscoveryLineage] = ()) -> tuple[DiscoveryLineage, ...]:
    """Call only the authority-class executable query; alternates are provenance.

    This legacy discovery helper has no budget material itself, so it must use
    the same conservative first-candidate rule as the structured compiler.
    """
    lineages: list[DiscoveryLineage] = []
    completed_queries = {(row.locator_subject_ref, row.locator_abn, row.query) for row in existing_lineage}
    for query_index, query in enumerate(identity.queries()[:1]):
        if (identity.locator_subject_ref, identity.locator_abn, query) in completed_queries:
            continue
        # Discovery is provider-neutral; a production crossing is only possible
        # through a FrozenPacket, whose identity binds attempt and A3 material.
        request_identity = "locator-discovery:" + _hash({"locator_subject_ref": identity.locator_subject_ref,
                                                            "locator_abn": identity.locator_abn,
                                                            "query": query, "index": query_index})
        response = provider.search(query=query, locator_subject_ref=identity.locator_subject_ref,
                                   locator_abn=identity.locator_abn, request_identity=request_identity)
        for result in response.results[:MAX_SEARCH_RESULTS_CONSIDERED_PER_QUERY]:
            lineages.append(DiscoveryLineage(identity.locator_subject_ref, identity.locator_abn, query,
                provider.provider_id, response.provider_call_id,
                result.url, result.title, result.snippet, result.rank, result.source_metadata, (), False,
                "pending_identity_authentication"))
    return tuple(lineages)
