"""Provider-free ACNC source/evidence/rights binding for the bounded T3 task.

The adapter consumes already-retained catalogue metadata and representation
bytes.  It does not acquire sources, resolve identities from names or ABNs,
interpret prose, call a model, or send material.  A row is lowered to the
existing :class:`GovernedReference` contract only after the source receipt,
durable subject/scope, exact representation bytes, citation and per-use rights
decisions all agree.
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
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
    governed_rights_policy,
)


BINDER_SCHEMA = "charitygraph.gate4.t3.acnc-source-evidence-binding/v1"
SOURCE_UNIVERSE_VERSION = "v1"
RIGHTS_DECISION_VERSION = "1"
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
PUBLIC_FACTS_ONLY_POLICY_ID = "PUBLIC_FACTS_ONLY_V1"
AXES = ("local_retention", "private_provider_processing", "public_redistribution")
_AVAILABLE_OUTCOMES = {"available", "partial"}

RowStatus = Literal["BOUND", "BLOCKED", "MISSING"]
ObservationKind = Literal["observation", "candidate", "missingness"]


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
    return value.lower()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe(value: Any) -> Any:
    if isinstance(value, bytes):
        raise ValueError("raw/private bytes are not binding metadata")
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"unsupported binding metadata value: {type(value).__name__}")


def _entries(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        source = []
        for key, item in value.items():
            if not isinstance(item, Mapping):
                raise ValueError(f"{label} entry {key!r} is not a mapping")
            row = dict(item)
            row.setdefault("id", str(key))
            source.append(row)
    elif isinstance(value, (list, tuple)):
        if any(not isinstance(item, Mapping) for item in value):
            raise ValueError(f"{label} must contain mappings")
        source = [dict(item) for item in value]
    else:
        raise ValueError(f"{label} must be a mapping or sequence of mappings")
    result: dict[str, dict[str, Any]] = {}
    for item in source:
        identifier = item.get("id") or item.get("record_id") or item.get("artifact_id") or item.get("decision_id")
        identifier = _text(identifier, f"{label}.id")
        if identifier in result:
            raise ValueError(f"duplicate {label} identity: {identifier}")
        item["id"] = identifier
        result[identifier] = item
    return result


def _load_rows(rows: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(rows, (str, Path)):
        rows = json.loads(Path(rows).read_text(encoding="utf-8"))
    if isinstance(rows, Mapping):
        if "rows" not in rows or not isinstance(rows["rows"], list):
            raise ValueError("ACNC binding input must contain a rows list")
        rows = rows["rows"]
    if not isinstance(rows, (list, tuple)) or any(not isinstance(item, Mapping) for item in rows):
        raise ValueError("ACNC binding rows must be mappings")
    result = tuple(dict(item) for item in rows)
    ordinals = [item.get("ordinal") for item in result]
    if any(not isinstance(item, int) for item in ordinals) or len(set(ordinals)) != len(ordinals):
        raise ValueError("ACNC binding row ordinals must be unique integers")
    return tuple(sorted(result, key=lambda item: item["ordinal"]))


def _bytes_reader(
    representations: Mapping[str, Mapping[str, Any]],
    retained_bytes: Mapping[str, bytes] | Callable[[str], bytes] | None,
    artifact_id: str,
) -> bytes | None:
    item = representations.get(artifact_id, {})
    if "content" in item:
        content = item["content"]
        return content if isinstance(content, bytes) else None
    if retained_bytes is None:
        return None
    try:
        value = retained_bytes[artifact_id] if isinstance(retained_bytes, Mapping) else retained_bytes(artifact_id)
    except (KeyError, FileNotFoundError, OSError, ValueError):
        return None
    return value if isinstance(value, bytes) else None


def _scope_identity(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("evidence_scope must be a mapping")
    return _safe(dict(value))


def _decision_map(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        items = []
        for key, raw in value.items():
            if not isinstance(raw, Mapping):
                raise ValueError(f"rights decision {key!r} is not a mapping")
            item = dict(raw)
            item.setdefault("axis", str(key))
            items.append(item)
    elif isinstance(value, (list, tuple)):
        if any(not isinstance(item, Mapping) for item in value):
            raise ValueError("rights_decisions must contain mappings")
        items = [dict(item) for item in value]
    else:
        raise ValueError("rights_decisions must be a mapping or sequence")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        axis = _text(item.get("axis"), "rights decision axis")
        if axis not in AXES:
            raise ValueError(f"unsupported rights decision axis: {axis}")
        if axis in result:
            raise ValueError(f"duplicate rights decision axis: {axis}")
        result[axis] = item
    return result


def _policy_ok(axis: str, decision: Mapping[str, Any]) -> bool:
    policy_id = decision.get("policy_id")
    policy_version = decision.get("policy_version")
    if axis == "local_retention":
        return policy_id == LOCAL_RETENTION_POLICY_ID and policy_version == LOCAL_RETENTION_POLICY_VERSION
    if axis == "private_provider_processing":
        return (
            policy_id == PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID
            and policy_version == "1.0.0"
            and decision.get("provider_policy_id") == OPENAI_PROVIDER_POLICY_ID
            and decision.get("provider_policy_version") == "1"
        )
    if axis == "public_redistribution":
        return governed_rights_policy(str(policy_id), policy_version) is not None or policy_id == PUBLIC_FACTS_ONLY_POLICY_ID
    return False


def _decision_reasons(
    axis: str,
    decision: Mapping[str, Any] | None,
    *,
    source_artifact_id: str,
    source_record_id: str,
    representation_artifact_id: str,
    representation_sha256: str,
    scope_id: str | None,
    as_of: date,
) -> tuple[str, ...]:
    if decision is None:
        return (f"{axis}_rights_decision_not_observed",)
    reasons: list[str] = []
    if decision.get("source_artifact_id") != source_artifact_id or decision.get("source_record_id") != source_record_id:
        reasons.append("rights_source_lineage_mismatch")
    if decision.get("representation_artifact_id") != representation_artifact_id:
        reasons.append("rights_representation_identity_mismatch")
    if decision.get("representation_sha256") != representation_sha256:
        reasons.append("rights_representation_sha_mismatch")
    if scope_id is not None and decision.get("scope_id") != scope_id:
        reasons.append("rights_scope_mismatch")
    if decision.get("decision_version", RIGHTS_DECISION_VERSION) != RIGHTS_DECISION_VERSION:
        reasons.append("rights_decision_version_mismatch")
    status = decision.get("status")
    if status != "authorized":
        reasons.append(f"{axis}_rights_{status or 'not_observed'}")
    if not _policy_ok(axis, decision):
        reasons.append(f"{axis}_rights_policy_version_mismatch")
    if not _text(decision.get("decision_id"), f"{axis}.decision_id"):
        reasons.append(f"{axis}_rights_decision_id_missing")
    if decision.get("assessed_on") is None or decision.get("review_deadline") is None:
        reasons.append(f"{axis}_rights_dates_missing")
    else:
        try:
            assessed = date.fromisoformat(str(decision["assessed_on"]))
            deadline = date.fromisoformat(str(decision["review_deadline"]))
        except ValueError:
            reasons.append(f"{axis}_rights_date_invalid")
        else:
            if deadline < assessed or deadline < as_of:
                reasons.append(f"{axis}_rights_stale")
    if decision.get("authority_kind") in {"provider", "provider_owned", "provider_metadata"}:
        reasons.append("provider_owned_rights_metadata_not_authority")
    if decision.get("lawful_public_access") is not True:
        reasons.append(f"{axis}_lawful_access_not_confirmed")
    if decision.get("circumvention_used") is not False:
        reasons.append(f"{axis}_circumvention_not_excluded")
    if decision.get("explicit_prohibition_found") is not False:
        reasons.append(f"{axis}_explicit_prohibition_not_excluded")
    if axis == "private_provider_processing":
        if decision.get("provider_no_training_default") is not True:
            reasons.append("provider_no_training_condition_missing")
        if decision.get("provider_data_sharing_opt_in") is not False:
            reasons.append("provider_data_sharing_condition_missing")
    return tuple(dict.fromkeys(reasons))


@dataclass(frozen=True)
class SourceEvidenceBindingRow:
    ordinal: int
    subject_id: str
    scope_id: str | None
    original_evidence_scope: Mapping[str, Any] | None
    source_family: str
    source_role: str
    source_definition_id: str
    source_record_id: str
    source_artifact_id: str
    source_sha256: str
    acquisition_receipt_id: str
    acquisition_status: str | None
    representation_artifact_id: str | None
    representation_sha256: str | None
    citation_locator: str | None
    date_or_period: str | None
    observation_kind: ObservationKind
    status: RowStatus
    decision_or_evidence_deficit: tuple[str, ...]
    governed_reference: GovernedReference | None = None

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.decision_or_evidence_deficit

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "original_evidence_scope": dict(self.original_evidence_scope) if self.original_evidence_scope else None,
            "source_family": self.source_family,
            "source_role": self.source_role,
            "source_definition_id": self.source_definition_id,
            "source_record_id": self.source_record_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "acquisition_receipt_id": self.acquisition_receipt_id,
            "acquisition_status": self.acquisition_status,
            "representation_artifact_id": self.representation_artifact_id,
            "representation_sha256": self.representation_sha256,
            "citation_locator": self.citation_locator,
            "date_or_period": self.date_or_period,
            "observation_kind": self.observation_kind,
            "status": self.status,
            "decision_or_evidence_deficit": list(self.decision_or_evidence_deficit),
        }


@dataclass(frozen=True)
class SourceEvidenceBindingResult:
    schema: str
    source_universe_version: str
    input_manifest_sha256: str
    rows: tuple[SourceEvidenceBindingRow, ...]
    canonical_hash: str

    @property
    def bound_count(self) -> int:
        return sum(row.status == "BOUND" for row in self.rows)

    @property
    def observed_count(self) -> int:
        return sum(row.observation_kind == "observation" and row.status == "BOUND" for row in self.rows)

    @property
    def candidate_count(self) -> int:
        return sum(row.observation_kind == "candidate" for row in self.rows)

    @property
    def missing_count(self) -> int:
        return sum(row.observation_kind == "missingness" for row in self.rows)

    @property
    def all_ten_missing(self) -> bool:
        return len(self.rows) == 10 and self.bound_count == 0 and self.missing_count == 10

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_universe_version": self.source_universe_version,
            "input_manifest_sha256": self.input_manifest_sha256,
            "rows": [row.as_dict() for row in self.rows],
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_payload())


def bind_acnc_source_evidence(
    rows: Any,
    *,
    existing: Mapping[str, Any] | None = None,
    retained_bytes: Mapping[str, bytes] | Callable[[str], bytes] | None = None,
    as_of: date = date(2026, 11, 1),
    require_five_subject_ten_rows: bool = False,
) -> SourceEvidenceBindingResult:
    """Validate retained ACNC rows and lower verified observations to Factory refs.

    ``existing`` is catalogue metadata only.  It may contain ``subjects``,
    ``scopes``, ``source_definitions``, ``source_records``,
    ``acquisition_receipts``, ``representations`` and ``rights_decisions``.
    Bytes are read only for SHA verification and never returned or persisted.
    """
    raw_input = json.loads(Path(rows).read_text(encoding="utf-8")) if isinstance(rows, (str, Path)) else rows
    row_items = _load_rows(raw_input)
    if require_five_subject_ten_rows and (len(row_items) != 10 or len({item.get("subject_id") for item in row_items}) != 5):
        raise ValueError("the T3 acceptance harness requires ten rows across five durable subjects")
    supplied = dict(existing or {})
    subjects = _entries(supplied.get("subjects") or supplied.get("subject_records"), "subject")
    scopes = _entries(supplied.get("scopes"), "scope")
    source_definitions = _entries(supplied.get("source_definitions"), "source definition")
    source_records = _entries(supplied.get("source_records"), "source record")
    receipts = _entries(supplied.get("acquisition_receipts"), "acquisition receipt")
    representations = _entries(supplied.get("representations"), "representation")
    rights = _entries(supplied.get("rights_decisions"), "rights decision")
    rights_by_rep: dict[str, dict[str, dict[str, Any]]] = {}
    rights_decision_ids: dict[str, str] = {}
    for item in rights.values():
        rep_id = item.get("representation_artifact_id") or item.get("representation_id")
        if rep_id is None:
            raise ValueError("rights decision must identify a representation artifact")
        axis = _text(item.get("axis"), "rights decision axis")
        bucket = rights_by_rep.setdefault(_text(rep_id, "rights representation_artifact_id"), {})
        if axis in bucket:
            raise ValueError(f"duplicate rights decision axis for {rep_id}: {axis}")
        decision_id = item.get("decision_id")
        if decision_id:
            prior = rights_decision_ids.get(str(decision_id))
            if prior is not None and prior != str(rep_id):
                raise ValueError("rights decision reused across unrelated representations")
            rights_decision_ids[str(decision_id)] = str(rep_id)
        bucket[axis] = item

    manifest_metadata = raw_input if isinstance(raw_input, Mapping) else {}
    source_policy_version = manifest_metadata.get("source_universe_version", SOURCE_UNIVERSE_VERSION)
    if isinstance(raw_input, Mapping):
        manifest_for_hash = dict(raw_input)
        manifest_for_hash["rows"] = list(row_items)
    else:
        manifest_for_hash = list(row_items)
    manifest_bytes = canonical_json_bytes(_safe(manifest_for_hash))
    manifest_hash = _digest(manifest_bytes)
    duplicate_records: set[str] = set()
    duplicate_artifacts: set[str] = set()
    seen_records: dict[str, int] = {}
    seen_artifacts: dict[str, int] = {}
    for item in row_items:
        record_id = item.get("source_record_id")
        artifact_id = item.get("source_artifact_id")
        if record_id in seen_records:
            duplicate_records.update({str(record_id)})
        elif record_id is not None:
            seen_records[str(record_id)] = int(item["ordinal"])
        if artifact_id in seen_artifacts:
            duplicate_artifacts.update({str(artifact_id)})
        elif artifact_id is not None:
            seen_artifacts[str(artifact_id)] = int(item["ordinal"])

    output: list[SourceEvidenceBindingRow] = []
    for item in row_items:
        ordinal = int(item["ordinal"])
        subject_id = _text(item.get("subject_id"), f"row {ordinal} subject_id")
        scope_id = item.get("scope_id")
        scope_id = None if scope_id is None else _text(scope_id, f"row {ordinal} scope_id")
        family = _text(item.get("source_family"), f"row {ordinal} source_family")
        role = _text(item.get("source_role"), f"row {ordinal} source_role")
        source_definition_id = _text(item.get("source_definition_id"), f"row {ordinal} source_definition_id")
        source_record_id = _text(item.get("source_record_id"), f"row {ordinal} source_record_id")
        source_artifact_id = _text(item.get("source_artifact_id"), f"row {ordinal} source_artifact_id")
        source_sha256 = _sha(item.get("source_sha256"), f"row {ordinal} source_sha256")
        receipt_id = _text(item.get("acquisition_receipt_id"), f"row {ordinal} acquisition_receipt_id")
        requested_kind = item.get("observation_kind", item.get("epistemic_status"))
        if requested_kind is None:
            requested_kind = "observation"
        if requested_kind not in {"observation", "candidate", "missingness"}:
            raise ValueError(f"row {ordinal} observation_kind is unsupported")
        kind: ObservationKind = requested_kind
        reasons: list[str] = []
        if source_policy_version != SOURCE_UNIVERSE_VERSION:
            reasons.append("source_policy_version_mismatch")
        if family not in ADMITTED_SOURCE_FAMILIES:
            reasons.append("unauthorized_source_family")
        subject = subjects.get(subject_id)
        if subject is None:
            reasons.append("durable_subject_not_observed")
        elif subject.get("subject_id", subject.get("id")) != subject_id:
            reasons.append("durable_subject_identity_mismatch")
        if item.get("abn") and subject is None:
            reasons.append("abn_is_not_subject_identity")
        scope = scopes.get(scope_id) if scope_id else None
        if scope_id and scope is None:
            reasons.append("durable_scope_not_observed")
        elif scope is not None and scope.get("subject_id") != subject_id:
            reasons.append("cross_subject_scope_substitution")
        source = source_records.get(source_record_id)
        original_scope = _scope_identity(source.get("evidence_scope")) if source else None
        if source is None:
            reasons.append("source_record_not_observed")
        else:
            about = source.get("about_subject_ids") or source.get("subject_ids") or []
            if not isinstance(about, (list, tuple, set)) or subject_id not in about:
                reasons.append("source_record_wrong_subject")
            if source.get("subject_id") is not None and source.get("subject_id") != subject_id:
                reasons.append("source_record_wrong_subject")
            destinations = source.get("destination_subject_ids")
            if source.get("binding_status") == "ambiguous" or source.get("destination_status") == "ambiguous":
                reasons.append("ambiguous_destination")
            if len(about) != 1 or isinstance(destinations, (list, tuple, set)) and len(destinations) != 1:
                reasons.append("ambiguous_destination")
            if source.get("source_family") != family or source.get("source_role") != role:
                reasons.append("source_record_identity_mismatch")
            if source.get("payload_ref") != source_artifact_id or source.get("payload_hash") != source_sha256:
                reasons.append("source_object_hash_or_lineage_mismatch")
            requested_scope = _scope_identity(item.get("evidence_scope"))
            if requested_scope is not None and original_scope != requested_scope:
                reasons.append("original_evidence_scope_mismatch")
            if scope_id is not None and (original_scope is None or original_scope.get("scope_id") != scope_id):
                reasons.append("cross_scope_source_substitution")
            source_content = _bytes_reader({}, retained_bytes, source_artifact_id)
            if source_content is None:
                reasons.append("source_bytes_not_observed")
            elif _digest(source_content) != source_sha256:
                reasons.append("source_bytes_sha_mismatch")
        if source_record_id in duplicate_records or source_artifact_id in duplicate_artifacts:
            reasons.append("duplicate_source")
        source_definition = source_definitions.get(source_definition_id)
        if source_definition is None:
            reasons.append("source_definition_not_observed")
        receipt = receipts.get(receipt_id)
        acquisition_status = None if receipt is None else receipt.get("outcome", receipt.get("status"))
        if receipt is None:
            reasons.append("acquisition_receipt_not_observed")
        else:
            if receipt.get("source_definition_id") != source_definition_id:
                reasons.append("acquisition_source_definition_mismatch")
            if receipt.get("artifact_id") != source_artifact_id or receipt.get("content_hash") != source_sha256:
                reasons.append("acquisition_source_sha_mismatch")
            if acquisition_status not in _AVAILABLE_OUTCOMES:
                reasons.append(f"acquisition_{acquisition_status or 'status_not_observed'}")
            if receipt.get("status") in {"stale", "expired"} or receipt.get("expires_on") and str(receipt["expires_on"]) < as_of.isoformat():
                reasons.append("acquisition_receipt_stale")

        representation_id: str | None = None
        representation_sha: str | None = None
        citation_locator = item.get("citation_locator")
        date_or_period = item.get("date_or_period")
        rep = None
        if item.get("representation_artifact_id") is not None:
            representation_id = _text(item.get("representation_artifact_id"), f"row {ordinal} representation_artifact_id")
            rep = representations.get(representation_id)
        if rep is None:
            reasons.append("representation_not_observed")
        else:
            representation_sha = _sha(rep.get("content_hash"), f"row {ordinal} representation_sha256")
            if representation_id == source_artifact_id or representation_sha == source_sha256:
                reasons.append("source_sha_substituted_for_representation")
            if rep.get("source_artifact_id") != source_artifact_id or rep.get("source_record_id") not in {None, source_record_id}:
                reasons.append("representation_source_lineage_mismatch")
            if rep.get("subject_id") != subject_id:
                reasons.append("representation_wrong_subject")
            if scope_id is not None and rep.get("scope_id") != scope_id:
                reasons.append("representation_scope_mismatch")
            content = _bytes_reader(representations, retained_bytes, representation_id)
            if content is None:
                reasons.append("representation_bytes_not_observed")
            elif _digest(content) != representation_sha:
                reasons.append("representation_bytes_sha_mismatch")
            citation_locator = citation_locator or rep.get("citation_locator") or rep.get("source_locator")
            date_or_period = date_or_period or rep.get("date_or_period") or rep.get("period")
            if not rep.get("evidence_locator_ids"):
                reasons.append("evidence_locator_not_observed")
            if rep.get("representation_class") not in {"structured_factual", "bounded_excerpt"}:
                reasons.append("representation_class_not_governed")
        if source is not None:
            citation_locator = citation_locator or source.get("source_locator") or source.get("citation_locator")
            date_or_period = date_or_period or source.get("date_or_period") or source.get("period")
        if citation_locator is not None and (not isinstance(citation_locator, str) or not citation_locator.strip()):
            reasons.append("citation_locator_invalid")
        elif citation_locator is None:
            reasons.append("citation_locator_not_observed")
        if kind == "observation" and (source is None or receipt is None or rep is None):
            # A row selected for assessment but lacking an observed source,
            # receipt or representation is an explicit coverage state, not a
            # failed observation and never a successful binding.
            kind = "missingness"
        if kind == "candidate":
            reasons.append("candidate_requires_governance")
        if kind == "missingness":
            if "explicit_missingness" not in reasons:
                reasons.append("explicit_missingness")

        provider_decision_id: str | None = None
        provider_policy_id: str | None = None
        provider_policy_version: str | None = None
        decision_bucket = rights_by_rep.get(representation_id or "", {})
        for axis in AXES:
            axis_reasons = _decision_reasons(
                axis,
                decision_bucket.get(axis),
                source_artifact_id=source_artifact_id,
                source_record_id=source_record_id,
                representation_artifact_id=representation_id or "unresolved",
                representation_sha256=representation_sha or "0" * 64,
                scope_id=scope_id,
                as_of=as_of,
            )
            if axis in {"local_retention", "private_provider_processing"}:
                reasons.extend(axis_reasons)
            if axis == "private_provider_processing" and decision_bucket.get(axis):
                provider_decision_id = decision_bucket[axis].get("decision_id")
                provider_policy_id = decision_bucket[axis].get("policy_id")
                provider_policy_version = decision_bucket[axis].get("policy_version")
        if not reasons:
            reference = GovernedReference(
                reference_id=f"g4-t3-acnc-source-binding:{ordinal:02d}",
                subject_id=subject_id,
                scope_id=scope_id,
                source_family=family,
                source_definition_id=source_definition_id,
                acquisition_receipt_ids=(receipt_id,),
                source_record_ids=(source_record_id,),
                evidence_locator_ids=tuple(rep.get("evidence_locator_ids") or ()),
                representation_artifact_ids=(representation_id,),
                representation_hashes={representation_id: representation_sha},
                rights_decision_ids=(str(provider_decision_id),),
                rights_policy_id=provider_policy_id,
                rights_policy_version=provider_policy_version,
                rights_role=role,
                provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
                provider_processing_policy_version="1",
                claim_family_id="g4-t3-acnc-source-evidence-binding-v1",
                task_profile="g4_t3_acnc_source_evidence_binding",
            )
            status: RowStatus = "BOUND"
        else:
            reference = None
            status = "BLOCKED" if any(
                token in reason
                for reason in reasons
                for token in ("mismatch", "wrong", "ambiguous", "duplicate", "unauthorized", "blocked", "stale", "prohibition", "candidate", "policy_version")
            ) else "MISSING"
            if kind == "missingness":
                status = "MISSING"
        output.append(SourceEvidenceBindingRow(
            ordinal=ordinal,
            subject_id=subject_id,
            scope_id=scope_id,
            original_evidence_scope=original_scope,
            source_family=family,
            source_role=role,
            source_definition_id=source_definition_id,
            source_record_id=source_record_id,
            source_artifact_id=source_artifact_id,
            source_sha256=source_sha256,
            acquisition_receipt_id=receipt_id,
            acquisition_status=acquisition_status,
            representation_artifact_id=representation_id,
            representation_sha256=representation_sha,
            citation_locator=citation_locator if isinstance(citation_locator, str) else None,
            date_or_period=date_or_period if isinstance(date_or_period, str) else None,
            observation_kind=kind,
            status=status,
            decision_or_evidence_deficit=tuple(dict.fromkeys(reasons)),
            governed_reference=reference,
        ))
    payload = {
        "schema": BINDER_SCHEMA,
        "source_universe_version": SOURCE_UNIVERSE_VERSION,
        "input_manifest_sha256": manifest_hash,
        "rows": [row.as_dict() for row in output],
    }
    return SourceEvidenceBindingResult(
        schema=BINDER_SCHEMA,
        source_universe_version=SOURCE_UNIVERSE_VERSION,
        input_manifest_sha256=manifest_hash,
        rows=tuple(output),
        canonical_hash=_digest(canonical_json_bytes(payload)),
    )


bind_t3_acnc_source_evidence = bind_acnc_source_evidence

__all__ = [
    "ADMITTED_SOURCE_FAMILIES",
    "BINDER_SCHEMA",
    "SourceEvidenceBindingResult",
    "SourceEvidenceBindingRow",
    "bind_acnc_source_evidence",
    "bind_t3_acnc_source_evidence",
]
