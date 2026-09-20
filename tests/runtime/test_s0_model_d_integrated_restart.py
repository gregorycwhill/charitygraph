from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog
from charitygraph.scale_s0 import ExecutionAttemptIdentity, ScalePreflightError, ScaleS0Preflight
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from charitygraph.s0_acquisition_bridge import (
    FrozenCorpus, MandatePopulation, PhysicalBundle, RepresentationRecord,
    SourcePlan, SourceSnapshot, TaskApplicability, bundle_packets,
    persist_bridge, task_applicability,
)
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
    mandate = replace(base, mandate_id="mandate:model-d", subject_ids=SUBJECTS,
                      mandatory_source_families=("latest_authorised_annual_report",),
                      applicable_source_families=("latest_authorised_annual_report",))
    attempt = _attempt(mandate)
    catalog = SQLiteCatalog(tmp_path / "model-d.sqlite3").open(initialize=True)
    durable_sources = {f"source:model-d:{index}": replace(source, source_id=f"source:model-d:{index}", source_family="latest_authorised_annual_report", source_record_id=f"source-record:model-d:{index}", snapshot_hash=f"{index + 1:064x}") for index in range(len(SUBJECTS))}
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, durable_sources)
    catalog.register_cohort({"record_id": "cohort:model-d", "cohort_code": "MODEL-D", "definition_version": "1", "membership_hash": "e" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:model-d", "run_kind": "s0", "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    population = MandatePopulation.from_mandate(mandate, SUBJECTS)
    plans, snapshots, representations, corpora, packets = [], [], [], [], []
    for index, subject in enumerate(SUBJECTS):
        plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, subject, f"scope:{subject}", "latest_authorised_annual_report", "offline_fixture", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", f"fixture://model-d/{index}", mandate.policy_hashes["source_universe"], NOW)
        snapshot = SourceSnapshot(plan.plan_id, f"source:model-d:{index}", f"source-record:model-d:{index}", f"{index + 1:064x}", "text/plain", plan.locator, NOW, "acquired", __import__("charitygraph.scale_s0", fromlist=["DocumentRepresentation"]).DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only", f"fixture:model-d:{index}")
        representation = RepresentationRecord(f"representation:model-d:{index}", snapshot.source_id, snapshot.snapshot_hash, "reliable_extracted_text", "text_extraction_only", snapshot.snapshot_hash, (), (), {"fixture": True}, NOW)
        corpus = FrozenCorpus(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, subject, (snapshot.source_record_id,), (snapshot.snapshot_hash,), (representation.representation_kind,), (), NOW)
        applicability = tuple(item for item in task_applicability(REGISTRY, mandate, corpus, scope_id=f"scope:{subject}") if item.task_id == TASK.task_id)
        packets.extend(__import__("charitygraph.s0_acquisition_bridge", fromlist=["frozen_packets"]).frozen_packets(mandate, REGISTRY, corpus, (snapshot,), applicability, now=datetime.fromisoformat(NOW)))
        plans.append(plan); snapshots.append(snapshot); representations.append(representation); corpora.append(corpus)
    population_subjects = population.subject_ids
    bundles = bundle_packets(mandate, packets, now=datetime.fromisoformat(NOW))
    persist_bridge(catalog, mandate, plans=plans, snapshots=snapshots, representations=representations, corpora=corpora, bundles=(), execution_attempt_id=attempt.attempt_id)
    for packet in packets:
        ScaleS0Preflight.register_durable_packet(catalog, mandate, packet, execution_attempt_id=attempt.attempt_id)
    persist_bridge(catalog, mandate, plans=(), snapshots=(), representations=(), corpora=(), bundles=bundles, execution_attempt_id=attempt.attempt_id)
    provider_packet = next(packet for packet in packets if packet.task_id == TASK.task_id)
    catalog.register_task({"record_id": TASK.key, "run_id": attempt.run_id, "subject_id": provider_packet.subject_id, "scope_id": provider_packet.scope_id, "cohort_id": "cohort:model-d", "task_type": "s0", "task_schema": TASK.input_profile_id, "cache_key": TASK.key, "provider_id": "synthetic", "model_snapshot": "fixture"}, run_id=attempt.run_id, now=NOW)
    reservation = catalog.reserve_cost({"record_id": "reservation:model-d", "cohort_id": "cohort:model-d", "run_id": attempt.run_id, "reserved_aud": {"amount": "1", "currency": "AUD"}, "model_task_ids": (TASK.key,)}, now=NOW)
    economics = replace(_economics, reservation_id=reservation["reservation_id"], reservation_active=True, reservation_mandate_id=mandate.mandate_id, reservation_slice_id=mandate.slice_id, reservation_task_key=TASK.key, reservation_remaining=Decimal("1"), estimated_provider_cost=Decimal("0.1"), reservation_currency="AUD")
    ScaleS0Preflight.record_durable_reservation(catalog, economics, recorded_at=NOW, execution_attempt_id=attempt.attempt_id)
    restarted = SQLiteCatalog(tmp_path / "model-d.sqlite3").open()
    assert restarted.get_scale_s0_execution_attempt(attempt.attempt_id)["run_id"] == attempt.run_id
    assert restarted.get_scale_s0_frozen_corpus(corpora[0].corpus_id)["execution_attempt_id"] == attempt.attempt_id
    assert restarted.get_scale_s0_frozen_packet(packets[-1].packet_id)["execution_attempt_id"] == attempt.attempt_id
    live = ScaleS0Preflight.from_catalog(restarted, mandate_id=mandate.mandate_id, packet_id=provider_packet.packet_id)
    from charitygraph.scale_s0 import SendRequest
    request = SendRequest("physical:model-d", TASK.task_id, TASK.version, provider_packet.subject_id, provider_packet.scope_id, provider_packet.binding_hash, True, TASK.default_routing, reservation["reservation_id"], provider_packet.source_ids, False)
    assert live.provider_send(request) == TASK
    with pytest.raises(ScalePreflightError):
        ScaleS0Preflight.from_catalog(restarted, mandate_id=mandate.mandate_id, packet_id=provider_packet.packet_id, economics=economics)
    with restarted._connection(immediate=True) as conn:
        conn.execute("DELETE FROM scale_s0_reservation_bindings WHERE reservation_id=?", (reservation["reservation_id"],))
        conn.execute("DELETE FROM reservation_tasks WHERE reservation_id=?", (reservation["reservation_id"],))
        conn.execute("DELETE FROM budget_reservations WHERE reservation_id=?", (reservation["reservation_id"],))
        restarted._commit(conn)
    with pytest.raises(ConflictError):
        live.provider_send(request)
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_physical_bundle({"bundle_id": "bundle:model-d-substitute", "mandate_id": mandate.mandate_id, "routing_class": TASK.default_routing.value, "packet_ids": tuple(item.packet_id for item in packets), "packet_hashes": tuple(item.binding_hash for item in packets), "frozen_at": NOW}, execution_attempt_id="attempt:other")
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_source_plan({**{k: v for k, v in {"plan_id": "plan:model-d:cross", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "subject_id": SUBJECTS[0], "subject_scope": "scope:x", "source_family": "retained_fixture", "created_at": NOW}.items()}}, execution_attempt_id="attempt:other")
    assert len(packets) == 8 and population_subjects == tuple(sorted(SUBJECTS))
