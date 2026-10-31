"""Provider-free, fail-closed handoff from the accepted E3 brief to Factory.

The E3 brief remains a derivative.  This module only validates its retained
identities against a selected T3 manifest, reloads the current rights
authority through the existing governed-rights preflight, and returns the
resulting deterministic Factory plan.  It does not create evidence, rights,
canonical observations, provider requests, or publication state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Mapping

from .contracts.canonical import canonical_sha256
from .phase5_factory import FactoryPlan
from .phase5_governed_rights_preflight import (
    PreflightDiagnostic,
    RightsPreflightReference,
    preflight_governed_rights,
)
from .phase5_t4b_source_answer_projection import (
    MANIFEST_SCHEMA_PREFIX,
    QUESTION_ACTIVITY,
    QUESTION_CURRENTNESS,
    QUESTION_SCALE,
    SUPPORTED_SOURCE_FAMILIES,
)
from .phase5_t4c_private_answer_brief import PrivateAnswerBrief


BUILD_ID = "phase5-t4-e3-factory-handoff-v1"
ROUTE_POLICY_VERSION = "phase5-t4-e3-deterministic-route-v1"
TASK_IDENTITY = "g4_t4_e3_factory_handoff_v1"
SCHEMA_VERSION = "1"
TASK_PROFILE = TASK_IDENTITY
CLAIM_FAMILY = TASK_IDENTITY
_EXPECTED_E3_SIDE_EFFECT_KEYS = (
    "provider_calls",
    "transport_requests",
    "budget_reservations",
    "source_acquisitions",
    "publications",
    "sqlite_opens",
)
_MANIFEST_FIELDS = (
    "subject_id",
    "scope_id",
    "source_family",
    "source_role",
    "source_record_id",
    "representation_sha256",
    "rights_record_id",
    "rights_policy_id",
    "rights_policy_version",
    "provider_processing_status",
    "public_redistribution_status",
    "status",
    "source_definition_id",
    "acquisition_receipt_id",
    "evidence_locator_id",
)
_E3_FIELDS = (
    "subject_id",
    "scope_id",
    "source_family",
    "source_role",
    "source_record_id",
    "representation_sha256",
    "rights_record_id",
    "rights_policy_id",
    "rights_policy_version",
    "provider_processing_status",
    "public_redistribution_status",
    "binding_status",
)


@dataclass(frozen=True)
class E3FactoryHandoff:
    """Operational derivative returned by the bounded handoff."""

    tasks: tuple[dict[str, Any], ...]
    diagnostics: tuple[PreflightDiagnostic, ...]
    factory_plan: FactoryPlan
    summary: Mapping[str, Any]

    @property
    def accepted_count(self) -> int:
        return len(self.tasks)


def _diagnostic(
    state: str,
    reason: str,
    *details: str,
    subject_id: str = "unresolved",
    reference_id: str = TASK_IDENTITY,
) -> PreflightDiagnostic:
    return PreflightDiagnostic(
        reference_id=reference_id,
        subject_id=subject_id,
        state=state,  # type: ignore[arg-type]
        reason=reason,
        details=tuple(details),
    )


def _hex(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a SHA-256 value")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a SHA-256 value") from exc
    return value


def _text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manifest row is missing {key}")
    return value


def _validate_manifest(selected_manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if not isinstance(selected_manifest, Mapping):
        raise ValueError("selected T3 manifest must be a mapping")
    schema = selected_manifest.get("schema")
    if not isinstance(schema, str) or not schema.startswith(MANIFEST_SCHEMA_PREFIX):
        raise ValueError("unsupported T3 manifest schema")
    _hex(selected_manifest.get("selected_manifest_sha256"), "selected manifest identity")
    identity = selected_manifest.get("manifest_identity_sha256")
    if not isinstance(identity, str) or canonical_sha256(
        {key: value for key, value in selected_manifest.items() if key != "manifest_identity_sha256"}
    ) != identity:
        raise ValueError("canonical T3 manifest identity mismatch")
    raw_rows = selected_manifest.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != 10:
        raise ValueError("selected T3 manifest must contain exactly ten rows")

    rows: list[dict[str, Any]] = []
    ordinals: set[int] = set()
    tuples: set[tuple[str, str, str]] = set()
    subjects: dict[str, set[str]] = {}
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("selected T3 manifest row is not an object")
        row = dict(raw)
        for field in _MANIFEST_FIELDS:
            _text(row, field)
        try:
            ordinal = int(row.get("ordinal"))
        except (TypeError, ValueError) as exc:
            raise ValueError("manifest ordinal is invalid") from exc
        if ordinal in ordinals:
            raise ValueError("manifest ordinals are not unique")
        ordinals.add(ordinal)
        source_hash = _hex(row.get("source_sha256"), "source hash")
        representation_hash = _hex(row["representation_sha256"], "representation hash")
        if source_hash != representation_hash:
            raise ValueError("source and representation hashes do not match")
        if row["source_artifact_id"] != f"srcblob:{source_hash}":
            raise ValueError("source artifact identity does not match its hash")
        if row["representation_artifact_id"] != f"artifact:{representation_hash}":
            raise ValueError("representation artifact identity does not match its hash")
        if row["source_family"] not in SUPPORTED_SOURCE_FAMILIES:
            raise ValueError("manifest contains a non-admitted source family")
        binding = (row["source_record_id"], representation_hash, row["rights_record_id"])
        if binding in tuples:
            raise ValueError("manifest contains a duplicate source/representation/rights tuple")
        tuples.add(binding)
        subjects.setdefault(row["subject_id"], set()).add(row["source_family"])
        rows.append(row)
    if len(subjects) != 5 or any(families != set(SUPPORTED_SOURCE_FAMILIES) for families in subjects.values()):
        raise ValueError("selected T3 manifest must contain two admitted source families for five subjects")
    return tuple(sorted(rows, key=lambda row: int(row["ordinal"])))


def _brief_records(brief: PrivateAnswerBrief) -> tuple[Any, ...]:
    if not isinstance(brief, PrivateAnswerBrief):
        raise ValueError("accepted E3 input must be a PrivateAnswerBrief")
    if len(brief.subjects) != 5 or len({item.subject_id for item in brief.subjects}) != 5:
        raise ValueError("E3 brief must contain five unique subjects")
    if len(brief.answer_slots) != 15 or len(brief.north_star_coverage) != 20:
        raise ValueError("E3 brief must contain fifteen answer slots and twenty coverage entries")
    if tuple(sorted(item.section_id for item in brief.north_star_coverage)) != tuple(range(1, 21)):
        raise ValueError("E3 North Star coverage must contain sections one through twenty")
    if any(item.projection_contract != "north-star-v0.3" for item in brief.north_star_coverage):
        raise ValueError("E3 coverage contract is not North Star v0.3")
    if set(brief.source_hash_bindings) != {
        (record.source_record_id, record.representation_sha256) for record in brief.answer_slots
    } or len(brief.source_hash_bindings) != 10:
        raise ValueError("E3 source/hash inventory is not the exact ten-row inventory")
    expected_tuples = {
        (record.source_record_id, record.representation_sha256, record.rights_record_id)
        for record in brief.answer_slots
    }
    if len(expected_tuples) != 10 or set(brief.source_rights_bindings) != expected_tuples:
        raise ValueError("E3 source/representation/rights inventory is not the exact ten-row inventory")
    if set(brief.side_effects) != set(_EXPECTED_E3_SIDE_EFFECT_KEYS) or any(
        brief.side_effects[key] != 0 for key in _EXPECTED_E3_SIDE_EFFECT_KEYS
    ):
        raise ValueError("E3 brief reports a non-zero or incomplete side-effect counter")
    return tuple(brief.answer_slots)


def _e3_envelope(record: Any) -> tuple[Any, ...]:
    return tuple(getattr(record, field) for field in _E3_FIELDS)


def _current_rights_matches(row: Mapping[str, Any], record: Any) -> str | None:
    checks = {
        "rights record content hash": record.content_hash == row["rights_record_id"],
        "subject": record.subject_id == row["subject_id"],
        "scope": record.scope == row["scope_id"],
        "source record": record.source_record_id == row["source_record_id"],
        "representation": str(record.representation_sha256) == row["representation_sha256"],
        "source role": record.source_role == row["source_role"],
        "acquisition receipt": tuple(record.acquisition_lineage_ids) == (row["acquisition_receipt_id"],),
        "rights policy": record.rights_policy_id == row["rights_policy_id"],
        "rights policy version": record.rights_policy_version == row["rights_policy_version"],
        "provider status": (
            row["provider_processing_status"] == "blocked_provider_contract_not_bound"
            and record.provider_transmission.status == "blocked"
        ),
        "redistribution status": (
            record.public_redistribution.status == row["public_redistribution_status"]
        ),
        "binding status": row["status"] == "bound_not_task_eligible",
    }
    for label, matched in checks.items():
        if not matched:
            return label
    return None


def _summary(tasks: tuple[dict[str, Any], ...], brief: PrivateAnswerBrief) -> dict[str, Any]:
    plan = FactoryPlan.from_manifest(list(tasks))
    return {
        "task_identity": TASK_IDENTITY,
        "schema_version": SCHEMA_VERSION,
        "build_id": BUILD_ID,
        "route_policy_version": ROUTE_POLICY_VERSION,
        "difficulty": "deterministic",
        "bundle_key": None,
        "subjects": len(brief.subjects),
        "answer_slots": len(brief.answer_slots),
        "coverage_entries": len(brief.north_star_coverage),
        "source_hashes": len(brief.source_hash_bindings),
        "rights_bindings": len(brief.source_rights_bindings),
        "accepted_tasks": len(tasks),
        "logical_task_ids": tuple(item["logical_task_id"] for item in plan.logical_tasks),
        "plan_hash": plan.manifest_hash,
        "side_effects": dict(brief.side_effects),
    }


def preflight_e3_private_answer_brief(
    brief: PrivateAnswerBrief,
    selected_manifest: Mapping[str, Any],
    rights_store: Any,
    rights_projection: Any,
    catalog: Any,
    as_of: date,
    retained_bytes: Callable[[str], bytes] | None,
    *,
    difficulty: str = "deterministic",
    route_policy_version: str = ROUTE_POLICY_VERSION,
) -> E3FactoryHandoff:
    """Validate one accepted E3 brief and lower its exact ten rows to Factory.

    This function is deliberately a read-only preflight.  Callers use the
    returned ``factory_plan`` with the existing ``ReferenceFactory`` when a
    disposable operational catalogue has been prepared.
    """

    try:
        records = _brief_records(brief)
        rows = _validate_manifest(selected_manifest)
    except (TypeError, ValueError) as exc:
        diagnostic = _diagnostic("structurally_invalid", "E3/T3 handoff shape or identity is invalid", str(exc))
        return E3FactoryHandoff((), (diagnostic,), FactoryPlan.from_manifest([]), {"accepted_tasks": 0})

    if difficulty != "deterministic" or route_policy_version != ROUTE_POLICY_VERSION:
        diagnostic = _diagnostic(
            "blocked",
            "provider or non-deterministic route is blocked for the E3 handoff",
            f"difficulty={difficulty}",
            f"route_policy_version={route_policy_version}",
        )
        return E3FactoryHandoff((), (diagnostic,), FactoryPlan.from_manifest([]), {"accepted_tasks": 0})

    manifest_by_tuple = {
        (row["source_record_id"], row["representation_sha256"], row["rights_record_id"]): row
        for row in rows
    }
    e3_tuples = {
        (record.source_record_id, record.representation_sha256, record.rights_record_id)
        for record in records
    }
    if e3_tuples != set(manifest_by_tuple):
        diagnostic = _diagnostic("mismatched", "E3 and T3 do not contain the same ten exact tuples")
        return E3FactoryHandoff((), (diagnostic,), FactoryPlan.from_manifest([]), {"accepted_tasks": 0})

    diagnostics: list[PreflightDiagnostic] = []
    references: list[RightsPreflightReference] = []
    for row in rows:
        tuple_key = (row["source_record_id"], row["representation_sha256"], row["rights_record_id"])
        matching_records = [
            record for record in records
            if (record.source_record_id, record.representation_sha256, record.rights_record_id) == tuple_key
        ]
        expected_envelope = tuple(
            row["status"] if field == "binding_status" else row[field]
            for field in _E3_FIELDS
        )
        if not matching_records or any(_e3_envelope(record) != expected_envelope for record in matching_records):
            diagnostics.append(_diagnostic(
                "mismatched",
                "E3 answer envelope does not match the exact T3 row",
                row["source_record_id"],
                subject_id=row["subject_id"],
                reference_id=f"{TASK_IDENTITY}:{row['source_record_id']}",
            ))
            continue
        try:
            rights_record = rights_store.load_record(row["rights_record_id"])
        except Exception as exc:
            diagnostics.append(_diagnostic(
                "blocked",
                "current authoritative rights record is unavailable",
                str(exc),
                subject_id=row["subject_id"],
                reference_id=f"{TASK_IDENTITY}:{row['source_record_id']}",
            ))
            continue
        mismatch = _current_rights_matches(row, rights_record)
        if mismatch is not None:
            diagnostics.append(_diagnostic(
                "mismatched",
                "current authoritative rights record does not match T3",
                mismatch,
                subject_id=row["subject_id"],
                reference_id=f"{TASK_IDENTITY}:{row['source_record_id']}",
            ))
            continue
        try:
            references.append(RightsPreflightReference(
                reference_id=f"{TASK_IDENTITY}:{row['source_record_id']}",
                rights_record_id=row["rights_record_id"],
                source_family=row["source_family"],
                source_definition_id=row["source_definition_id"],
                evidence_locator_ids=(row["evidence_locator_id"],),
                claim_family_id=CLAIM_FAMILY,
                task_profile=TASK_PROFILE,
                task_profile_version=SCHEMA_VERSION,
                schema_version=SCHEMA_VERSION,
                difficulty="deterministic",
                physical_bundle_opportunity=None,
            ))
        except Exception as exc:
            diagnostics.append(_diagnostic(
                "structurally_invalid",
                "T3 row cannot form a deterministic rights preflight reference",
                str(exc),
                subject_id=row["subject_id"],
                reference_id=f"{TASK_IDENTITY}:{row['source_record_id']}",
            ))

    if diagnostics:
        return E3FactoryHandoff((), tuple(diagnostics), FactoryPlan.from_manifest([]), {"accepted_tasks": 0})

    try:
        result = preflight_governed_rights(
            references,
            store=rights_store,
            projection=rights_projection,
            catalog=catalog,
            as_of=as_of,
            retained_bytes=retained_bytes,
            build_id=BUILD_ID,
            route_policy_version=ROUTE_POLICY_VERSION,
        )
    except Exception as exc:
        diagnostic = _diagnostic("blocked", "governed rights preflight failed closed", str(exc))
        return E3FactoryHandoff((), (diagnostic,), FactoryPlan.from_manifest([]), {"accepted_tasks": 0})
    if result.diagnostics:
        return E3FactoryHandoff((), result.diagnostics, FactoryPlan.from_manifest([]), {"accepted_tasks": 0})
    tasks = tuple(result.tasks)
    return E3FactoryHandoff(tasks, (), result.factory_plan, _summary(tasks, brief))


def _row_value(row: Mapping[str, Any], field: str) -> Any:
    return row[field]


__all__ = [
    "BUILD_ID",
    "CLAIM_FAMILY",
    "E3FactoryHandoff",
    "ROUTE_POLICY_VERSION",
    "TASK_IDENTITY",
    "TASK_PROFILE",
    "preflight_e3_private_answer_brief",
]
