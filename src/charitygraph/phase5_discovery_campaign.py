"""Deterministic, provider-free preparation helpers for the Phase-5 Standard campaign."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from .phase5_openai_dry_run import MONEY_QUANTUM, conservative_money_ceiling, conservative_member_aud_ceiling


INPUT_ALLOWANCE_FACTOR = Decimal("1.30")
STANDARD_OUTPUT_TOKENS = 8000
PHASE5_CAMPAIGN_BUDGET_AUD = Decimal("10000.00")


def conservative_input_allowance(estimated_input_tokens: int, factor: Decimal = INPUT_ALLOWANCE_FACTOR) -> int:
    """Return a whole-token allowance rounded upward, never downward."""
    if not isinstance(estimated_input_tokens, int) or estimated_input_tokens < 0:
        raise ValueError("estimated input tokens must be a non-negative integer")
    if factor <= 0:
        raise ValueError("input allowance factor must be positive")
    return int((Decimal(estimated_input_tokens) * factor).to_integral_value(rounding=ROUND_CEILING))


def standard_hard_max_usd(
    estimated_input_tokens: int,
    *,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
    output_tokens: int = STANDARD_OUTPUT_TOKENS,
) -> Decimal:
    allowance = conservative_input_allowance(estimated_input_tokens)
    raw = (Decimal(allowance) / Decimal(1_000_000)) * input_price_per_million
    raw += (Decimal(output_tokens) / Decimal(1_000_000)) * output_price_per_million
    return conservative_money_ceiling(raw, MONEY_QUANTUM)


def standard_hard_max_aud(usd: Decimal, aud_per_usd: Decimal) -> Decimal:
    return conservative_member_aud_ceiling(usd, aud_per_usd)


def campaign_budget_fits(total_aud: Decimal, cap_aud: Decimal = PHASE5_CAMPAIGN_BUDGET_AUD) -> bool:
    return total_aud <= cap_aud


__all__ = [
    "INPUT_ALLOWANCE_FACTOR",
    "STANDARD_OUTPUT_TOKENS",
    "PHASE5_CAMPAIGN_BUDGET_AUD",
    "conservative_input_allowance",
    "standard_hard_max_usd",
    "standard_hard_max_aud",
    "campaign_budget_fits",
]
