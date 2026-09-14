from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput, wire_to_domain
from charitygraph.phase5_semantic_contracts import direct_service_representation_schema_v1_2

_path = Path("scripts/continue_phase5_direct_service_v12_amendment3.py")
_spec = importlib.util.spec_from_file_location("v12_amendment3_continuation", _path)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
FAILED_CANARY = _module.FAILED_CANARY
select_surviving_rows = _module.select_surviving_rows


def test_continuation_excludes_only_failed_canary_and_preserves_manifest_order():
    ids = [f"requestitem:{n:064x}" for n in range(18)]
    ids[7] = FAILED_CANARY
    rows = [{"provider_request_item_id": item, "ordinal": index} for index, item in enumerate(ids)]
    selected = select_surviving_rows(rows)
    assert len(selected) == 17
    assert all(row["provider_request_item_id"] != FAILED_CANARY for row in selected)
    assert [row["ordinal"] for row in selected] == [i for i in range(18) if i != 7]


@pytest.mark.parametrize("ids", [[], [{"provider_request_item_id": "duplicate"}] * 18])
def test_continuation_rejects_non_exact_manifest_shape(ids):
    with pytest.raises(RuntimeError, match="exact 18-item"):
        select_surviving_rows(ids)


def test_continuation_entry_point_does_not_activate_or_reprepare_authority():
    path = Path("scripts/continue_phase5_direct_service_v12_amendment3.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "activate_execution_mandate",
        "revoke_execution_mandate",
        "register_execution_mandate",
        "reserve_execution_mandate",
        "reserve_cost",
        "prepare_physical_attempt",
        "create_provider_request_item",
        "create_provider_request_attempt",
        "create_zero_crossing_pre_send_replacement",
    }
    assert not called.intersection(forbidden)


def test_terminal_item_canary_failure_does_not_block_independent_remainder():
    assert _module.canary_requires_campaign_stop({"results": [{"status": "failed_terminal"}]}) is False
    assert _module.canary_requires_campaign_stop({"results": [{"status": "completed_parse_failed"}]}) is False
    assert _module.canary_requires_campaign_stop({"results": [{"status": "ambiguous"}]}) is True
    assert _module.canary_requires_campaign_stop({"results": [{"status": "failed_pre_send"}]}) is True
    assert _module.canary_requires_campaign_stop({"results": [{"status": "completed_accounting_failed"}]}) is True
    assert _module.canary_requires_campaign_stop({"stop_campaign": True, "results": []}) is True


def test_responses_usage_is_projected_for_cost_ledger_without_losing_raw_details():
    original = {
        "input_tokens": 67925,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 67922},
        "output_tokens": 896,
        "output_tokens_details": {"reasoning_tokens": 174},
        "total_tokens": 68821,
    }
    ledger = _module.base.provider_usage_for_cost_ledger(original)
    assert ledger == {
        "input_tokens": 67925, "cached_input_tokens": 0, "output_tokens": 896,
        "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0,
        "other_billable_units": [],
    }
    assert original["output_tokens_details"]["reasoning_tokens"] == 174
    assert original["input_tokens_details"]["cache_write_tokens"] == 67922


def test_pinned_v12_section_array_response_parses_through_v12_contract_and_bindings():
    locator = "locator:" + "a" * 64
    scope = "scope:" + "b" * 64
    row = {
        "provider_schema_name": "direct_service_semantics_v2",
        "schema_hash": "",
        "request_body": {
            "input": [
                {"content": [{"text": f"scope:{scope.split(':', 1)[1]} | organisation | test"}]},
                {"content": [{"text": __import__("json").dumps({"evidence_bindings": [{"evidence_id": locator}]})}]},
            ],
            "text": {"format": {"type": "json_schema", "name": "direct_service_semantics_v2", "strict": True, "schema": {}}},
        }
    }
    schema = direct_service_representation_schema_v1_2()
    row["request_body"]["text"]["format"]["schema"] = schema
    row["schema_hash"] = hashlib.sha256(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    wire_output = {
        "section": "capability_access_availability",
        "participation": [],
        "capability_access_availability": [{
            "proposition_type": "service_offer", "scope_id": scope,
            "scope_kind": "organisation", "scope_label": "test organisation",
            "coverage_state": "supported", "value": "counselling",
            "unit": None, "scheme_id": None, "scheme_version": None,
            "scheme_status": None, "scheme_identifier": None,
            "observation_time": None,
            "evidence": [{"locator": locator, "role": "supporting"}],
            "qualification": None,
        }],
        "scheme_accreditation": [], "relationships": [],
    }
    _, domain = _module.base.parse_v12_response({"output_text": __import__("json").dumps(wire_output)}, row)
    assert len(domain.propositions) == 1
    assert domain.propositions[0].proposition_type == "service_offer"
    assert domain.propositions[0].evidence[0].locator == locator
    with pytest.raises(ValueError, match="pinned strict schema identity"):
        _module.base.parse_v12_response({"output_text": json.dumps(wire_output)}, {**row, "schema_hash": "0" * 64})


def test_legacy_v11_propositions_dto_remains_valid_for_legacy_parser():
    legacy = {
        "section": "participation",
        "propositions": [{
            "proposition_type": "participation_measure", "scope_id": "scope:" + "c" * 32,
            "scope_kind": "organisation", "scope_label": None, "coverage_state": "unknown",
            "value": 1, "unit": "person", "scheme_id": None, "scheme_version": None,
            "scheme_status": None, "scheme_identifier": None, "observation_time": None,
            "evidence": [], "qualification": None,
        }],
        "relationships": [],
    }
    parsed = DirectServiceWireOutput.model_validate_json(json.dumps(legacy))
    domain = wire_to_domain(parsed)
    assert len(domain.propositions) == 1
    assert domain.propositions[0].proposition_type == "participation_measure"


def test_response_metadata_path_matches_retained_transport_artifact_name(tmp_path):
    raw = tmp_path / "requestitem_example.json"
    assert _module.response_metadata_path(raw).name == "requestitem_example.meta.json"


def test_provider_free_replay_is_idempotent_and_does_not_mutate_accounting(monkeypatch, tmp_path):
    manifest = {"mandate_id_required": _module.MANDATE}
    jsonl = ("{}\n" * 18).encode()
    monkeypatch.setattr(_module, "load_campaign_assets", lambda root: (manifest, [], b"prep", jsonl, b"ticket"))
    monkeypatch.setattr(_module, "sha", lambda raw: _module.PREP_SHA if raw == b"prep" else _module.JSONL_SHA)
    monkeypatch.setattr(_module.rebind, "build_rows", lambda catalog, rows: [
        {"provider_request_item_id": _module.FAILED_CANARY},
        {"provider_request_item_id": _module.LIVE_CANARY, "physical_attempt_id": "taskrun:" + "d" * 64},
        *[{"provider_request_item_id": f"requestitem:{i:064x}"} for i in range(16)],
    ])
    evidence = {
        "builder_reservation_status": "consumed", "mandate_reservation_status": "settled",
        "corrected_interpretation": "directly_valid_v12_wire_and_domain",
        "provider_request_id": "req_local_fixture", "responses_id": "resp_local_fixture",
        "raw_response_sha256": "a" * 64, "section_counts": {"participation": 0},
        "proposal_count": 0, "relationship_count": 0,
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "actual_usd": "0.000007", "actual_aud": "0.000011",
    }
    calls = []
    monkeypatch.setattr(_module, "completed_canary_evidence", lambda catalog, row, root: calls.append(row) or evidence)
    raw_path = tmp_path / "standard-results" / (_module.LIVE_CANARY.replace(":", "_") + ".json")
    raw_path.parent.mkdir()
    body = {"id": "resp_local_fixture", "status": "completed", "usage": evidence["usage"]}
    raw_path.write_text(json.dumps(body), encoding="utf-8")
    _module.response_metadata_path(raw_path).write_text(json.dumps({"status_code": 200, "request_id": "req_local_fixture"}), encoding="utf-8")
    class QueryResult:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row
    class ReadOnlyConnection:
        def execute(self, query, args):
            if "count(*)" in query:
                return QueryResult((1,))
            return QueryResult({"actual_spend_aud": "2.728923", "unresolved_reserved_aud": "1.171788"})
    catalog = SimpleNamespace(
        list_provider_request_attempts=lambda **kwargs: [{"completed_at": "2026-09-12T00:00:00+00:00"}],
        _authorization_connection=lambda: nullcontext(ReadOnlyConnection()),
    )
    def replay(catalog, row, response, root, timestamp, parsed, *, result_dir):
        parsed[_module.LIVE_CANARY] = {"valid": True, "proposals": 0, "response_id": response.body["id"]}
    monkeypatch.setattr(_module.base, "reconcile", replay)
    result1 = _module.reconcile_completed_canary_without_provider(catalog, tmp_path)
    result2 = _module.reconcile_completed_canary_without_provider(catalog, tmp_path)
    assert result1 == result2
    assert result1["actual_entries_for_canary"] == 1
    assert result1["duplicate_actual_entries"] == 0
    assert result1["accounting_mutations"] == 0
    assert result1["provider_operations"] == 0
    assert len(calls) == 4
