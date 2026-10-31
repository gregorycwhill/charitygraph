from __future__ import annotations

import hashlib
import json
from datetime import date
from types import SimpleNamespace

import pytest

from charitygraph.contracts.canonical import canonical_json_bytes
from charitygraph.g4_provider_policy_registry import (
    PROVIDER_POLICY_REGISTRY_SCHEMA,
    ProviderPolicyResolution,
    ProviderPolicyRecord,
    resolve_provider_policy_registry,
)
from charitygraph.phase5_governed_rights_preflight import (
    ProviderRealSendGate,
    require_authenticated_provider_authority_for_real_send,
)


def _route(**changes):
    value = {
        "provider": "openai",
        "project_id": "project-fixture",
        "service": "responses_api",
        "endpoint": "https://provider.invalid/v1/responses",
        "model": "model-fixture",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
    }
    value.update(changes)
    return value


def _authority_document_bytes():
    return canonical_json_bytes({
        "authority_document": "fixture-provider-policy",
        "authority_document_version": "1",
    })


def _entry(**changes):
    value = {
        "schema_id": PROVIDER_POLICY_REGISTRY_SCHEMA,
        "contract_id": "contract-fixture",
        "contract_version": "3.2",
        "provider_policy_id": "provider-policy-fixture",
        "provider_policy_version": "7.4",
        "authority_locator": "authority://fixture/provider-policy",
        "authority_content_sha256": hashlib.sha256(_authority_document_bytes()).hexdigest(),
        "status": "current",
        "effective_from": date(2026, 1, 1),
        "renewal_check_date": date(2027, 1, 1),
        "route": {
            "provider": "openai",
            "project_id": "project-fixture",
            "service": "responses_api",
            "endpoint": "https://provider.invalid/v1/responses",
            "model": "model-fixture",
        },
        "retention_posture": "ordinary",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
        "renewal_revalidation_rule": "revalidate-before-each-request",
    }
    value.update(changes)
    return value


def _bytes_and_pin(value=None):
    record = ProviderPolicyRecord.model_validate(_entry() if value is None else value)
    raw = record.canonical_bytes
    return raw, hashlib.sha256(raw).hexdigest(), _authority_document_bytes()


def _resolve(raw, pin, **changes):
    authority_document_bytes = changes.pop("authority_document_bytes", _authority_document_bytes())
    return resolve_provider_policy_registry(
        authority_bytes=raw,
        trusted_authority_sha256=pin,
        authority_document_bytes=authority_document_bytes,
        expected_contract_id=changes.pop("expected_contract_id", "contract-fixture"),
        expected_contract_version=changes.pop("expected_contract_version", "3.2"),
        expected_provider_policy_id=changes.pop("expected_provider_policy_id", "provider-policy-fixture"),
        expected_provider_policy_version=changes.pop("expected_provider_policy_version", "7.4"),
        caller_route=changes.pop("caller_route", _route()),
        as_of=changes.pop("as_of", date(2026, 10, 31)),
        **changes,
    )


def test_structural_record_is_deterministic_but_unauthenticated_and_never_send_ready():
    raw, pin, document = _bytes_and_pin()
    first = _resolve(raw, pin)
    second = _resolve(raw, pin)

    assert first.status == "STRUCTURE_ONLY_UNAUTHENTICATED"
    assert first.authority_verified is False
    assert first.verified is False
    assert first.real_send_ready is False
    assert first.action == "NONE"
    assert first.host_authentication_required is True
    assert first.send_authorization == "not_authorized_for_send"
    assert first.reasons == ("source_owned_authority_unbound",)
    assert first.content_hash == second.content_hash
    assert first.observed_record_sha256 == pin
    assert first.observed_authority_document_sha256 == hashlib.sha256(document).hexdigest()
    assert first.trusted_record_sha256 is None


def test_hash_and_identity_mismatch_fail_closed():
    raw, pin, _document = _bytes_and_pin()
    assert "trusted_authority_pin_mismatch" in _resolve(raw, "b" * 64).reasons
    assert "trusted_authority_pin_invalid" in _resolve(raw, "not-a-hash").reasons
    assert "expected_contract_identity_mismatch" in _resolve(
        raw, pin, expected_contract_id="other-contract"
    ).reasons
    assert "provider_policy_version_mismatch" in _resolve(
        raw, pin, expected_provider_policy_version="other-version"
    ).reasons


def test_missing_authority_and_missing_pin_fail_closed():
    missing = resolve_provider_policy_registry(
        expected_contract_id="contract-fixture",
        expected_contract_version="3.2",
    )
    assert missing.status == "missing"
    raw, _pin, _document = _bytes_and_pin()
    unpinned = _resolve(raw, None)
    assert unpinned.status == "blocked"
    assert "trusted_authority_pin_missing" in unpinned.reasons


@pytest.mark.parametrize("status", ["stale", "revoked", "expired"])
def test_stale_revoked_and_expired_statuses_fail_closed(status):
    raw, pin, _document = _bytes_and_pin(_entry(status=status))
    result = _resolve(raw, pin)
    assert result.status == "blocked"
    assert f"source_owned_authority_{status}" in result.reasons


def test_renewal_check_date_expiry_fails_closed():
    raw, pin, _document = _bytes_and_pin(_entry(renewal_check_date=date(2026, 10, 30)))
    result = _resolve(raw, pin, as_of=date(2026, 10, 31))
    assert "source_owned_authority_renewal_check_expired" in result.reasons


def test_route_mismatch_and_no_sharing_posture_fail_closed():
    raw, pin, _document = _bytes_and_pin()
    route_mismatch = _resolve(raw, pin, caller_route=_route(model="other-model"))
    assert "caller_model_mismatch" in route_mismatch.reasons
    no_sharing = _entry(provider_data_sharing_opt_in=True)
    raw, pin, _document = _bytes_and_pin(no_sharing)
    result = _resolve(raw, pin)
    assert "no_sharing_posture_not_authorized" in result.reasons


def test_duplicate_entries_are_rejected_without_selecting_one():
    record = ProviderPolicyRecord.model_validate(_entry())
    result = resolve_provider_policy_registry(
        authority_records=(record, record),
        trusted_authority_sha256=record.content_hash,
        expected_contract_id=record.contract_id,
        expected_contract_version=record.contract_version,
        expected_provider_policy_id=record.provider_policy_id,
        expected_provider_policy_version=record.provider_policy_version,
        caller_route=_route(),
        authority_document_bytes=_authority_document_bytes(),
        as_of=date(2026, 10, 31),
    )
    assert result.status == "invalid"
    assert result.authority_verified is False
    assert result.reasons == ("duplicate_authority_entries",)


def test_forged_matching_record_and_caller_pin_remain_unauthenticated():
    raw, pin, _document = _bytes_and_pin()
    result = _resolve(raw, pin)
    assert result.status == "STRUCTURE_ONLY_UNAUTHENTICATED"
    assert result.authority_verified is False
    assert "source_owned_authority_unbound" in result.reasons


def test_authority_content_hash_must_match_separate_document_bytes():
    raw, pin, _document = _bytes_and_pin()
    supplied = json.loads(raw)
    supplied["authority_content_sha256"] = hashlib.sha256(b"different-authority-document").hexdigest()
    forged = canonical_json_bytes(supplied)
    result = _resolve(forged, hashlib.sha256(forged).hexdigest())
    assert result.status == "blocked"
    assert "authority_content_sha256_mismatch" in result.reasons


def test_missing_or_self_referential_authority_document_fails_closed():
    raw, pin, _document = _bytes_and_pin()
    missing = resolve_provider_policy_registry(
        authority_bytes=raw,
        trusted_authority_sha256=pin,
        expected_contract_id="contract-fixture",
        expected_contract_version="3.2",
        expected_provider_policy_id="provider-policy-fixture",
        expected_provider_policy_version="7.4",
        caller_route=_route(),
    )
    assert missing.status == "blocked"
    assert "authority_document_bytes_missing" in missing.reasons
    self_referential = _resolve(raw, pin, authority_document_bytes=raw)
    assert self_referential.status == "blocked"
    assert "authority_document_self_referential" in self_referential.reasons


def test_missing_source_owned_origin_fails_closed():
    supplied = _entry(authority_locator="")
    raw = canonical_json_bytes(supplied)
    result = resolve_provider_policy_registry(
        authority_bytes=raw,
        trusted_authority_sha256=hashlib.sha256(raw).hexdigest(),
        authority_document_bytes=_authority_document_bytes(),
        expected_contract_id="contract-fixture",
        expected_contract_version="3.2",
        expected_provider_policy_id="provider-policy-fixture",
        expected_provider_policy_version="7.4",
        caller_route=_route(),
        as_of=date(2026, 10, 31),
    )
    assert result.status == "invalid"
    assert "authority_record_invalid" in result.reasons


def test_no_rights_does_not_create_send_readiness():
    raw, pin, _document = _bytes_and_pin()
    result = _resolve(raw, pin, rights_authority=None)
    assert result.authority_verified is False
    assert result.real_send_ready is False
    assert result.send_authorization == "not_authorized_for_send"


def test_present_but_blocked_provider_rights_fail_closed():
    raw, pin, _document = _bytes_and_pin()
    rights = SimpleNamespace(
        can_promote=lambda *, as_of: True,
        local_retention=SimpleNamespace(status="authorized"),
        provider_transmission=SimpleNamespace(status="blocked"),
        provider_processing_policy_id="provider-policy-fixture",
        provider_processing_policy_version="7.4",
    )
    result = _resolve(raw, pin, rights_authority=rights)
    assert result.status == "blocked"
    assert "provider_transmission_rights_missing" in result.reasons


def test_blocked_resolution_is_side_effect_free(monkeypatch):
    import builtins
    import socket

    def fail(*_args, **_kwargs):
        raise AssertionError("resolver attempted an external side effect")

    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(socket, "socket", fail)
    raw, _pin, _document = _bytes_and_pin()
    result = _resolve(raw, "not-a-hash")
    assert result.status == "blocked"
    assert "trusted_authority_pin_invalid" in result.reasons


def test_provider_real_send_gate_is_mandatory_and_fail_closed():
    raw, pin, _document = _bytes_and_pin()
    structural = _resolve(raw, pin)
    gate = require_authenticated_provider_authority_for_real_send(
        provider_policy_resolution=structural,
    )
    assert isinstance(gate, ProviderRealSendGate)
    assert gate.status == "BLOCKED"
    assert gate.action == "NONE"
    assert gate.allowed is False
    assert gate.real_send_ready is False
    assert gate.host_authentication_required is True
    assert {
        "source_owned_provider_policy_authority_unauthenticated",
        "rights_authority_missing",
        "current_v29_missing",
        "provider_route_missing",
    } <= set(gate.reasons)


def test_real_send_gate_keeps_local_retention_and_provider_transmission_separate():
    raw, pin, _document = _bytes_and_pin()
    structural = _resolve(raw, pin)
    rights = SimpleNamespace(
        can_promote=lambda *, as_of: True,
        local_retention=SimpleNamespace(status="blocked"),
        provider_transmission=SimpleNamespace(status="blocked"),
    )
    gate = require_authenticated_provider_authority_for_real_send(
        provider_policy_resolution=structural,
        rights_authority=rights,
        current_v29={},
        caller_route=_route(),
        as_of=date(2026, 10, 31),
    )
    assert "local_retention_rights_missing" in gate.reasons
    assert "provider_transmission_rights_missing" in gate.reasons
    assert "current_v29_mismatch" in gate.reasons


def test_resolution_model_cannot_be_caller_promoted_to_verified():
    with pytest.raises(ValueError):
        ProviderPolicyResolution(status="verified", authority_verified=True)

