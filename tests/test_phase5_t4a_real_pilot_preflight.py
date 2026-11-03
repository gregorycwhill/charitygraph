from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from charitygraph.phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
    PolicyEvidence,
    ProviderConfiguration,
    ProviderProcessingPolicy,
)
from charitygraph.phase5_t4a_real_pilot_preflight import (
    ProviderContractBinding,
    build_real_pilot_preflight,
)
from charitygraph.phase5_governed_source_binding import SELECTED_ROWS


ARCHIVE_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\objects")
EXECUTION_CONTEXT = {
    "bridge_fence": "v50",
    "branch": "gate3-cg406-remediation",
    "head": "3c5cd6280e9011400399dce0153fd1dbe8180d57",
}
PROJECT = "proj_test_t4a_no_send"


def _configuration(**changes: object) -> ProviderConfiguration:
    values: dict[str, object] = {
        "provider": "openai",
        "project_id": PROJECT,
        "service": "responses_api",
        "endpoint": "https://api.openai.com/v1/responses",
        "model": "gpt-5.6-luna",
        "delivery_mode": "standard",
        "reasoning_effort": "low",
        "retention_posture": "ordinary",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
    }
    values.update(changes)
    return ProviderConfiguration.model_validate(values)


def _policy(configuration: ProviderConfiguration | None = None, **changes: object) -> ProviderProcessingPolicy:
    values: dict[str, object] = {
        "policy_id": PROVIDER_PROCESSING_POLICY_ID,
        "policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        "authority_basis": "product_owner_dated_explicit_approval",
        "authority_reference": "G4-T4A-PROVIDER-PROCESSING-20261029",
        "effective_from": date(2026, 10, 29),
        "effective_evidence": (PolicyEvidence(locator="local:test/t4a-policy"),),
        "provider": configuration or _configuration(),
        "allowed_operations": ("semantic_analysis", "structured_extraction"),
    }
    values.update(changes)
    return ProviderProcessingPolicy.model_validate(values).sealed()


def _binding(configuration: ProviderConfiguration | None = None) -> ProviderContractBinding:
    return ProviderContractBinding("test-openai-contract", "1.0.0", configuration or _configuration())


def _build(tmp_path: Path, **kwargs):
    policy = kwargs.pop("provider_policy", _policy())
    contract = kwargs.pop("provider_contract", _binding())
    return build_real_pilot_preflight(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path / "work",
        execution_context=EXECUTION_CONTEXT,
        provider_policy=policy,
        provider_contract=contract,
        **kwargs,
    )


def test_reproducible_no_send_packet_and_cost_hashes(tmp_path):
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")

    assert first.packet_sha256 == second.packet_sha256
    assert first.document["routes"]["standard"]["plan_sha256"] == second.document["routes"]["standard"]["plan_sha256"]
    assert first.document["routes"]["batch"]["plan_sha256"] == second.document["routes"]["batch"]["plan_sha256"]
    assert first.document["routes"]["standard"]["forecast"]["upper_bound_aud"] == second.document["routes"]["standard"]["forecast"]["upper_bound_aud"]
    assert first.document["routes"]["batch"]["forecast"]["upper_bound_aud"] == second.document["routes"]["batch"]["forecast"]["upper_bound_aud"]
    assert len(first.document["tasks"]) == 10
    assert len({item["subject_id"] for item in first.document["tasks"]}) == 5
    assert len(first.document["t3_selected_manifest"]) == 4
    assert first.document["cohort"]["source_row_count"] == 10
    assert first.provider_calls == first.reservations == 0
    assert first.send_ready is False


def test_route_contract_and_no_raw_material_are_sanitized(tmp_path):
    packet = _build(tmp_path)
    text = str(packet.document)
    assert packet.provider_binding_ready is True
    assert packet.document["semantic_contract"]["task_profile"] == "direct_service_semantics"
    assert packet.document["semantic_contract"]["prompt_sha256"]
    assert packet.document["routes"]["standard"]["request_items"]
    assert packet.document["routes"]["batch"]["delivery_jobs"]
    assert "'prompt_template':" not in text
    assert "source_body" not in text
    assert "raw_bytes" not in text
    assert packet.document["execution_policy"]["ambiguity_rule"] == "stop_and_reconcile; never_automatic_resend"


def test_wrong_provider_project_and_policy_version_are_denied_without_work(tmp_path):
    wrong_project = _build(tmp_path / "project", provider_contract=_binding(_configuration(project_id="proj_wrong")))
    assert wrong_project.provider_binding_ready is False
    assert wrong_project.document["execution_policy"]["reservations"] == 0
    assert wrong_project.document["execution_policy"]["provider_calls"] == 0

    wrong_policy = build_real_pilot_preflight(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path / "policy",
        execution_context=EXECUTION_CONTEXT,
        provider_policy=_policy().model_copy(update={"policy_version": "9.9.9"}),
        provider_contract=_binding(),
    )
    assert wrong_policy.provider_binding_ready is False
    assert any("policy" in reason for reason in wrong_policy.document["authority"]["reasons"])
    assert wrong_policy.reservations == 0


def test_revoked_policy_is_denied_without_reservation_or_send(tmp_path):
    packet = build_real_pilot_preflight(
        source_archive_root=ARCHIVE_ROOT,
        work_root=tmp_path,
        execution_context=EXECUTION_CONTEXT,
        provider_policy=_policy(status="revoked"),
        provider_contract=_binding(),
    )
    assert packet.provider_binding_ready is False
    assert packet.provider_calls == packet.reservations == 0


def test_missing_cap_fx_or_pricing_fails_closed_without_reservation(tmp_path):
    missing_cap = _build(tmp_path / "cap", program_cap_aud=None)
    missing_fx = _build(tmp_path / "fx", aud_per_usd=None)
    missing_pricing = _build(tmp_path / "pricing", model="model-not-priced")
    for packet in (missing_cap, missing_fx, missing_pricing):
        assert packet.document["budget"]["status"] == "blocked"
        assert packet.document["execution_policy"]["reservations"] == 0
        assert packet.document["execution_policy"]["provider_calls"] == 0


def test_all_ten_source_identities_are_retained_and_tampered_source_blocks(tmp_path):
    packet = _build(tmp_path / "positive")
    identities = {(row["source_record_ids"][0], row["subject_id"], row["source_family"]) for row in packet.document["tasks"]}
    assert len(identities) == 10
    assert {row.source_record_id for row in SELECTED_ROWS} == {item[0] for item in identities}

    archive = tmp_path / "archive"
    for row in SELECTED_ROWS:
        source = ARCHIVE_ROOT / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target = archive / "objects" / "sha256" / row.source_sha256[:2] / row.source_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"tampered" if row.ordinal == 2 else source.read_bytes())
    blocked = build_real_pilot_preflight(
        source_archive_root=archive,
        work_root=tmp_path / "tampered-work",
        execution_context=EXECUTION_CONTEXT,
        provider_policy=_policy(),
        provider_contract=_binding(),
    )
    assert blocked.document["blocked_reason"] is not None
    assert blocked.document["execution_policy"]["provider_calls"] == 0
    assert blocked.document["execution_policy"]["reservations"] == 0

