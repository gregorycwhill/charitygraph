"""Provider-free contract harness for the existing Phase-5 health export seam.

The harness deliberately wraps ``Phase5OperatorHealthCatalogueAdapter.project``
instead of creating another reader or projection.  It records the safe rows
returned by that read-only adapter, compares its delegated health document with
an independent direct observer call, and emits only canonical JSON-safe
diagnostic material.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .phase5_operator_health import OperatorHealthProjection, project_operator_health
from .phase5_operator_health_catalogue import (
    Phase5CatalogueProjection,
    Phase5OperatorHealthCatalogueAdapter,
)


SCHEMA_ID = "charitygraph.phase5.operator-health-runtime-contract"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"

_RECORD_GROUPS = (
    "runs",
    "jobs",
    "requests",
    "tasks",
    "attempts",
    "task_attempts",
    "physical",
    "receipts",
    "reservations",
    "cost_entries",
)
_FORBIDDEN_KEY_PARTS = (
    "authorization",
    "credential",
    "error_message",
    "failure_message",
    "prompt",
    "raw_result",
    "response_body",
    "result_ref",
    "source_text",
    "task_material",
    "transport_exception",
    "usage_json",
)


class RuntimeContractError(ValueError):
    """Raised when the existing export seam violates this contract."""


@dataclass(frozen=True)
class RuntimeContractProjection:
    """The safe persisted view, direct comparison and canonical contract."""

    runtime_export: Phase5CatalogueProjection
    direct_observer: OperatorHealthProjection
    persisted_representation: dict[str, Any]
    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    @property
    def checks(self) -> Mapping[str, bool]:
        return self.document["checks"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(child) for child in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _reject_forbidden_keys(value: Any, *, path: str = "contract") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_KEY_PARTS):
                raise RuntimeContractError(f"non-allowlisted field at {path}.{key_text}")
            _reject_forbidden_keys(child, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, path=f"{path}[{index}]")


def _safe_persisted_representation(snapshot: Any) -> dict[str, Any]:
    records: dict[str, list[dict[str, Any]]] = {}
    for group in _RECORD_GROUPS:
        rows = [dict(row) for row in snapshot.records.get(group, ())]
        records[group] = sorted(rows, key=_canonical_bytes)
    representation = {
        "schema": "charitygraph.phase5.persisted-runtime-safe-view/v1",
        "run_selection": {
            "requested": list(snapshot.run_ids_requested),
            "found": list(snapshot.run_ids_found),
            "bounded": True,
        },
        "source_lineage": {
            "source_id": snapshot.source_id,
            "source_version": snapshot.source_version,
            "evidence_basis": snapshot.evidence_basis,
        },
        "timestamps": {
            "as_of": snapshot.as_of,
            "reporting_window_start": snapshot.reporting_window_start,
            "reporting_window_end": snapshot.reporting_window_end,
        },
        "coverage": _canonical(snapshot.coverage),
        "record_counts": {group: len(records[group]) for group in _RECORD_GROUPS},
        "records": records,
    }
    _reject_forbidden_keys(representation)
    return representation


def _identity_checks(snapshot: Any, direct: OperatorHealthProjection) -> dict[str, bool]:
    document = direct.document
    records = snapshot.records
    persisted_run_ids = sorted({str(row["run_id"]) for group in _RECORD_GROUPS for row in records.get(group, ()) if row.get("run_id") is not None})
    persisted_source_ids = {snapshot.source_id}
    for group in _RECORD_GROUPS:
        persisted_source_ids.update(str(row["source_id"]) for row in records.get(group, ()) if row.get("source_id") is not None)
    per_run: dict[str, dict[str, set[str]]] = {}
    for group in _RECORD_GROUPS:
        for row in records.get(group, ()):
            run_id = row.get("run_id")
            if run_id is None:
                continue
            entry = per_run.setdefault(str(run_id), {"subject_ids": set(), "scope_ids": set()})
            for output_key, names in (("subject_ids", ("subject_id", "durable_subject_id")), ("scope_ids", ("scope_id", "durable_scope_id"))):
                for name in names:
                    if row.get(name) is not None:
                        entry[output_key].add(str(row[name]))
                        break
    direct_per_run = {str(row["run_id"]): row for row in document["per_run"]}
    identity_ok = set(document["scope"]["run_ids"]) == set(persisted_run_ids) == set(snapshot.run_ids_found)
    identity_ok = identity_ok and set(document["scope"]["source_ids"]) == persisted_source_ids
    for run_id, values in per_run.items():
        row = direct_per_run.get(run_id)
        identity_ok = identity_ok and row is not None
        if row is not None:
            identity_ok = identity_ok and set(row["subject_ids"]) == values["subject_ids"] and set(row["scope_ids"]) == values["scope_ids"]
    return {
        "run_request_task_subject_scope_source_identity": identity_ok,
        "timestamp_provenance_is_exact": (
            document["scope"]["as_of"] == snapshot.as_of
            and document["reporting_window"]["start"] is not None
            and document["reporting_window"]["end"] is not None
        ),
    }


def _cost_missingness_is_closed(document: Mapping[str, Any]) -> bool:
    cost = document["cost"]
    for name in ("actual", "committed_reserved", "forecast"):
        row = cost[name]
        if row["state"] in {"missing", "unknown", "ambiguous", "stale"} and row["amount"] is not None:
            return False
    return cost["provenance"]["ledger_source_id"] is None or isinstance(cost["provenance"]["ledger_source_id"], str)


def project_phase5_operator_health_runtime_contract(
    catalogue: str | Path,
    *,
    run_ids: Sequence[str],
    as_of: str,
    reporting_window_start: str,
    reporting_window_end: str,
    source_id: str | None = None,
    evidence_basis: str = "persisted Phase-5 runtime catalogue; provider evidence not claimed",
    ledger: Mapping[str, Any] | None = None,
    stalled_after_seconds: int | None = None,
) -> RuntimeContractProjection:
    """Exercise the real read-only catalogue export and verify its observer contract."""

    runtime_export = Phase5OperatorHealthCatalogueAdapter(
        catalogue,
        run_ids=run_ids,
        as_of=as_of,
        reporting_window_start=reporting_window_start,
        reporting_window_end=reporting_window_end,
        source_id=source_id,
        evidence_basis=evidence_basis,
        ledger=ledger,
        stalled_after_seconds=stalled_after_seconds,
    ).project()
    direct = project_operator_health(runtime_export.snapshot.operator_snapshot)
    persisted = _safe_persisted_representation(runtime_export.snapshot)
    checks = {
        "runtime_export_matches_direct_observer": runtime_export.operator_health.canonical_json == direct.canonical_json,
        "runtime_export_selection_matches_snapshot": runtime_export.document["catalogue_integration"]["run_selection"] == runtime_export.snapshot.coverage["run_selection"],
        "runtime_export_lineage_matches_snapshot": runtime_export.document["catalogue_integration"]["coverage"]["source_lineage"] == runtime_export.snapshot.coverage["source_lineage"],
        "safe_persisted_representation_is_allowlisted": True,
        **_identity_checks(runtime_export.snapshot, direct),
        "stalled_retry_failure_recovery_are_observer_derived": runtime_export.document["flags"] == direct.document["flags"],
        "cost_missingness_and_provenance_are_observer_derived": runtime_export.document["cost"] == direct.document["cost"] and _cost_missingness_is_closed(direct.document),
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, value in checks.items() if not value)
        raise RuntimeContractError(f"Phase-5 runtime health contract failed: {failed}")
    document = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "checks": checks,
        "persisted_representation": persisted,
        "operator_health": json.loads(direct.canonical_json.decode("utf-8")),
    }
    canonical_json = _canonical_bytes(document)
    return RuntimeContractProjection(
        runtime_export=runtime_export,
        direct_observer=direct,
        persisted_representation=persisted,
        document=document,
        canonical_json=canonical_json,
        sha256=hashlib.sha256(canonical_json).hexdigest(),
    )


def canonical_runtime_contract_json(projection: RuntimeContractProjection | Mapping[str, Any]) -> bytes:
    document = projection.document if isinstance(projection, RuntimeContractProjection) else projection
    return _canonical_bytes(document)


def runtime_contract_sha256(projection: RuntimeContractProjection | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_runtime_contract_json(projection)).hexdigest()


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "RuntimeContractError",
    "RuntimeContractProjection",
    "project_phase5_operator_health_runtime_contract",
    "canonical_runtime_contract_json",
    "runtime_contract_sha256",
]
