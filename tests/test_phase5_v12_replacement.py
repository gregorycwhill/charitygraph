from datetime import datetime, timezone

import pytest

from charitygraph.phase5_execution_mandate import (
    proposed_phase5_standard_luna_v1_2_amendment4_manifest,
)
from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
from charitygraph.runtime import SQLiteCatalog


NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def test_amendment4_is_narrow_zero_crossing_authority():
    manifest = proposed_phase5_standard_luna_v1_2_amendment4_manifest()
    assert manifest["supersedes_mandate_id"].endswith("amendment-3")
    assert manifest["mandate_id"].endswith("amendment-4")
    assert manifest["zero_crossing_pre_send_replacement"]["max_replacements"] == 1
    assert manifest["zero_crossing_pre_send_replacement"]["provider_retry_or_resend"] is False
    assert manifest["model"] == "gpt-5.6-luna"
    assert manifest["delivery_mode"] == "standard"


def test_certification_rejects_missing_executor_mandate_fields():
    with pytest.raises(ValueError, match="contract_identity_hash"):
        certify_standard_execution_row(object(), {"provider": "openai"}, mandate_id="mandate:test")


def test_zero_crossing_replacement_preserves_terminal_history(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    catalog = SQLiteCatalog(path, authorization_path=path).open(initialize=True)
    cohort = "cohort:" + "a" * 64
    run = "run:" + "b" * 64
    old_job = "deliveryjob:" + "c" * 64
    new_job = "deliveryjob:" + "d" * 64
    task = "modeltask:" + "e" * 64
    subject = "subject:" + "f" * 64
    old_mandate = "mandate:" + "1" * 64
    new_mandate = "mandate:" + "2" * 64
    catalog.register_cohort({"record_id": cohort, "cohort_code": "T", "definition_version": "1", "membership_hash": "3" * 64, "budget_cap": {"amount": "2", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": run, "cohort_id": cohort, "run_kind": "t", "status": "planned", "configuration_hash": "4" * 64, "created_at": NOW})
    catalog.register_task({"record_id": task, "subject_id": subject, "cohort_id": cohort, "task_type": "t", "task_schema": {"schema_id": "urn:t"}, "cache_key": "5" * 64, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run, now=NOW)
    for job, suffix in ((old_job, "6"), (new_job, "7")):
        catalog.create_delivery_job(delivery_job_id=job, run_id=run, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id="pricing:t", now=NOW)
    for mandate, supersedes, manifest_hash, auth_hash in ((old_mandate, None, "8" * 64, "9" * 64), (new_mandate, old_mandate, "a" * 64, "b" * 64)):
        catalog.register_execution_mandate(mandate_id=mandate, manifest_hash=manifest_hash, authorization_text_hash=auth_hash, scope={"m": mandate}, contract_allowlist=(), aggregate_hard_aud="10", per_request_hard_aud="10", phase_scope="test", supersedes_mandate_id=supersedes, now=NOW)
        catalog.activate_execution_mandate(mandate_id=mandate, authorization_text_hash=auth_hash, authorized_by="test", now=NOW)
    old_res = "reservation:" + "a" * 64
    new_res = "reservation:" + "b" * 64
    for reservation, mandate in ((old_res, old_mandate), (new_res, new_mandate)):
        catalog.reserve_cost({"record_id": reservation, "cohort_id": cohort, "run_id": run, "reserved_aud": {"amount": "0.10", "currency": "AUD"}, "model_task_ids": (task,)}, now=NOW)
        catalog.reserve_execution_mandate(mandate_id=mandate, reservation_id=reservation, amount_aud="0.10", now=NOW)
    item = "requestitem:" + "c" * 64
    old_phys = "taskrun:" + "d" * 64
    old_attempt = "deliveryattempt:" + "e" * 64
    catalog.prepare_physical_attempt(physical_attempt_id=old_phys, run_id=run, subject_id=subject, delivery_mode="standard", provider_request_id=item, model_task_ids=(task,), reservation_id=old_res, now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=item, run_id=run, model_task_id=task, provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=old_job, physical_attempt_id=old_phys, now=NOW)
    catalog.create_provider_request_attempt(delivery_attempt_id=old_attempt, provider_request_item_id=item, physical_attempt_id=old_phys, delivery_job_id=old_job, attempt_ordinal=1, authorization_id=old_mandate, attempt_class="initial", predecessor_attempt_id=None, now=NOW)
    catalog.settle_standard_failure(old_attempt, failure_class="pre_send_validation", message="missing mandate binding", ambiguous=False, now=NOW)
    replacement = catalog.create_zero_crossing_pre_send_replacement(replacement_id="presendreplacement:" + "1" * 64, provider_request_item_id=item, new_physical_attempt_id="taskrun:" + "f" * 64, new_delivery_attempt_id="deliveryattempt:" + "2" * 64, new_delivery_job_id=new_job, new_reservation_id=new_res, authorization_id=new_mandate, provider_material_sha256="a" * 64, expected_provider_material_sha256="a" * 64, reason="zero-crossing local correction", now=NOW)
    assert replacement["old_delivery_attempt_id"] == old_attempt
    assert catalog.get_provider_request_attempt(old_attempt)["status"] == "failed"
    assert catalog.get_provider_request_item(item)["physical_attempt_id"] != old_phys
    with catalog._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM provider_pre_send_replacements").fetchone()[0] == 1
