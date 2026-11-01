"""Exact representation and rights binding for the bounded Gate 4 T3 cohort.

This module is an adapter over existing durable material.  It does not acquire
sources, create a rights store, infer a representation, or send to a provider.
The selected manifest is a selection input; exact representation metadata,
validated receipts, source records, scopes, and rights decisions must be
supplied by an existing authority before a row can be lowered to the existing
governed Factory preflight contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping

from .contracts.canonical import canonical_json_bytes
from .phase5_governed_factory_integration import GovernedReference
from .source_rights import (
    FAIR_DEALING_POLICY_ID,
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
    governed_rights_policy,
)


BINDER_SCHEMA = "charitygraph.gate4.t3.exact-representation-rights-binding/v1"
SELECTED_MANIFEST_SHA256 = "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9"
ADMITTED_SOURCE_FAMILIES = frozenset(
    {
        "acnc_register",
        "acnc_ais_bundle",
        "ato_abr_dgr",
        "official_website",
        "annual_report",
        "wikipedia_wikimedia",
        "pfra",
    }
)
LOCAL_RETENTION_POLICY_ID = "CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1"
LOCAL_RETENTION_POLICY_VERSION = "1.0.0"
KNOWN_POLICY_VERSIONS = {
    FAIR_DEALING_POLICY_ID: "1.0.0",
    LOCAL_RETENTION_POLICY_ID: LOCAL_RETENTION_POLICY_VERSION,
    PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID: "1.0.0",
}
REPRESENTATION_CLASSES = frozenset({"structured_factual", "bounded_excerpt"})
AXES = ("local_retention", "private_provider_processing", "public_redistribution")

AxisStatus = Literal[
    "authorized",
    "blocked",
    "not_observed",
    "not_assessed",
    "revoked",
    "superseded",
    "stale",
    "conflict",
]
RowStatus = Literal["BOUND", "BLOCKED", "NOT_OBSERVED"]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonblank text")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    value = _text(value, field)
    if len(value) != 64:
        raise ValueError(f"{field} must be a SHA-256 value")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a SHA-256 value") from exc
    return value


def _date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def _lookup_entries(value: Any, label: str) -> tuple[dict[str, Any], ...]:
    """Normalise list-or-id-map metadata without accepting duplicate IDs."""
    if value is None:
        return ()
    if isinstance(value, Mapping):
        entries: list[dict[str, Any]] = []
        for key, item in value.items():
            if hasattr(item, "model_dump"):
                item = item.model_dump(mode="python")
            if not isinstance(item, Mapping):
                raise ValueError(f"{label} entry {key!r} is not a mapping")
            row = dict(item)
            row.setdefault("id", str(key))
            entries.append(row)
    elif isinstance(value, (list, tuple)):
        if any(not isinstance(item, Mapping) for item in value):
            raise ValueError(f"{label} must contain mappings")
        entries = [item.model_dump(mode="python") if hasattr(item, "model_dump") else dict(item) for item in value]
    else:
        raise ValueError(f"{label} must be a mapping or sequence of mappings")
    seen: set[str] = set()
    for entry in entries:
        identifier = (
            entry.get("id")
            or entry.get("artifact_id")
            or entry.get("representation_artifact_id")
            or entry.get("decision_id")
            or entry.get("record_id")
        )
        identifier = _text(identifier, f"{label}.id")
        if identifier in seen:
            raise ValueError(f"duplicate {label} identity: {identifier}")
        seen.add(identifier)
        entry["id"] = identifier
    return tuple(entries)


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        raise ValueError("raw/private bytes are not valid binding metadata")
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"unsupported non-serialisable metadata value: {type(value).__name__}")


@dataclass(frozen=True)
class AxisDecision:
    """One independently assessed rights axis, bound to one representation."""

    axis: str
    status: AxisStatus
    decision_id: str | None = None
    representation_sha256: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None
    assessed_authority: str | None = None
    assessed_on: date | None = None
    review_deadline: date | None = None
    lawful_public_access: bool | None = None
    circumvention_used: bool | None = None
    explicit_prohibition_found: bool | None = None
    provider_policy_id: str | None = None
    provider_policy_version: str | None = None
    provider_no_training_default: bool | None = None
    provider_data_sharing_opt_in: bool | None = None
    authority_kind: str | None = None
    provider_owned: bool | None = None

    @classmethod
    def from_mapping(cls, axis: str, raw: Mapping[str, Any] | None) -> "AxisDecision":
        if raw is None:
            return cls(axis=axis, status="not_observed")
        value = dict(raw)
        status = value.get("status", "not_observed")
        if status not in {"authorized", "blocked", "not_observed", "not_assessed", "revoked", "superseded", "stale", "conflict"}:
            raise ValueError(f"unsupported {axis} decision status")
        return cls(
            axis=axis,
            status=status,
            decision_id=None if value.get("decision_id") is None else _text(value["decision_id"], f"{axis}.decision_id"),
            representation_sha256=None if value.get("representation_sha256") is None else _sha(value["representation_sha256"], f"{axis}.representation_sha256"),
            policy_id=None if value.get("policy_id") is None else _text(value["policy_id"], f"{axis}.policy_id"),
            policy_version=None if value.get("policy_version") is None else _text(value["policy_version"], f"{axis}.policy_version"),
            assessed_authority=None if value.get("assessed_authority") is None else _text(value["assessed_authority"], f"{axis}.assessed_authority"),
            assessed_on=None if value.get("assessed_on") is None else _date(value["assessed_on"], f"{axis}.assessed_on"),
            review_deadline=None if value.get("review_deadline") is None else _date(value["review_deadline"], f"{axis}.review_deadline"),
            lawful_public_access=value.get("lawful_public_access"),
            circumvention_used=value.get("circumvention_used"),
            explicit_prohibition_found=value.get("explicit_prohibition_found"),
            provider_policy_id=None if value.get("provider_policy_id") is None else _text(value["provider_policy_id"], f"{axis}.provider_policy_id"),
            provider_policy_version=None if value.get("provider_policy_version") is None else _text(value["provider_policy_version"], f"{axis}.provider_policy_version"),
            provider_no_training_default=value.get("provider_no_training_default"),
            provider_data_sharing_opt_in=value.get("provider_data_sharing_opt_in"),
            authority_kind=None if value.get("authority_kind") is None else _text(value["authority_kind"], f"{axis}.authority_kind"),
            provider_owned=value.get("provider_owned"),
        )

    def validate(self, *, representation_sha256: str, representation_class: str, as_of: date) -> tuple[str, ...]:
        if self.status != "authorized":
            return ()
        reasons: list[str] = []
        if self.authority_kind in {"provider", "provider_owned", "provider_metadata"} or self.provider_owned is True:
            reasons.append("provider_owned_rights_metadata_not_authority")
        if self.decision_id is None:
            reasons.append("decision_id_missing")
        if self.representation_sha256 != representation_sha256:
            reasons.append("decision_representation_sha_mismatch")
        if self.policy_id is None or self.policy_version is None:
            reasons.append("policy_identity_missing")
        elif self.policy_id in KNOWN_POLICY_VERSIONS and KNOWN_POLICY_VERSIONS[self.policy_id] != self.policy_version:
            reasons.append("policy_version_mismatch")
        elif self.policy_id not in KNOWN_POLICY_VERSIONS and governed_rights_policy(self.policy_id, self.policy_version) is None:
            reasons.append("policy_identity_unknown")
        if self.assessed_authority is None:
            reasons.append("assessed_authority_missing")
        if self.assessed_on is None:
            reasons.append("assessed_on_missing")
        if self.review_deadline is None:
            reasons.append("review_deadline_missing")
        elif self.assessed_on is not None and self.review_deadline < self.assessed_on:
            reasons.append("review_deadline_before_assessment")
        elif self.review_deadline < as_of:
            reasons.append("review_deadline_stale")
        if self.lawful_public_access is not True:
            reasons.append("lawful_public_access_not_confirmed")
        if self.circumvention_used is not False:
            reasons.append("circumvention_not_excluded")
        if self.explicit_prohibition_found is not False:
            reasons.append("explicit_prohibition_not_excluded")
        if representation_class not in REPRESENTATION_CLASSES:
            reasons.append("representation_class_not_governed")
        if self.axis == "local_retention" and self.policy_id == LOCAL_RETENTION_POLICY_ID and representation_class not in REPRESENTATION_CLASSES:
            reasons.append("local_representation_class_outside_policy")
        if self.axis == "private_provider_processing":
            if self.provider_policy_id != OPENAI_PROVIDER_POLICY_ID or self.provider_policy_version != "1":
                reasons.append("provider_policy_identity_missing")
            if self.provider_no_training_default is not True:
                reasons.append("provider_no_training_condition_missing")
            if self.provider_data_sharing_opt_in is not False:
                reasons.append("provider_data_sharing_condition_missing")
        if self.axis == "public_redistribution" and self.policy_id in {
            FAIR_DEALING_POLICY_ID,
            PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
            LOCAL_RETENTION_POLICY_ID,
        }:
            reasons.append("public_redistribution_not_authorized_by_internal_policy")
        return tuple(dict.fromkeys(reasons))

    def as_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "status": self.status,
            "decision_id": self.decision_id,
            "representation_sha256": self.representation_sha256,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "assessed_authority": self.assessed_authority,
            "assessed_on": self.assessed_on.isoformat() if self.assessed_on else None,
            "review_deadline": self.review_deadline.isoformat() if self.review_deadline else None,
            "lawful_public_access": self.lawful_public_access,
            "circumvention_used": self.circumvention_used,
            "explicit_prohibition_found": self.explicit_prohibition_found,
            "provider_policy_id": self.provider_policy_id,
            "provider_policy_version": self.provider_policy_version,
            "provider_no_training_default": self.provider_no_training_default,
            "provider_data_sharing_opt_in": self.provider_data_sharing_opt_in,
            "authority_kind": self.authority_kind,
            "provider_owned": self.provider_owned,
        }


@dataclass(frozen=True)
class ExactBindingRow:
    ordinal: int
    subject_id: str
    scope_id: str | None
    source_family: str
    source_role: str
    source_definition_id: str
    source_record_id: str
    source_artifact_id: str
    source_sha256: str
    acquisition_receipt_ids: tuple[str, ...]
    representation_artifact_id: str | None
    representation_sha256: str | None
    representation_class: str | None
    local_retention: AxisDecision
    private_provider_processing: AxisDecision
    public_redistribution: AxisDecision
    status: RowStatus
    reasons: tuple[str, ...]
    governed_reference: GovernedReference | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "source_role": self.source_role,
            "source_definition_id": self.source_definition_id,
            "source_record_id": self.source_record_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "acquisition_receipt_ids": list(self.acquisition_receipt_ids),
            "representation_artifact_id": self.representation_artifact_id,
            "representation_sha256": self.representation_sha256,
            "representation_class": self.representation_class,
            "rights": {
                "local_retention": self.local_retention.as_dict(),
                "private_provider_processing": self.private_provider_processing.as_dict(),
                "public_redistribution": self.public_redistribution.as_dict(),
            },
            "status": self.status,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ExactRepresentationRightsBindingResult:
    schema: str
    selected_manifest_sha256: str
    rows: tuple[ExactBindingRow, ...]
    coverage_records: tuple[dict[str, Any], ...]
    canonical_hash: str

    @property
    def eligible_count(self) -> int:
        return sum(row.governed_reference is not None for row in self.rows)

    @property
    def bound_count(self) -> int:
        return sum(row.status == "BOUND" for row in self.rows)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "selected_manifest_sha256": self.selected_manifest_sha256,
            "rows": [row.as_dict() for row in self.rows],
            "coverage_records": list(self.coverage_records),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_payload())


def _load_manifest(manifest: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        return json.loads(path.read_text(encoding="utf-8"))
    return dict(manifest)


def _manifest_rows(manifest: Mapping[str, Any], *, require_selected_cohort: bool) -> tuple[dict[str, Any], ...]:
    if manifest.get("selected_manifest_sha256") != SELECTED_MANIFEST_SHA256:
        raise ValueError("selection manifest identity is outside the authorised T3 cohort")
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise ValueError("selection manifest rows must be a list")
    parsed = tuple(dict(row) for row in rows if isinstance(row, Mapping))
    if len(parsed) != len(rows):
        raise ValueError("selection manifest rows must contain mappings")
    ordinals = [row.get("ordinal") for row in parsed]
    if len(set(ordinals)) != len(parsed):
        raise ValueError("selection manifest row ordinals must be unique")
    if require_selected_cohort and (len(parsed) != 10 or len({row.get("subject_id") for row in parsed}) != 5):
        raise ValueError("the selected T3 cohort must contain ten rows and five subjects")
    return tuple(sorted(parsed, key=lambda row: int(row["ordinal"])))


def bind_selected_manifest(
    manifest: Mapping[str, Any] | str | Path,
    *,
    existing: Mapping[str, Any] | None = None,
    representation_bytes: Mapping[str, bytes] | Callable[[str], bytes] | None = None,
    coverage_records: Iterable[Mapping[str, Any]] = (),
    as_of: date = date(2026, 11, 1),
    require_selected_cohort: bool = True,
) -> ExactRepresentationRightsBindingResult:
    """Bind existing exact material and lower only fully governed rows.

    ``existing`` is metadata from an existing catalogue/store, not an input
    source.  The optional byte reader verifies an already-retained
    representation but is never persisted or returned.
    """
    selected = _load_manifest(manifest)
    rows = _manifest_rows(selected, require_selected_cohort=require_selected_cohort)
    supplied = dict(existing or {})
    source_records = {item["id"]: item for item in _lookup_entries(supplied.get("source_records"), "source record")}
    receipts = {item["id"]: item for item in _lookup_entries(supplied.get("acquisition_receipts"), "acquisition receipt")}
    representations = {item["id"]: item for item in _lookup_entries(supplied.get("representations"), "representation")}
    scopes = {item["id"]: item for item in _lookup_entries(supplied.get("scopes"), "scope")}
    rights_by_rep: dict[str, dict[str, Mapping[str, Any]]] = {}
    for item in _lookup_entries(supplied.get("rights_decisions"), "rights decision"):
        rep_id = item.get("representation_artifact_id") or item.get("representation_id")
        if rep_id is None:
            raise ValueError("rights decision must identify a representation artifact")
        rep_id = _text(rep_id, "rights decision representation_artifact_id")
        axes = item.get("axes")
        if not isinstance(axes, Mapping):
            axes = {
                "local_retention": item.get("local_retention"),
                "private_provider_processing": item.get("private_provider_processing") or item.get("provider_transmission"),
                "public_redistribution": item.get("public_redistribution"),
            }
        bucket = rights_by_rep.setdefault(rep_id, {})
        for axis in AXES:
            raw = axes.get(axis)
            if raw is not None:
                if hasattr(raw, "model_dump"):
                    raw = raw.model_dump(mode="python")
                raw = dict(raw)
                raw.setdefault("representation_sha256", item.get("representation_sha256"))
                raw.setdefault("assessed_on", item.get("assessed_on"))
                raw.setdefault("assessed_authority", item.get("assessed_authority") or item.get("actor_id"))
                raw.setdefault("review_deadline", item.get("review_deadline") or item.get("retention_review_due_on") or item.get("expires_on"))
                raw.setdefault("lawful_public_access", item.get("lawful_public_access", item.get("lawful_access_confirmed")))
                raw.setdefault("circumvention_used", item.get("circumvention_used"))
                raw.setdefault("explicit_prohibition_found", item.get("explicit_prohibition_found"))
                if axis in bucket:
                    raise ValueError(f"duplicate/conflicting {axis} decision for {rep_id}")
                bucket[axis] = raw
                if item.get("decision_id") and bucket[axis].get("decision_id") is None:
                    bucket[axis]["decision_id"] = item["decision_id"]
    safe_coverage = tuple(sorted((_json_safe(dict(item)) for item in coverage_records), key=lambda item: canonical_json_bytes(item)))
    output: list[ExactBindingRow] = []
    claim_family_id = _text(supplied.get("claim_family_id", "g4-t3-exact-representation-rights-binding-v1"), "claim_family_id")
    task_profile = _text(supplied.get("task_profile", "g4_t3_exact_representation_binding"), "task_profile")

    for raw in rows:
        ordinal = int(raw["ordinal"])
        subject_id = _text(raw.get("subject_id"), f"row {ordinal} subject_id")
        family = _text(raw.get("source_family"), f"row {ordinal} source_family")
        role = _text(raw.get("source_role"), f"row {ordinal} source_role")
        source_definition_id = _text(raw.get("source_definition_id"), f"row {ordinal} source_definition_id")
        source_record_id = _text(raw.get("source_record_id"), f"row {ordinal} source_record_id")
        source_artifact_id = _text(raw.get("source_artifact_id"), f"row {ordinal} source_artifact_id")
        source_sha = _sha(raw.get("source_sha256"), f"row {ordinal} source_sha256")
        scope_id = raw.get("scope_id")
        scope_id = None if scope_id is None else _text(scope_id, f"row {ordinal} scope_id")
        receipt_id = _text(raw.get("acquisition_receipt_id"), f"row {ordinal} acquisition_receipt_id")
        local = AxisDecision.from_mapping("local_retention", None)
        provider = AxisDecision.from_mapping("private_provider_processing", None)
        public = AxisDecision.from_mapping("public_redistribution", None)
        reasons: list[str] = []
        if family not in ADMITTED_SOURCE_FAMILIES:
            reasons.append("unauthorized_source_family")
        if family not in {"acnc_register", "acnc_ais_bundle"} and require_selected_cohort:
            reasons.append("selected_manifest_source_family_mismatch")
        source = source_records.get(source_record_id)
        if source is None:
            reasons.append("source_record_not_observed")
        else:
            source_material = source.get("material") if isinstance(source.get("material"), Mapping) else {}
            about = set(source.get("about_subject_ids") or source.get("subject_ids") or source_material.get("about_subject_ids") or ())
            if source.get("source_family") != family or source.get("source_role") != role:
                reasons.append("source_record_identity_mismatch")
            if subject_id not in about:
                reasons.append("source_record_cross_subject")
            if source.get("payload_ref") != source_artifact_id or source.get("payload_hash") != source_sha:
                reasons.append("source_object_hash_or_lineage_mismatch")
        receipt = receipts.get(receipt_id)
        if receipt is None:
            reasons.append("acquisition_receipt_not_observed")
        else:
            if receipt.get("source_definition_id") != source_definition_id:
                reasons.append("acquisition_source_definition_mismatch")
            if receipt.get("artifact_id") != source_artifact_id or receipt.get("content_hash") != source_sha:
                reasons.append("acquisition_source_sha_mismatch")
            if receipt.get("outcome") not in {"available", "partial"}:
                reasons.append("acquisition_not_available")
        scope = scopes.get(scope_id) if scope_id else None
        if scope_id and scope is None:
            reasons.append("governed_scope_not_observed")
        elif scope is not None and scope.get("subject_id") != subject_id:
            reasons.append("cross_subject_scope_substitution")

        representation_id: str | None = None
        representation_sha: str | None = None
        representation_class: str | None = None
        rep = representations.get(raw.get("representation_artifact_id"))
        if rep is None:
            reasons.append("exact_representation_not_observed")
        else:
            representation_id = _text(rep.get("artifact_id", rep.get("id")), f"row {ordinal} representation_artifact_id")
            representation_sha = _sha(rep.get("content_hash"), f"row {ordinal} representation_sha256")
            if representation_id == source_artifact_id or representation_sha == source_sha:
                reasons.append("source_sha_substituted_for_representation")
            if rep.get("source_artifact_id") != source_artifact_id or rep.get("subject_id") != subject_id:
                reasons.append("representation_lineage_or_subject_mismatch")
            if scope_id and rep.get("scope_id") != scope_id:
                reasons.append("representation_scope_mismatch")
            representation_class = rep.get("representation_class")
            content = rep.get("content")
            if content is not None:
                if not isinstance(content, bytes):
                    reasons.append("representation_bytes_invalid")
                elif _sha256(content) != representation_sha:
                    reasons.append("representation_bytes_sha_mismatch")
            elif representation_bytes is not None:
                try:
                    content = representation_bytes[representation_id] if isinstance(representation_bytes, Mapping) else representation_bytes(representation_id)
                except (KeyError, FileNotFoundError, OSError, ValueError):
                    content = None
                if content is None:
                    reasons.append("representation_bytes_not_observed")
                elif not isinstance(content, bytes) or _sha256(content) != representation_sha:
                    reasons.append("representation_bytes_sha_mismatch")
            else:
                reasons.append("representation_bytes_not_observed")
            if representation_class not in REPRESENTATION_CLASSES:
                reasons.append("representation_class_not_demonstrated")

        axis_bucket = rights_by_rep.get(representation_id or "", {})
        local = AxisDecision.from_mapping("local_retention", axis_bucket.get("local_retention"))
        provider = AxisDecision.from_mapping("private_provider_processing", axis_bucket.get("private_provider_processing"))
        public = AxisDecision.from_mapping("public_redistribution", axis_bucket.get("public_redistribution"))
        for axis, decision in (("local_retention", local), ("private_provider_processing", provider), ("public_redistribution", public)):
            if decision.status in {"blocked", "revoked", "superseded", "stale", "conflict"}:
                label = "provider_decision" if axis == "private_provider_processing" else axis + "_decision"
                reasons.append(f"{label}_{decision.status}")
        if representation_sha and representation_class in REPRESENTATION_CLASSES:
            for axis, decision in (("local_retention", local), ("private_provider_processing", provider), ("public_redistribution", public)):
                if decision.status == "authorized":
                    reasons.extend(f"{axis}:{reason}" for reason in decision.validate(representation_sha256=representation_sha, representation_class=representation_class, as_of=as_of))
        if representation_id and representation_id not in rights_by_rep:
            reasons.append("rights_decisions_not_observed")
        local_ok = local.status == "authorized" and not any(reason.startswith("local_retention:") for reason in reasons)
        provider_ok = provider.status == "authorized" and not any(reason.startswith("private_provider_processing:") for reason in reasons)
        if local.status == "authorized" and not local_ok:
            reasons.append("local_retention_decision_invalid")
        if provider.status == "authorized" and not provider_ok:
            reasons.append("provider_decision_invalid")
        status: RowStatus
        if reasons:
            status = "BLOCKED" if any(
                token in reason
                for reason in reasons
                for token in ("mismatch", "prohibition", "unauthorized", "conflict", "stale", "revoked", "superseded", "not_authorized")
            ) else "NOT_OBSERVED"
        elif local_ok and provider_ok:
            status = "BOUND"
        else:
            status = "NOT_OBSERVED"
        reference = None
        if status == "BOUND":
            # Evidence locator IDs are supplied by the existing authority.  An
            # empty value is intentionally not lowered to a task: the current
            # preflight contract requires a durable locator.
            locator_ids = tuple(str(item) for item in (rep.get("evidence_locator_ids") or ())) if rep else ()
            if not locator_ids:
                status = "NOT_OBSERVED"
                reasons.append("evidence_locator_not_observed")
            else:
                reference = GovernedReference(
                    reference_id=f"g4-t3-exact-binding:{ordinal:02d}",
                    subject_id=subject_id,
                    scope_id=scope_id,
                    source_family=family,
                    source_definition_id=_text(raw.get("source_definition_id"), f"row {ordinal} source_definition_id"),
                    acquisition_receipt_ids=(receipt_id,),
                    source_record_ids=(source_record_id,),
                    evidence_locator_ids=locator_ids,
                    representation_artifact_ids=(representation_id,),
                    representation_hashes={representation_id: representation_sha},
                    rights_decision_ids=(provider.decision_id,),
                    rights_policy_id=provider.policy_id,
                    rights_policy_version=provider.policy_version,
                    rights_role=role,
                    provider_processing_policy_id=provider.provider_policy_id,
                    provider_processing_policy_version=provider.provider_policy_version,
                    claim_family_id=claim_family_id,
                    task_profile=task_profile,
                )
        output.append(ExactBindingRow(
            ordinal=ordinal,
            subject_id=subject_id,
            scope_id=scope_id,
            source_family=family,
            source_role=role,
            source_definition_id=source_definition_id,
            source_record_id=source_record_id,
            source_artifact_id=source_artifact_id,
            source_sha256=source_sha,
            acquisition_receipt_ids=(receipt_id,),
            representation_artifact_id=representation_id,
            representation_sha256=representation_sha,
            representation_class=representation_class,
            local_retention=local,
            private_provider_processing=provider,
            public_redistribution=public,
            status=status,
            reasons=tuple(dict.fromkeys(reasons)),
            governed_reference=reference,
        ))
    output.sort(key=lambda item: item.ordinal)
    payload = {
        "schema": BINDER_SCHEMA,
        "selected_manifest_sha256": SELECTED_MANIFEST_SHA256,
        "rows": [row.as_dict() for row in output],
        "coverage_records": list(safe_coverage),
    }
    digest = _sha256(canonical_json_bytes(payload))
    return ExactRepresentationRightsBindingResult(
        schema=BINDER_SCHEMA,
        selected_manifest_sha256=SELECTED_MANIFEST_SHA256,
        rows=tuple(output),
        coverage_records=safe_coverage,
        canonical_hash=digest,
    )


bind_t3_exact_representation_rights = bind_selected_manifest

__all__ = [
    "ADMITTED_SOURCE_FAMILIES",
    "AxisDecision",
    "BINDER_SCHEMA",
    "ExactBindingRow",
    "ExactRepresentationRightsBindingResult",
    "SELECTED_MANIFEST_SHA256",
    "bind_selected_manifest",
    "bind_t3_exact_representation_rights",
]
