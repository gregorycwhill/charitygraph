from decimal import Decimal

import pytest

from charitygraph.phase5_discovery_campaign import (
    campaign_budget_fits,
    conservative_input_allowance,
    standard_hard_max_aud,
    standard_hard_max_usd,
)


def test_input_allowance_rounds_up_at_1_30x():
    assert conservative_input_allowance(10001) == 13002


def test_standard_hard_ceiling_is_conservative_and_aud_converts_upward():
    usd = standard_hard_max_usd(4886, input_price_per_million=Decimal("0.20"), output_price_per_million=Decimal("1.20"))
    aud = standard_hard_max_aud(usd, Decimal("1.52"))
    assert usd == Decimal("0.010871")
    assert aud == Decimal("0.016524")


def test_campaign_budget_is_fail_closed():
    assert campaign_budget_fits(Decimal("1.720961"))
    assert not campaign_budget_fits(Decimal("10000.000001"))


@pytest.mark.parametrize("value", [-1, 1.2])
def test_invalid_token_count_rejected(value):
    with pytest.raises(ValueError):
        conservative_input_allowance(value)  # type: ignore[arg-type]
