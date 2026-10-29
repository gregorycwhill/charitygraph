import ast
import hashlib
import json
from pathlib import Path

import pytest

from charitygraph.contracts.canonical import canonical_json_bytes
from charitygraph.phase5_t4a_provider_contract_registry import (
    PROVIDER_CONTRACT_REGISTRY_SCHEMA,
    ProviderContractRegistryEntry,
    resolve_source_owned_provider_contract_registry,
)


POLICY_ID = "source-owned-policy-fixture"
POLICY_VERSION = "7.4"


def _caller(**changes):
    value = {
        "provider": "openai",
        "project_id": "project-fixture",
        "service": "responses_api",
        "endpoint": "https://provider.invalid/v1/responses",
        "model": "model-fixture",
        "delivery_mode": "standard",
        "reasoning_effort": "low",
        "retention_posture": "ordinary",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
    }
    value.update(changes)
    return value


def _entry(**changes):
    value = {
        "schema_id": PROVIDER_CONTRACT_REGISTRY_SCHEMA,
        "contract_id": "contract-fixture",
        "contract_version": "3.2",
        "provider_policy_id": POLICY_ID,
        "provider_policy_version": POLICY_VERSION,
        "authority_locator": "authority://fixture/provider-contract",
        "authority_content_sha256": "a" * 64,
        "status": "current",
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
    raw = ProviderContractRegistryEntry.model_validate(
        _entry() if value is None else value
    ).canonical_bytes
    return raw, hashlib.sha256(raw).hexdigest()


def _resolve(raw, pin, **kwargs):
    kwargs.setdefault("expected_contract_id", "contract-fixture")
    kwargs.setdefault("expected_contract_version", "3.2")
    return resolve_source_owned_provider_contract_registry(
        authority_bytes=raw,
        trusted_authority_sha256=pin,
        caller_route=_caller(),
        source_owned_policy_id=POLICY_ID,
        source_owned_policy_version=POLICY_VERSION,
        **kwargs,
    )


def test_canonical_hash_replay_and_verified_non_send_state():
    raw, pin = _bytes_and_pin()
    first = _resolve(raw, pin)
    second = _resolve(raw, pin)

    assert first.status == "IDENTITY_EVIDENCE_VERIFIED_NON_SEND"
    assert first.reasons == ()
    assert first.request_ticket is None
    assert first.send_authorization == "not_authorized_for_send"
    assert first.content_hash == second.content_hash
    assert first.registry_entry_sha256 == second.registry_entry_sha256


def test_independent_pin_rejects_forged_self_attested_hash():
    raw, _ = _bytes_and_pin()
    forged_self_hash = json.loads(raw)
    forged_self_hash["authority_content_sha256"] = hashlib.sha256(raw).hexdigest()
    forged_raw = canonical_json_bytes(forged_self_hash)

    result = _resolve(forged_raw, forged_self_hash["authority_content_sha256"])

    assert result.status == "NOT_VERIFIED"
    assert "trusted_authority_pin_mismatch" in result.reasons


@pytest.mark.parametrize(
    ("expected_contract_id", "expected_contract_version", "expected_reason"),
    [
        (None, "3.2", "expected_contract_id_missing"),
        ("contract-fixture", None, "expected_contract_version_missing"),
        ("different-contract", "3.2", "expected_contract_id_mismatch"),
        ("contract-fixture", "different-version", "expected_contract_version_mismatch"),
    ],
)
def test_expected_contract_identity_and_version_are_required_and_exact(
    expected_contract_id, expected_contract_version, expected_reason
):
    raw, pin = _bytes_and_pin()
    result = _resolve(
        raw,
        pin,
        expected_contract_id=expected_contract_id,
        expected_contract_version=expected_contract_version,
    )

    assert result.status == "NOT_VERIFIED"
    assert expected_reason in result.reasons
    assert result.expected_contract_id == expected_contract_id
    assert result.expected_contract_version == expected_contract_version


@pytest.mark.parametrize(
    "schema_id",
    [
        "charitygraph.provider-contract-registry/0",
        "unknown.registry-schema/1",
    ],
)
def test_registry_schema_must_be_the_exact_current_literal(schema_id):
    raw = canonical_json_bytes({**_entry(), "schema_id": schema_id})
    result = _resolve(raw, hashlib.sha256(raw).hexdigest())

    assert result.status == "NOT_VERIFIED"
    assert "authority_registry_schema_invalid" in result.reasons


@pytest.mark.parametrize(
    ("authority", "expected"),
    [
        (None, "source_owned_contract_authority_missing"),
        ("stale", "source_owned_contract_stale"),
        ("revoked", "source_owned_contract_revoked"),
        ("invalid", "authority_bytes_invalid"),
    ],
)
def test_missing_stale_revoked_and_invalid_entries_fail_closed(authority, expected):
    if authority is None:
        result = resolve_source_owned_provider_contract_registry(
            caller_route=_caller(),
            source_owned_policy_id=POLICY_ID,
            source_owned_policy_version=POLICY_VERSION,
        )
    elif authority == "invalid":
        result = _resolve(b"not-json", hashlib.sha256(b"not-json").hexdigest())
    else:
        raw, pin = _bytes_and_pin(_entry(status=authority))
        result = _resolve(raw, pin)

    assert result.status in {"UNBOUND", "NOT_VERIFIED"}
    assert expected in result.reasons


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("provider_policy_id", "provider_policy_id_mismatch"),
        ("provider_policy_version", "provider_policy_version_mismatch"),
    ],
)
def test_provider_policy_identity_and_version_mismatch(field, expected):
    raw, pin = _bytes_and_pin(_entry(**{field: "different"}))
    result = _resolve(raw, pin)
    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


@pytest.mark.parametrize("field", ["provider", "project_id", "service", "endpoint", "model"])
def test_each_route_attribute_must_match_exactly(field):
    raw, pin = _bytes_and_pin()
    result = resolve_source_owned_provider_contract_registry(
        authority_bytes=raw,
        trusted_authority_sha256=pin,
        caller_route=_caller(**{field: "different"}),
        source_owned_policy_id=POLICY_ID,
        source_owned_policy_version=POLICY_VERSION,
    )
    assert result.status == "NOT_VERIFIED"
    assert f"caller_{field}_mismatch" in result.reasons


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"retention_posture": "short"}, "retention_posture_mismatch"),
        ({"provider_data_sharing_opt_in": True}, "no_sharing_posture_mismatch"),
    ],
)
def test_retention_and_no_sharing_drift_is_blocked(change, expected):
    raw, pin = _bytes_and_pin()
    result = resolve_source_owned_provider_contract_registry(
        authority_bytes=raw,
        trusted_authority_sha256=pin,
        caller_route=_caller(**change),
        source_owned_policy_id=POLICY_ID,
        source_owned_policy_version=POLICY_VERSION,
    )
    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


def test_pure_resolver_has_no_network_provider_cost_or_filesystem_side_effects(monkeypatch):
    raw, pin = _bytes_and_pin()
    calls = []

    class Forbidden:
        def __call__(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("side effect attempted")

    monkeypatch.setattr("socket.socket", Forbidden())
    monkeypatch.setattr("builtins.open", Forbidden())
    result = _resolve(raw, pin)

    assert result.status == "IDENTITY_EVIDENCE_VERIFIED_NON_SEND"
    assert calls == []
    ast.parse(Path("src/charitygraph/phase5_t4a_provider_contract_registry.py").read_text(encoding="utf-8"))
