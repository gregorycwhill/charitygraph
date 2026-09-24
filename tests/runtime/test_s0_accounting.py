from decimal import Decimal
from dataclasses import replace
from types import SimpleNamespace

import pytest

from charitygraph.s0_accounting import S0ProviderAccountingFactory
from charitygraph.s0_locator_discovery import S0LocatorSearchExecutionGate
from charitygraph.scale_s0 import ScalePreflightError, ScaleS0Preflight

from .test_s0_locator_search_lifecycle import NOW, _prepared_catalog


def _receipt(catalog, mandate, packet, prepared, usage):
    live = ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)
    gate = S0LocatorSearchExecutionGate(
        preflight=live,
        request=prepared.request,
        catalog=catalog,
        delivery_attempt_id=prepared.delivery_attempt_id,
        client_request_id=prepared.client_request_id,
        request_identity=packet.provider_request_identity,
        now=NOW,
    )
    gate.begin(request_identity=packet.provider_request_identity, subject_abn=packet.subject_id, query=packet.locator_query)
    gate.complete(provider_receipt_id="response:accounting", result_ref="provider-response:accounting", usage=usage)


def _usage(amount="0.04", currency="USD", pricing="pricing:locator-v1"):
    return {
        "input_tokens": 10,
        "output_tokens": 5,
        "provider_cost": {"amount": amount, "currency": currency},
        "pricing_snapshot_id": pricing,
    }


def test_factory_reconciles_one_durable_actual_and_release_across_restart(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    usage = _usage()
    _receipt(catalog, mandate, packet, prepared, usage)
    accounting = S0ProviderAccountingFactory(
        catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator"
    ).create()

    first = accounting.reconcile(
        request=prepared.request,
        packet=packet,
        provider_receipt_id="response:accounting",
        usage=usage,
    )
    again = accounting.reconcile(
        request=prepared.request,
        packet=packet,
        provider_receipt_id="response:accounting",
        usage=usage,
    )
    assert first == again
    position = catalog.accounting_reservation_position("reservation:locator")
    assert position["actual"] == Decimal("0.040000")
    assert position["released"] == Decimal("0.060000")
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='reservation_release'").fetchone()[0] == 1

    catalog.close()
    reopened = type(catalog)(tmp_path / "locator.sqlite3").open()
    recovered = S0ProviderAccountingFactory(
        catalog=reopened, now=lambda: NOW, execution_attempt_id="attempt:locator"
    ).create().reconcile_durable(request=prepared.request, packet=packet)
    assert recovered["entry_key"] == first["entry_key"]
    reopened.close()


@pytest.mark.parametrize(
    "usage, message",
    [
        ({}, "missing or partial"),
        ({"input_tokens": 10}, "missing or partial"),
        (_usage(pricing="pricing:other"), "does not match"),
        ({**_usage(), "accounting_cost": {"amount": "0.05", "currency": "USD"}}, "conflicts"),
        ({**_usage(currency="EUR"), "accounting_cost": {"amount": "0.04", "currency": "USD"}}, "FX"),
    ],
)
def test_accounting_rejects_missing_partial_and_mismatched_provider_evidence(tmp_path, usage, message):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    _receipt(catalog, mandate, packet, prepared, usage)
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    with pytest.raises(ScalePreflightError, match=message):
        accounting.reconcile(
            request=prepared.request,
            packet=packet,
            provider_receipt_id="response:accounting",
            usage=usage,
        )
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 0


def test_actual_cost_overrun_is_recorded_without_fabricated_release(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    usage = _usage(amount="0.15")
    _receipt(catalog, mandate, packet, prepared, usage)
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    accounting.reconcile(request=prepared.request, packet=packet, provider_receipt_id="response:accounting", usage=usage)
    position = catalog.accounting_reservation_position("reservation:locator")
    assert position["actual"] == Decimal("0.150000")
    assert position["released"] == Decimal("0")
    assert catalog.accounting_budget_position("cohort:locator").reservation_overrun == Decimal("0.050000")


@pytest.mark.parametrize("bad_amount", [0.04, True])
def test_accounting_rejects_binary_or_boolean_decimal_evidence(tmp_path, bad_amount):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    usage = _usage(amount=bad_amount)
    _receipt(catalog, mandate, packet, prepared, usage)
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    with pytest.raises(ScalePreflightError, match="decimal"):
        accounting.reconcile(request=prepared.request, packet=packet, provider_receipt_id="response:accounting", usage=usage)


def test_accounting_rejects_request_bound_to_another_reservation(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    usage = _usage()
    _receipt(catalog, mandate, packet, prepared, usage)
    replacement = replace(prepared.request, reservation_id="reservation:substituted")
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    with pytest.raises(ScalePreflightError, match="lifecycle identity"):
        accounting.reconcile(request=replacement, packet=packet, provider_receipt_id="response:accounting", usage=usage)


def test_accounting_rejects_non_alpha_currency_and_response_model_mismatch(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    bad_currency = _usage(currency="U1D")
    _receipt(catalog, mandate, packet, prepared, bad_currency)
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    with pytest.raises(ScalePreflightError, match="upper-case ISO currency"):
        accounting.reconcile(request=prepared.request, packet=packet, provider_receipt_id="response:accounting", usage=bad_currency)

    model_root = tmp_path / "model"
    model_root.mkdir()
    catalog2, mandate2, packet2, prepared2 = _prepared_catalog(model_root)
    usage = _usage()
    _receipt(catalog2, mandate2, packet2, prepared2, usage)
    accounting2 = S0ProviderAccountingFactory(catalog=catalog2, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    accepted = accounting2.reconcile(
        request=prepared2.request,
        packet=packet2,
        provider_receipt_id="response:accounting",
        usage=usage,
        provider_response=SimpleNamespace(body={"model": "synthetic"}),
    )
    assert accepted["actual"] == "0.04"
    with pytest.raises(ScalePreflightError, match="response model"):
        accounting2.reconcile(
            request=prepared2.request,
            packet=packet2,
            provider_receipt_id="response:accounting",
            usage=usage,
            provider_response=SimpleNamespace(body={"model": "wrong-model"}),
        )
