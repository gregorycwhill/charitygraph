from __future__ import annotations

import builtins
import socket
import urllib.request

from charitygraph.phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
    ProviderConfiguration,
)
from charitygraph.phase5_t4a_provider_contract_identity_probe import (
    ProviderContractBinding,
    SourceOwnedProviderContract,
    probe_provider_contract_identity,
)


PROJECT = "proj_fixture_non_secret"
APPROVAL = "G4-T4A-PROVIDER-PROCESSING-20261029"


def _provider(**changes: object) -> ProviderConfiguration:
    values: dict[str, object] = {
        "provider": "openai",
        "project_id": PROJECT,
        "service": "responses_api",
        "endpoint": "https://api.openai.com/v1/responses",
        "model": "gpt-fixture",
        "delivery_mode": "standard",
        "reasoning_effort": "low",
        "retention_posture": "ordinary",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
    }
    values.update(changes)
    return ProviderConfiguration.model_validate(values)


def _authority(**changes: object) -> SourceOwnedProviderContract:
    values: dict[str, object] = {
        "contract_id": "provider-contract-fixture",
        "contract_version": "2026-10-fixture",
        "provider_policy_id": PROVIDER_PROCESSING_POLICY_ID,
        "provider_policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        "binding": ProviderContractBinding(
            provider="openai",
            project_id=PROJECT,
            service="responses_api",
            endpoint="https://api.openai.com/v1/responses",
            model="gpt-fixture",
        ),
        "authority_locator": "fixture:independent-provider-contract",
        "authority_content_sha256": "a" * 64,
    }
    values.update(changes)
    return SourceOwnedProviderContract.model_validate(values)


def _probe(**changes: object):
    values: dict[str, object] = {
        "provider_metadata": _provider(),
        "metadata_origin": "configured_non_secret",
        "local_policy_id": PROVIDER_PROCESSING_POLICY_ID,
        "local_policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        "source_owned_policy_id": PROVIDER_PROCESSING_POLICY_ID,
        "source_owned_policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        "product_owner_approval_reference": APPROVAL,
        "authoritative_contract": _authority(),
    }
    values.update(changes)
    return probe_provider_contract_identity(**values)


def test_same_inputs_have_stable_content_address_and_replay():
    first = _probe()
    second = _probe()
    assert first == second
    assert first.content_hash == first.computed_hash
    assert first.status == "identity_consistent_not_authorization"
    assert first.reasons == ()


def test_missing_source_owned_contract_and_version_fail_closed():
    diagnostic = _probe(
        source_owned_policy_id=None,
        source_owned_policy_version=None,
        authoritative_contract=None,
    )
    assert diagnostic.status == "blocked"
    assert "source_owned_policy_identity_missing" in diagnostic.reasons
    assert "source_owned_policy_version_missing" in diagnostic.reasons
    assert "authoritative_provider_contract_identity_missing" in diagnostic.reasons
    assert "authoritative_provider_contract_version_missing" in diagnostic.reasons


def test_missing_contract_version_is_named_and_fails_closed():
    raw = _authority().model_dump()
    raw.pop("contract_version")
    diagnostic = _probe(authoritative_contract=raw)
    assert diagnostic.status == "blocked"
    assert "authoritative_provider_contract_version_missing" in diagnostic.reasons


def test_stale_contract_and_missing_authoritative_evidence_fail_closed():
    diagnostic = _probe(authoritative_contract=_authority(status="stale", authority_content_sha256=None))
    assert diagnostic.status == "blocked"
    assert "authoritative_provider_contract_is_stale_or_revoked" in diagnostic.reasons
    assert "authoritative_provider_contract_evidence_missing" in diagnostic.reasons


def test_provider_project_service_model_and_endpoint_mismatches_fail_closed():
    for field, value in {
        "provider": "other-provider",
        "project_id": "proj-other",
        "service": "chat_completions",
        "model": "gpt-other",
        "endpoint": "https://api.example.invalid/v1/responses",
    }.items():
        binding = ProviderContractBinding(
            provider="openai",
            project_id=PROJECT,
            service="responses_api",
            endpoint="https://api.openai.com/v1/responses",
            model="gpt-fixture",
        ).model_copy(update={field: value})
        diagnostic = _probe(authoritative_contract=_authority(binding=binding))
        assert diagnostic.status == "blocked"
        assert f"authoritative_contract_{field}_mismatch" in diagnostic.reasons


def test_policy_identity_and_version_mismatches_fail_closed():
    cases = (
        {"source_owned_policy_id": "different-policy"},
        {"source_owned_policy_version": "9.9.9"},
        {"local_policy_id": "different-policy"},
        {"local_policy_version": "9.9.9"},
        {"authoritative_contract": _authority(provider_policy_id="different-policy")},
        {"authoritative_contract": _authority(provider_policy_version="9.9.9")},
    )
    expected = (
        "source_owned_policy_identity_mismatch",
        "source_owned_policy_version_mismatch",
        "local_policy_identity_mismatch",
        "local_policy_version_mismatch",
        "authoritative_contract_policy_identity_mismatch",
        "authoritative_contract_policy_version_mismatch",
    )
    for changes, reason in zip(cases, expected):
        diagnostic = _probe(**changes)
        assert diagnostic.status == "blocked"
        assert reason in diagnostic.reasons


def test_product_owner_approval_local_policy_and_fixture_metadata_are_distinct():
    diagnostic = _probe(metadata_origin="test_fixture_metadata")
    assert diagnostic.status == "blocked"
    assert diagnostic.product_owner_approval_reference == APPROVAL
    assert diagnostic.local_policy_version == PROVIDER_PROCESSING_POLICY_VERSION
    assert diagnostic.metadata_origin == "test_fixture_metadata"
    assert "test_fixture_metadata_is_not_authority" in diagnostic.reasons


def test_only_non_secret_metadata_is_retained_and_no_side_effect_seam_exists(monkeypatch):
    calls: list[str] = []

    def forbidden(*args, **kwargs):
        calls.append("side-effect")
        raise AssertionError("provider, filesystem, or network side effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    diagnostic = _probe(authoritative_contract=None)
    dumped = diagnostic.model_dump()
    assert diagnostic.observed_provider_binding_hash is not None
    assert "credential" not in dumped
    assert "prompt" not in dumped
    assert "response" not in dumped
    assert "provider_request" not in dumped
    assert "cost" not in dumped
    assert "filesystem" not in dumped
    assert "network" not in dumped
    assert calls == []
