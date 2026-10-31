"""Provider-free structural resolver for one provider policy record.

The record accepted here is non-secret authority metadata.  It is not a
configuration default, a transport ticket, a budget approval, or a send
authorisation.  The resolver is deliberately pure: it reloads the supplied
canonical bytes, checks a caller-supplied content-address comparison, checks
the record's reference to separately supplied canonical authority-document
bytes, and returns a deterministic diagnostic without touching storage or the
network.  No caller input is a source-owned authentication root.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any, Literal

from pydantic import ValidationError, field_validator

from .contracts.canonical import canonical_json_bytes
from .contracts.common import Sha256, StrictModel, require_nonblank
from .runtime.rights_governance_record import RightsGovernanceRecord


PROVIDER_POLICY_REGISTRY_SCHEMA = "charitygraph.provider-policy-registry/1"
_ACTIVE_STATUSES = {"current", "effective"}
_INACTIVE_STATUSES = {"stale", "revoked", "expired"}


class ProviderPolicyRoute(StrictModel):
    """Exact non-secret provider route identity."""

    provider: str
    project_id: str
    service: str
    endpoint: str
    model: str

    @field_validator("provider", "project_id", "service", "endpoint", "model")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)


class ProviderPolicyRecord(StrictModel):
    """One versioned, source-owned provider contract/policy assertion."""

    schema_id: Literal[PROVIDER_POLICY_REGISTRY_SCHEMA] = PROVIDER_POLICY_REGISTRY_SCHEMA
    contract_id: str
    contract_version: str
    provider_policy_id: str
    provider_policy_version: str
    authority_locator: str
    authority_content_sha256: Sha256
    status: Literal["current", "effective", "stale", "revoked", "expired"]
    effective_from: date
    renewal_check_date: date
    route: ProviderPolicyRoute
    retention_posture: str = "ordinary"
    provider_no_training_default: bool
    provider_data_sharing_opt_in: bool
    renewal_revalidation_rule: str | None = None

    @field_validator(
        "contract_id", "contract_version", "provider_policy_id", "provider_policy_version",
        "authority_locator", "retention_posture",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("renewal_revalidation_rule")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


class ProviderPolicyResolution(StrictModel):
    """Deterministic read-only result; it can never authorize a send.

    The current Builder tranche has no source-owned provider authority binding,
    so every structurally coherent result is explicitly unauthenticated.
    ``authority_verified`` is intentionally constrained to ``False`` so an
    ordinary caller cannot manufacture a privileged resolution object.
    """

    schema_id: Literal[PROVIDER_POLICY_REGISTRY_SCHEMA] = PROVIDER_POLICY_REGISTRY_SCHEMA
    status: Literal["missing", "invalid", "blocked", "STRUCTURE_ONLY_UNAUTHENTICATED"]
    authority_verified: Literal[False] = False
    observed_record_sha256: Sha256 | None = None
    trusted_record_sha256: Sha256 | None = None
    observed_authority_document_sha256: Sha256 | None = None
    contract_id: str | None = None
    contract_version: str | None = None
    provider_policy_id: str | None = None
    provider_policy_version: str | None = None
    reasons: tuple[str, ...] = ()
    real_send_ready: Literal[False] = False
    action: Literal["NONE"] = "NONE"
    host_authentication_required: Literal[True] = True
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"
    content_hash: Sha256 | None = None
    route: ProviderPolicyRoute | None = None

    @field_validator(
        "contract_id", "contract_version", "provider_policy_id", "provider_policy_version",
    )
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("reasons")
    @classmethod
    def _reasons_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("resolution reasons must be nonblank")
        return tuple(dict.fromkeys(value))

    @property
    def verified(self) -> bool:
        return self.authority_verified

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self, exclude={"content_hash"})

    @property
    def computed_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def sealed(self) -> "ProviderPolicyResolution":
        expected = self.computed_hash
        if self.content_hash is not None and self.content_hash != expected:
            raise ValueError("resolution content hash does not match canonical bytes")
        return self.model_copy(update={"content_hash": expected})


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _parse_supplied(value: bytes | Mapping[str, Any] | ProviderPolicyRecord) -> tuple[
    ProviderPolicyRecord | None, str | None, list[str]
]:
    reasons: list[str] = []
    if isinstance(value, bytes):
        if not value:
            return None, None, ["authority_record_bytes_missing"]
        observed = hashlib.sha256(value).hexdigest()
        try:
            decoded = json.loads(value.decode("utf-8"))
            record = ProviderPolicyRecord.model_validate(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
            return None, observed, ["authority_record_invalid"]
        if value != record.canonical_bytes:
            reasons.append("authority_record_not_canonical")
        return record, observed, reasons
    try:
        record = value if isinstance(value, ProviderPolicyRecord) else ProviderPolicyRecord.model_validate(value)
    except (TypeError, ValueError, ValidationError):
        return None, None, ["authority_record_invalid"]
    return record, record.content_hash, reasons


def _caller_values(caller_route: Mapping[str, Any] | Any | None) -> tuple[dict[str, Any] | None, list[str]]:
    if caller_route is None:
        return None, ["caller_route_missing"]
    if hasattr(caller_route, "model_dump"):
        raw = caller_route.model_dump(mode="python")
    elif isinstance(caller_route, Mapping):
        raw = dict(caller_route)
    else:
        return None, ["caller_route_invalid"]
    if isinstance(raw.get("route"), Mapping):
        raw = {**dict(raw["route"]), **{key: value for key, value in raw.items() if key != "route"}}
    posture = {
        "provider_no_training_default": raw.get(
            "provider_no_training_default", raw.get("no_training_default")
        ),
        "provider_data_sharing_opt_in": raw.get(
            "provider_data_sharing_opt_in", raw.get("data_sharing_opt_in")
        ),
    }
    values = {key: raw.get(key) for key in ("provider", "project_id", "service", "endpoint", "model")}
    values.update(posture)
    if any(value is None for value in values.values()):
        return None, ["caller_route_incomplete"]
    return values, []


def _resolution(
    *,
    status: Literal["missing", "invalid", "blocked", "STRUCTURE_ONLY_UNAUTHENTICATED"],
    reasons: Iterable[str],
    observed: str | None = None,
    authority_document: str | None = None,
    record: ProviderPolicyRecord | None = None,
) -> ProviderPolicyResolution:
    return ProviderPolicyResolution(
        status=status,
        observed_record_sha256=observed,
        observed_authority_document_sha256=authority_document,
        contract_id=record.contract_id if record else None,
        contract_version=record.contract_version if record else None,
        provider_policy_id=record.provider_policy_id if record else None,
        provider_policy_version=record.provider_policy_version if record else None,
        route=record.route if record else None,
        reasons=_unique(reasons),
    ).sealed()


def _authority_document_hash(
    authority_document_bytes: bytes | None,
    *,
    record_bytes: bytes,
) -> tuple[str | None, list[str]]:
    """Hash exact canonical JSON bytes that are separate from the record.

    The hash is over the supplied bytes, not over the record, its locator, or
    the record's self-declared hash.  Requiring canonical JSON makes the
    payload stable while leaving its source-owned schema outside this tranche.
    """

    if authority_document_bytes is None:
        return None, ["authority_document_bytes_missing"]
    if not isinstance(authority_document_bytes, bytes) or not authority_document_bytes:
        return None, ["authority_document_bytes_invalid"]
    observed = hashlib.sha256(authority_document_bytes).hexdigest()
    if authority_document_bytes == record_bytes:
        return observed, ["authority_document_self_referential"]
    try:
        decoded = json.loads(authority_document_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return observed, ["authority_document_not_canonical"]
    if canonical_json_bytes(decoded) != authority_document_bytes:
        return observed, ["authority_document_not_canonical"]
    return observed, []


def resolve_provider_policy_registry(
    *,
    authority_bytes: bytes | None = None,
    authority_record: Mapping[str, Any] | ProviderPolicyRecord | None = None,
    authority_records: Iterable[bytes | Mapping[str, Any] | ProviderPolicyRecord] | None = None,
    trusted_authority_sha256: str | None = None,
    authority_document_bytes: bytes | None = None,
    expected_contract_id: str | None = None,
    expected_contract_version: str | None = None,
    expected_provider_policy_id: str | None = None,
    expected_provider_policy_version: str | None = None,
    caller_route: Mapping[str, Any] | Any | None = None,
    rights_authority: RightsGovernanceRecord | None = None,
    as_of: date | None = None,
) -> ProviderPolicyResolution:
    """Resolve structural provider-policy consistency without authentication.

    The trusted hash is intentionally separate from the record's own
    ``authority_content_sha256``.  It is only a caller-supplied comparison in
    this provider-free tranche and never authenticates source ownership.  The
    record's ``authority_content_sha256`` must equal the SHA-256 of the exact,
    separately supplied canonical JSON ``authority_document_bytes``.  Caller
    defaults, URLs, policy names and coherent caller assertions never
    substitute for source-owned authority.
    """

    supplied_count = sum(value is not None for value in (authority_bytes, authority_record, authority_records))
    if supplied_count > 1:
        return _resolution(status="invalid", reasons=("authority_input_ambiguous",))
    if supplied_count == 0:
        return _resolution(status="missing", reasons=("source_owned_authority_missing",))

    parsed: list[tuple[ProviderPolicyRecord, str, list[str]]] = []
    raw_values = [authority_bytes] if authority_bytes is not None else [authority_record]
    if authority_records is not None:
        try:
            raw_values = list(authority_records)
        except TypeError:
            return _resolution(status="invalid", reasons=("authority_records_invalid",))
        if not raw_values:
            return _resolution(status="missing", reasons=("source_owned_authority_missing",))
    for raw in raw_values:
        record, observed, reasons = _parse_supplied(raw)  # type: ignore[arg-type]
        if record is None or observed is None:
            return _resolution(status="invalid", reasons=reasons)
        parsed.append((record, observed, reasons))

    identities = [(item.contract_id, item.contract_version) for item, _hash, _reasons in parsed]
    if len(set(identities)) != len(identities):
        return _resolution(status="invalid", reasons=("duplicate_authority_entries",))
    if expected_contract_id is None or expected_contract_version is None:
        return _resolution(
            status="blocked",
            reasons=("expected_contract_identity_missing",),
        )
    selected = [item for item in parsed if item[0].contract_id == expected_contract_id and item[0].contract_version == expected_contract_version]
    if len(selected) != 1:
        return _resolution(
            status="blocked",
            reasons=("expected_contract_identity_mismatch",),
        )
    record, observed, reasons = selected[0]
    record_bytes = record.canonical_bytes
    authority_document, authority_document_reasons = _authority_document_hash(
        authority_document_bytes,
        record_bytes=record_bytes,
    )
    reasons.extend(authority_document_reasons)
    if authority_document is not None and record.authority_content_sha256 != authority_document:
        reasons.append("authority_content_sha256_mismatch")
    if trusted_authority_sha256 is None:
        reasons.append("trusted_authority_pin_missing")
    elif not _valid_sha256(trusted_authority_sha256):
        reasons.append("trusted_authority_pin_invalid")
    elif observed != trusted_authority_sha256:
        reasons.append("trusted_authority_pin_mismatch")
    if expected_provider_policy_id is None or expected_provider_policy_version is None:
        reasons.append("expected_provider_policy_identity_missing")
    else:
        if record.provider_policy_id != expected_provider_policy_id:
            reasons.append("provider_policy_id_mismatch")
        if record.provider_policy_version != expected_provider_policy_version:
            reasons.append("provider_policy_version_mismatch")

    when = as_of or date.today()
    if record.status in _INACTIVE_STATUSES:
        reasons.append(f"source_owned_authority_{record.status}")
    elif record.status not in _ACTIVE_STATUSES:
        reasons.append("source_owned_authority_status_invalid")
    if when < record.effective_from:
        reasons.append("source_owned_authority_not_yet_effective")
    if when > record.renewal_check_date:
        reasons.append("source_owned_authority_renewal_check_expired")
    if record.provider_no_training_default is not True:
        reasons.append("no_training_posture_not_authorized")
    if record.provider_data_sharing_opt_in is not False:
        reasons.append("no_sharing_posture_not_authorized")

    caller, caller_reasons = _caller_values(caller_route)
    reasons.extend(caller_reasons)
    if caller is not None:
        for field in ("provider", "project_id", "service", "endpoint", "model"):
            if caller[field] != getattr(record.route, field):
                reasons.append(f"caller_{field}_mismatch")
        if caller["provider_no_training_default"] is not True:
            reasons.append("caller_no_training_posture_not_authorized")
        if caller["provider_data_sharing_opt_in"] is not False:
            reasons.append("caller_no_sharing_posture_not_authorized")
        if caller["provider_no_training_default"] != record.provider_no_training_default:
            reasons.append("no_training_posture_mismatch")
        if caller["provider_data_sharing_opt_in"] != record.provider_data_sharing_opt_in:
            reasons.append("no_sharing_posture_mismatch")

    if rights_authority is not None:
        if not rights_authority.can_promote(as_of=when):
            reasons.append("current_rights_authority_missing_or_stale")
        if rights_authority.local_retention.status != "authorized":
            reasons.append("local_retention_rights_missing")
        if rights_authority.provider_transmission.status != "authorized":
            reasons.append("provider_transmission_rights_missing")
        if (
            rights_authority.provider_processing_policy_id != record.provider_policy_id
            or rights_authority.provider_processing_policy_version != record.provider_policy_version
        ):
            reasons.append("rights_provider_policy_identity_mismatch")

    if reasons:
        return _resolution(
            status="blocked", reasons=reasons,
            observed=observed, authority_document=authority_document, record=record,
        )
    reasons.append("source_owned_authority_unbound")
    return _resolution(
        status="STRUCTURE_ONLY_UNAUTHENTICATED", reasons=reasons,
        observed=observed, authority_document=authority_document, record=record,
    )


resolve_source_owned_provider_policy = resolve_provider_policy_registry
resolve_source_owned_provider_contract = resolve_provider_policy_registry


__all__ = [
    "PROVIDER_POLICY_REGISTRY_SCHEMA", "ProviderPolicyRoute", "ProviderPolicyRecord",
    "ProviderPolicyResolution", "resolve_provider_policy_registry",
    "resolve_source_owned_provider_policy", "resolve_source_owned_provider_contract",
]
