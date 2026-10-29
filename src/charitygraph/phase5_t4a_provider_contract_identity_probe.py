"""Provider-free diagnostics for the unresolved T4A contract-identity seam.

This module is deliberately smaller than the provider-processing policy.  It
does not register a provider contract, select defaults, or authorise a send.
It compares explicit non-secret metadata with an explicitly supplied
authority-shaped record and returns a content-addressed diagnostic.  The
authority-shaped record is an input assertion only; the existing repository
does not manufacture or verify an external provider contract.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.canonical import canonical_json_bytes
from .contracts.common import Sha256, StrictModel, require_nonblank
from .phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
    ProviderConfiguration,
)


PROVIDER_CONTRACT_IDENTITY_PROBE_SCHEMA = "charitygraph.provider-contract-identity-probe/1"
MetadataOrigin = Literal["configured_non_secret", "test_fixture_metadata"]
ContractStatus = Literal["current", "stale", "revoked"]


class ProviderContractBinding(StrictModel):
    """Exact non-secret route fields used only for byte-for-byte comparison."""

    provider: str
    project_id: str
    service: str
    endpoint: str
    model: str

    @field_validator("provider", "project_id", "service", "endpoint", "model")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self)).hexdigest()


class SourceOwnedProviderContract(StrictModel):
    """An explicit external authority assertion; this is not a local registry."""

    contract_id: str
    contract_version: str
    provider_policy_id: str
    provider_policy_version: str
    binding: ProviderContractBinding
    authority_locator: str
    authority_content_sha256: Sha256 | None = None
    status: ContractStatus = "current"

    @field_validator(
        "contract_id", "contract_version", "provider_policy_id", "provider_policy_version", "authority_locator"
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


class ProviderContractIdentityDiagnostic(StrictModel):
    """Immutable result; ``identity_consistent`` is never send permission."""

    schema_id: str = PROVIDER_CONTRACT_IDENTITY_PROBE_SCHEMA
    status: Literal["blocked", "identity_consistent_not_authorization"]
    metadata_origin: MetadataOrigin
    observed_provider_binding_hash: Sha256 | None = None
    local_policy_id: str | None = None
    local_policy_version: str | None = None
    source_owned_policy_id: str | None = None
    source_owned_policy_version: str | None = None
    product_owner_approval_reference: str | None = None
    authoritative_contract_hash: Sha256 | None = None
    authoritative_contract_id: str | None = None
    authoritative_contract_version: str | None = None
    compared_fields: tuple[str, ...] = ()
    reasons: tuple[str, ...]
    content_hash: Sha256 | None = None

    @field_validator(
        "local_policy_id", "local_policy_version", "source_owned_policy_id",
        "source_owned_policy_version", "product_owner_approval_reference",
        "authoritative_contract_id", "authoritative_contract_version",
    )
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("compared_fields", "reasons")
    @classmethod
    def _text_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("diagnostic text entries must be nonblank")
        return value

    @model_validator(mode="after")
    def _status_matches_reasons(self) -> "ProviderContractIdentityDiagnostic":
        if self.status == "blocked" and not self.reasons:
            raise ValueError("blocked diagnostic requires fail-closed reasons")
        if self.status == "identity_consistent_not_authorization" and self.reasons:
            raise ValueError("identity-consistent diagnostic cannot carry fail-closed reasons")
        return self

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self, exclude={"content_hash"})

    @property
    def computed_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def sealed(self) -> "ProviderContractIdentityDiagnostic":
        expected = self.computed_hash
        if self.content_hash is not None and self.content_hash != expected:
            raise ValueError("diagnostic content hash does not match canonical bytes")
        return self.model_copy(update={"content_hash": expected})


def _contract_from_input(value: SourceOwnedProviderContract | dict[str, object] | None) -> SourceOwnedProviderContract | None:
    if value is None:
        return None
    if isinstance(value, SourceOwnedProviderContract):
        return value
    return SourceOwnedProviderContract.model_validate(value)


def probe_provider_contract_identity(
    *,
    provider_metadata: ProviderConfiguration | dict[str, object] | None,
    metadata_origin: MetadataOrigin,
    local_policy_id: str | None,
    local_policy_version: str | None,
    source_owned_policy_id: str | None,
    source_owned_policy_version: str | None,
    product_owner_approval_reference: str | None = None,
    authoritative_contract: SourceOwnedProviderContract | dict[str, object] | None = None,
) -> ProviderContractIdentityDiagnostic:
    """Compare explicit identity inputs without crossing any provider boundary.

    A missing or malformed input is represented as a blocked diagnostic where
    possible.  The only non-blocked result means that the supplied identities
    are internally consistent; it never means that a provider request is safe.
    """

    reasons: list[str] = []
    compared: list[str] = []
    observed: ProviderConfiguration | None = None
    contract: SourceOwnedProviderContract | None = None

    if provider_metadata is None:
        reasons.append("configured_provider_metadata_missing")
    else:
        try:
            observed = provider_metadata if isinstance(provider_metadata, ProviderConfiguration) else ProviderConfiguration.model_validate(provider_metadata)
        except ValueError:
            reasons.append("configured_provider_metadata_invalid")

    if local_policy_id != PROVIDER_PROCESSING_POLICY_ID:
        reasons.append("local_policy_identity_mismatch")
    if local_policy_version != PROVIDER_PROCESSING_POLICY_VERSION:
        reasons.append("local_policy_version_mismatch")
    if source_owned_policy_id is None:
        reasons.append("source_owned_policy_identity_missing")
    elif source_owned_policy_id != local_policy_id:
        reasons.append("source_owned_policy_identity_mismatch")
    if source_owned_policy_version is None:
        reasons.append("source_owned_policy_version_missing")
    elif source_owned_policy_version != local_policy_version:
        reasons.append("source_owned_policy_version_mismatch")
    if product_owner_approval_reference is None:
        reasons.append("product_owner_approval_missing")
    if metadata_origin == "test_fixture_metadata":
        reasons.append("test_fixture_metadata_is_not_authority")

    if authoritative_contract is None:
        reasons.append("authoritative_provider_contract_identity_missing")
        reasons.append("authoritative_provider_contract_version_missing")
    else:
        if isinstance(authoritative_contract, dict):
            if not authoritative_contract.get("contract_id"):
                reasons.append("authoritative_provider_contract_identity_missing")
            if not authoritative_contract.get("contract_version"):
                reasons.append("authoritative_provider_contract_version_missing")
        try:
            contract = _contract_from_input(authoritative_contract)
        except ValueError:
            reasons.append("authoritative_provider_contract_identity_invalid")

    if contract is not None:
        if contract.status != "current":
            reasons.append("authoritative_provider_contract_is_stale_or_revoked")
        if contract.authority_content_sha256 is None:
            reasons.append("authoritative_provider_contract_evidence_missing")
        if source_owned_policy_id is not None and contract.provider_policy_id != source_owned_policy_id:
            reasons.append("authoritative_contract_policy_identity_mismatch")
        if source_owned_policy_version is not None and contract.provider_policy_version != source_owned_policy_version:
            reasons.append("authoritative_contract_policy_version_mismatch")
        if observed is not None:
            fields = (
                "provider", "project_id", "service", "endpoint", "model",
            )
            observed_values = observed.model_dump()
            authority_values = contract.binding.model_dump()
            for field in fields:
                compared.append(field)
                if observed_values[field] != authority_values[field]:
                    reasons.append(f"authoritative_contract_{field}_mismatch")

    diagnostic = ProviderContractIdentityDiagnostic(
        status="blocked" if reasons else "identity_consistent_not_authorization",
        metadata_origin=metadata_origin,
        observed_provider_binding_hash=None if observed is None else observed.content_hash,
        local_policy_id=local_policy_id,
        local_policy_version=local_policy_version,
        source_owned_policy_id=source_owned_policy_id,
        source_owned_policy_version=source_owned_policy_version,
        product_owner_approval_reference=product_owner_approval_reference,
        authoritative_contract_hash=None if contract is None else contract.content_hash,
        authoritative_contract_id=None if contract is None else contract.contract_id,
        authoritative_contract_version=None if contract is None else contract.contract_version,
        compared_fields=tuple(compared),
        reasons=tuple(dict.fromkeys(reasons)),
    )
    return diagnostic.sealed()


__all__ = [
    "PROVIDER_CONTRACT_IDENTITY_PROBE_SCHEMA",
    "ProviderContractBinding",
    "SourceOwnedProviderContract",
    "ProviderContractIdentityDiagnostic",
    "probe_provider_contract_identity",
]
