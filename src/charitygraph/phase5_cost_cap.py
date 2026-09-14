"""Mechanical Phase-5 cost-cap classification for prepared request rows."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping


ELIGIBLE_UNDER_CURRENT_CAP = "ELIGIBLE_UNDER_CURRENT_CAP"
EXCLUDED_COST_CAP = "EXCLUDED_COST_CAP"


def partition_cost_cap_requests(
    rows: list[Mapping[str, Any]], *, amount_key: str = "corrected_hard_max_aud",
    cap_aud: Decimal | str = "0.25",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition exclusively by each row's corrected AUD bound; never inspect semantics."""
    cap = Decimal(str(cap_aud))
    if not cap.is_finite() or cap <= 0:
        raise ValueError("per-request AUD cap must be finite and positive")
    ids = [row.get("provider_request_item_id") for row in rows]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("cost-cap partition requires unique provider request item IDs")
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for source in rows:
        try:
            amount = Decimal(str(source[amount_key]))
        except (KeyError, ArithmeticError) as exc:
            raise ValueError("cost-cap partition requires a corrected hard AUD amount") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("corrected hard AUD amount must be finite and non-negative")
        row = dict(source)
        row["classification"] = ELIGIBLE_UNDER_CURRENT_CAP if amount <= cap else EXCLUDED_COST_CAP
        (eligible if amount <= cap else excluded).append(row)
    return eligible, excluded


__all__ = ["ELIGIBLE_UNDER_CURRENT_CAP", "EXCLUDED_COST_CAP", "partition_cost_cap_requests"]
