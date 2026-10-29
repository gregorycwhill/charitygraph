"""Versioned, provider-free authority for private provider eligibility.

The v29 ``RightsGovernanceRecord`` remains the authority for local retention,
source/representation binding, and the independent public-redistribution axis.
This module adds the separate provider-processing decision required before a
hypothetical request.  It contains identifiers, hashes, configuration
metadata, and exact exclusion evidence only; it never contains payload bytes,
prompts, credentials, tokens, or provider responses.

The provider policy identity is deliberately the existing source-owned
OpenAI policy identity.  This module does not register, replace, or broaden
that identity.  A configured provider binding must be supplied by the caller
and is compared byte-for-byte through its content hash; there is no guessed
default project, service, or model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, Literal, Mapping

from pydantic import field_validator, model_validator

from .contracts.canonical import canonical_json_bytes
from .contracts.common import Sha256, StrictModel, require_nonblank
from .runtime.rights_governance_record import (
    OPENAI_PROVIDER_POLICY_ID,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    RightsStorageError,
)
from .runtime.rights_governance_projection import (
    RightsGovernanceProjection,
    RightsProjectionError,
)


PROVIDER_PROCESSING_POLICY_ID = OPENAI_PROVIDER_POLICY_ID
PROVIDER_PROCESSING_POLICY_VERSION = "1.0.0"
PROVIDER_PROCESSING_POLICY_SCHEMA = "charitygraph.provider-processing-policy/1"
PROVIDER_PROCESSING_DECISION_SCHEMA = "charitygraph.provider-processing-decision/1"
SOURCE_UNIVERSE_V1 = (
    "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
    "annual_report", "wikipedia_wikimedia", "pfra",
)
T4A_PILOT_SOURCE_FAMILIES = ("acnc_register", "acnc_ais_bundle")
DEFAULT_REVIEW_RULE = "revalidate_policy_rights_representation_and_provider_binding_immediately_before_send"


class ProviderProcessingPolicyError(ValueError):
    """A provider policy or eligibility record is not safe to use."""


class ProviderConfiguration(StrictModel):
    """Non-secret identity of the configured provider route."""

    provider: str
    project_id: str
    service: str
    endpoint: str
    model: str
    delivery_mode: str
    reasoning_effort: str
    retention_posture: Literal["ordinary"]
    provider_no_training_default: bool
    provider_data_sharing_opt_in: bool

    @field_validator("provider", "project_id", "service", "endpoint", "model", "delivery_mode", "reasoning_effort")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _safe_posture(self) -> "ProviderConfiguration":
        if self.provider.casefold() != "openai":
            raise ProviderProcessingPolicyError("provider configuration is not the configured OpenAI provider")
        if self.provider_no_training_default is not True:
            raise ProviderProcessingPolicyError("provider configuration lacks the ordinary no-training default")
        if self.provider_data_sharing_opt_in is not False:
            raise ProviderProcessingPolicyError("provider data-sharing opt-in must be disabled")
        return self

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self)).hexdigest()


class PolicyEvidence(StrictModel):
    """Locator-only provenance for the effective policy authority."""

    locator: str
    content_sha256: Sha256 | None = None

    @field_validator("locator")
    @classmethod
    def _locator(cls, value: str) -> str:
        return require_nonblank(value, "policy evidence locator")


class ProviderProcessingPolicy(StrictModel):
    """The exact policy and configured route accepted by a decision."""

    schema_id: str = PROVIDER_PROCESSING_POLICY_SCHEMA
    policy_id: str
    policy_version: str
    authority_basis: Literal["product_owner_dated_explicit_approval"]
    authority_reference: str
    effective_from: date
    effective_evidence: tuple[PolicyEvidence, ...]
    provider: ProviderConfiguration
    allowed_operations: tuple[str, ...]
    source_families: tuple[str, ...] = SOURCE_UNIVERSE_V1
    pilot_source_families: tuple[str, ...] = T4A_PILOT_SOURCE_FAMILIES
    public_redistribution_allowed: Literal[False] = False
    review_rule: Literal[DEFAULT_REVIEW_RULE] = DEFAULT_REVIEW_RULE
    status: Literal["current", "revoked"] = "current"
    content_hash: Sha256 | None = None

    @field_validator("policy_id", "policy_version", "authority_reference")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("allowed_operations", "source_families", "pilot_source_families")
    @classmethod
    def _unique_text(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ProviderProcessingPolicyError("policy lists must be non-empty and nonblank")
        if len(set(value)) != len(value):
            raise ProviderProcessingPolicyError("policy lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _authority_shape(self) -> "ProviderProcessingPolicy":
        if self.policy_id != PROVIDER_PROCESSING_POLICY_ID:
            raise ProviderProcessingPolicyError("provider policy ID is not the source-owned OpenAI policy identity")
        if self.policy_version != PROVIDER_PROCESSING_POLICY_VERSION:
            raise ProviderProcessingPolicyError("provider policy version is not the exact supported version")
        if tuple(self.source_families) != SOURCE_UNIVERSE_V1:
            raise ProviderProcessingPolicyError("provider policy source universe is not exactly Source Universe v1")
        if tuple(self.pilot_source_families) != T4A_PILOT_SOURCE_FAMILIES:
            raise ProviderProcessingPolicyError("T4A pilot source families are not exactly ACNC register and AIS")
        if not set(self.pilot_source_families).issubset(self.source_families):
            raise ProviderProcessingPolicyError("pilot source family is outside Source Universe v1")
        if not self.effective_evidence:
            raise ProviderProcessingPolicyError("effective provider policy requires provenance")
        return self

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self, exclude={"content_hash"})

    @property
    def computed_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def sealed(self) -> "ProviderProcessingPolicy":
        expected = self.computed_hash
        if self.content_hash is not None and self.content_hash != expected:
            raise ProviderProcessingPolicyError("provider policy content hash does not match canonical bytes")
        return self.model_copy(update={"content_hash": expected})


class SourceOperationExclusion(StrictModel):
    """An explicit operation-specific denial; uncertainty is not an exclusion."""

    operation: str
    wording: str
    evidence_locator: str
    evidence_sha256: Sha256 | None = None

    @field_validator("operation", "wording", "evidence_locator")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)


class ProviderProcessingDecision(StrictModel):
    """Content-addressed, exact-representation-bound provider decision."""

    schema_id: str = PROVIDER_PROCESSING_DECISION_SCHEMA
    decision_id: str
    reference_id: str
    rights_record_id: Sha256
    subject_id: str
    scope_id: str
    source_family: str
    source_artifact_id: str
    source_record_id: str
    representation_artifact_id: str
    representation_sha256: Sha256
    rights_policy_id: str
    rights_policy_version: str
    provider_processing_policy_id: str
    provider_processing_policy_version: str
    policy_content_hash: Sha256
    provider_binding_hash: Sha256
    operation: str
    status: Literal["eligible", "denied"]
    decision_basis: str
    exclusion: SourceOperationExclusion | None = None
    denial_reason: str | None = None
    content_hash: Sha256 | None = None

    @field_validator(
        "decision_id", "reference_id", "subject_id", "scope_id", "source_family",
        "source_artifact_id", "source_record_id", "representation_artifact_id",
        "rights_policy_id", "rights_policy_version", "provider_processing_policy_id",
        "provider_processing_policy_version", "operation", "decision_basis",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("denial_reason")
    @classmethod
    def _optional_reason(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _status_fields(self) -> "ProviderProcessingDecision":
        if self.status == "eligible" and (self.exclusion is not None or self.denial_reason is not None):
            raise ProviderProcessingPolicyError("eligible provider decision cannot carry a denial")
        if self.status == "denied" and not self.denial_reason:
            raise ProviderProcessingPolicyError("denied provider decision requires a reason")
        if self.exclusion is not None and self.exclusion.operation != self.operation:
            raise ProviderProcessingPolicyError("source exclusion must name the denied operation")
        return self

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self, exclude={"content_hash"})

    @property
    def computed_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def sealed(self) -> "ProviderProcessingDecision":
        expected = self.computed_hash
        if self.content_hash is not None and self.content_hash != expected:
            raise ProviderProcessingPolicyError("provider decision content hash does not match canonical bytes")
        return self.model_copy(update={"content_hash": expected})


@dataclass(frozen=True)
class ProviderProcessingValidation:
    eligible: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderProcessingPreflight:
    tasks: tuple[dict[str, Any], ...]
    diagnostics: tuple[Any, ...]
    decisions: tuple[ProviderProcessingDecision, ...] = ()

    @property
    def accepted_count(self) -> int:
        return len(self.tasks)

    @property
    def factory_plan(self) -> Any:
        from .phase5_factory import FactoryPlan
        return FactoryPlan.from_manifest(list(self.tasks))


def issue_provider_processing_decision(
    rights_record: RightsGovernanceRecord,
    policy: ProviderProcessingPolicy,
    *,
    reference_id: str,
    source_family: str,
    operation: str,
    exclusion: SourceOperationExclusion | None = None,
    as_of: date | None = None,
) -> ProviderProcessingDecision:
    """Issue a decision from existing rights authority without changing it."""

    policy = policy.sealed()
    if rights_record.representation_artifact_id is None:
        raise ProviderProcessingPolicyError("provider decision requires an exact representation artifact")
    reasons = _eligibility_reasons(
        rights_record, policy, policy.provider, source_family=source_family,
        operation=operation, exclusion=exclusion, as_of=as_of,
    )
    status: Literal["eligible", "denied"] = "eligible" if not reasons else "denied"
    denial_reason = None if not reasons else "; ".join(reasons)
    if exclusion is not None and exclusion.operation == operation and not reasons:
        status = "denied"
        denial_reason = "explicit source exclusion denies the requested operation"
    material = {
        "reference_id": reference_id,
        "rights_record_id": rights_record.content_hash,
        "source_family": source_family,
        "operation": operation,
        "provider_policy": policy.computed_hash,
        "provider_binding": policy.provider.content_hash,
    }
    decision_id = "provider-decision:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()[:32]
    return ProviderProcessingDecision(
        decision_id=decision_id,
        reference_id=reference_id,
        rights_record_id=rights_record.content_hash,
        subject_id=rights_record.subject_id,
        scope_id=rights_record.scope,
        source_family=source_family,
        source_artifact_id=rights_record.source_artifact_id,
        source_record_id=rights_record.source_record_id,
        representation_artifact_id=rights_record.representation_artifact_id,
        representation_sha256=rights_record.representation_sha256,
        rights_policy_id=rights_record.rights_policy_id,
        rights_policy_version=rights_record.rights_policy_version,
        provider_processing_policy_id=policy.policy_id,
        provider_processing_policy_version=policy.policy_version,
        policy_content_hash=policy.computed_hash,
        provider_binding_hash=policy.provider.content_hash,
        operation=operation,
        status=status,
        decision_basis="product_owner_dated_explicit_approval_for_private_processing; not a source licence or public-redistribution permission",
        exclusion=exclusion,
        denial_reason=denial_reason,
    ).sealed()


def _eligibility_reasons(
    rights_record: RightsGovernanceRecord,
    policy: ProviderProcessingPolicy,
    provider: ProviderConfiguration,
    *,
    source_family: str,
    operation: str,
    exclusion: SourceOperationExclusion | None,
    as_of: date | None = None,
) -> list[str]:
    reasons: list[str] = []
    if policy.status != "current":
        reasons.append("provider processing policy is not current")
    if provider != policy.provider:
        reasons.append("configured provider/project/model/service does not match policy")
    if source_family not in policy.source_families:
        reasons.append("source family is outside Source Universe v1")
    elif source_family not in policy.pilot_source_families:
        reasons.append("source family is outside the bounded T4A pilot")
    if operation not in policy.allowed_operations:
        reasons.append("operation is not explicitly allowlisted by provider policy")
    if rights_record.status != "authorized" or rights_record.review_status != "current":
        reasons.append("rights record is not current and authorized")
    if as_of is not None and not rights_record.can_promote(as_of=as_of):
        reasons.append("rights record is stale, expired, revoked, or superseded at the processing date")
    if not rights_record.local_retention_allowed:
        reasons.append("local/private retention axis is not authorized")
    if rights_record.public_redistribution.status == "authorized":
        reasons.append("public redistribution authorization cannot be used as provider-processing authority")
    if rights_record.explicit_prohibition_found:
        reasons.append("rights record carries an explicit prohibition")
    if exclusion is not None and exclusion.operation == operation:
        reasons.append("explicit source exclusion denies the requested operation")
    if rights_record.representation_artifact_id is None:
        reasons.append("exact representation artifact is missing")
    return reasons


def revalidate_provider_processing(
    decision: ProviderProcessingDecision,
    rights_record: RightsGovernanceRecord,
    policy: ProviderProcessingPolicy,
    provider: ProviderConfiguration | None,
    *,
    source_family: str,
    operation: str,
    retained_bytes: Callable[[str], bytes] | None = None,
    as_of: date | None = None,
) -> ProviderProcessingValidation:
    """Revalidate all mutable inputs immediately before a hypothetical send."""

    reasons: list[str] = []
    try:
        policy = policy.sealed()
        decision = decision.sealed()
    except (ProviderProcessingPolicyError, ValueError) as exc:
        return ProviderProcessingValidation(False, (str(exc),))
    if provider is None:
        reasons.append("configured provider identity/project/service/model is unavailable")
    else:
        reasons.extend(_eligibility_reasons(
            rights_record, policy, provider,
            source_family=source_family, operation=operation, exclusion=decision.exclusion,
            as_of=as_of,
        ))
    if decision.status != "eligible":
        reasons.append(decision.denial_reason or "provider decision is denied")
    if decision.rights_record_id != rights_record.content_hash:
        reasons.append("rights record content address changed")
    if decision.subject_id != rights_record.subject_id or decision.scope_id != rights_record.scope:
        reasons.append("subject or scope binding changed")
    if decision.source_artifact_id != rights_record.source_artifact_id or decision.source_record_id != rights_record.source_record_id:
        reasons.append("source binding changed")
    if decision.representation_artifact_id != rights_record.representation_artifact_id or decision.representation_sha256 != rights_record.representation_sha256:
        reasons.append("representation binding or hash changed")
    if decision.source_family != source_family or decision.operation != operation:
        reasons.append("source family or operation changed")
    if decision.provider_processing_policy_id != policy.policy_id or decision.provider_processing_policy_version != policy.policy_version:
        reasons.append("provider policy identity or version changed")
    if decision.policy_content_hash != policy.computed_hash:
        reasons.append("authoritative provider policy content changed")
    if provider is not None and decision.provider_binding_hash != provider.content_hash:
        reasons.append("configured provider binding changed")
    if retained_bytes is not None and rights_record.representation_artifact_id is not None:
        try:
            actual = hashlib.sha256(retained_bytes(rights_record.representation_artifact_id)).hexdigest()
        except (FileNotFoundError, OSError, ValueError):
            reasons.append("exact representation bytes are unavailable")
        else:
            if actual != str(rights_record.representation_sha256):
                reasons.append("exact representation bytes changed")
    return ProviderProcessingValidation(not reasons, tuple(dict.fromkeys(reasons)))


def preflight_provider_processing(
    references: Iterable[Any],
    *,
    provider_policy: ProviderProcessingPolicy | Mapping[str, Any] | None,
    provider_configuration: ProviderConfiguration | Mapping[str, Any] | None,
    decisions: Mapping[str, ProviderProcessingDecision | Mapping[str, Any]],
    store: RightsGovernanceStore,
    projection: RightsGovernanceProjection,
    catalog: Any,
    as_of: date,
    retained_bytes: Callable[[str], bytes] | None = None,
    operation: str = "semantic_analysis",
) -> ProviderProcessingPreflight:
    """Compose provider eligibility with the existing clean T1B preflight."""

    from .phase5_governed_factory_integration import PreflightDiagnostic
    from .phase5_governed_rights_preflight import RightsPreflightReference, preflight_governed_rights

    raw_refs = [item if isinstance(item, RightsPreflightReference) else RightsPreflightReference.model_validate(item) for item in references]
    diagnostics: list[Any] = []
    try:
        policy = provider_policy if isinstance(provider_policy, ProviderProcessingPolicy) else ProviderProcessingPolicy.model_validate(provider_policy)
        policy = policy.sealed()
    except Exception as exc:
        return ProviderProcessingPreflight((), tuple(
            PreflightDiagnostic(reference_id=getattr(item, "reference_id", "unresolved"), subject_id="unresolved", state="blocked", reason="provider policy identity or version is unknown", details=(str(exc),))
            for item in raw_refs
        ))
    try:
        provider = provider_configuration if isinstance(provider_configuration, ProviderConfiguration) else ProviderConfiguration.model_validate(provider_configuration)
    except Exception as exc:
        return ProviderProcessingPreflight((), tuple(
            PreflightDiagnostic(reference_id=item.reference_id, subject_id="unresolved", state="blocked", reason="configured provider identity/version is unavailable", details=(str(exc),))
            for item in raw_refs
        ))

    eligible_refs: list[Any] = []
    eligible_decisions: list[ProviderProcessingDecision] = []
    for reference in raw_refs:
        raw_decision = decisions.get(reference.reference_id) or decisions.get(reference.rights_record_id)
        try:
            decision = raw_decision if isinstance(raw_decision, ProviderProcessingDecision) else ProviderProcessingDecision.model_validate(raw_decision)
            record = store.load_record(reference.rights_record_id)
            validation = revalidate_provider_processing(
                decision, record, policy, provider,
                source_family=reference.source_family, operation=operation,
                retained_bytes=retained_bytes, as_of=as_of,
            )
        except (RightsStorageError, RightsProjectionError, ValueError) as exc:
            validation = ProviderProcessingValidation(False, ("provider decision or rights authority is unavailable", str(exc)))
            decision = None
        if not validation.eligible:
            diagnostics.append(PreflightDiagnostic(
                reference_id=reference.reference_id,
                subject_id=getattr(decision, "subject_id", "unresolved"),
                state="blocked",
                reason="provider processing policy preflight failed closed",
                details=validation.reasons,
            ))
            continue
        eligible_refs.append(reference)
        assert decision is not None
        eligible_decisions.append(decision)

    if not eligible_refs:
        return ProviderProcessingPreflight((), tuple(diagnostics), tuple(eligible_decisions))
    local = preflight_governed_rights(
        eligible_refs, store=store, projection=projection, catalog=catalog,
        as_of=as_of, retained_bytes=retained_bytes,
    )
    diagnostics.extend(local.diagnostics)
    return ProviderProcessingPreflight(local.tasks, tuple(diagnostics), tuple(eligible_decisions))


def pre_send_revalidate(
    decision: ProviderProcessingDecision,
    *,
    policy: ProviderProcessingPolicy | Mapping[str, Any] | None,
    provider_configuration: ProviderConfiguration | Mapping[str, Any] | None,
    store: RightsGovernanceStore,
    projection: RightsGovernanceProjection,
    catalog: Any | None = None,
    reference: Any | None = None,
    as_of: date,
    retained_bytes: Callable[[str], bytes] | None = None,
    operation: str = "semantic_analysis",
) -> ProviderProcessingValidation:
    """Fail closed if policy, rights, source, or representation changed."""

    try:
        current_policy = policy if isinstance(policy, ProviderProcessingPolicy) else ProviderProcessingPolicy.model_validate(policy)
        provider = provider_configuration if isinstance(provider_configuration, ProviderConfiguration) else ProviderConfiguration.model_validate(provider_configuration)
        record = store.load_record(decision.rights_record_id)
        current = projection.current_record(
            record_id=record.content_hash, subject_id=record.subject_id,
            scope=record.scope, as_of=as_of,
        )
        if current is None or current.get("record_id") != record.content_hash:
            return ProviderProcessingValidation(False, ("authoritative v29 rights projection is not current",))
        result = revalidate_provider_processing(
            decision, record, current_policy, provider,
            source_family=decision.source_family, operation=operation,
            retained_bytes=retained_bytes, as_of=as_of,
        )
        if not result.eligible:
            return result
        if catalog is not None and reference is not None:
            from .phase5_governed_rights_preflight import preflight_governed_rights
            local = preflight_governed_rights(
                (reference,), store=store, projection=projection, catalog=catalog,
                as_of=as_of, retained_bytes=retained_bytes,
            )
            if local.accepted_count != 1:
                return ProviderProcessingValidation(False, ("clean T1B rights preflight failed immediately before send",) + tuple(item.reason for item in local.diagnostics))
        return result
    except Exception as exc:
        return ProviderProcessingValidation(False, ("pre-send provider revalidation failed closed", str(exc)))


__all__ = [
    "DEFAULT_REVIEW_RULE", "PROVIDER_PROCESSING_POLICY_ID", "PROVIDER_PROCESSING_POLICY_VERSION",
    "ProviderConfiguration", "PolicyEvidence", "ProviderProcessingPolicy", "SourceOperationExclusion",
    "ProviderProcessingDecision", "ProviderProcessingValidation", "ProviderProcessingPreflight",
    "issue_provider_processing_decision", "revalidate_provider_processing",
    "preflight_provider_processing", "pre_send_revalidate",
]
