import hashlib
import json

from charitygraph.phase5_t4a9_sqlite_accounting_contract import (
    validate_sqlite_accounting_contract,
)


AUTHORITY = {
    "source_id": "source:fixture",
    "source_kind": "runtime-catalogue-view",
    "source_version": "migration-29",
    "content_sha256": "a" * 64,
    "authority_id": "authority:fixture",
    "authority_version": "1",
    "retention_id": "retention:private",
    "retention_version": "1",
    "retention_status": "authorized",
}
PROVENANCE = {"source_id": AUTHORITY["source_id"], "source_kind": AUTHORITY["source_kind"], "content_sha256": AUTHORITY["content_sha256"]}
VIEW_NAMES = (
    "tasks", "task_attempts", "cost_entries", "physical_attempts",
    "physical_attempt_members", "provider_request_items",
    "provider_request_attempts", "provider_receipts",
)


def _coverage():
    return {
        "population_complete": True,
        "project_wide": True,
        "scope": "project:fixture",
        "requested_population": list(VIEW_NAMES),
        "flags": {name: True for name in VIEW_NAMES},
        "source_provenance": PROVENANCE,
    }


def _views():
    return {
        "tasks": [{"model_task_id": "task:1", "run_id": "run:1", "subject_id": "subject:1"}],
        "task_attempts": [{
            "task_run_id": "taskrun:1", "model_task_id": "task:1", "attempt_number": 1,
            "status": "succeeded", "provider_request_id": "request:1",
            "pricing_snapshot_id": "pricing:1", "fx_snapshot_id": "fx:1", "reservation_id": "reservation:1",
        }],
        "cost_entries": [{
            "entry_key": "cost:1", "run_id": "run:1", "task_run_id": "taskrun:1",
            "entry_type": "actual", "provider_amount": "1.00", "provider_currency": "AUD",
            "aud_amount": "1.00", "pricing_snapshot_id": "pricing:1", "fx_snapshot_id": "fx:1",
            "usage_json": '{"provider_receipt_id":"receipt:1","provider_request_item_id":"item:1"}',
            "accounting_amount": "1.00", "accounting_currency": "AUD",
        }],
        "physical_attempts": [{
            "physical_attempt_id": "physical:1", "run_id": "run:1", "subject_id": "subject:1",
            "status": "validated", "provider_request_id": "request:1", "reservation_id": "reservation:1",
        }],
        "physical_attempt_members": [{"physical_attempt_id": "physical:1", "model_task_id": "task:1"}],
        "provider_request_items": [{
            "provider_request_item_id": "item:1", "run_id": "run:1", "model_task_id": "task:1",
            "physical_attempt_id": "physical:1", "status": "completed", "provider_request_id": "request:1",
            "provider_receipt_id": "receipt:1",
        }],
        "provider_request_attempts": [{
            "delivery_attempt_id": "delivery:1", "provider_request_item_id": "item:1",
            "physical_attempt_id": "physical:1", "provider_receipt_id": "receipt:1",
            "status": "completed", "provider_request_id": "request:1",
        }],
        "provider_receipts": [{
            "provider_receipt_id": "receipt:1", "physical_attempt_id": "physical:1",
            "provider_request_id": "request:1",
        }],
    }


def _valid(views=None, coverage=None):
    return validate_sqlite_accounting_contract(views or _views(), source_authority=AUTHORITY, coverage=coverage or _coverage())


def test_linked_success_candidate_has_no_ticket_and_no_total():
    result = _valid()

    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert result.request_ticket is None
    assert result.independent_trust == "NOT_SUPPLIED"
    assert result.send_authorization == "NO_SEND_TICKET"
    assert result.linkage[0]["provider_receipt_id"] == "receipt:1"
    assert "actual_amount" not in result.linkage[0]
    assert result.canonical_sha256 == hashlib.sha256(result.canonical_bytes).hexdigest()


def test_duplicate_orphan_and_missing_receipt_are_not_attestable():
    views = _views()
    views["provider_request_attempts"].append(dict(views["provider_request_attempts"][0]))
    views["provider_request_items"][0]["provider_receipt_id"] = "receipt:missing"

    result = _valid(views)

    assert result.status == "NOT_ATTESTABLE"
    assert "duplicate_identity:provider_request_attempts:delivery:1" in result.diagnostics
    assert "duplicate_provider_request_attempts_physical_attempt_id:physical:1" in result.diagnostics
    assert "orphaned_provider_request_item_receipt:item:1" in result.diagnostics


def test_physical_attempt_contradiction_is_rejected():
    views = _views()
    views["provider_receipts"][0]["provider_request_id"] = "request:other"

    result = _valid(views)

    assert result.status == "NOT_ATTESTABLE"
    assert "contradictory_receipt_physical_identity:receipt:1" in result.diagnostics


def test_unpriced_and_ambiguous_are_rejected():
    views = _views()
    views["cost_entries"][0]["fx_snapshot_id"] = None
    views["physical_attempts"][0]["status"] = "held"

    result = _valid(views)

    assert result.status == "NOT_ATTESTABLE"
    assert "unpriced_cost_or_fx:cost:1" in result.diagnostics
    assert "physical_attempt_unresolved:physical:1" in result.diagnostics


def test_missing_authority_or_requested_population_coverage_fails_closed():
    coverage = _coverage()
    coverage["flags"]["provider_receipts"] = False
    coverage["requested_population"].remove("provider_receipts")

    result = validate_sqlite_accounting_contract(_views(), source_authority=None, coverage=coverage)
    assert result.status == "NOT_ATTESTABLE"
    assert "source_authority_missing_or_invalid" in result.diagnostics

    result = _valid(coverage=coverage)
    assert result.status == "NOT_ATTESTABLE"
    assert "requested_population_missing:provider_receipts" in result.diagnostics
    assert "coverage_not_complete:provider_receipts" in result.diagnostics


def test_canonical_replay_is_deterministic_for_mapping_view_order():
    first = _valid()
    views = _views()
    for name in views:
        views[name] = list(reversed(views[name]))
    second = _valid(views)

    assert first.canonical_bytes == second.canonical_bytes
    assert first.canonical_sha256 == second.canonical_sha256
    assert json.loads(first.canonical_bytes) == json.loads(second.canonical_bytes)


def test_non_aud_accounting_mismatch_and_missing_relationship_fail_closed():
    views = _views()
    views["cost_entries"][0]["accounting_currency"] = "USD"
    views["cost_entries"][0]["usage_json"] = "{}"

    result = _valid(views)

    assert result.status == "NOT_ATTESTABLE"
    assert "accounting_currency_not_aud:cost:1" in result.diagnostics
    assert "missing_relationship:cost_entries.provider_request_item_id:cost:1" in result.diagnostics


def test_validator_has_no_filesystem_database_socket_or_provider_surface():
    import inspect

    from charitygraph import phase5_t4a9_sqlite_accounting_contract as contract

    source = inspect.getsource(contract)
    assert "sqlite3" not in source
    assert "socket" not in source
    assert "open(" not in source
    assert "Path(" not in source
