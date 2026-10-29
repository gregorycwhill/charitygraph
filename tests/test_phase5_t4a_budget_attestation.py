import builtins
import hashlib
import json
import socket
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from charitygraph.contracts.canonical import canonical_json_bytes
from charitygraph.phase5_t4a_budget_attestation import (
    BUDGET_LEDGER_SNAPSHOT_SCHEMA,
    verify_cumulative_budget_attestation,
)


NOW = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
PROJECT = "charitygraph-project"


def snapshot(**changes):
    value = {
        "schema_id": BUDGET_LEDGER_SNAPSHOT_SCHEMA,
        "project_id": PROJECT,
        "as_of": "2026-10-28T12:00:00Z",
        "currency": "AUD",
        "actual_aud": "0.250000",
        "outstanding_reservations_aud": "0.750000",
        "pending_or_ambiguous_physical_attempts": [],
        "coverage": {
            "project_wide": True,
            "actuals_complete": True,
            "reservations_complete": True,
            "physical_attempts_complete": True,
        },
        "approved_cap_aud": "10.00",
        "content_sha256": "a" * 64,
    }
    value.update(changes)
    return value


def packed(value=None):
    raw = canonical_json_bytes(snapshot() if value is None else value)
    return raw, hashlib.sha256(raw).hexdigest()


def verify(raw, pin, **changes):
    return verify_cumulative_budget_attestation(
        raw,
        trusted_sha256=pin,
        project_id=PROJECT,
        now=NOW,
        **changes,
    )


def test_replay_is_deterministic_and_positive_state_is_non_send():
    raw, pin = packed()
    first, second = verify(raw, pin), verify(raw, pin)

    assert first == second
    assert first.status == "BUDGET_EVIDENCE_VERIFIED_NON_SEND"
    assert first.headroom_after_proposed_reservation_aud == Decimal("9")
    assert first.request_ticket is None
    assert first.send_authorization == "not_authorized_for_send"


def test_independent_pin_is_exact_and_not_snapshot_provenance():
    raw, pin = packed(snapshot(content_sha256="b" * 64))

    accepted = verify(raw, pin)
    assert accepted.status == "BUDGET_EVIDENCE_VERIFIED_NON_SEND"
    assert accepted.snapshot_sha256 == pin

    rejected = verify(raw, "b" * 64)
    assert rejected.status == "NOT_VERIFIED"
    assert "trusted_snapshot_pin_mismatch" in rejected.reasons


@pytest.mark.parametrize(
    "raw",
    [
        b'{"project_id":"first","project_id":"second"}',
        b'{"coverage":{"project_wide":true,"project_wide":false}}',
    ],
)
def test_duplicate_json_keys_at_root_and_nested_levels_fail_closed(raw):
    result = verify(raw, hashlib.sha256(raw).hexdigest())

    assert result.status == "NOT_VERIFIED"
    assert "snapshot_bytes_invalid_json" in result.reasons


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "project_wide_budget_snapshot_missing"),
        (canonical_json_bytes({**snapshot(), "coverage": {"project_wide": True}}), "ledger_coverage_assertion_invalid"),
    ],
)
def test_missing_or_incomplete_snapshot_fails_closed(raw, expected):
    pin = hashlib.sha256(raw).hexdigest() if raw is not None else None
    result = verify(raw, pin)

    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


@pytest.mark.parametrize(
    ("actual", "reserved", "proposed", "status", "reason"),
    [
        ("9.01", "1.00", "0", "BLOCKED", "cumulative_budget_over_cap"),
        ("0.25", "0.75", "9.01", "BLOCKED", "proposed_reservation_exceeds_budget_headroom"),
        ("0.25", "0.75", "9.00", "BUDGET_EVIDENCE_VERIFIED_NON_SEND", None),
    ],
)
def test_actual_reserved_and_proposed_reservation_share_the_cap(actual, reserved, proposed, status, reason):
    raw, pin = packed(snapshot(actual_aud=actual, outstanding_reservations_aud=reserved))
    result = verify(raw, pin, proposed_max_one_request_reservation_aud=proposed)

    assert result.status == status
    if reason:
        assert reason in result.reasons


def test_decimal_proposal_is_accepted_without_float_or_bool_coercion():
    raw, pin = packed()

    result = verify(raw, pin, proposed_max_one_request_reservation_aud=Decimal("1.2500"))

    assert result.status == "BUDGET_EVIDENCE_VERIFIED_NON_SEND"
    assert result.proposed_max_one_request_reservation_aud == Decimal("1.2500")
    assert result.headroom_after_proposed_reservation_aud == Decimal("7.75")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("-0.01"), "proposed_reservation_aud_negative"),
        (Decimal("NaN"), "proposed_reservation_aud_non_finite"),
        (Decimal("Infinity"), "proposed_reservation_aud_non_finite"),
        (1.25, "proposed_reservation_aud_invalid"),
        (True, "proposed_reservation_aud_invalid"),
        ({"amount": "1.25"}, "proposed_reservation_aud_invalid"),
    ],
)
def test_decimal_proposal_invalid_types_and_values_fail_closed(value, expected):
    raw, pin = packed()

    result = verify(raw, pin, proposed_max_one_request_reservation_aud=value)

    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


@pytest.mark.parametrize("state", ["pending", "ambiguous"])
def test_pending_or_ambiguous_attempt_blocks_even_with_headroom(state):
    raw, pin = packed(snapshot(pending_or_ambiguous_physical_attempts=[{"physical_attempt_id": "physical:one", "state": state}]))

    result = verify(raw, pin)

    assert result.status == "BLOCKED"
    assert result.pending_or_ambiguous_physical_attempt_ids == ("physical:one",)
    assert "unresolved_physical_attempts_present" in result.reasons


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"as_of": "2026-10-27T23:59:59Z"}, "budget_snapshot_stale"),
        ({"project_id": "different-project"}, "budget_snapshot_project_mismatch"),
        ({"currency": "USD"}, "budget_snapshot_currency_unsupported"),
    ],
)
def test_stale_project_and_currency_mismatch_are_not_verified(changes, expected):
    raw, pin = packed(snapshot(**changes))

    result = verify(raw, pin)

    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        ("2026-10-28T12:00:00", "snapshot_as_of_not_timezone_aware"),
        ("2026-10-29T00:00:01Z", "budget_snapshot_as_of_in_future"),
        ("2026-10-27T23:59:59Z", "budget_snapshot_stale"),
    ],
)
def test_naive_future_and_stale_as_of_values_fail_closed(as_of, expected):
    raw, pin = packed(snapshot(as_of=as_of))

    result = verify(raw, pin)

    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


def test_incomplete_coverage_fails_closed_even_with_other_valid_fields():
    incomplete = snapshot()
    incomplete["coverage"] = {**incomplete["coverage"], "physical_attempts_complete": False}
    raw, pin = packed(incomplete)

    result = verify(raw, pin)

    assert result.status == "NOT_VERIFIED"
    assert "ledger_coverage_incomplete" in result.reasons


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("actual_aud", "-0.01", "actual_aud_negative"),
        ("actual_aud", "NaN", "actual_aud_non_finite"),
        ("outstanding_reservations_aud", "Infinity", "outstanding_reservations_aud_non_finite"),
        ("actual_aud", 0.25, "snapshot_bytes_not_canonical"),
        ("actual_aud", True, "actual_aud_invalid"),
    ],
)
def test_decimal_edge_cases_fail_closed(field, value, expected):
    if isinstance(value, float):
        raw = json.dumps(snapshot(**{field: value})).encode("utf-8")
    else:
        raw = canonical_json_bytes(snapshot(**{field: value}))
    result = verify(raw, hashlib.sha256(raw).hexdigest())

    assert result.status == "NOT_VERIFIED"
    assert expected in result.reasons


def test_verifier_has_no_network_filesystem_or_provider_side_effects(monkeypatch):
    raw, pin = packed()
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("filesystem")))

    result = verify(raw, pin)

    assert result.status == "BUDGET_EVIDENCE_VERIFIED_NON_SEND"

