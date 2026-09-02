"""Deterministic projection of explicit regulator fields into candidate observations.

Only source-native structure is handled here; prose interpretation remains the
Compact Knowledge path.  The function is deliberately pure so callers can run
it in an isolated catalogue and replay it byte-for-byte.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from .contracts.ids import deterministic_id

_FIELD_ROLES = {
    "Abn": "abn",
    "Status": "status",
    "CharitySize": "charity_size",
    "DateEstablished": "established_at",
    "NextReportDue": "next_report_due",
    "ReportingLate": "reporting_late",
    "AddressStateOrProvince": "location_state",
    "AddressCountry": "location_country",
    "TotalGrossIncomeDonationsAndRequests": "financial_donations",
    "TotalGrossIncomeGovernmentGrants": "financial_government_grants",
    "TotalExpensesEmployee": "financial_employee_expenses",
    "TotalAssets": "assets",
    "TotalLiabilities": "liabilities",
}


def _source_date(value: Any) -> date | None:
    """Decode an explicit source timestamp without timezone-shifting it."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def deterministic_structured_observations(
    payload: Mapping[str, Any], *, subject_id: str, source_record_id: str,
    evidence_locator_ids: Iterable[str] = (), observed_at: datetime | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return stable candidate observation envelopes for explicit scalar fields."""
    observed = observed_at or datetime.now(timezone.utc)
    data = payload.get("data", payload)
    if not isinstance(data, Mapping):
        return ()
    evidence = tuple(evidence_locator_ids)
    result = []
    for field, predicate in _FIELD_ROLES.items():
        if field not in data or data[field] in (None, ""):
            continue
        value = data[field]
        temporal = _source_date(value) if predicate in {"established_at", "next_report_due", "reporting_late"} else None
        result.append({
            "record_id": deterministic_id("observation:", {"subject_id": subject_id, "source_record_id": source_record_id, "field": field, "value": value}),
            "subject_id": subject_id,
            "predicate": predicate,
            "value": {"source_field": field, "source_value": value},
            "source_record_ids": (source_record_id,),
            "evidence_locator_ids": evidence,
            "observed_at": observed.isoformat(),
            "effective_date": temporal.isoformat() if temporal else None,
            "method": "structured-source-deterministic-v1",
            "lifecycle_status": "candidate",
        })
    return tuple(result)


__all__ = ["deterministic_structured_observations"]
