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


def _frozen_luna_pricing():
    return SimpleNamespace(
        record_id="pricing:locator-v1", model_snapshot="gpt-5.6-luna", provider_currency="USD",
        rates=tuple(SimpleNamespace(dimension=dimension, unit_quantity=Decimal("1000000" if dimension != "tool_calls" else "1000"), price_per_unit=Decimal(price))
                    for dimension, price in (("input_tokens", "1"), ("cached_input_tokens", "0.5"), ("output_tokens", "2"), ("tool_calls", "10"))),
    )


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


def test_post_response_locator_schema_failure_reconciles_frozen_pricing_once_without_sources(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    with catalog._connection(immediate=True) as conn:
        conn.execute("UPDATE provider_request_items SET model_route='gpt-5.6-luna' WHERE provider_request_item_id=?", (packet.provider_request_identity,))
        catalog._commit(conn)
    live = ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)
    gate = S0LocatorSearchExecutionGate(preflight=live, request=prepared.request, catalog=catalog,
                                        delivery_attempt_id=prepared.delivery_attempt_id, client_request_id=prepared.client_request_id,
                                        request_identity=packet.provider_request_identity, now=NOW)
    usage = {"input_tokens": 10, "output_tokens": 5}
    gate.begin(request_identity=packet.provider_request_identity, subject_abn=packet.subject_id, query=packet.locator_query)
    gate.complete(provider_receipt_id="response:schema", result_ref="provider-response:schema", usage=usage,
                  response_facts={"model": "gpt-5.6-luna", "web_search_calls": 1})
    gate.fail(failure_class="provider_schema_failure", message="missing web-search source structure")
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator",
                                             pricing_snapshot=_frozen_luna_pricing()).create()
    first = accounting.reconcile_durable(request=prepared.request, packet=packet)
    again = accounting.reconcile_durable(request=prepared.request, packet=packet)
    assert first == again
    assert catalog.get_scale_s0_locator_terminal_outcome(prepared.request.physical_attempt_id)["outcome_class"] == "provider_schema_failure"
    assert catalog.accounting_reservation_position("reservation:locator")["released"] > Decimal("0")
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='reservation_release'").fetchone()[0] == 1


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


def test_reentry_repairs_actual_committed_before_release_crash(tmp_path, monkeypatch):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    usage = _usage()
    _receipt(catalog, mandate, packet, prepared, usage)
    accounting = S0ProviderAccountingFactory(catalog=catalog, now=lambda: NOW, execution_attempt_id="attempt:locator").create()
    release = catalog.release_reservation

    def crash_before_release(*args, **kwargs):
        raise RuntimeError("synthetic release persistence crash")

    monkeypatch.setattr(catalog, "release_reservation", crash_before_release)
    with pytest.raises(RuntimeError, match="release persistence"):
        accounting.reconcile(request=prepared.request, packet=packet, provider_receipt_id="response:accounting", usage=usage)
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='reservation_release'").fetchone()[0] == 0

    monkeypatch.setattr(catalog, "release_reservation", release)
    accounting.reconcile(request=prepared.request, packet=packet, provider_receipt_id="response:accounting", usage=usage)
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='reservation_release'").fetchone()[0] == 1


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
