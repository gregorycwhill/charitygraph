from datetime import datetime, timezone
from decimal import Decimal
import sqlite3
import runpy

import pytest

from charitygraph.runtime import BudgetExceededError, CatalogError, ConflictError, SQLiteCatalog
import charitygraph.runtime.catalog as catalog_module
from charitygraph.runtime.migrations import MIGRATIONS


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
COHORT = "cohort:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
RUN = "run:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
RES = "reservation:cccccccccccccccccccccccccccccccc"


def cohort(currency="USD", amount="8"):
    return {"record_id": COHORT, "cohort_code": "SPIKE", "definition_version": "1", "membership_hash": "a" * 64, "budget_cap": {"amount": amount, "currency": currency}, "created_at": NOW}


def opened(tmp_path, currency="USD", amount="8"):
    catalog = SQLiteCatalog(tmp_path / "currency.sqlite3").open(initialize=True)
    catalog.register_cohort(cohort(currency, amount))
    catalog.register_run({"record_id": RUN, "cohort_id": COHORT, "run_kind": "economics_spike", "status": "planned", "configuration_hash": "b" * 64, "created_at": NOW})
    return catalog


def reservation(amount="0.25", currency="USD", rid=RES):
    return {"record_id": rid, "cohort_id": COHORT, "run_id": RUN, "reserved_amount": {"amount": amount, "currency": currency}, "model_task_ids": (), "expires_at": None}


def test_usd_budget_and_reservation_are_durable_truthful_and_restart_safe(tmp_path):
    catalog = opened(tmp_path)
    assert catalog.get_cohort(COHORT)["budget_cap_amount"] == "8"
    assert catalog.get_cohort(COHORT)["accounting_currency"] == "USD"
    row = catalog.reserve_cost(reservation(), now=NOW)
    assert (row["reserved_amount"], row["accounting_currency"], row["reserved_aud"]) == ("0.25", "USD", "0")
    position = catalog.accounting_budget_position(COHORT)
    assert (position.currency, position.cohort_cap, position.remaining_budget) == ("USD", Decimal("8"), Decimal("7.75"))
    assert catalog.accounting_reservation_position(RES)["currency"] == "USD"
    catalog.release_reservation(RES, {"amount": "0.05", "currency": "USD"}, now=NOW, entry_key="usd-release")
    assert catalog.accounting_reservation_position(RES)["outstanding"] == Decimal("0.200000")
    with pytest.raises(CatalogError, match="AUD-only"):
        catalog.budget_position(COHORT)
    catalog.close()
    reopened = SQLiteCatalog(tmp_path / "currency.sqlite3").open()
    assert reopened.accounting_reservation_position(RES)["reserved"] == Decimal("0.25")


def test_currency_mismatch_and_budget_overrun_fail_closed(tmp_path):
    catalog = opened(tmp_path, amount="0.25")
    with pytest.raises(ConflictError, match="currency"):
        catalog.reserve_cost(reservation(currency="AUD"), now=NOW)
    catalog.reserve_cost(reservation(), now=NOW)
    with pytest.raises(BudgetExceededError):
        catalog.reserve_cost(reservation(rid="reservation:dddddddddddddddddddddddddddddddd"), now=NOW)


def test_aud_legacy_surface_stays_aud(tmp_path):
    catalog = opened(tmp_path, currency="AUD", amount="1")
    catalog.reserve_cost({"record_id": RES, "cohort_id": COHORT, "run_id": RUN, "reserved_aud": {"amount": "0.25", "currency": "AUD"}, "model_task_ids": (), "expires_at": None}, now=NOW)
    assert catalog.budget_position(COHORT).cohort_cap_aud == Decimal("1")
    assert catalog.reservation_position(RES)["reserved"] == Decimal("0.25")


def test_upgrade_from_immediately_previous_schema_preserves_aud_authority(tmp_path, monkeypatch):
    path = tmp_path / "prior.sqlite3"
    monkeypatch.setattr(catalog_module, "MIGRATIONS", MIGRATIONS[:-1])
    monkeypatch.setattr(catalog_module, "SUPPORTED_VERSION", MIGRATIONS[-2].version)
    prior = SQLiteCatalog(path).open(initialize=True)
    prior.close()
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO cohorts(cohort_id, cohort_code, definition_version, membership_hash, budget_cap_aud, created_at, material_hash, budget_cap_amount, accounting_currency) VALUES (?,?,?,?,?,?,?,?,?)", (COHORT, "SPIKE", "1", "a" * 64, "1", NOW.isoformat(), "cohort-hash", "1", "AUD"))
        conn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)", (RUN, COHORT, "economics_spike", "planned", "b" * 64, NOW.isoformat(), None, None, NOW.isoformat(), "run-hash"))
        conn.execute("INSERT INTO budget_reservations(reservation_id, cohort_id, run_id, reserved_aud, status, reserved_at, expires_at, updated_at, material_hash, reserved_amount, accounting_currency) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (RES, COHORT, RUN, "0.25", "active", NOW.isoformat(), None, NOW.isoformat(), "reservation-hash", "0.25", "AUD"))
    monkeypatch.setattr(catalog_module, "MIGRATIONS", MIGRATIONS)
    monkeypatch.setattr(catalog_module, "SUPPORTED_VERSION", MIGRATIONS[-1].version)
    upgraded = SQLiteCatalog(path).open(initialize=True)
    assert upgraded.get_cohort(COHORT)["budget_cap_amount"] == "1"
    assert upgraded.get_reservation(RES)["reserved_amount"] == "0.25"
    assert upgraded.accounting_budget_position(COHORT).currency == "AUD"


def test_offline_s0_usd_limits_and_durable_binding_need_no_fx(tmp_path):
    """A throwaway S0 rehearsal: only offline catalogue control-plane writes."""
    scale = runpy.run_path("tests/test_scale_s0.py")
    from charitygraph.scale_s0 import EconomicState, ScaleS0Preflight
    harness, packet, _, policies = scale["harness"]()
    mandate = scale["mandate"](
        policies, currency_basis="USD", provider_spend_ceiling="8",
        strong_model_spend_ceiling="4", per_request_reservation_cap="0.25",
        provider_call_ceiling=150,
    )
    economics = EconomicState(0, Decimal("0"), Decimal("0"), "reservation:offline-usd", True, mandate.mandate_id, mandate.slice_id, scale["TASK"].key, Decimal("0.25"), "USD", Decimal("0.25"), Decimal("0"))
    catalog = SQLiteCatalog(tmp_path / "offline-usd.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, scale["REGISTRY"], harness.routing, policies, harness.sources, offline=True)
    ScaleS0Preflight.record_durable_reservation(catalog, economics, recorded_at=NOW, offline=True)
    binding = catalog.get_scale_s0_reservation_binding(mandate_id=mandate.mandate_id, slice_id=mandate.slice_id, task_key=scale["TASK"].key, offline=True)
    assert binding["state"]["reservation_currency"] == "USD"
    assert ScaleS0Preflight(mandate, scale["REGISTRY"], harness.routing, harness.sources, harness.halts, packets=harness.packets, policies=policies, economics=economics).provider_send(scale["request"](packet, reservation_id="reservation:offline-usd")) == scale["TASK"]
