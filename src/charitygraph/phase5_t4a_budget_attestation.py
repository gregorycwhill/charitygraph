"""Provider-free verification of the project-wide cumulative AUD budget.

The verifier consumes an authority-supplied, versioned snapshot.  It is
deliberately a pure boundary: it does not open a catalogue, read a file,
create a reservation, or issue a provider/send ticket.  The trusted SHA-256
pin is supplied independently by the caller; a snapshot's optional
``content_sha256`` field is never used as that trust decision.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal


BUDGET_LEDGER_SNAPSHOT_SCHEMA = "charitygraph.project-wide-aud-ledger-snapshot/1"
APPROVED_CUMULATIVE_CAP_AUD = Decimal("10")
DEFAULT_MAX_SNAPSHOT_AGE = timedelta(hours=24)

BudgetAttestationStatus = Literal[
    "BUDGET_EVIDENCE_VERIFIED_NON_SEND", "NOT_VERIFIED", "BLOCKED"
]


@dataclass(frozen=True)
class BudgetAttestation:
    """Typed diagnostic; the positive state is evidence-only and non-send."""

    status: BudgetAttestationStatus
    schema_id: str = BUDGET_LEDGER_SNAPSHOT_SCHEMA
    project_id: str | None = None
    snapshot_sha256: str | None = None
    as_of: str | None = None
    actual_aud: Decimal | None = None
    outstanding_reservations_aud: Decimal | None = None
    proposed_max_one_request_reservation_aud: Decimal | None = None
    headroom_after_proposed_reservation_aud: Decimal | None = None
    pending_or_ambiguous_physical_attempt_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    request_ticket: None = None
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"


def _result(status: BudgetAttestationStatus, reasons: list[str], **values: object) -> BudgetAttestation:
    return BudgetAttestation(status=status, reasons=tuple(dict.fromkeys(reasons)), **values)


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_amount(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_invalid")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}_invalid") from None
    if not amount.is_finite():
        raise ValueError(f"{field}_non_finite")
    if amount < 0:
        raise ValueError(f"{field}_negative")
    return amount


def _parse_as_of(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("snapshot_as_of_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("snapshot_as_of_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("snapshot_as_of_not_timezone_aware")
    return parsed.astimezone(timezone.utc)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("snapshot_duplicate_key")
        result[key] = value
    return result


def _load_snapshot(snapshot_bytes: bytes) -> tuple[Mapping[str, object] | None, list[str], str]:
    observed_hash = hashlib.sha256(snapshot_bytes).hexdigest()
    reasons: list[str] = []
    if not isinstance(snapshot_bytes, bytes) or not snapshot_bytes:
        return None, ["snapshot_bytes_missing_or_invalid"], observed_hash
    try:
        decoded = json.loads(
            snapshot_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ["snapshot_bytes_invalid_json"], observed_hash
    if not isinstance(decoded, Mapping):
        return None, ["snapshot_root_not_object"], observed_hash
    try:
        from .contracts.canonical import canonical_json_bytes

        canonical = canonical_json_bytes(decoded)
    except (TypeError, ValueError):
        return None, ["snapshot_bytes_not_canonical"], observed_hash
    if snapshot_bytes != canonical:
        reasons.append("snapshot_bytes_not_canonical")
    return decoded, reasons, observed_hash


def _validate_shape(snapshot: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    reasons: list[str] = []
    required = {
        "schema_id",
        "project_id",
        "as_of",
        "currency",
        "actual_aud",
        "outstanding_reservations_aud",
        "pending_or_ambiguous_physical_attempts",
        "coverage",
        "approved_cap_aud",
    }
    allowed = required | {"content_sha256"}
    missing = sorted(required - set(snapshot))
    extra = sorted(set(snapshot) - allowed)
    if missing:
        reasons.append("snapshot_fields_missing:" + ",".join(missing))
    if extra:
        reasons.append("snapshot_fields_unsupported:" + ",".join(extra))
    return dict(snapshot), reasons


def verify_cumulative_budget_attestation(
    snapshot_bytes: bytes | None,
    *,
    trusted_sha256: str | None,
    project_id: str,
    now: datetime,
    proposed_max_one_request_reservation_aud: str | Decimal = "0",
    max_snapshot_age: timedelta = DEFAULT_MAX_SNAPSHOT_AGE,
) -> BudgetAttestation:
    """Verify a complete project-wide cumulative AUD10 snapshot.

    ``trusted_sha256`` and ``project_id`` are caller-supplied authority
    inputs.  ``now`` and the age limit are explicit so replay and freshness
    checks remain deterministic.  The function returns a diagnostic for every
    input state and never performs an external or mutable operation.
    """

    if not isinstance(project_id, str) or not project_id.strip():
        return _result("NOT_VERIFIED", ["expected_project_id_missing_or_invalid"])
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        return _result("NOT_VERIFIED", ["verification_now_not_timezone_aware"])
    if not isinstance(max_snapshot_age, timedelta) or max_snapshot_age <= timedelta(0):
        return _result("NOT_VERIFIED", ["max_snapshot_age_invalid"])

    proposed: Decimal | None = None
    reasons: list[str] = []
    try:
        proposed = _parse_amount(proposed_max_one_request_reservation_aud, "proposed_reservation_aud")
    except ValueError as error:
        reasons.append(str(error))

    if not _valid_sha256(trusted_sha256):
        reasons.append("trusted_snapshot_pin_missing_or_invalid")

    if snapshot_bytes is None:
        reasons.append("project_wide_budget_snapshot_missing")
        return _result("NOT_VERIFIED", reasons, proposed_max_one_request_reservation_aud=proposed)
    if not isinstance(snapshot_bytes, bytes):
        reasons.append("snapshot_bytes_missing_or_invalid")
        return _result("NOT_VERIFIED", reasons, proposed_max_one_request_reservation_aud=proposed)

    snapshot, load_reasons, observed_hash = _load_snapshot(snapshot_bytes)
    reasons.extend(load_reasons)
    if _valid_sha256(trusted_sha256) and not hmac.compare_digest(observed_hash, trusted_sha256):
        reasons.append("trusted_snapshot_pin_mismatch")
    if snapshot is None:
        return _result(
            "NOT_VERIFIED",
            reasons,
            snapshot_sha256=observed_hash,
            proposed_max_one_request_reservation_aud=proposed,
        )

    values, shape_reasons = _validate_shape(snapshot)
    reasons.extend(shape_reasons)
    if values.get("schema_id") != BUDGET_LEDGER_SNAPSHOT_SCHEMA:
        reasons.append("budget_snapshot_schema_invalid")
    if values.get("project_id") != project_id:
        reasons.append("budget_snapshot_project_mismatch")
    if values.get("currency") != "AUD":
        reasons.append("budget_snapshot_currency_unsupported")
    if not _valid_sha256(values.get("content_sha256")) and "content_sha256" in values:
        reasons.append("snapshot_content_sha256_invalid")

    actual: Decimal | None = None
    reserved: Decimal | None = None
    cap: Decimal | None = None
    as_of: datetime | None = None
    for field in ("actual_aud", "outstanding_reservations_aud", "approved_cap_aud"):
        try:
            parsed = _parse_amount(values.get(field), field)
        except ValueError as error:
            reasons.append(str(error))
            continue
        if field == "actual_aud":
            actual = parsed
        elif field == "outstanding_reservations_aud":
            reserved = parsed
        else:
            cap = parsed
    try:
        as_of = _parse_as_of(values.get("as_of"))
    except ValueError as error:
        reasons.append(str(error))

    coverage = values.get("coverage")
    expected_coverage = {
        "project_wide",
        "actuals_complete",
        "reservations_complete",
        "physical_attempts_complete",
    }
    if not isinstance(coverage, Mapping) or set(coverage) != expected_coverage or any(
        type(coverage.get(key)) is not bool for key in expected_coverage
    ):
        reasons.append("ledger_coverage_assertion_invalid")
    elif not all(coverage.values()):
        reasons.append("ledger_coverage_incomplete")

    attempts = values.get("pending_or_ambiguous_physical_attempts")
    attempt_ids: list[str] = []
    if not isinstance(attempts, list):
        reasons.append("physical_attempt_coverage_invalid")
    else:
        for item in attempts:
            if not isinstance(item, Mapping) or set(item) != {"physical_attempt_id", "state"}:
                reasons.append("physical_attempt_record_invalid")
                continue
            attempt_id, state = item.get("physical_attempt_id"), item.get("state")
            if not isinstance(attempt_id, str) or not attempt_id.strip() or state not in {"pending", "ambiguous"}:
                reasons.append("physical_attempt_record_invalid")
                continue
            if attempt_id in attempt_ids:
                reasons.append("physical_attempt_record_duplicate")
            attempt_ids.append(attempt_id)

    now_utc = now.astimezone(timezone.utc) if isinstance(now, datetime) else now
    if as_of is not None:
        if as_of > now_utc:
            reasons.append("budget_snapshot_as_of_in_future")
        elif now_utc - as_of > max_snapshot_age:
            reasons.append("budget_snapshot_stale")

    common = {
        "project_id": values.get("project_id") if isinstance(values.get("project_id"), str) else None,
        "snapshot_sha256": observed_hash,
        "as_of": values.get("as_of") if isinstance(values.get("as_of"), str) else None,
        "actual_aud": actual,
        "outstanding_reservations_aud": reserved,
        "proposed_max_one_request_reservation_aud": proposed,
        "pending_or_ambiguous_physical_attempt_ids": tuple(attempt_ids),
    }
    if cap != APPROVED_CUMULATIVE_CAP_AUD:
        reasons.append("approved_cap_mismatch")
    if reasons:
        return _result("NOT_VERIFIED", reasons, **common)

    committed = actual + reserved  # type: ignore[operator]
    headroom = APPROVED_CUMULATIVE_CAP_AUD - committed
    if attempt_ids:
        reasons.append("unresolved_physical_attempts_present")
    if committed > APPROVED_CUMULATIVE_CAP_AUD:
        reasons.append("cumulative_budget_over_cap")
    if proposed > headroom:  # type: ignore[operator]
        reasons.append("proposed_reservation_exceeds_budget_headroom")
    common["headroom_after_proposed_reservation_aud"] = headroom - proposed  # type: ignore[operator]
    return _result("BLOCKED" if reasons else "BUDGET_EVIDENCE_VERIFIED_NON_SEND", reasons, **common)

