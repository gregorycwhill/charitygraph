from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from charitygraph.contracts import (
    BudgetCohort, CostLedger, CostLedgerEntry, FxRateSnapshot, Money, PriceRate,
    PricingSnapshot, ReservationReconciliation, RunManifest, SignedMoney,
)
from charitygraph.contracts.tasks import ProviderUsage

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
RESERVATION_A = "reservation:" + "6" * 32
RESERVATION_B = "reservation:" + "7" * 32
RESERVATION_UNMATCHED = "reservation:" + "8" * 32


def money(amount, currency="AUD"):
    return Money(amount=Decimal(str(amount)), currency=currency)


def signed(amount, currency="AUD"):
    return SignedMoney(amount=Decimal(str(amount)), currency=currency)


def entry(entry_type, amount, *, reservation_id=RESERVATION_A, direction=None):
    return CostLedgerEntry(
        cohort_id="cohort:" + "1" * 32, run_id="run:" + "4" * 32, task_run_id="taskrun:" + "5" * 32,
        reservation_id=reservation_id, pricing_snapshot_id="pricing:" + "2" * 32,
        fx_snapshot_id="fx:" + "3" * 32, entry_type=entry_type, paid_output_category="extraction",
        provider_cost=money(amount, "USD"), aud_cost=money(amount), usage=ProviderUsage(input_tokens=1),
        recorded_at=NOW, adjustment_direction=direction,
    )


def position(reservation_id, reserved, actual, released, *, consumed=None, overrun=None, outstanding=None):
    reserved_decimal = Decimal(str(reserved))
    actual_decimal = Decimal(str(actual))
    consumed_decimal = min(actual_decimal, reserved_decimal) if consumed is None else Decimal(str(consumed))
    overrun_decimal = max(actual_decimal - reserved_decimal, Decimal("0")) if overrun is None else Decimal(str(overrun))
    outstanding_decimal = reserved_decimal - consumed_decimal - Decimal(str(released)) if outstanding is None else Decimal(str(outstanding))
    return ReservationReconciliation(
        reservation_id=reservation_id, reserved_aud=money(reserved), actual_charge_aud=money(actual),
        actual_consuming_reservation_aud=money(consumed_decimal), released_unused_reserve_aud=money(released),
        reservation_overrun_aud=money(overrun_decimal), outstanding_reserved_exposure_aud=money(outstanding_decimal),
    )


def ledger(
    entries, *, positions=(), reserved=0, released=0, actual=0, overrun=0, unreserved=0,
    credits=0, adjustment_debits=0, adjustment_credits=0, net_actual=0, committed=0, remaining=100, breach=False,
):
    return CostLedger(
        record_id="costledger:" + "9" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"},
        cohort_id="cohort:" + "1" * 32, budget_cap_aud=money(100), entries=tuple(entries),
        reservation_reconciliations=tuple(positions), as_at=NOW,
        reserved_exposure_aud=money(reserved), released_reservations_aud=money(released), actual_spend_aud=money(actual),
        reservation_overrun_aud=money(overrun), unreserved_actual_aud=money(unreserved), credits_aud=money(credits),
        adjustment_debits_aud=money(adjustment_debits), adjustment_credits_aud=money(adjustment_credits),
        net_actual_spend_aud=signed(net_actual), committed_exposure_aud=signed(committed),
        remaining_budget_aud=signed(remaining), breach=breach,
    )


def test_money_and_exact_cohort_caps():
    with pytest.raises((ValidationError, TypeError)):
        Money(amount=1.2, currency="AUD")
    cohort = BudgetCohort(
        record_id="cohort:" + "1" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, cohort_code="C100",
        definition_version="1", ranking_metric="donor_decision_exposure_proxy", rank_start=1, rank_end=100,
        expected_member_count=100, membership_manifest_ref="manifest:1", membership_hash="a" * 64,
        budget_cap=money(100), pooling="within_cohort_only",
    )
    assert cohort.budget_cap.amount == Decimal("100")
    with pytest.raises(ValidationError):
        BudgetCohort(**{**cohort.model_dump(), "cohort_code": "C1K"})


def test_pricing_fx_and_url_rules():
    rate = PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.2"))
    pricing = PricingSnapshot(
        record_id="pricing:" + "2" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, provider_id="fake",
        model_snapshot="model-1", effective_at=NOW, retrieved_at=NOW, provider_currency="USD",
        authoritative_source_url="https://example.test/pricing", rates=(rate,), source_content_hash="b" * 64,
    )
    assert pricing.rates[0].price_per_unit == Decimal("0.2")
    with pytest.raises(ValidationError):
        FxRateSnapshot(
            record_id="fx:" + "3" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, base_currency="USD",
            quote_currency="AUD", aud_per_base_unit=Decimal("1.5"), observed_at=NOW, source_name="fx", source_url="https://example.test/fx?x=1", source_content_hash="c" * 64,
        )


def test_reservation_partial_actual_and_release_are_not_credits():
    result = ledger(
        [entry("reservation", 100), entry("actual", 30), entry("reservation_release", 70)],
        positions=(position(RESERVATION_A, 100, 30, 70),), reserved=0, released=70, actual=30,
        net_actual=30, committed=30, remaining=70,
    )
    assert result.net_actual_spend_aud.amount == Decimal("30")
    assert result.credits_aud.amount == Decimal("0")


def test_actual_overrun_is_recorded_not_rejected_and_can_breach():
    result = ledger(
        [entry("reservation", 100), entry("actual", 110)],
        positions=(position(RESERVATION_A, 100, 110, 0),), reserved=0, actual=110, overrun=10,
        net_actual=110, committed=110, remaining=-10, breach=True,
    )
    assert result.reservation_overrun_aud.amount == Decimal("10")
    assert result.breach is True


def test_releases_are_reconciled_per_reservation_not_cohort_capacity():
    valid_positions = (
        position(RESERVATION_A, 100, 0, 100),
        position(RESERVATION_B, 100, 10, 0),
    )
    with pytest.raises(ValidationError, match="releases cannot exceed"):
        ledger(
            [entry("reservation", 100, reservation_id=RESERVATION_A), entry("reservation", 100, reservation_id=RESERVATION_B),
             entry("actual", 10, reservation_id=RESERVATION_B), entry("reservation_release", 110, reservation_id=RESERVATION_A)],
            positions=valid_positions, reserved=90, released=110, actual=10, net_actual=10, committed=100, remaining=0,
        )


def test_actual_without_reservation_is_explicit_unreserved_actual_cost():
    result = ledger(
        [entry("actual", 25, reservation_id=RESERVATION_UNMATCHED)],
        positions=(), actual=25, unreserved=25, net_actual=25, committed=25, remaining=75,
    )
    assert result.unreserved_actual_aud.amount == Decimal("25")


def test_partial_actual_followed_by_excessive_release_fails():
    with pytest.raises(ValidationError, match="releases cannot exceed"):
        ledger(
            [entry("reservation", 100), entry("actual", 30), entry("reservation_release", 71)],
            positions=(position(RESERVATION_A, 100, 30, 70),), released=71, actual=30,
            net_actual=30, committed=30, remaining=70,
        )


def test_credits_and_adjustments_use_explicit_signed_reconciliation():
    result = ledger(
        [entry("reservation", 10), entry("actual", 10), entry("credit", 20), entry("adjustment", 5, direction="debit"), entry("adjustment", 3, direction="credit")],
        positions=(position(RESERVATION_A, 10, 10, 0),), actual=10, credits=20,
        adjustment_debits=5, adjustment_credits=3, net_actual=-8, committed=-8, remaining=108,
    )
    assert result.net_actual_spend_aud.amount == Decimal("-8")
    with pytest.raises(ValidationError):
        entry("adjustment", 1)
    with pytest.raises(ValidationError):
        entry("actual", 1, direction="debit")


def test_cost_ledger_breach_and_reservation_reconciliation_are_exact():
    result = ledger(
        [entry("reservation", 120)], positions=(position(RESERVATION_A, 120, 0, 0),),
        reserved=120, net_actual=0, committed=120, remaining=-20, breach=True,
    )
    assert result.breach is True
    with pytest.raises(ValidationError, match="matching reservation"):
        ledger(
            [entry("reservation_release", 1)], positions=(), released=1,
        )


def test_run_manifest_status_and_times():
    with pytest.raises(ValidationError):
        RunManifest(
            record_id="run:" + "8" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, run_kind="contract_fixture",
            status="running", configuration_hash="d" * 64, completed_at=NOW,
        )
    run = RunManifest(
        record_id="run:" + "9" * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test"}, run_kind="contract_fixture",
        status="planned", configuration_hash="d" * 64,
    )
    assert run.status == "planned"
