from dataclasses import replace
from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog
from charitygraph.scale_s0 import ExecutionAttemptIdentity, ScalePreflightError, ScaleS0Preflight
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from runtime.test_scale_s0_durability import authority, REGISTRY


NOW = datetime(2026, 9, 18, tzinfo=timezone.utc).isoformat()


def attempt(mandate, run_id="run:s0-attempt"):
    builder_repository = "gregorycwhill/charitygraph"
    builder_commit_sha = "f3ea027c6159344d82b075304e5d33bf0b30c7c7"
    data_repository = "gregorycwhill/charitygraph-data"
    data_commit_sha = "870fe92502583a85133005bc5ebab62154920e22"
    bridge_certification = "S0_ACQUISITION_PACKET_BRIDGE_CERTIFIED"
    bridge_version = "1"
    schema_version = 19
    recovery_authority_ref = "recovery:2026-09-18"
    return ExecutionAttemptIdentity(
        "attempt:s0:test", mandate.mandate_id, mandate.identity_hash, mandate.slice_id, run_id,
        builder_repository, builder_commit_sha, data_repository, data_commit_sha,
        bridge_certification, bridge_version, schema_version, recovery_authority_ref,
        canonical_execution_configuration_hash(mandate_hash=mandate.identity_hash, slice_id=mandate.slice_id, run_id=run_id,
            builder_repository=builder_repository, builder_commit_sha=builder_commit_sha, data_repository=data_repository,
            data_commit_sha=data_commit_sha, bridge_certification=bridge_certification, bridge_version=bridge_version,
            schema_version=schema_version, recovery_authority_ref=recovery_authority_ref), "prepared", NOW)


def test_attempt_identity_is_idempotent_restart_safe_and_drift_locked(tmp_path):
    mandate, routing, policies, source, packet, _ = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {})
    catalog.register_cohort({"record_id": "cohort:test", "cohort_code": "s0-test", "definition_version": "1", "membership_hash": "m" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    identity = attempt(mandate)
    catalog.register_run({"record_id": "run:s0-attempt", "cohort_id": "cohort:test", "run_kind": "s0", "status": "planned", "configuration_hash": identity.configuration_hash, "created_at": NOW})
    first = ScaleS0Preflight.register_durable_execution_attempt(catalog, identity)
    assert first["builder_commit_sha"].startswith("f3ea027")
    assert ScaleS0Preflight.register_durable_execution_attempt(catalog, identity)["material_hash"] == first["material_hash"]
    reopened = SQLiteCatalog(tmp_path / "state.sqlite3").open()
    assert reopened.get_scale_s0_execution_attempt(identity.attempt_id)["data_commit_sha"].startswith("870fe925")
    with pytest.raises(ConflictError):
        ScaleS0Preflight.register_durable_execution_attempt(catalog, replace(identity, builder_commit_sha="0" * 40))
    with pytest.raises(ConflictError):
        catalog.require_scale_s0_execution_attempt(attempt_id=identity.attempt_id, mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash, slice_id=mandate.slice_id, run_id="run:other", builder_commit_sha=identity.builder_commit_sha, data_commit_sha=identity.data_commit_sha, bridge_certification=identity.bridge_certification, schema_version=19)
    with pytest.raises(ConflictError):
        ScaleS0Preflight.register_durable_execution_attempt(catalog, replace(identity, attempt_id="attempt:s0:second"))


def test_source_plan_requires_matching_attempt_when_live(tmp_path):
    mandate, routing, policies, source, packet, _ = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {})
    catalog.register_cohort({"record_id": "cohort:test", "cohort_code": "s0-test", "definition_version": "1", "membership_hash": "m" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    identity = attempt(mandate)
    catalog.register_run({"record_id": "run:s0-attempt", "cohort_id": "cohort:test", "run_kind": "s0", "status": "planned", "configuration_hash": identity.configuration_hash, "created_at": NOW})
    plan = {"plan_id": "source-plan:test", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "subject_id": "subject:a", "subject_scope": "scope:a", "source_family": "annual_report", "created_at": NOW}
    with pytest.raises(ConflictError): catalog.register_scale_s0_source_plan(plan, execution_attempt_id="attempt:s0:missing")
    ScaleS0Preflight.register_durable_execution_attempt(catalog, identity)
    assert catalog.register_scale_s0_source_plan(plan, execution_attempt_id=identity.attempt_id)["plan_id"] == plan["plan_id"]


def test_live_fresh_process_cannot_reconstruct_unbound_packet(tmp_path):
    mandate, routing, policies, source, packet, _ = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {})
    ScaleS0Preflight.register_durable_packet(catalog, mandate, packet, offline=True)
    with pytest.raises(ScalePreflightError):
        ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)


def test_snapshot_owner_is_derived_from_persisted_plan_not_caller(tmp_path):
    mandate, routing, policies, source, packet, _ = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {})
    catalog.register_cohort({"record_id": "cohort:test", "cohort_code": "s0-test", "definition_version": "1", "membership_hash": "m" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    identity = attempt(mandate)
    catalog.register_run({"record_id": "run:s0-attempt", "cohort_id": "cohort:test", "run_kind": "s0", "status": "planned", "configuration_hash": identity.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, identity)
    plan = {"plan_id": "source-plan:owner", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "subject_id": "subject:a", "subject_scope": "scope:a", "source_family": "annual_report", "created_at": NOW}
    catalog.register_scale_s0_source_plan(plan, execution_attempt_id=identity.attempt_id)
    snapshot = {"snapshot_id": "snapshot:owner", "plan_id": plan["plan_id"], "source_record_id": "source-record:owner", "snapshot_hash": "a" * 64, "acquired_at": NOW}
    with pytest.raises(ConflictError): catalog.register_scale_s0_source_snapshot(snapshot, mandate_id=mandate.mandate_id, execution_attempt_id="attempt:s0:other")
    stored = catalog.register_scale_s0_source_snapshot(snapshot, mandate_id=mandate.mandate_id, execution_attempt_id=identity.attempt_id)
    assert stored["execution_attempt_id"] == identity.attempt_id
