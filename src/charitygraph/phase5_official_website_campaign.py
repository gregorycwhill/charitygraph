"""Immutable, known-URL acquisition preparation for Phase-5 official sites.

This module deliberately separates an immutable acquisition intent from the
runtime result.  It orchestrates the existing bounded ``NetworkLedger`` and
source-provenance primitives; it does not implement another HTTP client.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contracts import AcquisitionReceipt
from .contracts.ids import deterministic_id
from .baseline_corpus import MaterialOrigin
from .evidence_store import ContentAddressedArtifactStore
from .phase5_baseline_corpus import (
    NetworkLedger,
    NetworkPolicyError,
    governed_website_hosts,
    governed_website_url,
    persist_available,
    source_definition,
)
from .runtime import SQLiteCatalog


CAMPAIGN_VERSION = "phase5-known-url-official-website-acquisition-v1"
DISCOVERY_REQUIRED_ABNS = frozenset({
    "30157737329", "60964279191", "47613674461", "94178965125",
    "84114483091", "22627812672", "16641057338", "85182077563",
    "53406142168", "56190972059", "41069508398", "46029271914",
    "21194706909",
})
RANK_67_ABN = "15000002522"
KNOWN_URL_STATES = frozenset({"provenance_unresolved", "attempted_unavailable", "not_attempted"})


class AcquisitionCampaignError(RuntimeError):
    """A campaign invariant failed before an external operation."""


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _url(value: str) -> str:
    normalized = governed_website_url(value)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcquisitionCampaignError("governed official URL is not an absolute HTTP(S) locator")
    return normalized


def _profiles(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))["entities"]


def _identity_rows(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["abn"]): row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def _official_inventory(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["abn"]): row for row in payload["cells"] if row["source_family"] == "official_website"}


def build_campaign(*, profiles_path: Path, identity_map_path: Path, inventory_path: Path) -> dict[str, Any]:
    """Build the exact governed known-URL campaign, with no runtime mutation."""
    profiles, identities, inventory = _profiles(profiles_path), _identity_rows(identity_map_path), _official_inventory(inventory_path)
    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    for abn, item in sorted(inventory.items(), key=lambda pair: (int(pair[1].get("rank", 0)), pair[0])):
        profile = profiles.get(abn) or {}
        governed = ((profile.get("profile") or {}).get("data") or {}).get("Website")
        state = str(item.get("state"))
        if abn == RANK_67_ABN:
            exclusions.append({"abn": abn, "reason": "rank_67_not_in_direct_service_task_set"})
            continue
        if abn in DISCOVERY_REQUIRED_ABNS:
            if governed:
                raise AcquisitionCampaignError(f"discovery-required ABN unexpectedly has governed URL: {abn}")
            exclusions.append({"abn": abn, "reason": "url_discovery_required"})
            continue
        if state == "acquired_available":
            exclusions.append({"abn": abn, "reason": "already_admitted_clean_material"})
            continue
        if state not in KNOWN_URL_STATES or not governed:
            raise AcquisitionCampaignError(f"known-URL candidate is not governed and eligible: {abn}")
        identity = identities.get(abn)
        if identity is None:
            raise AcquisitionCampaignError(f"known-URL candidate has no canonical subject identity: {abn}")
        original = str(governed)
        normalized = _url(original)
        hosts = sorted(governed_website_hosts(normalized))
        intent = {
            "subject_id": str(identity["subject_id"]), "abn": abn,
            "governed_url": original, "normalized_initial_url": normalized,
            "source_family": "official_website", "http_method": "GET",
            "allowed_initial_host": (urlsplit(normalized).hostname or "").casefold(),
            "permitted_redirect_hosts": hosts, "redirect_policy": "same_governed_host_or_www_counterpart_only",
            "timeout_seconds": 45, "max_response_bytes": 30_000_000,
            "max_initial_requests": 1, "retry_policy": "no_automatic_retry",
            "retention_strategy": "content_addressed_raw_bytes_then_receipt_then_source_record",
            "governed_url_evidence": "acnc_profile.data.Website",
            "current_source_state": state, "current_source_reason": str(item.get("reason") or ""),
        }
        # `acq:` is the established deterministic namespace for governed
        # acquisition operations.  The intent identity stays distinct from a
        # receipt because successful receipts additionally include the actual
        # response hash, which is not known at preparation time.
        intent["acquisition_attempt_id"] = deterministic_id("acq:", intent)
        intent["receipt_identity_inputs"] = {"source_definition_family": "official_website", "requested_locator": normalized, "content_hash": "runtime_response_sha256"}
        intent["source_record_identity_inputs"] = {"source_family": "official_website", "source_role": "official_homepage", "resolved_locator": "runtime_resolved_url", "payload_hash": "runtime_response_sha256"}
        rows.append(intent)
    if len(rows) != 80 or len({row["abn"] for row in rows}) != len(rows) or len({row["acquisition_attempt_id"] for row in rows}) != len(rows):
        raise AcquisitionCampaignError("known-URL campaign is not exactly 80 unique rows/attempt identities")
    immutable = {
        "campaign_version": CAMPAIGN_VERSION,
        "campaign_id": "acqcampaign:phase5-top100-known-url-official-website-v1",
        "source_policy": {"method": "GET", "no_post": True, "no_forms": True, "no_authentication": True, "no_crawl": True, "no_sitemap": True, "no_url_discovery": True, "max_initial_requests_per_subject": 1, "timeout_seconds": 45, "max_response_bytes": 30_000_000, "retry_policy": "no_automatic_retry"},
        "rows": rows,
        "excluded_subjects": exclusions,
        "preparation_inputs": {"profiles_sha256": hashlib.sha256(profiles_path.read_bytes()).hexdigest(), "identity_map_sha256": hashlib.sha256(identity_map_path.read_bytes()).hexdigest(), "source_inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest()},
        "provider_operations": 0, "network_operations_at_preparation": 0,
    }
    immutable["manifest_sha256"] = _json_hash(immutable)
    return immutable


def validate_campaign(manifest: dict[str, Any]) -> None:
    recorded = manifest.get("manifest_sha256")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if recorded != _json_hash(unsigned):
        raise AcquisitionCampaignError("acquisition campaign manifest hash mismatch")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise AcquisitionCampaignError("acquisition campaign must contain exactly 80 rows")
    seen_subjects: set[str] = set(); seen_attempts: set[str] = set()
    for row in rows:
        if row.get("http_method") != "GET" or row.get("max_initial_requests") != 1 or row.get("retry_policy") != "no_automatic_retry":
            raise AcquisitionCampaignError("campaign row expands the bounded acquisition policy")
        if row.get("abn") in DISCOVERY_REQUIRED_ABNS or row.get("abn") == RANK_67_ABN:
            raise AcquisitionCampaignError("campaign contains an excluded ABN")
        normalized = _url(str(row.get("governed_url") or ""))
        if normalized != row.get("normalized_initial_url"):
            raise AcquisitionCampaignError("governed URL changed after manifest preparation")
        host = (urlsplit(normalized).hostname or "").casefold()
        expected_hosts = sorted(governed_website_hosts(normalized))
        if row.get("allowed_initial_host") != host or row.get("permitted_redirect_hosts") != expected_hosts:
            raise AcquisitionCampaignError("campaign host policy does not match governed URL")
        if row.get("timeout_seconds", 46) > 45 or row.get("max_response_bytes", 30_000_001) > 30_000_000:
            raise AcquisitionCampaignError("campaign row exceeds transport bounds")
        if row["subject_id"] in seen_subjects or row["acquisition_attempt_id"] in seen_attempts:
            raise AcquisitionCampaignError("campaign has duplicate subject or acquisition attempt identity")
        seen_subjects.add(row["subject_id"]); seen_attempts.add(row["acquisition_attempt_id"])


def request_arguments(row: dict[str, Any]) -> dict[str, Any]:
    """The exact arguments passed to the existing production transport."""
    return {"source_family": "official_website", "url": row["normalized_initial_url"], "allowed_hosts": set(row["permitted_redirect_hosts"]), "timeout_seconds": row["timeout_seconds"], "max_bytes": row["max_response_bytes"]}


def rehearse_network_edge(manifest: dict[str, Any], *, boundary: Callable[..., Any] | None = None) -> list[dict[str, Any]]:
    """Validate every production transport invocation without crossing I/O.

    A boundary is supplied only by tests; the default validates arguments and
    deliberately never calls ``NetworkLedger.fetch``.
    """
    validate_campaign(manifest)
    prepared = []
    for row in manifest["rows"]:
        args = request_arguments(row)
        if boundary is not None:
            boundary(**args)
        prepared.append({"abn": row["abn"], "acquisition_attempt_id": row["acquisition_attempt_id"], "state": "READY_TO_CROSS_NETWORK_BOUNDARY", "request": {**args, "allowed_hosts": sorted(args["allowed_hosts"])}})
    return prepared


def _atomic_json(path: Path, value: Any) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _failure_outcome(event: dict[str, Any]) -> str:
    if event.get("outcome") == "blocked":
        return "host_policy_redirect_rejection"
    if event.get("error_class") in {"TimeoutError", "URLError"}:
        return "timeout"
    if event.get("error_class") == "response_too_large":
        return "oversized_response"
    if event.get("response_status"):
        return "http_terminal_failure"
    return "transport_error_before_response"


def execute_row(*, row: dict[str, Any], ledger: NetworkLedger, catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, now: datetime | None = None, fetched: dict[str, Any] | None = None) -> dict[str, Any]:
    """Use the existing transport and provenance path for one already-certified row.

    This function is intentionally not invoked by preparation or rehearsal.
    The ledger cache is the durable response boundary: a restart after an
    unambiguous response reuses cached bytes rather than issuing another GET.
    """
    timestamp = now or datetime.now(timezone.utc)
    fetched = fetched or ledger.fetch(**request_arguments(row))
    catalog.register_source_definition(source_definition("official_website", timestamp))
    if fetched["ok"]:
        return {"attempt_id": row["acquisition_attempt_id"], "outcome": "acquired_successfully", "lineage": persist_available(catalog=catalog, store=store, family="official_website", requested_url=row["normalized_initial_url"], resolved_url=fetched["resolved_url"], body=fetched["body"], media_type=fetched["media_type"], role="official_homepage", source_version=None, origin=MaterialOrigin.NEWLY_ACQUIRED, now=timestamp)}
    event = fetched["event"]
    outcome = _failure_outcome(event)
    receipt = AcquisitionReceipt(record_id=deterministic_id("acq:", {"attempt_id": row["acquisition_attempt_id"], "outcome": outcome}), created_at=timestamp, producer={"kind": "code", "producer_id": CAMPAIGN_VERSION, "version": "1"}, source_definition_id=source_definition("official_website", timestamp).record_id, requested_locator=row["normalized_initial_url"], outcome="failed" if outcome != "http_terminal_failure" else "unavailable", response_status=event.get("response_status"), tool_id="urllib", tool_version="stdlib", error_class=str(event.get("error_class") or outcome))
    catalog.record_acquisition_receipt(receipt)
    return {"attempt_id": row["acquisition_attempt_id"], "outcome": outcome, "event": event}


def execute_campaign(*, manifest: dict[str, Any], runtime_root: Path, catalog_path: Path, after_response_hook: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Execute only non-terminal rows, with durable at-most-once send state.

    An ``in_flight`` row is intentionally quarantined on restart: its send
    state cannot be proven.  A ``response_durable`` row is safe to finish
    because ``NetworkLedger`` will reuse its durable cache rather than fetch.
    """
    validate_campaign(manifest)
    runtime_root.mkdir(parents=True, exist_ok=True)
    state_path = runtime_root / "acquisition-runtime-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"manifest_sha256": manifest["manifest_sha256"], "attempts": {}}
    if state.get("manifest_sha256") != manifest["manifest_sha256"]:
        raise AcquisitionCampaignError("runtime acquisition state belongs to a different manifest")
    attempts: dict[str, dict[str, Any]] = state.setdefault("attempts", {})
    ledger = NetworkLedger(cache_root=runtime_root / "network-cache")
    catalog = SQLiteCatalog(catalog_path).open()
    store = ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,))
    try:
        for row in manifest["rows"]:
            attempt_id = row["acquisition_attempt_id"]
            prior = attempts.get(attempt_id, {})
            if prior.get("state") in {"acquired_successfully", "http_terminal_failure", "host_policy_redirect_rejection", "timeout", "oversized_response", "transport_error_before_response"}:
                continue
            if prior.get("state") == "in_flight":
                raise AcquisitionCampaignError(f"ambiguous external acquisition state quarantined: {attempt_id}")
            if prior.get("state") != "response_durable":
                attempts[attempt_id] = {"state": "in_flight", "abn": row["abn"]}
                _atomic_json(state_path, state)
                try:
                    fetched = ledger.fetch(**request_arguments(row))
                except NetworkPolicyError:
                    event = ledger.events[-1] if ledger.events else {"outcome": "blocked", "error_class": "NetworkPolicyError"}
                    attempts[attempt_id] = {"state": "host_policy_redirect_rejection", "abn": row["abn"], "event": event}
                    _atomic_json(state_path, state)
                    continue
                attempts[attempt_id] = {"state": "response_durable", "abn": row["abn"], "event": fetched.get("event")}
                _atomic_json(state_path, state)
                if after_response_hook:
                    after_response_hook(row)
                result = execute_row(row=row, ledger=ledger, catalog=catalog, store=store, fetched=fetched)
            else:
                result = execute_row(row=row, ledger=ledger, catalog=catalog, store=store)
            attempts[attempt_id] = {"state": result["outcome"], "abn": row["abn"], "result": result}
            _atomic_json(state_path, state)
    finally:
        catalog.close()
    return {"manifest_sha256": manifest["manifest_sha256"], "state_path": str(state_path), "attempts": attempts, "network_events": len(ledger.events)}


__all__ = ["AcquisitionCampaignError", "CAMPAIGN_VERSION", "DISCOVERY_REQUIRED_ABNS", "build_campaign", "execute_campaign", "execute_row", "rehearse_network_edge", "request_arguments", "validate_campaign"]
