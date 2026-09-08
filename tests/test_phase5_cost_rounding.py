from decimal import Decimal

from charitygraph.phase5_openai_dry_run import (
    conservative_member_aud_ceiling,
    conservative_money_ceiling,
)


def test_money_ceiling_rounds_up_at_ledger_precision() -> None:
    assert conservative_money_ceiling("0.05533712") == Decimal("0.055338")
    assert conservative_money_ceiling("0.05533700") == Decimal("0.055337")


def test_member_ceilings_sum_safely_against_aggregate() -> None:
    members = tuple(Decimal(value) for value in ("0.00559190", "0.00586890", "0.00589590", "0.00614190", "0.00625290", "0.00665390"))
    usd_sum = sum((conservative_money_ceiling(value) for value in members), Decimal("0"))
    aud_sum = sum((conservative_member_aud_ceiling(value, "1.52") for value in members), Decimal("0"))
    assert usd_sum == Decimal("0.036406")
    assert aud_sum == Decimal("0.055338")
    assert aud_sum >= conservative_money_ceiling(sum(members, Decimal("0")) * Decimal("1.52"))


def test_rounding_is_deterministic_and_wire_independent() -> None:
    first = tuple(conservative_member_aud_ceiling(value, "1.52") for value in ("0.005592", "0.005869"))
    second = tuple(conservative_member_aud_ceiling(value, "1.52") for value in ("0.005592", "0.005869"))
    assert first == second
