"""Governed S0 pricing derivation for Responses web-search receipts.

The provider receipt remains raw provider evidence.  This module derives a
separate, deterministic pricing fact from an immutable ``PricingSnapshot``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .contracts.economics import PricingSnapshot
from .scale_s0 import ScalePreflightError


@dataclass(frozen=True)
class PricingEvidence:
    snapshot_id: str
    model: str
    usage: dict[str, Any]
    web_search_calls: int
    amount_usd: Decimal


def _count(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ScalePreflightError(f"provider usage {field} is missing or invalid")
    return value


def _rate(snapshot: PricingSnapshot, dimension: str) -> tuple[Decimal, Decimal]:
    values = [item for item in snapshot.rates if item.dimension == dimension]
    if len(values) != 1:
        raise ScalePreflightError(f"pricing snapshot lacks unique {dimension} rate")
    return values[0].unit_quantity, values[0].price_per_unit


def _tool_calls(body: Mapping[str, Any]) -> int:
    output = body.get("output")
    if not isinstance(output, list):
        raise ScalePreflightError("provider output is not a list")
    total = 0
    for item in output:
        if not isinstance(item, Mapping):
            raise ScalePreflightError("provider output contains malformed item")
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        if not isinstance(action, Mapping) or not isinstance(action.get("type"), str):
            raise ScalePreflightError("web-search call lacks a validated action")
        total += 1
    return total


def derive_luna_web_search_cost(*, snapshot: PricingSnapshot, response_body: Mapping[str, Any], expected_model: str = "gpt-5.6-luna") -> PricingEvidence:
    if snapshot.model_snapshot != expected_model or snapshot.provider_currency != "USD":
        raise ScalePreflightError("pricing snapshot model or currency does not match S0")
    if not isinstance(response_body.get("model"), str) or response_body["model"] != expected_model:
        raise ScalePreflightError("provider response model does not match the pricing snapshot")
    usage = response_body.get("usage")
    if not isinstance(usage, Mapping):
        raise ScalePreflightError("provider response lacks usage evidence")
    input_tokens = _count(usage.get("input_tokens"), "input_tokens")
    output_tokens = _count(usage.get("output_tokens"), "output_tokens")
    details = usage.get("input_tokens_details", {})
    if details is None:
        details = {}
    if not isinstance(details, Mapping):
        raise ScalePreflightError("input token details are malformed")
    cached = _count(details.get("cached_tokens", 0), "cached_tokens")
    if cached > input_tokens:
        raise ScalePreflightError("cached input tokens exceed total input tokens")
    if "cache_creation_input_tokens" in details:
        cache_writes = _count(details.get("cache_creation_input_tokens"), "cache_creation_input_tokens")
    else:
        cache_writes = 0
    if cache_writes and cache_writes > input_tokens:
        raise ScalePreflightError("cache-write tokens exceed total input tokens")
    web_calls = _tool_calls(response_body)
    input_unit, input_price = _rate(snapshot, "input_tokens")
    cached_unit, cached_price = _rate(snapshot, "cached_input_tokens")
    output_unit, output_price = _rate(snapshot, "output_tokens")
    tool_unit, tool_price = _rate(snapshot, "tool_calls")
    long_context = input_tokens > 272_000
    input_multiplier = Decimal("2") if long_context else Decimal("1")
    output_multiplier = Decimal("1.5") if long_context else Decimal("1")
    uncached = input_tokens - cached - cache_writes
    if uncached < 0:
        raise ScalePreflightError("cached and cache-write input tokens exceed total input tokens")
    amount = (Decimal(uncached) / input_unit * input_price * input_multiplier
              + Decimal(cached) / cached_unit * cached_price * input_multiplier
              + Decimal(cache_writes) / input_unit * input_price * Decimal("1.25") * input_multiplier
              + Decimal(output_tokens) / output_unit * output_price * output_multiplier
              + Decimal(web_calls) / tool_unit * tool_price)
    if not amount.is_finite() or amount < 0:
        raise ScalePreflightError("derived provider cost is invalid")
    return PricingEvidence(snapshot.record_id, expected_model, dict(usage), web_calls, amount)


def load_pricing_snapshot(value: Mapping[str, Any], *, expected_source_hash: str | None = None) -> PricingSnapshot:
    """Validate a durable snapshot; source bytes must be supplied by the authority layer."""
    try:
        snapshot = PricingSnapshot.model_validate(value)
    except Exception as error:
        raise ScalePreflightError("governed pricing snapshot is invalid") from error
    if expected_source_hash is not None and snapshot.source_content_hash != expected_source_hash:
        raise ScalePreflightError("pricing snapshot source hash mismatch")
    if snapshot.effective_at > snapshot.retrieved_at:
        raise ScalePreflightError("pricing snapshot effective time follows retrieval time")
    return snapshot


def load_supervisor_capture(path: str | Path, *, expected_sha256: str) -> PricingSnapshot:
    """Load the supervisor's structured-facts capture without treating it as HTML."""
    raw = Path(path).read_bytes()
    observed = hashlib.sha256(raw).hexdigest()
    if observed != expected_sha256:
        raise ScalePreflightError("pricing capture SHA-256 mismatch")
    try:
        capture = json.loads(raw.decode("utf-8"))
    except Exception as error:
        raise ScalePreflightError("pricing capture is not valid JSON") from error
    if (capture.get("schema") != "charitygraph-supervisor-pricing-capture-v1"
            or not isinstance(capture.get("provenance_note"), str)
            or "not over raw upstream HTML" not in capture["provenance_note"]):
        raise ScalePreflightError("pricing capture provenance scope is not explicit")
    model = capture.get("model_pricing", {})
    search = capture.get("web_search_pricing", {})
    if capture.get("model") != "gpt-5.6-luna" or capture.get("currency") != "USD" or not search.get("search_content_tokens_billed_at_model_rates"):
        raise ScalePreflightError("pricing capture is not the authorised Luna/USD snapshot")
    now = datetime.fromisoformat(str(capture["captured_at"])).replace(tzinfo=timezone.utc)
    rates = (
        {"dimension": "input_tokens", "unit_quantity": "1000000", "price_per_unit": model["input_usd_per_million_tokens"]},
        {"dimension": "cached_input_tokens", "unit_quantity": "1000000", "price_per_unit": model["cached_input_usd_per_million_tokens"]},
        {"dimension": "output_tokens", "unit_quantity": "1000000", "price_per_unit": model["output_usd_per_million_tokens"]},
        {"dimension": "tool_calls", "unit_quantity": "1000", "price_per_unit": search["usd_per_1000_calls"]},
    )
    return PricingSnapshot(
        record_id="pricing:" + observed,
        provider_id="openai", model_snapshot="gpt-5.6-luna", effective_at=now,
        retrieved_at=now, provider_currency="USD",
        authoritative_source_url="https://developers.openai.com/api/docs/pricing",
        rates=rates, source_content_hash=observed,
        created_at=now,
        producer={"kind": "automation_policy", "producer_id": "supervisor-pricing-capture"},
    )
