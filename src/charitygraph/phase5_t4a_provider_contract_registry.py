"""Provider-free verification of a source-owned provider-contract registry entry.

This module is an authority check, not a provider policy or transport layer.
It accepts either the exact canonical JSON bytes of an authority entry or a
separately supplied entry together with an independently trusted SHA-256 pin.
The entry's own content hash is never treated as that independent pin.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal

from pydantic import TypeAdapter, ValidationError, field_validator

from .contracts.canonical import canonical_json_bytes
from .contracts.common import Sha256, StrictModel, require_nonblank
from .phase5_provider_processing_policy import ProviderConfiguration
from .phase5_t4a_provider_contract_identity_probe import ProviderContractBinding
from .runtime.rights_governance_record import RightsGovernanceRecord
from .source_rights import ArtifactRightsDecision


PROVIDER_CONTRACT_REGISTRY_SCHEMA = "charitygraph.provider-contract-registry/1"
_SHA256 = TypeAdapter(Sha256)


class ProviderContractRegistryEntry(StrictModel):
    """Non-secret, source-owned contract/version authority material."""

    schema_id: Literal[PROVIDER_CONTRACT_REGISTRY_SCHEMA] = PROVIDER_CONTRACT_REGISTRY_SCHEMA
    contract_id: str
    contract_version: str
    provider_policy_id: str
    provider_policy_version: str
    authority_locator: str
    authority_content_sha256: Sha256
    status: Literal["current", "effective", "stale", "revoked"]
    route: ProviderContractBinding
    retention_posture: str
    provider_no_training_default: bool
    provider_data_sharing_opt_in: bool
    renewal_revalidation_rule: str

    @field_validator(
        "contract_id",
        "contract_version",
        "provider_policy_id",
        "provider_policy_version",
        "authority_locator",
        "retention_posture",
        "renewal_revalidation_rule",
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


class _CallerRouteMetadata(StrictModel):
    """Non-authoritative caller metadata used to diagnose exact drift."""

    provider: str
    project_id: str
    service: str
    endpoint: str
    model: str
    delivery_mode: str
    reasoning_effort: str
    retention_posture: str
    provider_no_training_default: bool
    provider_data_sharing_opt_in: bool

    @field_validator(
        "provider", "project_id", "service", "endpoint", "model",
        "delivery_mode", "reasoning_effort", "retention_posture",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)


class ProviderContractRegistryDiagnostic(StrictModel):
    """Content-addressed diagnostic; it intentionally contains no send ticket."""

    schema_id: Literal[PROVIDER_CONTRACT_REGISTRY_SCHEMA] = PROVIDER_CONTRACT_REGISTRY_SCHEMA
    status: Literal["UNBOUND", "NOT_VERIFIED", "IDENTITY_EVIDENCE_VERIFIED_NON_SEND"]
    authority_input: Literal["missing", "canonical_bytes", "content_addressed_entry", "invalid"]
    trusted_authority_sha256: Sha256 | None = None
    observed_authority_sha256: Sha256 | None = None
    registry_entry_sha256: Sha256 | None = None
    contract_id: str | None = None
    contract_version: str | None = None
    expected_contract_id: str | None = None
    expected_contract_version: str | None = None
    compared_fields: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    request_ticket: None = None
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"
    content_hash: Sha256 | None = None

    @field_validator(
        "contract_id", "contract_version", "trusted_authority_sha256",
        "observed_authority_sha256", "registry_entry_sha256", "expected_contract_id",
        "expected_contract_version",
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

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self, exclude={"content_hash"})

    @property
    def computed_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def sealed(self) -> "ProviderContractRegistryDiagnostic":
        expected = self.computed_hash
        if self.content_hash is not None and self.content_hash != expected:
            raise ValueError("diagnostic content hash does not match canonical bytes")
        return self.model_copy(update={"content_hash": expected})


def _valid_sha256(value: object) -> bool:
    try:
        _SHA256.validate_python(value)
    except (TypeError, ValueError):
        return False
    return True


def _unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _parse_entry(value: ProviderContractRegistryEntry | Mapping[str, object]) -> ProviderContractRegistryEntry:
    if isinstance(value, ProviderContractRegistryEntry):
        return value
    return ProviderContractRegistryEntry.model_validate(value)


def _authority_parse_reason(error: ValueError, *, bytes_input: bool) -> str:
    if isinstance(error, ValidationError) and any(
        tuple(detail.get("loc", ())) == ("schema_id",) for detail in error.errors()
    ):
        return "authority_registry_schema_invalid"
    return "authority_bytes_invalid" if bytes_input else "authority_entry_invalid"


def _load_authority(
    *,
    authority_bytes: bytes | None,
    authority_entry: ProviderContractRegistryEntry | Mapping[str, object] | None,
    trusted_authority_sha256: str | None,
) -> tuple[
    ProviderContractRegistryEntry | None,
    Literal["missing", "canonical_bytes", "content_addressed_entry", "invalid"],
    str | None,
    str | None,
    list[str],
]:
    reasons: list[str] = []
    if authority_bytes is not None and authority_entry is not None:
        return None, "invalid", None, None, ["authority_input_ambiguous"]
    if authority_bytes is None and authority_entry is None:
        return None, "missing", None, None, ["source_owned_contract_authority_missing"]

    input_kind: Literal["canonical_bytes", "content_addressed_entry", "invalid"]
    entry: ProviderContractRegistryEntry | None = None
    canonical: bytes | None = None
    observed_hash: str | None = None
    if authority_bytes is not None:
        input_kind = "canonical_bytes"
        if not isinstance(authority_bytes, bytes) or not authority_bytes:
            return None, "invalid", None, None, ["authority_bytes_invalid"]
        observed_hash = hashlib.sha256(authority_bytes).hexdigest()
        try:
            decoded = json.loads(authority_bytes.decode("utf-8"))
            entry = _parse_entry(decoded)
            canonical = entry.canonical_bytes
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            reasons.append(_authority_parse_reason(error, bytes_input=True))
        if canonical is not None and authority_bytes != canonical:
            reasons.append("authority_bytes_not_canonical")
    else:
        input_kind = "content_addressed_entry"
        try:
            entry = _parse_entry(authority_entry)  # type: ignore[arg-type]
            canonical = entry.canonical_bytes
            observed_hash = hashlib.sha256(canonical).hexdigest()
        except (TypeError, ValueError) as error:
            reasons.append(_authority_parse_reason(error, bytes_input=False))

    if trusted_authority_sha256 is None:
        reasons.append("trusted_authority_pin_missing")
    elif not _valid_sha256(trusted_authority_sha256):
        reasons.append("trusted_authority_pin_invalid")
    elif observed_hash != trusted_authority_sha256:
        reasons.append("trusted_authority_pin_mismatch")

    return entry, input_kind, trusted_authority_sha256 if _valid_sha256(trusted_authority_sha256) else None, observed_hash, reasons


def _rights_reasons(
    rights_authority: ArtifactRightsDecision | RightsGovernanceRecord | None,
    entry: ProviderContractRegistryEntry,
) -> list[str]:
    """Read existing rights authority without treating it as contract authority."""

    if rights_authority is None:
        return []
    if isinstance(rights_authority, ArtifactRightsDecision):
        if rights_authority.status != "authorized" or not rights_authority.provider_transmission_allowed:
            return ["existing_source_rights_do_not_authorize_provider_transmission"]
        if (
            rights_authority.provider_processing_policy_id != entry.provider_policy_id
            or rights_authority.provider_processing_policy_version != entry.provider_policy_version
        ):
            return ["existing_source_rights_provider_policy_mismatch"]
        return []
    if rights_authority.status != "active":
        return ["existing_runtime_rights_record_not_active"]
    if not rights_authority.provider_transmission_allowed:
        return ["existing_runtime_rights_do_not_authorize_provider_transmission"]
    if (
        rights_authority.provider_processing_policy_id != entry.provider_policy_id
        or rights_authority.provider_processing_policy_version != entry.provider_policy_version
    ):
        return ["existing_runtime_rights_provider_policy_mismatch"]
    return []


def resolve_source_owned_provider_contract_registry(
    *,
    authority_bytes: bytes | None = None,
    authority_entry: ProviderContractRegistryEntry | Mapping[str, object] | None = None,
    trusted_authority_sha256: str | None = None,
    expected_contract_id: str | None = None,
    expected_contract_version: str | None = None,
    caller_route: ProviderConfiguration | Mapping[str, object] | None = None,
    source_owned_policy_id: str | None = None,
    source_owned_policy_version: str | None = None,
    rights_authority: ArtifactRightsDecision | RightsGovernanceRecord | None = None,
) -> ProviderContractRegistryDiagnostic:
    """Resolve one exact source-owned entry, never authorising a request.

    ``trusted_authority_sha256`` is deliberately separate from the entry's
    ``authority_content_sha256``.  A self-attested field, local policy value,
    fixture, or Product Owner approval reference cannot serve as the pin.
    """

    entry, authority_input, trusted_pin, observed_hash, reasons = _load_authority(
        authority_bytes=authority_bytes,
        authority_entry=authority_entry,
        trusted_authority_sha256=trusted_authority_sha256,
    )
    compared: list[str] = []
    if entry is None:
        status: Literal["UNBOUND", "NOT_VERIFIED"] = (
            "UNBOUND" if authority_input == "missing" else "NOT_VERIFIED"
        )
        return ProviderContractRegistryDiagnostic(
            status=status,
            authority_input=authority_input,
            trusted_authority_sha256=trusted_pin,
            observed_authority_sha256=observed_hash,
            reasons=_unique(reasons),
        ).sealed()

    if entry.status in {"stale", "revoked"}:
        reasons.append(f"source_owned_contract_{entry.status}")
    if expected_contract_id is None:
        reasons.append("expected_contract_id_missing")
    elif entry.contract_id != expected_contract_id:
        reasons.append("expected_contract_id_mismatch")
    if expected_contract_version is None:
        reasons.append("expected_contract_version_missing")
    elif entry.contract_version != expected_contract_version:
        reasons.append("expected_contract_version_mismatch")
    if source_owned_policy_id is None:
        reasons.append("source_owned_provider_policy_id_missing")
    elif entry.provider_policy_id != source_owned_policy_id:
        reasons.append("provider_policy_id_mismatch")
    if source_owned_policy_version is None:
        reasons.append("source_owned_provider_policy_version_missing")
    elif entry.provider_policy_version != source_owned_policy_version:
        reasons.append("provider_policy_version_mismatch")

    if caller_route is None:
        reasons.append("caller_route_missing")
        caller: ProviderConfiguration | None = None
    else:
        try:
            if isinstance(caller_route, ProviderConfiguration):
                caller = caller_route
            else:
                try:
                    caller = ProviderConfiguration.model_validate(caller_route)
                except (TypeError, ValueError):
                    caller = _CallerRouteMetadata.model_validate(caller_route)
        except (TypeError, ValueError):
            caller = None
            reasons.append("caller_route_invalid")
    if caller is not None:
        caller_values = caller.model_dump()
        entry_values = entry.route.model_dump()
        for field in ("provider", "project_id", "service", "endpoint", "model"):
            compared.append(field)
            if caller_values[field] != entry_values[field]:
                reasons.append(f"caller_{field}_mismatch")
        compared.extend(("retention_posture", "provider_no_training_default", "provider_data_sharing_opt_in"))
        if caller.retention_posture != entry.retention_posture:
            reasons.append("retention_posture_mismatch")
        if caller.provider_no_training_default != entry.provider_no_training_default:
            reasons.append("no_training_posture_mismatch")
        if caller.provider_data_sharing_opt_in != entry.provider_data_sharing_opt_in:
            reasons.append("no_sharing_posture_mismatch")

    reasons.extend(_rights_reasons(rights_authority, entry))
    return ProviderContractRegistryDiagnostic(
        status="NOT_VERIFIED" if reasons else "IDENTITY_EVIDENCE_VERIFIED_NON_SEND",
        authority_input=authority_input,
        trusted_authority_sha256=trusted_pin,
        observed_authority_sha256=observed_hash,
        registry_entry_sha256=entry.content_hash,
        contract_id=entry.contract_id,
        contract_version=entry.contract_version,
        expected_contract_id=expected_contract_id,
        expected_contract_version=expected_contract_version,
        compared_fields=_unique(compared),
        reasons=_unique(reasons),
    ).sealed()


__all__ = [
    "PROVIDER_CONTRACT_REGISTRY_SCHEMA",
    "ProviderContractRegistryEntry",
    "ProviderContractRegistryDiagnostic",
    "resolve_source_owned_provider_contract_registry",
]
