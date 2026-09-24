"""Canonical, provider-free S0 provider accounting boundary.

The adapter deliberately accepts only provider-supplied usage/cost evidence.
It never prices a request from token defaults, the frozen estimate, or a
missing response.  Reservations and ledger rows remain owned by the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Mapping

from .scale_s0 import ScalePreflightError, packet_task_key


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ScalePreflightError(f"{field} must be a decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ScalePreflightError(f"{field} must be a decimal") from error
    if not result.is_finite() or result < 0:
        raise ScalePreflightError(f"{field} must be finite and non-negative")
    return result


def _currency(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 3 or not value.isascii() or not value.isupper():
        raise ScalePreflightError(f"{field} must be an upper-case ISO currency")
    return value


def _timestamp(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ScalePreflightError("accounting timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProviderCostEvidence:
    amount: Decimal
    currency: str
    accounting_amount: Decimal
    accounting_currency: str
    pricing_snapshot_id: str
    fx_snapshot_id: str | None = None


class S0ProviderAccounting:
    """One idempotent accounting adapter shared by every S0 provider route."""

    def __init__(self, *, catalog: Any, now: Any = None, execution_attempt_id: str | None = None) -> None:
        if catalog is None:
            raise ValueError("S0 accounting requires the canonical catalog")
        self.catalog = catalog
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.execution_attempt_id = execution_attempt_id

    @staticmethod
    def _usage(value: Any) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ScalePreflightError("provider receipt lacks complete usage evidence")
        for field in ("input_tokens", "output_tokens"):
            count = value.get(field)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ScalePreflightError("provider receipt usage is missing or partial")
        return value

    @staticmethod
    def _same_usage(left: Any, right: Any) -> bool:
        return isinstance(left, Mapping) and isinstance(right, Mapping) and dict(left) == dict(right)

    def _evidence(self, usage: Any, *, expected_currency: str, expected_pricing: str) -> ProviderCostEvidence:
        data = self._usage(usage)
        cost = data.get("provider_cost")
        if not isinstance(cost, Mapping) or "amount" not in cost or "currency" not in cost:
            raise ScalePreflightError("provider receipt lacks governed provider cost evidence")
        provider_amount = _decimal(cost["amount"], "provider cost")
        provider_currency = _currency(cost["currency"], "provider cost currency")
        pricing_snapshot_id = data.get("pricing_snapshot_id")
        if not isinstance(pricing_snapshot_id, str) or not pricing_snapshot_id or pricing_snapshot_id != expected_pricing:
            raise ScalePreflightError("provider pricing evidence does not match the frozen reservation")
        accounting = data.get("accounting_cost")
        if provider_currency == expected_currency:
            if accounting is not None:
                if not isinstance(accounting, Mapping) or "amount" not in accounting or "currency" not in accounting:
                    raise ScalePreflightError("accounting cost conflicts with provider cost")
                if (_decimal(accounting["amount"], "accounting cost") != provider_amount
                        or _currency(accounting["currency"], "accounting cost currency") != expected_currency):
                    raise ScalePreflightError("accounting cost conflicts with provider cost")
            accounting_amount, accounting_currency, fx_id = provider_amount, provider_currency, None
        else:
            if not isinstance(accounting, Mapping) or "amount" not in accounting or "currency" not in accounting or not data.get("fx_snapshot_id"):
                raise ScalePreflightError("provider/accounting currency mismatch lacks governed FX evidence")
            accounting_amount = _decimal(accounting["amount"], "accounting cost")
            accounting_currency = _currency(accounting["currency"], "accounting cost currency")
            fx_id = data["fx_snapshot_id"]
            if not isinstance(fx_id, str) or not fx_id:
                raise ScalePreflightError("provider/accounting currency mismatch lacks governed FX evidence")
            if accounting_currency != expected_currency:
                raise ScalePreflightError("accounting cost currency does not match the reservation")
        return ProviderCostEvidence(provider_amount, provider_currency, accounting_amount,
                                    accounting_currency, str(pricing_snapshot_id), fx_id)

    def reconcile(self, *, request: Any, packet: Any, provider_receipt_id: str,
                  usage: Any, provider_response: Any = None) -> dict[str, Any]:
        if not provider_receipt_id:
            raise ScalePreflightError("accounting requires a provider receipt identity")
        if not request.reservation_id:
            raise ScalePreflightError("accounting requires a reservation")
        receipt = self.catalog.get_physical_receipt(request.physical_attempt_id)
        if receipt is None or receipt.get("provider_receipt_id") != provider_receipt_id:
            raise ScalePreflightError("accounting requires the matching durable provider receipt")
        receipt_usage = receipt.get("usage_json")
        if isinstance(receipt_usage, str):
            try:
                receipt_usage = json.loads(receipt_usage)
            except json.JSONDecodeError as error:
                raise ScalePreflightError("durable provider receipt usage is invalid") from error
        if not self._same_usage(receipt_usage, usage):
            raise ScalePreflightError("provider usage does not match the durable provider receipt")
        binding = self.catalog.get_scale_s0_reservation_binding(
            mandate_id=packet.mandate_id, slice_id=packet.slice_id,
            task_key=packet_task_key(packet),
            execution_attempt_id=self.execution_attempt_id,
        ) if hasattr(self.catalog, "get_scale_s0_reservation_binding") else None
        reservation = self.catalog.get_reservation(request.reservation_id)
        if reservation is None or reservation.get("accounting_currency") is None:
            raise ScalePreflightError("canonical reservation is absent")
        expected_currency = str(reservation["accounting_currency"])
        expected_pricing = str(getattr(packet, "pricing_snapshot_id", "") or "")
        if not expected_pricing and binding:
            expected_pricing = str((binding.get("state") or {}).get("pricing_snapshot_id") or "")
        if not expected_pricing:
            raise ScalePreflightError("canonical pricing evidence is absent")
        evidence = self._evidence(usage, expected_currency=expected_currency, expected_pricing=expected_pricing)
        request_id = str(getattr(packet, "provider_request_identity", ""))
        if not request_id:
            raise ScalePreflightError("accounting request identity is absent")
        recorded_at = _timestamp(self.now())
        release_key = "release:s0:" + request_id
        prior_release = self.catalog.get_cost_entry(release_key)
        entry = self.catalog.record_accounting_actual(
            entry_key="actual:s0:" + request_id,
            provider_request_item_id=request_id,
            provider_receipt_id=provider_receipt_id,
            reservation_id=request.reservation_id,
            provider_amount=evidence.amount,
            provider_currency=evidence.currency,
            accounting_amount=evidence.accounting_amount,
            accounting_currency=evidence.accounting_currency,
            pricing_snapshot_id=evidence.pricing_snapshot_id,
            fx_snapshot_id=evidence.fx_snapshot_id,
            usage=usage,
            recorded_at=recorded_at,
        )
        position = self.catalog.accounting_reservation_position(request.reservation_id)
        outstanding = max(Decimal("0"), Decimal(position["reserved"]) - min(Decimal(position["actual"]), Decimal(position["reserved"])) - Decimal(position["released"]))
        released_now = (Decimal(prior_release["accounting_amount"]) if prior_release is not None else outstanding)
        if outstanding:
            self.catalog.release_reservation(
                request.reservation_id,
                {"amount": str(outstanding), "currency": expected_currency},
                now=recorded_at, entry_key=release_key,
            )
        return {"entry_key": entry["entry_key"], "actual": str(evidence.accounting_amount), "currency": evidence.accounting_currency, "released": str(released_now)}

    def reconcile_durable(self, *, request: Any, packet: Any) -> dict[str, Any]:
        receipt = self.catalog.get_physical_receipt(request.physical_attempt_id)
        if receipt is None:
            raise ScalePreflightError("completed provider item lacks a durable receipt")
        try:
            usage = json.loads(receipt["usage_json"]) if isinstance(receipt.get("usage_json"), str) else receipt.get("usage_json")
        except json.JSONDecodeError as error:
            raise ScalePreflightError("completed provider item has invalid durable usage") from error
        return self.reconcile(request=request, packet=packet, provider_receipt_id=str(receipt["provider_receipt_id"]), usage=usage)


class S0ProviderAccountingFactory:
    """Factory kept as the sole construction seam for S0 accounting."""

    def __init__(self, *, catalog: Any, now: Any = None, execution_attempt_id: str | None = None) -> None:
        self.catalog, self.now, self.execution_attempt_id = catalog, now, execution_attempt_id

    def create(self) -> S0ProviderAccounting:
        return S0ProviderAccounting(catalog=self.catalog, now=self.now, execution_attempt_id=self.execution_attempt_id)


S0AccountingAdapter = S0ProviderAccounting

__all__ = ["ProviderCostEvidence", "S0ProviderAccounting", "S0AccountingAdapter", "S0ProviderAccountingFactory"]
