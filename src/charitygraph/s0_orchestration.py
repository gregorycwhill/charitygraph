"""The narrow production execution boundary for one durable Scale S0 attempt.

This module is intentionally an adapter, not a second runtime.  It rebuilds
authority from ``SQLiteCatalog`` for each item, delegates policy to
``ScaleS0Preflight``, delegates semantic transport to
``StandardCampaignCoordinator``, and delegates locator transport to the
existing ``S0LocatorSearchExecutionGate``.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

from .phase5_standard_transport import StandardCampaignCoordinator
from .s0_accounting import S0ProviderAccountingFactory
from .s0_locator_discovery import S0LocatorSearchExecutionGate
from .scale_s0 import (
    ExecutionAttemptIdentity, FrozenPacket, ScalePreflightError, ScaleS0Preflight,
    SendRequest,
)


class LocatorProvider(Protocol):
    provider_id: str
    def search(self, *, query: str, subject_abn: str, request_identity: str) -> Any: ...


@dataclass(frozen=True)
class S0SemanticWork:
    """A caller-supplied, already-frozen semantic request lifecycle row."""
    packet_id: str
    row: Mapping[str, Any]
    request: SendRequest


@dataclass(frozen=True)
class S0LocatorWork:
    packet_id: str
    request: SendRequest
    delivery_attempt_id: str
    client_request_id: str
    query: str


@dataclass(frozen=True)
class S0ExecutionSummary:
    attempt_id: str
    preflight: bool
    provider_posts: int
    locator_items: int
    semantic_items: int
    counts: Mapping[str, int]
    stop_campaign: bool
    errors: tuple[str, ...] = ()
    accounting: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["counts"] = dict(sorted(self.counts.items()))
        value["accounting"] = {key: dict(sorted(item.items())) for key, item in sorted(self.accounting.items())}
        return value


class ScaleS0Executor:
    """Execute only one catalog-bound attempt; no authority is created here."""

    def __init__(self, *, catalog: Any, attempt_id: str, builder_commit_sha: str,
                 runtime_root: str | Path,
                 provider: Any = None, locator_provider: LocatorProvider | None = None,
                 locator_provider_factory: Callable[[Any, FrozenPacket, Any], LocatorProvider] | None = None,
                 now: Callable[[], datetime] | None = None,
                 max_concurrency: int = 1,
                 accounting: Any = None,
                 pricing_snapshot: Any = None,
                 on_reconciled: Callable[[Mapping[str, Any], Any, Mapping[str, Any]], None] | None = None) -> None:
        if catalog is None or not attempt_id or not builder_commit_sha:
            raise ValueError("catalog, attempt_id, and builder_commit_sha are required")
        self.catalog = catalog
        self.attempt_id = attempt_id
        self.builder_commit_sha = builder_commit_sha
        self.runtime_root = Path(runtime_root)
        self.provider = provider
        self.locator_provider = locator_provider
        self.locator_provider_factory = locator_provider_factory
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.max_concurrency = max_concurrency
        self.accounting = accounting or S0ProviderAccountingFactory(catalog=catalog, now=self.now, execution_attempt_id=attempt_id, pricing_snapshot=pricing_snapshot).create()
        self.on_reconciled = on_reconciled

    def _attempt(self) -> ExecutionAttemptIdentity:
        row = self.catalog.get_scale_s0_execution_attempt(self.attempt_id)
        if row is None:
            raise ScalePreflightError("durable execution attempt is absent")
        material = row.get("material")
        if not isinstance(material, Mapping):
            raise ScalePreflightError("durable execution attempt material is absent")
        expected = ExecutionAttemptIdentity(**{name: material[name] for name in ExecutionAttemptIdentity.__dataclass_fields__})
        if expected.builder_commit_sha != self.builder_commit_sha:
            raise ScalePreflightError("durable execution attempt is bound to a different Builder head")
        self.catalog.require_scale_s0_execution_attempt(
            attempt_id=expected.attempt_id, mandate_id=expected.mandate_id,
            mandate_hash=expected.mandate_hash, slice_id=expected.slice_id,
            run_id=expected.run_id, builder_commit_sha=expected.builder_commit_sha,
            data_commit_sha=expected.data_commit_sha,
            bridge_certification=expected.bridge_certification,
            schema_version=expected.schema_version)
        if expected.material_hash != row.get("material_hash"):
            raise ScalePreflightError("durable execution attempt material hash mismatch")
        return expected

    def _preflight_for(self, packet_id: str) -> tuple[ExecutionAttemptIdentity, ScaleS0Preflight, FrozenPacket]:
        attempt = self._attempt()
        stored = self.catalog.get_scale_s0_frozen_packet(packet_id)
        if stored is None:
            raise ScalePreflightError("durable frozen packet is absent")
        material = stored.get("material")
        if not isinstance(material, Mapping):
            raise ScalePreflightError("durable frozen packet material is absent")
        packet = FrozenPacket(**{name: material[name] for name in FrozenPacket.__dataclass_fields__ if name in material})
        if packet.packet_id != packet_id or material.get("binding_hash") != packet.binding_hash:
            raise ScalePreflightError("durable frozen packet material is substituted")
        live = ScaleS0Preflight.from_catalog(self.catalog, mandate_id=attempt.mandate_id, packet_id=packet_id)
        if live.execution_attempt is None or live.execution_attempt.attempt_id != attempt.attempt_id:
            raise ScalePreflightError("packet is not bound to the requested execution attempt")
        return attempt, live, packet

    def _semantic_evaluator(self, item: S0SemanticWork) -> Callable[[dict[str, Any]], Any]:
        def evaluate(row: dict[str, Any]) -> Any:
            attempt, preflight, packet = self._preflight_for(item.packet_id)
            if row.get("provider_request_item_id") != packet.provider_request_identity:
                raise ScalePreflightError("semantic row identity is not bound to its frozen packet")
            preflight.provider_send(item.request, now=self.now(), allow_prepared_lifecycle=True)
            return type("Evaluation", (), {"authorized": True})()
        return evaluate

    def _validate_item_request(self, item: S0SemanticWork) -> None:
        _, preflight, packet = self._preflight_for(item.packet_id)
        if item.request.packet_hash != packet.binding_hash or item.request.subject_id != packet.subject_id:
            raise ScalePreflightError("semantic request is not bound to its frozen packet")
        if item.request.provider_account_project is None or item.request.execution_authority is None:
            raise ScalePreflightError("semantic request lacks explicit A3 account/project and authority")
        request_id = str(item.row.get("provider_request_item_id", ""))
        if request_id != packet.provider_request_identity or item.row.get("physical_attempt_id") != item.request.physical_attempt_id:
            raise ScalePreflightError("semantic lifecycle identity is not bound to its frozen packet")

    def _run_semantic(self, items: tuple[S0SemanticWork, ...], *, dry_run: bool) -> tuple[list[dict[str, Any]], int, bool]:
        if not items:
            return [], 0, False
        results: list[dict[str, Any]] = []
        pending: list[S0SemanticWork] = []
        for item in items:
            self._validate_item_request(item)
            packet = self._preflight_for(item.packet_id)[2]
            durable = self.catalog.get_provider_request_item(packet.provider_request_identity)
            if durable is not None and durable.get("status") in {"completed", "failed", "held", "send_ambiguous", "cancelled"}:
                if durable.get("status") == "completed" and not dry_run:
                    try:
                        self.accounting.reconcile_durable(request=item.request, packet=packet)
                    except Exception as error:
                        results.append({"request_item_id": packet.provider_request_identity,
                                        "status": "accounting_recovery_failed", "provider_posts": 0,
                                        "error": str(error)[:512]})
                        return results, 0, True
                results.append({"request_item_id": packet.provider_request_identity,
                                "status": "replayed_terminal", "provider_posts": 0})
                continue
            pending.append(item)
        items = tuple(pending)
        if not items:
            return results, 0, False
        if dry_run:
            for item in items:
                _, preflight, _ = self._preflight_for(item.packet_id)
                preflight.provider_send(item.request, now=self.now(), allow_prepared_lifecycle=True)
            results.extend({"request_item_id": str(item.row["provider_request_item_id"]), "status": "eligible", "provider_posts": 0} for item in items)
            return results, 0, False
        if self.provider is None:
            raise ScalePreflightError("semantic execution requires the canonical Standard provider")
        coordinator = StandardCampaignCoordinator(
            catalog=self.catalog, provider=self.provider, runtime_root=self.runtime_root,
            max_concurrency=self.max_concurrency,
            now=None,
            on_reconciled=lambda row, response, usage: self._reconcile_semantic(items, row, response, usage),
            mandate_evaluator=lambda row: next(self._semantic_evaluator(item)(row) for item in items if item.row["provider_request_item_id"] == row["provider_request_item_id"]),
        )
        result = coordinator.run([dict(item.row) for item in items])
        combined = results + result["results"]
        accounting_failed = any(item.get("status") in {"completed_accounting_failed", "accounting_recovery_failed"} for item in combined)
        return combined, int(result["provider_posts"]), bool(result["stop_campaign"] or accounting_failed)

    def _reconcile_semantic(self, items: tuple[S0SemanticWork, ...], row: Mapping[str, Any], response: Any, usage: Any) -> None:
        item = next(item for item in items if item.row["provider_request_item_id"] == row["provider_request_item_id"])
        packet = self._preflight_for(item.packet_id)[2]
        receipt_id = "standard-receipt:" + __import__("hashlib").sha256((packet.provider_request_identity + ":" + str(response.body["id"])).encode()).hexdigest()
        self.accounting.reconcile(request=item.request, packet=packet, provider_receipt_id=receipt_id, usage=usage, provider_response=response)
        if self.on_reconciled is not None:
            self.on_reconciled(row, response, usage)

    def _run_locator(self, items: tuple[S0LocatorWork, ...], *, dry_run: bool) -> tuple[list[dict[str, Any]], int, bool]:
        results: list[dict[str, Any]] = []
        posts = 0
        for item in sorted(items, key=lambda value: value.packet_id):
            _, preflight, packet = self._preflight_for(item.packet_id)
            durable = self.catalog.get_provider_request_item(packet.provider_request_identity)
            if durable is not None and durable.get("status") in {"completed", "failed", "held", "send_ambiguous", "cancelled"}:
                if durable.get("status") == "completed":
                    try:
                        self.accounting.reconcile_durable(request=item.request, packet=packet)
                    except Exception as error:
                        results.append({"request_item_id": packet.provider_request_identity,
                                        "status": "accounting_recovery_failed", "provider_posts": 0,
                                        "error": str(error)[:512]})
                        return results, posts, True
                results.append({"request_item_id": packet.provider_request_identity, "status": "replayed_terminal", "provider_posts": 0})
                continue
            item_locator_provider = (self.locator_provider_factory(item.request, packet, preflight)
                                     if self.locator_provider_factory is not None else self.locator_provider)
            supplied_gate = getattr(item_locator_provider, "execution_gate", None)
            if supplied_gate is not None:
                if (getattr(supplied_gate, "request_identity", None) != packet.provider_request_identity
                        or getattr(getattr(supplied_gate, "request", None), "physical_attempt_id", None) != item.request.physical_attempt_id):
                    raise ScalePreflightError("locator provider gate is bound to a different request")
                gate = supplied_gate
            else:
                gate = S0LocatorSearchExecutionGate(
                    preflight=preflight, request=item.request, catalog=self.catalog,
                    delivery_attempt_id=item.delivery_attempt_id,
                    client_request_id=item.client_request_id,
                    request_identity=packet.provider_request_identity, now=self.now())
            if dry_run:
                preflight.provider_send(item.request, now=self.now())
                results.append({"request_item_id": packet.provider_request_identity, "status": "eligible", "provider_posts": 0})
                continue
            if item_locator_provider is None:
                raise ScalePreflightError("locator execution requires the governed locator provider")
            provider_manages_gate = supplied_gate is not None
            provider_crossing_started = False
            try:
                if not provider_manages_gate:
                    gate.begin(request_identity=packet.provider_request_identity,
                               subject_abn=packet.subject_id, query=item.query)
                provider_crossing_started = True
                response = item_locator_provider.search(query=item.query, subject_abn=packet.subject_id, request_identity=packet.provider_request_identity)
                response_id = str(getattr(response, "provider_call_id", ""))
                if not response_id:
                    raise ScalePreflightError("locator provider response lacks a durable identity")
                if not provider_manages_gate:
                    gate.complete(provider_receipt_id=response_id,
                                  result_ref="provider-response:" + response_id,
                                  usage=getattr(response, "usage", None))
                try:
                    provider_response = response
                    if not hasattr(provider_response, "body") and getattr(response, "response_body", None) is not None:
                        provider_response = type("LocatorProviderResponse", (), {"body": response.response_body})()
                    self.accounting.reconcile(request=item.request, packet=packet,
                                              provider_receipt_id=response_id,
                                              usage=getattr(response, "usage", None), provider_response=provider_response)
                except Exception as error:
                    results.append({"request_item_id": packet.provider_request_identity,
                                    "status": "completed_accounting_failed", "provider_posts": 1,
                                    "error": str(error)[:512]})
                    return results, posts + 1, True
                if self.on_reconciled is not None:
                    try:
                        self.on_reconciled({"provider_request_item_id": packet.provider_request_identity,
                                            "physical_attempt_id": item.request.physical_attempt_id},
                                           response, getattr(response, "usage", None) or {})
                    except Exception as error:
                        results.append({"request_item_id": packet.provider_request_identity,
                                        "status": "completed_accounting_failed", "provider_posts": 1,
                                        "error": str(error)[:512]})
                        return results, posts + 1, True
                results.append({"request_item_id": packet.provider_request_identity, "status": "completed", "provider_posts": 1, "response_id": response_id})
                posts += 1
            except Exception as error:
                # The governed provider adapter records the outcome.  A
                # crossing ambiguity stops the campaign; a definite rejection
                # is terminal for this item but does not authorize a retry.
                if not provider_manages_gate:
                    gate.fail(failure_class="provider_transport_failure", message=str(error), ambiguous=True)
                post_count = int(provider_crossing_started)
                results.append({"request_item_id": packet.provider_request_identity, "status": "failed", "provider_posts": post_count, "error": str(error)[:512]})
                return results, posts + post_count, True
        return results, posts, False

    def run(self, *, semantic: Iterable[S0SemanticWork] = (), locator: Iterable[S0LocatorWork] = (), dry_run: bool = False) -> S0ExecutionSummary:
        semantic_items, locator_items = tuple(semantic), tuple(locator)
        self._attempt()  # reconstruct once before work, then again per item
        if not semantic_items and not locator_items:
            return S0ExecutionSummary(self.attempt_id, dry_run, 0, 0, 0, {}, False)
        semantic_results, semantic_posts, semantic_stop = self._run_semantic(semantic_items, dry_run=dry_run)
        if semantic_stop:
            locator_results, locator_posts, locator_stop = [], 0, True
        else:
            locator_results, locator_posts, locator_stop = self._run_locator(locator_items, dry_run=dry_run)
        all_results = semantic_results + locator_results
        counts: dict[str, int] = {}
        for result in all_results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        accounting: dict[str, Mapping[str, str]] = {}
        reservations = {item.request.reservation_id for item in (*semantic_items, *locator_items) if item.request.reservation_id}
        for reservation_id in sorted(reservations):
            position = self.catalog.accounting_reservation_position(reservation_id)
            accounting[reservation_id] = {key: str(value) for key, value in position.items()}
        return S0ExecutionSummary(self.attempt_id, dry_run, semantic_posts + locator_posts,
                                   len(locator_items), len(semantic_items), counts,
                                   semantic_stop or locator_stop, accounting=accounting)


def summary_json(summary: S0ExecutionSummary) -> str:
    return json.dumps(summary.as_dict(), sort_keys=True, separators=(",", ":"))


__all__ = ["S0SemanticWork", "S0LocatorWork", "S0ExecutionSummary", "ScaleS0Executor", "summary_json"]
