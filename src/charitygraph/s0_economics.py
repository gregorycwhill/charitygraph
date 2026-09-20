"""Pure S0 pre-live currency contract; this module performs no lookups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .scale_s0 import ScalePreflightError


def conversion_required(policy_currency: str, provider_currency: str) -> bool:
    """Return whether a conversion basis is needed for the supplied currencies."""
    currencies = (policy_currency, provider_currency)
    if any(not isinstance(value, str) or len(value) != 3 or not value.isascii() or not value.isupper() for value in currencies):
        raise ScalePreflightError("S0 currencies must be three-letter uppercase codes")
    return policy_currency != provider_currency


def validate_conversion_basis(
    policy_currency: str,
    provider_currency: str,
    observation: Mapping[str, object] | None,
    *,
    as_of: datetime,
    max_age: timedelta = timedelta(days=1),
) -> None:
    """Validate the caller-supplied FX observation only when currencies differ.

    Caller contract: pre-live code passes frozen policy/provider currencies and an
    already acquired observation. USD/USD passes ``None``; mismatches fail closed
    unless the observation has a positive finite rate, matching base/quote, a UTC
    timestamp no older than ``max_age`` and no future timestamp.
    """
    if not conversion_required(policy_currency, provider_currency):
        return
    if observation is None:
        raise ScalePreflightError("currency mismatch requires a current FX conversion basis")
    try:
        if observation.get("base_currency") != provider_currency or observation.get("quote_currency") != policy_currency:
            raise ValueError
        rate = Decimal(str(observation["rate"]))
        observed_at = datetime.fromisoformat(str(observation["observed_at"]).replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError
        observed_at = observed_at.astimezone(timezone.utc)
        reference = as_of.astimezone(timezone.utc)
        if not rate.is_finite() or rate <= 0 or observed_at > reference or reference - observed_at > max_age:
            raise ValueError
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise ScalePreflightError("FX conversion basis is absent, stale, invalid, or incorrectly quoted") from error
