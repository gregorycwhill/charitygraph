from __future__ import annotations

import json
from pathlib import Path

import pytest

from charitygraph.phase5_execution_tickets import (
    build_cost_cap_remainder_ticket,
    build_superseding_ticket,
    canonical_bytes,
    create_completed_canary_ticket,
    create_cost_cap_remainder_ticket,
    create_superseding_ticket,
    sha256,
    validate_completed_canary_ticket,
    validate_cost_cap_remainder_ticket,
    validate_superseding_ticket,
)


def fixture_material(tmp_path: Path):
    rows = []
    lines = []
    for i in range(18):
        rid = f"requestitem:{i:064x}"
        body = {"model": "gpt-5.6-luna", "input": [{"text": f"pinned-{i}"}], "max_output_tokens": 8000}
        rows.append({
            "provider_request_item_id": rid, "logical_task_id": f"semtask:{i:064x}",
            "subject_id": f"subject:{i:032x}", "request_body": body,
            "request_body_sha256": sha256(canonical_bytes(body)), "wire_fingerprint": f"{i:064x}",
            "hard_max_usd": "0.010000", "hard_max_aud": "0.015200",
            "contract_id": "urn:charitygraph:builder:semantic-contract:direct-service-v1",
            "contract_version": "1.2", "contract_identity_hash": "contract-hash",
            "prompt_sha256": "prompt-hash", "schema_id": "schema-id", "schema_version": "1.2",
            "schema_hash": "schema-hash", "provider_schema_name": "direct_service_semantics_v2",
        })
        lines.append({"custom_id": rid, "body": body})
    prep = {
        "request_items": rows, "model": "gpt-5.6-luna", "reasoning_effort": "low",
        "delivery_mode": "standard", "provider_service_tier": "omitted", "max_output_tokens": 8000,
        "mandate_id_required": "mandate:amendment-3", "max_concurrency": 4,
        "terminal_429_excluded": "requestitem:429", "old_v1_1_requests_excluded": ["requestitem:old"],
    }
    prep_raw = canonical_bytes(prep)
    jsonl_raw = b"\n".join(canonical_bytes(line) for line in lines) + b"\n"
    predecessor = {
        "ticket_version": "phase5-direct-service-v1.2-future-execution-ticket-v1",
        "campaign": "test-v1.2", "run_id": "run:test", "delivery_job_id": "deliveryjob:test",
        "builder_commit_required": "old-commit", "preparation_manifest_sha256": sha256(prep_raw),
        "preparation_manifest_bytes": len(prep_raw), "jsonl_sha256": sha256(jsonl_raw),
        "jsonl_bytes": len(jsonl_raw), "model": "gpt-5.6-luna", "reasoning_effort": "low",
        "delivery_mode": "standard", "max_output_tokens": 8000, "mandate_id_required": "mandate:amendment-3",
        "excluded_terminal_429": "requestitem:429", "excluded_v1_1_requests": ["requestitem:old"],
        "per_request_hard_aud": "0.25",
        "contract_identity": {"contract_id": rows[0]["contract_id"], "contract_version": rows[0]["contract_version"],
            "provider_schema_name": rows[0]["provider_schema_name"], "task_profile": "direct_service_semantics",
            "task_profile_version": "2"},
    }
    predecessor_path = tmp_path / "future-execution-ticket.json"
    predecessor_raw = canonical_bytes(predecessor)
    predecessor_path.write_bytes(predecessor_raw)
    evidence = {
        "request_item_id": rows[4]["provider_request_item_id"], "request_status": "failed",
        "physical_status": "failed", "failure_class": "pre_send_validation", "send_started": False,
        "provider_crossings": 0, "provider_request_id": None, "provider_receipt_id": None,
        "usage": None, "builder_reservation_status": "released",
        "mandate_reservation_status": "settled", "actual_aud": "0",
    }
    kwargs = dict(
        predecessor_path=predecessor_path, predecessor_bytes=predecessor_raw,
        builder_commit="new-commit", preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw,
        excluded_request_id=rows[4]["provider_request_item_id"], exclusion_evidence=evidence,
        supersession_reason="Append-only control-plane pin; same requests except proven no-send canary.",
    )
    return predecessor_path, predecessor_raw, prep_raw, jsonl_raw, evidence, kwargs


def test_superseding_ticket_is_append_only_and_repeatable(tmp_path):
    prior_path, prior_raw, prep, jsonl, _, kwargs = fixture_material(tmp_path)
    new_path = tmp_path / "future-execution-ticket-v2.json"
    value, created = create_superseding_ticket(ticket_path=new_path, **kwargs)
    assert created is True
    assert prior_path.read_bytes() == prior_raw
    assert new_path != prior_path
    assert value["request_set"]["count"] == 17
    assert value["limits"]["aggregate_hard_max_aud"] == "0.258400"
    assert value["supersedes"]["sha256"] == sha256(prior_raw)
    again, created_again = create_superseding_ticket(ticket_path=new_path, **kwargs)
    assert created_again is False
    assert again == value
    validate_superseding_ticket(ticket_path=new_path, **{
        k: v for k, v in kwargs.items() if k not in {"predecessor_bytes"}
    })


def test_ticket_rejects_stale_predecessor_body_set_and_commit(tmp_path):
    prior, _, prep, jsonl, _, kwargs = fixture_material(tmp_path)
    with pytest.raises(ValueError, match="unknown or changed predecessor"):
        build_superseding_ticket(**{**kwargs, "predecessor_path": tmp_path / "missing.json"})
    new = tmp_path / "future-execution-ticket-v2.json"
    create_superseding_ticket(ticket_path=new, **kwargs)
    with pytest.raises(ValueError, match="differs from deterministic supersession"):
        validate_superseding_ticket(ticket_path=new, predecessor_path=prior, builder_commit="other-commit",
            preparation_bytes=prep, jsonl_bytes=jsonl, excluded_request_id=kwargs["excluded_request_id"],
            exclusion_evidence=kwargs["exclusion_evidence"], supersession_reason=kwargs["supersession_reason"])
    changed = jsonl.replace(b"pinned-0", b"changed-0")
    with pytest.raises(ValueError, match="campaign JSONL differs"):
        build_superseding_ticket(**{**kwargs, "jsonl_bytes": changed})


def test_ticket_rejects_nonzero_crossing_exclusion_and_duplicate_successor(tmp_path):
    prior, _, _, _, evidence, kwargs = fixture_material(tmp_path)
    with pytest.raises(ValueError, match="not proven"):
        build_superseding_ticket(**{**kwargs, "exclusion_evidence": {**evidence, "provider_crossings": 1}})
    first = tmp_path / "future-execution-ticket-v2.json"
    second = tmp_path / "future-execution-ticket-v3.json"
    create_superseding_ticket(ticket_path=first, **kwargs)
    second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError, match="duplicate or ambiguous"):
        validate_superseding_ticket(ticket_path=first, predecessor_path=prior, builder_commit="new-commit",
            preparation_bytes=kwargs["preparation_bytes"], jsonl_bytes=kwargs["jsonl_bytes"],
            excluded_request_id=kwargs["excluded_request_id"], exclusion_evidence=kwargs["exclusion_evidence"],
            supersession_reason=kwargs["supersession_reason"])


def test_ticket_rejects_body_mismatch_even_when_jsonl_pin_is_updated(tmp_path):
    prior, prior_raw, prep_raw, jsonl_raw, _, kwargs = fixture_material(tmp_path)
    bad_lines = jsonl_raw.replace(b"pinned-0", b"changed-0")
    prior_value = json.loads(prior_raw)
    prior_value["jsonl_sha256"] = sha256(bad_lines)
    prior_value["jsonl_bytes"] = len(bad_lines)
    new_prior = canonical_bytes(prior_value)
    prior.write_bytes(new_prior)
    with pytest.raises(ValueError, match="provider body differs"):
        build_superseding_ticket(**{**kwargs, "predecessor_bytes": new_prior, "jsonl_bytes": bad_lines})


def test_completed_canary_ticket_appends_checkpoint_and_retains_16_prepared_ids(tmp_path):
    prior, prior_raw, prep, jsonl, _, kwargs = fixture_material(tmp_path)
    v2_path = tmp_path / "future-execution-ticket-v2.json"
    create_superseding_ticket(ticket_path=v2_path, **kwargs)
    v2_raw = v2_path.read_bytes()
    v2_value = json.loads(v2_raw)
    canary_id = v2_value["request_set"]["requests"][0]["provider_request_item_id"]
    completed = {
        "request_item_id": canary_id,
        "request_status": "completed",
        "delivery_attempt_status": "completed",
        "provider_crossings": 1,
        "provider_request_id": "req_fixture",
        "provider_receipt_id": "receipt_fixture",
        "responses_id": "resp_fixture",
        "raw_response_sha256": "a" * 64,
        "corrected_interpretation": "directly_valid_v12_wire_and_domain",
        "exact_evidence_validation": "valid",
        "provider_operations_during_reconciliation": 0,
    }
    ticket_path = tmp_path / "future-execution-ticket-v3.json"
    ticket_kwargs = {
        "predecessor_path": v2_path,
        "predecessor_bytes": v2_raw,
        "predecessor_sha256": sha256(v2_raw),
        "builder_commit": "recovered-commit",
        "preparation_bytes": prep,
        "jsonl_bytes": jsonl,
        "completed_canary": completed,
    }
    value, created = create_completed_canary_ticket(ticket_path=ticket_path, **ticket_kwargs)
    assert created is True
    assert prior.read_bytes() == prior_raw
    assert v2_path.read_bytes() == v2_raw
    assert value["request_set"]["count"] == 17
    assert len(value["request_set"]["outstanding_request_item_ids"]) == 16
    assert canary_id not in value["request_set"]["outstanding_request_item_ids"]
    again, created_again = create_completed_canary_ticket(ticket_path=ticket_path, **ticket_kwargs)
    assert created_again is False
    assert again == value
    validate_completed_canary_ticket(
        ticket_path=ticket_path,
        predecessor_path=v2_path,
        predecessor_sha256=sha256(v2_raw),
        builder_commit="recovered-commit",
        preparation_bytes=prep,
        jsonl_bytes=jsonl,
        completed_canary=completed,
    )


def test_cost_cap_ticket_binds_13_eligible_3_excluded_and_historical_canary(tmp_path):
    predecessor, _, prep_raw, jsonl_raw, _, old_kwargs = fixture_material(tmp_path)
    v2_path = tmp_path / "future-execution-ticket-v2.json"
    create_superseding_ticket(ticket_path=v2_path, **old_kwargs)
    v2_raw = v2_path.read_bytes()
    v2 = json.loads(v2_raw)
    canary_id = v2["request_set"]["requests"][0]["provider_request_item_id"]
    canary_evidence = {
        "request_item_id": canary_id, "request_status": "completed",
        "delivery_attempt_status": "completed", "provider_crossings": 1,
        "provider_request_id": "req_canary", "provider_receipt_id": "receipt_canary",
        "responses_id": "resp_canary", "raw_response_sha256": "d" * 64,
        "corrected_interpretation": "directly_valid_v12_wire_and_domain",
        "exact_evidence_validation": "valid", "provider_operations_during_reconciliation": 0,
    }
    v3_path = tmp_path / "future-execution-ticket-v3.json"
    create_completed_canary_ticket(
        ticket_path=v3_path, predecessor_path=v2_path, predecessor_bytes=v2_raw,
        predecessor_sha256=sha256(v2_raw), builder_commit="canary-commit",
        preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw, completed_canary=canary_evidence,
    )
    v3_raw = v3_path.read_bytes()
    v3 = json.loads(v3_raw)
    original = {r["provider_request_item_id"]: r for r in json.loads(prep_raw)["request_items"]}
    outstanding = v3["request_set"]["outstanding_request_item_ids"]
    excluded_ids = set(outstanding[-3:])
    eligible, excluded = [], []
    for index, rid in enumerate(outstanding):
        source = original[rid]
        common = {k: source[k] for k in ("provider_request_item_id", "logical_task_id", "subject_id", "request_body_sha256", "wire_fingerprint")}
        if rid in excluded_ids:
            excluded.append(common | {
                "classification": "EXCLUDED_COST_CAP", "reason": "economic_authority_cap_exceeded",
                "hard_max_usd": "0.200000", "hard_max_aud": ("0.269531" if index == 13 else "0.300608" if index == 14 else "0.462635"),
                "provider_crossings": 0, "provider_request_id": None, "provider_receipt_id": None,
                "usage": None, "actual_aud": "0", "builder_reservation_status": "released",
                "mandate_reservation_status": "settled",
            })
        else:
            eligible.append(common | {
                "old_reservation_id": f"reservation:old:{index}",
                "active_reservation_id": f"reservation:new:{index}",
                "hard_max_usd": "0.020000", "hard_max_aud": "0.030400",
            })
    kwargs = {
        "predecessor_path": v3_path, "predecessor_bytes": v3_raw,
        "builder_commit": "reduced-commit", "preparation_bytes": prep_raw,
        "jsonl_bytes": jsonl_raw, "eligible_requests": eligible,
        "excluded_requests": excluded, "mandate_id": "mandate:amendment-3",
    }
    v4_path = tmp_path / "future-execution-ticket-v4.json"
    value, created = create_cost_cap_remainder_ticket(ticket_path=v4_path, **kwargs)
    assert created is True
    assert predecessor.read_bytes() != b"" and v3_path.read_bytes() == v3_raw
    assert value["ticket_version"] == "phase5-execution-ticket-v4"
    assert value["builder_commit_required"] == "reduced-commit"
    assert value["request_set"]["count"] == 13
    assert len(value["request_set"]["excluded_cost_cap_requests"]) == 3
    assert value["historical_completed_canary"] == canary_evidence
    assert set(value["request_set"]["excluded_request_item_ids"]) == excluded_ids
    replay, created_again = create_cost_cap_remainder_ticket(ticket_path=v4_path, **kwargs)
    assert created_again is False and replay == value
    validate_cost_cap_remainder_ticket(ticket_path=v4_path, **kwargs)


def test_cost_cap_ticket_rejects_an_over_cap_member_as_eligible(tmp_path):
    predecessor, _, prep_raw, jsonl_raw, _, old_kwargs = fixture_material(tmp_path)
    v2_path = tmp_path / "future-execution-ticket-v2.json"
    create_superseding_ticket(ticket_path=v2_path, **old_kwargs)
    v2_raw = v2_path.read_bytes()
    v2 = json.loads(v2_raw)
    canary_id = v2["request_set"]["requests"][0]["provider_request_item_id"]
    v3_path = tmp_path / "future-execution-ticket-v3.json"
    evidence = {"request_item_id": canary_id, "request_status": "completed", "delivery_attempt_status": "completed", "provider_crossings": 1, "provider_request_id": "req", "provider_receipt_id": "receipt", "responses_id": "resp", "raw_response_sha256": "e"*64, "corrected_interpretation": "directly_valid_v12_wire_and_domain", "exact_evidence_validation": "valid", "provider_operations_during_reconciliation": 0}
    create_completed_canary_ticket(ticket_path=v3_path, predecessor_path=v2_path, predecessor_bytes=v2_raw, predecessor_sha256=sha256(v2_raw), builder_commit="canary-commit", preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw, completed_canary=evidence)
    v3=json.loads(v3_path.read_bytes()); outstanding=v3["request_set"]["outstanding_request_item_ids"]
    original={r["provider_request_item_id"]:r for r in json.loads(prep_raw)["request_items"]}
    eligible=[]; excluded=[]
    for i,rid in enumerate(outstanding):
        row={k:original[rid][k] for k in ("provider_request_item_id","logical_task_id","subject_id","request_body_sha256","wire_fingerprint")}
        if i==len(outstanding)-1:
            row.update({"classification":"EXCLUDED_COST_CAP","reason":"economic_authority_cap_exceeded","hard_max_aud":"0.300608","provider_crossings":0,"provider_request_id":None,"provider_receipt_id":None,"usage":None,"actual_aud":"0","builder_reservation_status":"released","mandate_reservation_status":"settled"}); excluded.append(row)
        else:
            row.update({"active_reservation_id":f"reservation:new:{i}","hard_max_usd":"0.2","hard_max_aud":"0.30"}); eligible.append(row)
    with pytest.raises(ValueError, match="eligible ticket request has changed identity or exceeds cost authority"):
        build_cost_cap_remainder_ticket(predecessor_path=v3_path, predecessor_bytes=v3_path.read_bytes(), builder_commit="commit", preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw, eligible_requests=eligible, excluded_requests=excluded, mandate_id="mandate:amendment-3")
