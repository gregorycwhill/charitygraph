from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from charitygraph.phase5_provider_processing_policy import (
    DEFAULT_REVIEW_RULE,
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
    PolicyEvidence,
    ProviderConfiguration,
    ProviderProcessingPolicy,
    SourceOperationExclusion,
    issue_provider_processing_decision,
    pre_send_revalidate,
    revalidate_provider_processing,
)
from charitygraph.runtime.rights_governance_record import (
    RightsAxis,
    RightsGovernanceRecord,
    RightsGovernanceStore,
)
from charitygraph.runtime.rights_governance_projection import RightsGovernanceProjection


AS_OF = date(2026, 10, 29)
RECORDED_AT = datetime(2026, 10, 29, tzinfo=timezone.utc)
PROJECT = "proj_vnAuU8uxocL0Rosg3SulgmRI"


def _provider(**changes: object) -> ProviderConfiguration:
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


def _policy(provider: ProviderConfiguration | None = None, **changes: object) -> ProviderProcessingPolicy:
    values: dict[str, object] = {
        "policy_id": PROVIDER_PROCESSING_POLICY_ID,
        "policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        "authority_basis": "product_owner_dated_explicit_approval",
        "authority_reference": "G4-T4A-PROVIDER-PROCESSING-20261029",
        "effective_from": AS_OF,
        "effective_evidence": (PolicyEvidence(locator="local:product-owner-approval/2026-10-29"),),
        "provider": provider or _provider(),
        "allowed_operations": ("semantic_analysis", "structured_extraction"),
        "review_rule": DEFAULT_REVIEW_RULE,
    }
    values.update(changes)
    return ProviderProcessingPolicy.model_validate(values).sealed()


def _record(**changes: object) -> RightsGovernanceRecord:
    values: dict[str, object] = {
        "decision_id": "rights:g4-t4a-fixture",
        "source_artifact_id": "srcblob:" + "a" * 32,
        "source_record_id": "srcrec:" + "b" * 32,
        "subject_id": "subject:" + "c" * 32,
        "source_origin_url": "https://example.invalid/acnc-register-row",
        "source_role": "register_identity",
        "acquisition_lineage_ids": ("acq:" + "d" * 32,),
        "representation_artifact_id": "artifact:" + "e" * 32,
        "representation_sha256": "1" * 64,
        "rights_basis": "explicit_open_license",
        "rights_policy_id": "CC_BY_4_0_V1",
        "rights_policy_version": "1.0.0",
        "purpose": "semantic_analysis",
        "scope": "scope:" + "f" * 32,
        "evidence_locator": "srcrec:" + "b" * 32 + "#acnc-field",
        "evidence_sha256": "2" * 64,
        "assessed_on": AS_OF,
        "local_retention": RightsAxis(
            status="authorized",
            policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
            policy_version="1.0.0",
            decision_id="rights:g4-t4a-fixture:retention",
        ),
        "provider_transmission": RightsAxis(status="blocked"),
        "public_redistribution": RightsAxis(status="blocked"),
        "status": "authorized",
        "review_status": "current",
        "actor_kind": "human",
        "actor_id": "actor:g4-t4a-fixture",
        "recorded_at": RECORDED_AT,
        "representation_class": "structured_factual",
        "factual_representation_only": True,
        "one_source_native_entity_record": True,
        "lawful_access_confirmed": True,
        "circumvention_used": False,
        "retention_lifecycle_status": "active_until_review",
        "retention_review_due_on": date(2027, 10, 29),
    }
    values.update(changes)
    values.pop("record_id", None)
    return RightsGovernanceRecord.model_validate(values)


def _decision(record: RightsGovernanceRecord, policy: ProviderProcessingPolicy, **kwargs: object):
    values: dict[str, object] = {
        "reference_id": "g4-t4a-ref-1",
        "source_family": "acnc_register",
        "operation": "semantic_analysis",
        "as_of": AS_OF,
    }
    values.update(kwargs)
    return issue_provider_processing_decision(
        record,
        policy,
        **values,
    )


def _assert_denied(decision, record, policy, provider=None, **kwargs: object) -> None:
    result = revalidate_provider_processing(
        decision,
        record,
        policy,
        provider or policy.provider,
        source_family="acnc_register",
        operation="semantic_analysis",
        as_of=AS_OF,
        **kwargs,
    )
    assert result.eligible is False
    assert result.reasons


def test_exact_policy_and_representation_binding_is_positive_for_acnc_rows(tmp_path):
    record = _record()
    policy = _policy()
    decision = _decision(record, policy)

    assert decision.status == "eligible"
    assert decision.provider_processing_policy_id == PROVIDER_PROCESSING_POLICY_ID
    assert decision.provider_processing_policy_version == "1.0.0"
    assert decision.rights_record_id == record.content_hash
    assert decision.representation_artifact_id == record.representation_artifact_id
    assert decision.representation_sha256 == record.representation_sha256
    assert decision.provider_binding_hash == policy.provider.content_hash
    assert decision.content_hash == decision.computed_hash
    result = revalidate_provider_processing(
        decision, record, policy, policy.provider,
        source_family="acnc_register", operation="semantic_analysis", as_of=AS_OF,
    )
    assert result == result.__class__(eligible=True)

    store = RightsGovernanceStore(tmp_path / "rights")
    store.put_record(record)
    projection = RightsGovernanceProjection(tmp_path / "projection.sqlite3").open(initialize=True)
    try:
        projection.rebuild_from_store(store, as_of=AS_OF)
        send_check = pre_send_revalidate(
            decision,
            policy=policy,
            provider_configuration=policy.provider,
            store=store,
            projection=projection,
            as_of=AS_OF,
        )
        assert send_check == result
    finally:
        projection.close()


@pytest.mark.parametrize(
    "changed_policy",
    [
        {"provider_processing_policy_id": "unknown-policy"},
        {"provider_processing_policy_version": ""},
    ],
)
def test_unknown_or_missing_policy_identity_is_denied_without_work(changed_policy):
    record = _record()
    policy = _policy()
    decision = _decision(record, policy).model_copy(update=changed_policy)
    _assert_denied(decision, record, policy)


@pytest.mark.parametrize(
    "changed_provider",
    [
        {"provider": "other-provider"},
        {"project_id": "proj-different"},
        {"service": "chat_completions"},
        {"model": "gpt-different"},
    ],
)
def test_provider_project_model_and_service_mismatch_is_denied(changed_provider):
    record = _record()
    policy = _policy()
    decision = _decision(record, policy)
    provider = policy.provider.model_copy(update=changed_provider)
    _assert_denied(decision, record, policy, provider=provider)


def test_stale_or_revoked_rights_are_denied():
    record = _record(expires_on=date(2026, 10, 28))
    policy = _policy()
    decision = _decision(record, policy, as_of=date(2026, 10, 28))
    _assert_denied(decision, record, policy)

    revoked = _record(review_status="under_review")
    revoked_decision = _decision(revoked, policy)
    _assert_denied(revoked_decision, revoked, policy)


def test_changed_source_or_representation_is_denied():
    record = _record()
    policy = _policy()
    decision = _decision(record, policy)
    changed_source = _record(source_artifact_id="srcblob:" + "9" * 32)
    changed_representation = _record(representation_sha256="3" * 64)
    _assert_denied(decision, changed_source, policy)
    _assert_denied(decision, changed_representation, policy)


def test_explicit_source_exclusion_is_exact_and_denied():
    record = _record()
    policy = _policy()
    exclusion = SourceOperationExclusion(
        operation="semantic_analysis",
        wording="ACNC row excluded from this operation by the source authority",
        evidence_locator="srcrec:" + "b" * 32 + "#restriction",
    )
    decision = _decision(record, policy, exclusion=exclusion)
    assert decision.status == "denied"
    assert decision.exclusion == exclusion
    _assert_denied(decision, record, policy)


def test_denied_local_axis_and_public_redistribution_confusion_are_denied():
    policy = _policy()
    denied_local = _record(local_retention=RightsAxis(status="blocked"))
    _assert_denied(_decision(denied_local, policy), denied_local, policy)

    public_record = _record(public_redistribution=RightsAxis(
        status="authorized", policy_id="CC_BY_4_0_V1", policy_version="1.0.0",
        decision_id="rights:g4-t4a-fixture:public",
    ))
    _assert_denied(_decision(public_record, policy), public_record, policy)


def test_policy_or_rights_change_fails_closed_at_pre_send_revalidation():
    record = _record()
    policy = _policy()
    decision = _decision(record, policy)

    changed_policy = _policy(effective_from=date(2026, 10, 30))
    _assert_denied(decision, record, changed_policy)

    changed_rights = _record(review_status="under_review")
    _assert_denied(decision, changed_rights, policy)


def test_policy_contract_requires_provenance_and_exact_source_universe():
    with pytest.raises(ValueError):
        _policy(effective_evidence=())
    with pytest.raises(ValueError):
        _policy(source_families=("acnc_register",))
