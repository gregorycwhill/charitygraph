from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from charitygraph.phase5_provider_history_evidence_adapter import (
    RAW_EXPORT_SCHEMA,
    SCHEMA,
    STATUS_FAIL_CLOSED,
    STATUS_PARTIAL,
    adapt_phase5_provider_history_evidence,
    canonical_provider_history_evidence_json,
    provider_history_evidence_sha256,
)


AS_OF = "2026-11-01T12:00:00Z"
WINDOW = {"start": "2026-11-01T00:00:00Z", "end": "2026-11-01T11:00:00Z", "coverage_state": "bounded"}
IDENTITY = {"source_id": "source:provider-history", "provider_id": "provider:fixture", "account_id": "account:fixture", "identity_version": "1"}
ACQUISITION = {"acquisition_id": "acq:provider-history:1", "acquired_at": AS_OF, "observed_at": AS_OF, "source_locator": "fixture://provider-history"}


def _raw(kind="run_index", *, records=None, **changes) -> bytes:
    value = {
        "schema": RAW_EXPORT_SCHEMA,
        "schema_version": 1,
        "export_kind": kind,
        "export_id": "export:fixture:1",
        "scope": {"scope_id": "project:paid", "kind": "project_window"},
        "window": dict(WINDOW),
        "missingness": {"state": "observed", "missing_ids": [], "reason": None},
        "records": records if records is not None else [
            {"run_id": "run:a", "physical_attempt_id": "physical:a", "observed_at": "2026-11-01T10:00:00Z"},
            {"run_id": "run:b", "physical_attempt_id": "physical:b", "observed_at": "2026-11-01T10:30:00Z"},
        ],
    }
    value.update(changes)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _project(raw=None, **kwargs):
    return adapt_phase5_provider_history_evidence(
        _raw() if raw is None else raw,
        source_identity=kwargs.pop("source_identity", deepcopy(IDENTITY)),
        acquisition_metadata=kwargs.pop("acquisition_metadata", deepcopy(ACQUISITION)),
        **kwargs,
    )


def test_observed_subset_is_sha_bound_but_never_authoritative():
    raw = _raw()
    result = _project(raw)
    assert result.status == STATUS_PARTIAL
    assert result.document["schema"] == SCHEMA
    assert result.document["evidence_state"] == "OBSERVED"
    assert result.document["source"]["raw_export_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result.document["observed"]["run_ids"] == ["run:a", "run:b"]
    assert result.document["authority"] == {
        "status": "FAIL_CLOSED",
        "basis": "no trusted host-authenticated provider provenance and source-owned completeness verifier is available in this bounded adapter",
        "project_wide_authoritative": False,
        "authoritative_total": None,
        "remaining_spend": None,
        "send_authorization": "not_authorized_for_send",
    }


def test_complete_looking_forgery_does_not_create_host_authority():
    raw = _raw(
        complete=True,
        authenticated=True,
        source_owned=True,
        signed="looks-signed",
        provenance="source-owned-complete",
    )
    result = _project(
        raw,
        host_attestation={"verified": True, "complete": True, "attestation_id": "attestation:forged"},
        source_owned_completeness={"source_owned": True, "complete": True, "signed": "looks-signed"},
    )
    reasons = set(result.document["reason_codes"])
    assert result.document["authority"]["project_wide_authoritative"] is False
    assert result.document["authority"]["authoritative_total"] is None
    assert result.document["authority"]["remaining_spend"] is None
    assert "CALLER_ASSERTED_HOST_ATTESTATION_UNVERIFIED" in reasons
    assert "CALLER_ASSERTED_SOURCE_OWNED_COMPLETENESS_UNVERIFIED" in reasons
    assert "CALLER_ASSERTED_WINDOW_COMPLETENESS_UNVERIFIED" not in reasons


def test_missing_host_attestation_and_completeness_are_explicit_fail_closed_inputs():
    result = _project()
    assert result.document["host_attestation"]["state"] == "MISSING"
    assert result.document["source_owned_completeness"]["state"] == "MISSING"
    assert {"MISSING_HOST_ATTESTATION", "MISSING_SOURCE_OWNED_COMPLETENESS"}.issubset(result.document["reason_codes"])
    assert result.document["authority"]["status"] == "FAIL_CLOSED"


def test_unsupported_provider_native_format_fails_closed_without_guessing():
    result = _project(_raw(export_kind="provider-native-v99", schema="provider-native/v99"))
    assert result.status == STATUS_FAIL_CLOSED
    assert "UNSUPPORTED_PROVIDER_NATIVE_FORMAT" in result.document["reason_codes"]
    assert result.document["observed"]["records"] == []


def test_stale_schema_and_unknown_version_fail_closed():
    result = _project(_raw(schema="charitygraph.phase5.provider-history-export/99", schema_version=99))
    assert result.status == STATUS_FAIL_CLOSED
    assert "STALE_OR_UNKNOWN_EXPORT_SCHEMA" in result.document["reason_codes"]


def test_duplicate_and_conflicting_records_are_retained_as_diagnostics():
    records = [
        {"run_id": "run:a", "physical_attempt_id": "physical:a"},
        {"run_id": "run:a", "physical_attempt_id": "physical:a"},
        {"run_id": "run:b", "physical_attempt_id": "physical:b"},
        {"run_id": "run:b", "physical_attempt_id": "physical:other"},
    ]
    result = _project(_raw(records=records))
    diagnostics = result.document["observed"]["record_diagnostics"]
    assert diagnostics["duplicate_record_ids"] == ["run:a"]
    assert diagnostics["conflicting_record_ids"] == ["run:b"]
    assert "DUPLICATE_EXPORT_RECORDS" in result.document["reason_codes"]
    assert "CONFLICTING_EXPORT_RECORDS" in result.document["reason_codes"]


def test_conflicting_physical_attempt_identity_is_not_resolved_by_first_row():
    result = _project(_raw(records=[
        {"run_id": "run:a", "physical_attempt_id": "physical:shared"},
        {"run_id": "run:b", "physical_attempt_id": "physical:shared"},
    ]))
    assert result.document["observed"]["record_diagnostics"]["conflicting_physical_attempt_ids"] == ["physical:shared"]
    assert "CONFLICTING_PHYSICAL_ATTEMPT_IDENTITY" in result.document["reason_codes"]


def test_identity_contradiction_fails_closed():
    result = _project(_raw(source_identity={"source_id": "source:other", "provider_id": "provider:other"}))
    assert result.status == STATUS_FAIL_CLOSED
    assert "EXPORT_SOURCE_IDENTITY_CONTRADICTION" in result.document["reason_codes"]


def test_acquisition_sha_mismatch_fails_closed():
    result = _project(acquisition_metadata={**ACQUISITION, "source_byte_sha256": "a" * 64})
    assert result.status == STATUS_FAIL_CLOSED
    assert "SOURCE_BYTE_SHA256_MISMATCH" in result.document["reason_codes"]


def test_mixed_time_window_is_visible():
    result = _project(_raw(records=[{"run_id": "run:a", "physical_attempt_id": "physical:a", "observed_at": "2026-12-01T00:00:00Z"}]))
    assert "MIXED_TIME_WINDOWS" in result.document["reason_codes"]


def test_source_silence_and_missingness_are_not_zero():
    result = _project(_raw(records=[], missingness={"state": "source_silence", "missing_ids": ["run:a"]}))
    reasons = set(result.document["reason_codes"])
    assert "SOURCE_SILENCE_OR_EMPTY" in reasons
    assert result.document["observed"]["run_ids"] == []
    assert result.document["authority"]["authoritative_total"] is None


def test_billing_receipt_linkage_and_cost_missingness_are_observed_without_aggregation():
    raw = _raw(
        "billing_receipts",
        records=[
            {"receipt_id": "receipt:a", "run_id": "run:unknown", "physical_attempt_id": "physical:unknown", "amount": "1.25", "currency": "AUD"},
            {"receipt_id": "receipt:b", "run_id": None, "physical_attempt_id": None},
        ],
    )
    result = _project(raw)
    reasons = set(result.document["reason_codes"])
    assert "BROKEN_RECEIPT_RUN_FOREIGN_KEY" in reasons
    assert "MISSING_RECEIPT_PHYSICAL_ATTEMPT_ID" in reasons
    assert "MISSING_PRICING_SNAPSHOT" in reasons
    assert "MISSING_FX_SNAPSHOT" in reasons
    assert "RUN_INDEX_NOT_PRESENT_FOR_RECEIPT_EXPORT" in reasons
    assert result.document["cost_missingness"]["state"] == "partial"
    assert "authoritative_total" not in result.document["cost_missingness"]


def test_run_inventory_contract_is_used_without_promoting_authority():
    result = _project(
        reconciliation_inputs={
            "run_inventory_sources": [{
                "source_id": "source:independent-fixture",
                "source_identity": "provider:fixture|account:fixture",
                "source_role": "run_index",
                "source_byte_sha256": "b" * 64,
                "observed_at": AS_OF,
                "scope": {"scope_id": "project:paid", "kind": "project_window"},
                "schema_version": 1,
                "run_ids": ["run:c"],
                "missingness": {"state": "observed", "missing_ids": []},
                "provenance": {"capture": "fixture"},
            }]
        }
    )
    audit = result.document["reconciliation"]["run_inventory_audit"]
    assert audit["status"] == "NOT_AUTHORITATIVE"
    assert "PROJECT_WIDE_COMPLETENESS_UNVERIFIED" in audit["reason_codes"]
    assert result.document["authority"]["project_wide_authoritative"] is False


def test_unknown_and_orphan_ids_against_existing_inventory_are_visible():
    result = _project(reconciliation_inputs={"known_run_ids": ["run:a", "run:b", "run:c"]})
    assert "OMITTED_KNOWN_RUN_IDS" in result.document["reason_codes"]


def test_duplicate_json_keys_fail_closed():
    raw = b'{"schema":"' + RAW_EXPORT_SCHEMA.encode() + b'","schema":"other","records":[]}'
    result = _project(raw)
    assert result.status == STATUS_FAIL_CLOSED
    assert result.document["parse_error_class"] == "invalid_utf8_or_json"


def test_missing_scope_and_window_fail_closed():
    value = json.loads(_raw())
    value.pop("scope")
    value.pop("window")
    result = _project(json.dumps(value, separators=(",", ":")).encode())
    assert result.status == STATUS_FAIL_CLOSED
    assert {"MISSING_EXPORT_SCOPE", "MISSING_EXPORT_WINDOW"}.issubset(result.document["reason_codes"])


def test_permutation_of_reconciliation_sources_is_canonical_stable():
    extra = {
        "source_id": "source:independent-fixture",
        "source_identity": "provider:fixture|account:fixture",
        "source_role": "run_index",
        "source_byte_sha256": "b" * 64,
        "observed_at": AS_OF,
        "scope": {"scope_id": "project:paid", "kind": "project_window"},
        "schema_version": 1,
        "run_ids": ["run:c"],
        "missingness": {"state": "observed", "missing_ids": []},
        "provenance": {"capture": "fixture"},
    }
    extra_two = {**extra, "source_id": "source:second-fixture", "source_byte_sha256": "c" * 64, "run_ids": ["run:d"]}
    left = _project(reconciliation_inputs={"run_inventory_sources": [extra, extra_two]})
    right = _project(reconciliation_inputs={"run_inventory_sources": [extra_two, extra]})
    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256 == provider_history_evidence_sha256(left)
    assert canonical_provider_history_evidence_json(left) == left.canonical_json


def test_raw_payload_and_assertion_text_are_not_emitted():
    raw = _raw(secret_payload="DO_NOT_EMIT", raw_provider_response="PRIVATE")
    result = _project(raw, host_attestation={"proof_ref": "signed-looking-but-not-proof", "signed": "PRIVATE-SIGNATURE"})
    encoded = result.canonical_json.decode("utf-8")
    assert "DO_NOT_EMIT" not in encoded
    assert "PRIVATE" not in encoded
    assert "signed-looking-but-not-proof" in encoded


def test_invalid_raw_bytes_return_explicit_fail_closed_projection():
    result = _project(b"not json")
    assert result.status == STATUS_FAIL_CLOSED
    assert result.document["evidence_state"] == "NOT_OBSERVED"
    assert "RAW_EXPORT_NOT_UTF8_JSON" in result.document["reason_codes"]


def test_non_bytes_are_rejected_at_call_boundary():
    with pytest.raises(ValueError):
        adapt_phase5_provider_history_evidence(
            "not bytes",  # type: ignore[arg-type]
            source_identity=IDENTITY,
            acquisition_metadata=ACQUISITION,
        )
