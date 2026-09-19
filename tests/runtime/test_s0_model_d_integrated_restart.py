from dataclasses import replace
from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog
from charitygraph.scale_s0 import ExecutionAttemptIdentity, ScaleS0Preflight
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from runtime.test_scale_s0_durability import authority, REGISTRY, TASK


NOW = datetime(2026, 9, 19, tzinfo=timezone.utc).isoformat()
SUBJECTS = (
    "28004778081", "28000030179", "74068758654", "37646526132",
    "50169561394", "47613674461", "78053639115", "61002643852",
)


def _attempt(mandate):
    values = dict(
        attempt_id="attempt:model-d", mandate_id=mandate.mandate_id,
        mandate_hash=mandate.identity_hash, slice_id=mandate.slice_id,
        run_id="run:model-d", builder_repository="gregorycwhill/charitygraph",
        builder_commit_sha="6d24cc695feedfa8286f85b80b55425c4e3690d6",
        data_repository="gregorycwhill/charitygraph-data",
        data_commit_sha="366509f6bf8a723058353e69402625a1b0ded3b2",
        bridge_certification="S0_ACQUISITION_PACKET_BRIDGE_CERTIFIED",
        bridge_version="1", schema_version=19,
        recovery_authority_ref="recovery:model-d", status="prepared", created_at=NOW,
    )
    values["configuration_hash"] = canonical_execution_configuration_hash(**{
        key: values[key] for key in (
            "mandate_hash", "slice_id", "run_id", "builder_repository",
            "builder_commit_sha", "data_repository", "data_commit_sha",
            "bridge_certification", "bridge_version", "schema_version",
            "recovery_authority_ref",
        )
    })
    return ExecutionAttemptIdentity(**values)


def test_model_d_exact_eight_materialises_and_restarts_from_durable_graph(tmp_path):
    base, routing, policies, source, _packet, _economics = authority()
    mandate = replace(base, mandate_id="mandate:model-d", subject_ids=SUBJECTS)
    attempt = _attempt(mandate)
    catalog = SQLiteCatalog(tmp_path / "model-d.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {source.source_id: source})
    catalog.register_cohort({"record_id": "cohort:model-d", "cohort_code": "MODEL-D", "definition_version": "1", "membership_hash": "e" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:model-d", "run_kind": "s0", "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    packet_ids = []
    for index, subject in enumerate(SUBJECTS):
        plan = {"plan_id": f"plan:model-d:{index}", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "subject_id": subject, "subject_scope": f"scope:{subject}", "source_family": "retained_fixture", "created_at": NOW}
        catalog.register_scale_s0_source_plan(plan, execution_attempt_id=attempt.attempt_id)
        snapshot = {"snapshot_id": f"snapshot:model-d:{index}", "plan_id": plan["plan_id"], "source_record_id": f"source-record:model-d:{index}", "snapshot_hash": f"{index + 1:064x}", "acquired_at": NOW}
        catalog.register_scale_s0_source_snapshot(snapshot, mandate_id=mandate.mandate_id, execution_attempt_id=attempt.attempt_id)
        catalog.register_scale_s0_frozen_corpus({"corpus_id": f"corpus:model-d:{index}", "mandate_id": mandate.mandate_id, "subject_id": subject, "source_record_ids": (snapshot["source_record_id"],), "snapshot_hashes": (snapshot["snapshot_hash"],), "frozen_at": NOW}, execution_attempt_id=attempt.attempt_id)
        packet = {"packet_id": f"packet:model-d:{index}", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "task_key": TASK.key, "task_id": TASK.task_id, "task_version": TASK.version, "subject_id": subject, "scope_id": f"scope:{subject}", "content_hash": f"{index + 11:064x}", "binding_hash": f"{index + 21:064x}", "frozen_at": NOW, "source_ids": (f"source:model-d:{index}",), "source_snapshot_hashes": (snapshot["snapshot_hash"],), "input_profile_id": TASK.input_profile_id, "output_schema_id": TASK.output_schema_id, "routing_class": TASK.default_routing.value, "provider_request_identity": f"provider-request:model-d:{index}", "corpus_id": f"corpus:model-d:{index}", "execution_attempt_id": attempt.attempt_id}
        catalog.register_scale_s0_frozen_packet(packet)
        packet_ids.append(packet["packet_id"])
    bundle = {"bundle_id": "bundle:model-d", "mandate_id": mandate.mandate_id, "routing_class": TASK.default_routing.value, "packet_ids": tuple(packet_ids), "packet_hashes": tuple(f"{index + 21:064x}" for index in range(len(SUBJECTS))), "frozen_at": NOW}
    catalog.register_scale_s0_physical_bundle(bundle, execution_attempt_id=attempt.attempt_id)
    restarted = SQLiteCatalog(tmp_path / "model-d.sqlite3").open()
    assert restarted.get_scale_s0_execution_attempt(attempt.attempt_id)["run_id"] == attempt.run_id
    assert restarted.get_scale_s0_frozen_corpus("corpus:model-d:0")["execution_attempt_id"] == attempt.attempt_id
    assert restarted.get_scale_s0_frozen_packet(packet_ids[-1])["execution_attempt_id"] == attempt.attempt_id
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_physical_bundle(bundle, execution_attempt_id="attempt:other")
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_source_plan({**{k: v for k, v in {"plan_id": "plan:model-d:cross", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "subject_id": SUBJECTS[0], "subject_scope": "scope:x", "source_family": "retained_fixture", "created_at": NOW}.items()}}, execution_attempt_id="attempt:other")
    assert len(packet_ids) == 8
