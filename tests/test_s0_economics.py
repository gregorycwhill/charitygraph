from datetime import datetime, timedelta, timezone

import pytest

from charitygraph.scale_s0 import ScalePreflightError
from charitygraph.s0_economics import conversion_required, validate_conversion_basis


AS_OF = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_usd_usd_requires_no_fx_observation() -> None:
    assert conversion_required("USD", "USD") is False
    validate_conversion_basis("USD", "USD", None, as_of=AS_OF)


@pytest.mark.parametrize("observation", [None, {"base_currency": "USD", "quote_currency": "AUD", "rate": "1.5", "observed_at": "2026-09-18T00:00:00Z"}, {"base_currency": "AUD", "quote_currency": "USD", "rate": "0", "observed_at": "2026-09-20T00:00:00Z"}])
def test_currency_mismatch_requires_valid_current_basis(observation) -> None:
    with pytest.raises(ScalePreflightError, match="FX|conversion"):
        validate_conversion_basis("AUD", "USD", observation, as_of=AS_OF)


def test_currency_mismatch_accepts_current_valid_basis() -> None:
    validate_conversion_basis("AUD", "USD", {"base_currency": "USD", "quote_currency": "AUD", "rate": "1.5", "observed_at": "2026-09-19T00:00:00Z"}, as_of=AS_OF)


def test_currency_mismatch_rejects_stale_basis() -> None:
    with pytest.raises(ScalePreflightError, match="stale"):
        validate_conversion_basis("AUD", "USD", {"base_currency": "USD", "quote_currency": "AUD", "rate": "1.5", "observed_at": (AS_OF - timedelta(days=2)).isoformat()}, as_of=AS_OF)
