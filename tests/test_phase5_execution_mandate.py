from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.phase5_execution_mandate import (
    MandateDecision,
    evaluate_execution_against_mandate,
    manifest_hash,
    proposed_phase5_standard_luna_manifest,
)
from charitygraph.runtime.catalog import BudgetExceededError, SQLiteCatalog


NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def _catalog(tmp_path):
    return SQLiteCatalog(tmp_path / "catalog.sqlite3", authorization_path=tmp_path / "authority.sqlite3").open(initialize=True)


def _register(catalog):
    manifest = proposed_phase5_standard_luna_manifest()
    row = catalog.register_execution_mandate(
        mandate_id=manifest["mandate_id"], manifest_hash=manifest_hash(manifest), authorization_text_hash="a" * 64,
        scope=manifest, contract_allowlist=tuple(manifest["allowed_contracts"]), aggregate_hard_aud=manifest["aggregate_hard_aud"],
        per_request_hard_aud=manifest["per_request_hard_aud"], phase_scope=manifest["phase_scope"], now=NOW,
    )
    return manifest, row


def _request(manifest, **changes):
    contract = manifest["allowed_contracts"][0]
    request = {
        "provider": "openai", "delivery_mode": "standard", "model": "gpt-5.6-luna", "reasoning_effort": "low",
        "automatic_retries": 0, "semantic_retries": 0, "fallbacks": [], "ambiguous_resend": False,
        "hard_max_aud": "0.20", **contract,
    }
    request.update(changes)
    return request


def test_proposed_mandate_is_deterministic_and_not_self_activated(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, row = _register(catalog)
    assert row["status"] == "proposed"
    assert manifest_hash(manifest) == manifest_hash(proposed_phase5_standard_luna_manifest())
    assert evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest)).decision == MandateDecision.HUMAN_AUTHORIZATION_REQUIRED


def test_multiple_campaigns_and_exact_contract_are_allowed_after_explicit_activation(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    first = evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest, hard_max_aud="0.20"))
    second = evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest, hard_max_aud="0.25"))
    assert first.authorized and second.authorized


def test_contract_delivery_model_and_boundary_changes_fail_closed(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    mandate = manifest["mandate_id"]
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, contract_identity_hash="b" * 64)).decision == MandateDecision.CONTRACT_NOT_ALLOWED
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, provider="azure")).decision == MandateDecision.PROVIDER_NOT_ALLOWED
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, model="gpt-5.6-terra")).decision == MandateDecision.MODEL_NOT_ALLOWED
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, delivery_mode="batch")).decision == MandateDecision.DELIVERY_NOT_ALLOWED
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, schema_version="changed")).decision == MandateDecision.CONTRACT_NOT_ALLOWED
    assert evaluate_execution_against_mandate(catalog, mandate, _request(manifest, prompt_sha256="changed")).decision == MandateDecision.CONTRACT_NOT_ALLOWED


def test_per_request_and_aggregate_authority_use_actual_exposure(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    mandate = manifest["mandate_id"]
    with pytest.raises(BudgetExceededError):
        catalog.reserve_execution_mandate(mandate_id=mandate, reservation_id="reservation:too-large", amount_aud="0.250001", now=NOW)
    catalog.reserve_execution_mandate(mandate_id=mandate, reservation_id="reservation:one", amount_aud="0.20", now=NOW)
    catalog.settle_execution_mandate_reservation(mandate_id=mandate, reservation_id="reservation:one", actual_aud="0.10", ambiguous=False, now=NOW)
    snapshot = catalog.get_execution_mandate(mandate)
    assert Decimal(snapshot["actual_spend_aud"]) == Decimal("0.10")
    assert Decimal(snapshot["unresolved_reserved_aud"]) == Decimal("0")
    catalog.reserve_execution_mandate(mandate_id=mandate, reservation_id="reservation:two", amount_aud="0.25", now=NOW)
    catalog.settle_execution_mandate_reservation(mandate_id=mandate, reservation_id="reservation:two", actual_aud="0", ambiguous=True, now=NOW)
    snapshot = catalog.get_execution_mandate(mandate)
    assert Decimal(snapshot["unresolved_reserved_aud"]) == Decimal("0.25")


def test_revocation_blocks_new_reservations_and_historical_one_off_stays_readable(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    catalog.revoke_execution_mandate(mandate_id=manifest["mandate_id"], now=NOW, reason="phase boundary")
    assert evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest)).decision == MandateDecision.MANDATE_REVOKED
    catalog.authorize_standing_scope(authorization_id="authorization:old", policy_scope_hash="policy:old", provider="openai", model="gpt-5.6-luna", material_class="historical", task_family="old", max_attempts=1, publication_policy="none", established_by="Greg", now=NOW)
    assert catalog.get_standing_authorization(provider="openai", model="gpt-5.6-luna", material_class="historical", task_family="old", now=NOW)["authorization_id"] == "authorization:old"
