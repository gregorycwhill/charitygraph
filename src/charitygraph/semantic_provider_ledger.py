"""Deterministic reconciliation of retained semantic-provider telemetry.

This is intentionally an audit reader.  It never calls a provider and never
alters historical records: a physical response can be retained even when no
logical experiment report linked it.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping


class ProviderLedgerError(ValueError):
    pass


def _physical(row: Mapping[str, Any]) -> dict[str, Any]:
    required = ("response_id", "model", "input_tokens", "output_tokens", "cost_usd")
    if any(not row.get(key) for key in ("response_id", "model")):
        raise ProviderLedgerError("physical record lacks response identity or model")
    if not isinstance(row.get("input_tokens"), int) or not isinstance(row.get("output_tokens"), int):
        raise ProviderLedgerError("physical record token counts must be integers")
    try:
        cost = Decimal(str(row["cost_usd"]))
    except Exception as exc:  # Decimal's exceptions vary by input type.
        raise ProviderLedgerError("physical record cost_usd is invalid") from exc
    if cost < 0 or row["input_tokens"] < 0 or row["output_tokens"] < 0:
        raise ProviderLedgerError("physical record usage must be non-negative")
    return {key: row[key] for key in required} | {"cost_usd": cost}


def reconcile_provider_ledger(
    physical_records: Iterable[Mapping[str, Any]], logical_executions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join immutable physical receipts to retained logical execution reports.

    Each logical execution must identify exactly one physical ``response_id``.
    Receipts absent from a report are retained as ``unlinked_physical`` rather
    than silently discarded, which makes historical 31-versus-33 accounting
    explicit and reproducible.
    """
    physical: dict[str, dict[str, Any]] = {}
    for raw in physical_records:
        row = _physical(raw)
        response_id = str(row["response_id"])
        if response_id in physical:
            raise ProviderLedgerError(f"duplicate physical response_id: {response_id}")
        physical[response_id] = row

    logical: list[dict[str, str]] = []
    linked: set[str] = set()
    for raw in logical_executions:
        response_id = str(raw.get("response_id") or "")
        execution_id = str(raw.get("execution_id") or "")
        if not response_id or not execution_id:
            raise ProviderLedgerError("logical execution lacks execution_id or response_id")
        if response_id not in physical:
            raise ProviderLedgerError(f"logical execution references absent physical response: {response_id}")
        if response_id in linked:
            raise ProviderLedgerError(f"multiple logical executions reference physical response: {response_id}")
        linked.add(response_id)
        logical.append({"execution_id": execution_id, "response_id": response_id})

    def totals(ids: Iterable[str]) -> dict[str, Any]:
        rows = [physical[value] for value in ids]
        return {
            "calls": len(rows),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "output_tokens": sum(row["output_tokens"] for row in rows),
            "usd": format(sum((row["cost_usd"] for row in rows), Decimal("0")), "f"),
        }

    unlinked = sorted(set(physical) - linked)
    return {
        "contract": "cg-semantic-provider-ledger-reconciliation-v1",
        "physical": totals(sorted(physical)),
        "logical": totals(sorted(linked)),
        "logical_executions": sorted(logical, key=lambda row: row["execution_id"]),
        "unlinked_physical": [
            {key: (format(value, "f") if key == "cost_usd" else value) for key, value in physical[response_id].items()}
            for response_id in unlinked
        ],
    }
