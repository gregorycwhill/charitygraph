from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from charitygraph.contracts import BudgetCohort, CostLedger, CostLedgerEntry, FxRateSnapshot, Money, PriceRate, PricingSnapshot, RunManifest
from charitygraph.contracts.tasks import ProviderUsage

NOW=datetime(2026,1,1,tzinfo=timezone.utc)

def money(amount, currency="AUD"):
    return Money(amount=amount, currency=currency)

def test_money_and_exact_cohort_caps():
    with pytest.raises((ValidationError, TypeError)):
        Money(amount=1.2, currency="AUD")
    cohort=BudgetCohort(
        record_id="cohort:"+"1"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, cohort_code="C100",
        definition_version="1", ranking_metric="donor_decision_exposure_proxy", rank_start=1, rank_end=100,
        expected_member_count=100, membership_manifest_ref="manifest:1", membership_hash="a"*64,
        budget_cap=money(Decimal("100")), pooling="within_cohort_only",
    )
    assert cohort.budget_cap.amount == Decimal("100")
    with pytest.raises(ValidationError):
        BudgetCohort(**{**cohort.model_dump(), "cohort_code":"C1K"})

def test_pricing_fx_and_url_rules():
    rate=PriceRate(dimension="input_tokens", unit_quantity=Decimal("1000000"), price_per_unit=Decimal("0.2"))
    pricing=PricingSnapshot(
        record_id="pricing:"+"2"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, provider_id="fake",
        model_snapshot="model-1", effective_at=NOW, retrieved_at=NOW, provider_currency="USD",
        authoritative_source_url="https://example.test/pricing", rates=(rate,), source_content_hash="b"*64,
    )
    assert pricing.rates[0].price_per_unit == Decimal("0.2")
    with pytest.raises(ValidationError):
        FxRateSnapshot(
            record_id="fx:"+"3"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, base_currency="USD",
            quote_currency="AUD", aud_per_base_unit=Decimal("1.5"), observed_at=NOW, source_name="fx", source_url="https://example.test/fx?x=1", source_content_hash="c"*64,
        )

def test_cost_ledger_reconciles_and_represents_breach():
    actual=CostLedgerEntry(
        cohort_id="cohort:"+"1"*32, run_id="run:"+"4"*32, task_run_id="taskrun:"+"5"*32, reservation_id="reservation:"+"6"*32,
        pricing_snapshot_id="pricing:"+"2"*32, fx_snapshot_id="fx:"+"3"*32, entry_type="actual", paid_output_category="extraction",
        provider_cost=money(Decimal("1"),"USD"), aud_cost=money(Decimal("101")), usage=ProviderUsage(input_tokens=1), recorded_at=NOW,
    )
    ledger=CostLedger(
        record_id="costledger:"+"7"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, cohort_id="cohort:"+"1"*32,
        budget_cap_aud=money(Decimal("100")), entries=(actual,), as_at=NOW, actual_spend_aud=money(Decimal("101")),
        credits_aud=money(Decimal("0")), net_spend_aud=money(Decimal("101")), breach=True,
    )
    assert ledger.breach is True

def test_run_manifest_status_and_times():
    with pytest.raises(ValidationError):
        RunManifest(
            record_id="run:"+"8"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, run_kind="contract_fixture",
            status="running", configuration_hash="d"*64, completed_at=NOW,
        )
    run=RunManifest(
        record_id="run:"+"9"*32, created_at=NOW, producer={"kind":"code","producer_id":"test"}, run_kind="contract_fixture",
        status="planned", configuration_hash="d"*64,
    )
    assert run.status == "planned"
