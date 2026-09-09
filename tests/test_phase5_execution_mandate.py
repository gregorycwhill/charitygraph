from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.phase5_execution_mandate import (
    MandateDecision,
    evaluate_execution_against_mandate,
    manifest_hash,
    proposed_phase5_standard_luna_manifest,
    proposed_phase5_standard_luna_historical_manifest,
    proposed_phase5_standard_luna_amendment_manifest,
)
from charitygraph.phase5_semantic_contracts import HISTORICAL_DISCOVERY_V2_CONTRACT, REGISTRY
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
        "hard_max_aud": "0.20", "mandate_reservation_id": "mandatereservation:default", **contract,
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
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:default", amount_aud="0.25", now=NOW)
    first = evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest, hard_max_aud="0.20"))
    second = evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest, hard_max_aud="0.25"))
    assert first.authorized and second.authorized


def test_contract_delivery_model_and_boundary_changes_fail_closed(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:default", amount_aud="0.25", now=NOW)
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
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:default", amount_aud="0.25", now=NOW)
    catalog.revoke_execution_mandate(mandate_id=manifest["mandate_id"], now=NOW, reason="phase boundary")
    assert evaluate_execution_against_mandate(catalog, manifest["mandate_id"], _request(manifest)).decision == MandateDecision.MANDATE_REVOKED
    catalog.authorize_standing_scope(authorization_id="authorization:old", policy_scope_hash="policy:old", provider="openai", model="gpt-5.6-luna", material_class="historical", task_family="old", max_attempts=1, publication_policy="none", established_by="Greg", now=NOW)
    assert catalog.get_standing_authorization(provider="openai", model="gpt-5.6-luna", material_class="historical", task_family="old", now=NOW)["authorization_id"] == "authorization:old"


def test_released_reservation_cannot_authorize_send_but_fresh_one_can(tmp_path):
    catalog = _catalog(tmp_path); manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    request = _request(manifest)
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:released", amount_aud="0.20", now=NOW)
    catalog.settle_execution_mandate_reservation(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:released", actual_aud="0", ambiguous=False, now=NOW)
    request["mandate_reservation_id"] = "mandatereservation:released"
    assert evaluate_execution_against_mandate(catalog, manifest["mandate_id"], request).decision == MandateDecision.RESERVATION_NOT_AUTHORIZED
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:fresh", amount_aud="0.20", now=NOW)
    request["mandate_reservation_id"] = "mandatereservation:fresh"
    assert evaluate_execution_against_mandate(catalog, manifest["mandate_id"], request).authorized


def test_evidenced_spend_correction_is_append_only_and_idempotent(tmp_path):
    catalog = _catalog(tmp_path); manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:c", amount_aud="0.25", now=NOW)
    catalog.settle_execution_mandate_reservation(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:c", actual_aud="0", ambiguous=False, now=NOW)
    event = {"physical_attempt_id": "physical:x", "provider_receipt_id": "receipt:x", "original_release": "mandatereservation:c", "reason": "provider usage evidenced after rehearsal release"}
    first = catalog.correct_execution_mandate_settlement(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:c", correction_id="mandatecorrection:c", evidenced_actual_aud="0.012345", correction_event=event, now=NOW)
    second = catalog.correct_execution_mandate_settlement(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:c", correction_id="mandatecorrection:c", evidenced_actual_aud="0.012345", correction_event=event, now=NOW)
    assert first["actual_spend_aud"] == second["actual_spend_aud"] == "0.012345"
    assert catalog.get_execution_mandate(manifest["mandate_id"])["actual_spend_aud"] == "0.012345"


def test_evidenced_spend_correction_cannot_expand_reservation(tmp_path):
    catalog = _catalog(tmp_path); manifest, _ = _register(catalog)
    catalog.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    catalog.reserve_execution_mandate(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:bounded", amount_aud="0.010000", now=NOW)
    catalog.settle_execution_mandate_reservation(mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:bounded", actual_aud="0", ambiguous=False, now=NOW)
    with pytest.raises(BudgetExceededError):
        catalog.correct_execution_mandate_settlement(
            mandate_id=manifest["mandate_id"], reservation_id="mandatereservation:bounded",
            correction_id="mandatecorrection:bounded", evidenced_actual_aud="0.010001",
            correction_event={"reason": "over-ceiling"}, now=NOW,
        )


def test_fake_rehearsal_authority_isolated_from_live_mandate(tmp_path):
    (tmp_path / "live").mkdir()
    (tmp_path / "rehearsal").mkdir()
    live = _catalog(tmp_path / "live")
    rehearsal = _catalog(tmp_path / "rehearsal")
    manifest, _ = _register(live)
    live.activate_execution_mandate(mandate_id=manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="Greg", now=NOW)
    fake_manifest, _ = _register(rehearsal)
    rehearsal.activate_execution_mandate(mandate_id=fake_manifest["mandate_id"], authorization_text_hash="a" * 64, authorized_by="test", now=NOW)
    for index in range(93):
        reservation_id = f"mandatereservation:fake:{index}"
        rehearsal.reserve_execution_mandate(mandate_id=fake_manifest["mandate_id"], reservation_id=reservation_id, amount_aud="0.010000", now=NOW)
        rehearsal.settle_execution_mandate_reservation(mandate_id=fake_manifest["mandate_id"], reservation_id=reservation_id, actual_aud="0", ambiguous=False, now=NOW)
    assert Decimal(live.get_execution_mandate(manifest["mandate_id"])["actual_spend_aud"]) == Decimal("0")
    assert Decimal(live.get_execution_mandate(manifest["mandate_id"])["unresolved_reserved_aud"]) == Decimal("0")


def test_representation_amendment_replaces_discovery_binding_only(tmp_path):
    catalog = _catalog(tmp_path)
    manifest, _ = _register(catalog)
    amended = proposed_phase5_standard_luna_amendment_manifest()
    discovery = next(item for item in amended["allowed_contracts"] if item["claim_families"] == ["program-service-discovery-v2"])
    direct = next(item for item in amended["allowed_contracts"] if item["claim_families"] == ["direct-service-access-v1"])
    assert discovery["contract_version"] == "2.1"
    assert discovery["schema_id"].endswith(":2.1")
    assert discovery["contract_identity_hash"] != HISTORICAL_DISCOVERY_V2_CONTRACT.identity_hash()
    assert direct["contract_version"] == "1.0"
    assert direct["contract_identity_hash"] == next(c for c in REGISTRY if c.contract_id.endswith("direct-service-v1")).identity_hash()
    assert amended["supersedes_mandate_id"] == "mandate:phase5-build-standard-luna-v1-amendment-1"


def test_amended_mandate_rejects_historical_discovery_identity_for_future_send(tmp_path):
    catalog = _catalog(tmp_path)
    amended = proposed_phase5_standard_luna_amendment_manifest()
    catalog.register_execution_mandate(
        mandate_id=amended["mandate_id"], manifest_hash=manifest_hash(amended), authorization_text_hash="b" * 64,
        scope=amended, contract_allowlist=tuple(amended["allowed_contracts"]), aggregate_hard_aud=amended["aggregate_hard_aud"],
        per_request_hard_aud=amended["per_request_hard_aud"], phase_scope=amended["phase_scope"], now=NOW,
    )
    catalog.activate_execution_mandate(mandate_id=amended["mandate_id"], authorization_text_hash="b" * 64, authorized_by="Greg", now=NOW)
    catalog.reserve_execution_mandate(mandate_id=amended["mandate_id"], reservation_id="mandatereservation:historical", amount_aud="0.20", now=NOW)
    old = next(item for item in proposed_phase5_standard_luna_historical_manifest()["allowed_contracts"] if item["claim_families"] == ["program-service-discovery-v2"])
    request = _request(amended, mandate_reservation_id="mandatereservation:historical", **{key: old[key] for key in ("contract_id", "contract_version", "task_profile", "task_profile_version", "prompt_sha256", "schema_id", "schema_version", "provider_schema_name", "contract_identity_hash")})
    assert evaluate_execution_against_mandate(catalog, amended["mandate_id"], request).decision == MandateDecision.CONTRACT_NOT_ALLOWED
