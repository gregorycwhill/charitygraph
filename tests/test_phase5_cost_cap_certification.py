from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

import pytest

from charitygraph.phase5_execution_mandate import manifest_hash, proposed_phase5_standard_luna_manifest
from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
from charitygraph.phase5_standard_transport import body_sha256, canonical_standard_body_bytes
from charitygraph.runtime import InvalidTransitionError, SQLiteCatalog


NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def _prepared_row(tmp_path, suffix="a"):
    path = tmp_path / "catalog.sqlite3"
    catalog = SQLiteCatalog(path, authorization_path=path).open(initialize=True)
    manifest = proposed_phase5_standard_luna_manifest()
    mandate = manifest["mandate_id"]
    catalog.register_execution_mandate(
        mandate_id=mandate, manifest_hash=manifest_hash(manifest), authorization_text_hash="a" * 64,
        scope=manifest, contract_allowlist=tuple(manifest["allowed_contracts"]),
        aggregate_hard_aud=manifest["aggregate_hard_aud"], per_request_hard_aud=manifest["per_request_hard_aud"],
        phase_scope=manifest["phase_scope"], now=NOW,
    )
    catalog.activate_execution_mandate(mandate_id=mandate, authorization_text_hash="a" * 64, authorized_by="test", now=NOW)
    rid = "requestitem:" + hashlib.sha256(suffix.encode()).hexdigest()
    task_id = "semtask:" + hashlib.sha256((suffix + "task").encode()).hexdigest()
    subject_id = "subject:" + hashlib.sha256((suffix + "subject").encode()).hexdigest()[:32]
    run_id = "run:" + hashlib.sha256((suffix + "run").encode()).hexdigest()
    cohort_id = "cohort:" + hashlib.sha256((suffix + "cohort").encode()).hexdigest()
    job_id = "deliveryjob:" + hashlib.sha256((suffix + "job").encode()).hexdigest()
    physical_id = "taskrun:" + hashlib.sha256((suffix + "physical").encode()).hexdigest()
    delivery_id = "deliveryattempt:" + hashlib.sha256((suffix + "delivery").encode()).hexdigest()
    reservation_id = "reservation:" + hashlib.sha256((suffix + "reservation").encode()).hexdigest()
    catalog.register_cohort({"record_id": cohort_id, "cohort_code": suffix, "definition_version": "1", "membership_hash": "b" * 64, "budget_cap": {"amount": "1", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "phase5-cost-cert-test", "status": "planned", "configuration_hash": "c" * 64, "created_at": NOW})
    catalog.register_task({"record_id": task_id, "subject_id": subject_id, "cohort_id": cohort_id, "task_type": "direct_service_semantics", "task_schema": {"schema_id": "schema:test"}, "cache_key": "d" * 64, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run_id, now=NOW)
    catalog.create_delivery_job(delivery_job_id=job_id, run_id=run_id, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id="pricing:test", now=NOW)
    catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": "0.20", "currency": "AUD"}, "model_task_ids": (task_id,)}, now=NOW)
    catalog.reserve_execution_mandate(mandate_id=mandate, reservation_id=reservation_id, amount_aud="0.20", now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id=physical_id, run_id=run_id, subject_id=subject_id, delivery_mode="standard", provider_request_id=rid, model_task_ids=(task_id,), reservation_id=reservation_id, now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=rid, run_id=run_id, model_task_id=task_id, provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=job_id, physical_attempt_id=physical_id, now=NOW)
    catalog.create_provider_request_attempt(delivery_attempt_id=delivery_id, provider_request_item_id=rid, physical_attempt_id=physical_id, delivery_job_id=job_id, attempt_ordinal=1, authorization_id=mandate, attempt_class="initial", predecessor_attempt_id=None, now=NOW)
    contract = next(c for c in manifest["allowed_contracts"] if "direct-service-access-v1" in c["claim_families"])
    schema = {"type": "object", "properties": {"propositions": {"type": "array", "items": {"type": "object"}}}, "required": ["propositions"], "additionalProperties": False}
    body = {"model": "gpt-5.6-luna", "reasoning": {"effort": "low"}, "max_output_tokens": 8000, "store": False,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "pinned"}]}],
            "text": {"format": {"type": "json_schema", "name": "direct_service_semantics_v2", "strict": True, "schema": schema}},
            "metadata": {"logical_task_id": task_id, "semantic_contract_hash": contract["contract_identity_hash"]}}
    row = {
        "provider": "openai", "provider_request_item_id": rid, "logical_task_id": task_id,
        "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        "contract_identity_hash": contract["contract_identity_hash"], "task_profile": "direct_service_semantics",
        "task_profile_version": "2", "prompt_sha256": contract["prompt_sha256"], "schema_id": contract["schema_id"],
        "schema_version": contract["schema_version"], "schema_hash": hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "provider_schema_name": "direct_service_semantics_v2", "model": "gpt-5.6-luna", "reasoning_effort": "low",
        "delivery_mode": "standard", "provider_service_tier": None, "max_output_tokens": 8000,
        "request_body_sha256": body_sha256(canonical_standard_body_bytes(body)), "request_body": body,
        "hard_max_aud": "0.20", "reservation_id": reservation_id, "mandate_reservation_id": reservation_id,
        "physical_attempt_id": physical_id, "delivery_attempt_id": delivery_id,
    }
    return catalog, row, mandate, reservation_id, cohort_id, run_id


def test_eligible_exact_row_certifies_only_with_active_corrected_reservation(tmp_path):
    catalog, row, mandate, _, _, _ = _prepared_row(tmp_path)
    cert = certify_standard_execution_row(catalog, row, mandate_id=mandate)
    assert cert["status"] == "READY_TO_CROSS_PROVIDER_BOUNDARY"


def test_excluded_cost_cap_request_is_terminal_and_certification_refuses(tmp_path):
    catalog, row, mandate, reservation, _, _ = _prepared_row(tmp_path, "excluded")
    item = row["provider_request_item_id"]
    catalog.abandon_pre_send_provider_request(item, now=NOW, reason="economic_authority_cap_exceeded")
    catalog.release_cost(reservation, {"amount": "0.20", "currency": "AUD"}, now=NOW, entry_key="release:cost-cap:" + item)
    catalog.settle_execution_mandate_reservation(mandate_id=mandate, reservation_id=reservation, actual_aud="0", ambiguous=False, now=NOW)
    row["hard_max_aud"] = "0.269531"
    with pytest.raises(ValueError, match="request item is not prepared"):
        certify_standard_execution_row(catalog, row, mandate_id=mandate)
    durable = catalog.get_provider_request_item(item)
    physical = catalog.get_physical_attempt(row["physical_attempt_id"])
    attempts = catalog.list_provider_request_attempts(provider_request_item_id=item)
    assert durable["status"] == "cancelled"
    assert physical["status"] == "failed" and physical["send_started_at"] is None
    assert len(attempts) == 1 and attempts[0]["status"] == "cancelled"
    assert attempts[0]["failure_message_redacted"] == "economic_authority_cap_exceeded"
    with pytest.raises(InvalidTransitionError, match="prepared delivery attempt"):
        catalog.mark_standard_send_started(row["delivery_attempt_id"], now=NOW)
    catalog.abandon_pre_send_provider_request(item, now=NOW, reason="economic_authority_cap_exceeded")
    catalog.release_cost(reservation, {"amount": "0.20", "currency": "AUD"}, now=NOW, entry_key="release:cost-cap:" + item)
    catalog.settle_execution_mandate_reservation(mandate_id=mandate, reservation_id=reservation, actual_aud="0", ambiguous=False, now=NOW)
    assert catalog.get_reservation(reservation)["status"] == "released"
    assert Decimal(catalog.get_execution_mandate(mandate)["unresolved_reserved_aud"]) == 0
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM cost_entries WHERE reservation_id=? AND entry_type='reservation_release'", (reservation,)).fetchone()[0] == 1
    with catalog._authorization_connection() as conn:
        assert conn.execute("SELECT count(*) FROM execution_mandate_events WHERE mandate_id=? AND event_type='provider_request_superseded_pre_send'", (mandate,)).fetchone()[0] == 1
