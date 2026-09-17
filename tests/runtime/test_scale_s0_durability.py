from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.runtime import CatalogError, ConflictError, SQLiteCatalog
from charitygraph.scale_s0 import (
    Candidate, DecisionDisposition, DocumentRepresentation, EconomicState,
    FrozenPacket, HaltController, PolicyArtifact, RepresentationPolicy,
    ReviewDecision, ReviewItem, ReviewStatus, RoutingClass, RoutingPolicy,
    ScaleMandate, ScaleS0Preflight, SourceAuthorisation, default_s0_registry,
)


NOW = datetime(2026, 9, 17, tzinfo=timezone.utc).isoformat()
REGISTRY = default_s0_registry()
TASK = next(item for item in REGISTRY.contracts if item.family == "program_service")


def authority():
    routing = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {trigger: RoutingClass.STRONG_REASONING for trigger in TASK.escalation_triggers})
    ids = {"sampling": ("sampling:test", "1"), "review": ("review:test", "1"), "promotion": ("promotion:test", "1"), "halt": ("halt:test", "1"), "reservation": ("reservation:test", "1"), "source_universe": ("sources:test", "1"), "specialist_source": ("specialist:test", "1"), "rights_transmission": ("rights:test", "1")}
    policies = {name: PolicyArtifact(policy_id, version, name[0] * 64) for name, (policy_id, version) in ids.items()}
    policies["routing"] = PolicyArtifact(routing.policy_id, routing.version, routing.immutable_hash)
    mandate = ScaleMandate(
        mandate_id="mandate:durable", mandate_version="1", slice_id="slice:durable", created_at=NOW, authorizing_actor_ref="actor:test", population_ref="population:synthetic", subject_ids=("subject:a",), snapshot_as_of="2026-09-17", ranking_policy_id="ranking:test", group_entity_policy_id="group:test", source_universe_policy_id="sources:test", source_universe_policy_version="1", mandatory_source_families=("annual_report",), applicable_source_families=("annual_report",), specialist_source_policy_id="specialist:test", rights_transmission_policy_id="rights:test", task_registry_version=REGISTRY.version, enabled_task_ids=tuple(task.task_id for task in REGISTRY.contracts), disabled_task_ids=(), routing_policy_id="routing:test", routing_policy_version="1", provider_spend_ceiling="10", strong_model_spend_ceiling="10", provider_call_ceiling=10, reservation_policy_id="reservation:test", currency_basis="AUD", review_policy_id="review:test", review_policy_version="1", promotion_policy_id="promotion:test", promotion_policy_version="1", sampling_policy_id="sampling:test", sampling_policy_version="1", halt_policy_id="halt:test", halt_policy_version="1", allowed_outputs=("governed_observations",), policy_hashes={**{name: item.content_hash for name, item in policies.items()}, "logical_task_registry": REGISTRY.immutable_hash},
    )
    source = SourceAuthorisation("source:one", "annual_report", "https://example.invalid/report", "official", "permitted", "acquired", "parsed", "a" * 64, (TASK.family,), "source-record:one")
    packet = FrozenPacket("packet:durable", TASK.task_id, TASK.version, "subject:a", "scope:a", (source.source_id,), (source.snapshot_hash,), TASK.input_profile_id, TASK.output_schema_id, TASK.default_routing, "provider-request:durable", "b" * 64, mandate_id=mandate.mandate_id, slice_id=mandate.slice_id, frozen_at=NOW)
    economics = EconomicState(0, Decimal("0"), Decimal("0"), "reservation:one", True, mandate.mandate_id, mandate.slice_id, TASK.key, Decimal("2"), "AUD", Decimal("1"), Decimal("0"))
    return mandate, routing, policies, source, packet, economics


def candidate(mandate, packet, **changes):
    values = dict(candidate_id="candidate:durable", task_id=TASK.task_id, task_version=TASK.version, subject_id="subject:a", scope_id="scope:a", source_ids=("source:one",), lineage_ids=("lineage:one",), mechanically_validated=True, claim_family=TASK.family, routing_class=TASK.default_routing, representation_policy=RepresentationPolicy(DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only"), semantic_payload={"program": "bounded"}, predicate="program_described", evidence_locator_ids=("locator:one",), source_record_ids=("source-record:one",), epistemic_basis="model_candidate", observation_time=NOW, mandate_id=mandate.mandate_id, packet_id=packet.packet_id, created_at=NOW)
    values.update(changes)
    return Candidate(**values)


def test_durable_authority_reconstructs_and_promotes_once_after_restart(tmp_path):
    mandate, routing, policies, source, packet, economics = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {source.source_id: source})
    ScaleS0Preflight.register_durable_packet(catalog, mandate, packet)
    ScaleS0Preflight.record_durable_reservation(catalog, economics, recorded_at=NOW)
    original = candidate(mandate, packet)
    ScaleS0Preflight.register_durable_candidate(catalog, original)
    item = ReviewItem("review:durable", original.candidate_id, original.binding_hash, original.task_id, original.task_version, original.subject_id, original.scope_id, original.source_ids, original.lineage_ids, ("mandatory",), "normal", NOW, ReviewStatus.DECIDED)
    ScaleS0Preflight.register_durable_review_item(catalog, item)
    decision = ReviewDecision("decision:durable", item.review_id, original.binding_hash, DecisionDisposition.PROMOTE, "reviewer:test", NOW, "supported", original.evidence_locator_ids)
    ScaleS0Preflight.register_durable_review_decision(catalog, decision, candidate_id=original.candidate_id)
    restarted = ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)
    assert restarted.economics == economics
    assert restarted.promote_durably(candidate_id=original.candidate_id, authorisation_id="promotion:one", persisted_at=NOW) == "observation:candidate:durable"
    assert restarted.promote_durably(candidate_id=original.candidate_id, authorisation_id="promotion:one", persisted_at=NOW) == "observation:candidate:durable"
    assert SQLiteCatalog(tmp_path / "state.sqlite3").open().get_scale_s0_promotion_result(original.candidate_id)["governed_artifact_id"] == "observation:candidate:durable"


def test_durable_identity_conflicts_orphans_and_correction_lineage_fail_closed(tmp_path):
    mandate, routing, policies, source, packet, _ = authority()
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {source.source_id: source})
    with pytest.raises(CatalogError):
        catalog.register_scale_s0_frozen_packet({"packet_id": "packet:orphan", "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id, "task_key": TASK.key, "subject_id": "subject:a", "scope_id": "scope:a", "content_hash": "x", "frozen_at": NOW})
    ScaleS0Preflight.register_durable_packet(catalog, mandate, packet)
    first = candidate(mandate, packet)
    ScaleS0Preflight.register_durable_candidate(catalog, first)
    with pytest.raises(ConflictError):
        ScaleS0Preflight.register_durable_candidate(catalog, replace(first, semantic_payload={"program": "substituted"}))
    corrected = candidate(mandate, packet, candidate_id="candidate:corrected", semantic_payload={"program": "narrowed"}, supersedes_candidate_id=first.candidate_id)
    ScaleS0Preflight.register_durable_candidate(catalog, corrected)
    item = ReviewItem("review:correction", first.candidate_id, first.binding_hash, first.task_id, first.task_version, first.subject_id, first.scope_id, first.source_ids, first.lineage_ids, ("correction",), "normal", NOW, ReviewStatus.DECIDED)
    ScaleS0Preflight.register_durable_review_item(catalog, item)
    correction = ReviewDecision("decision:correction", item.review_id, first.binding_hash, DecisionDisposition.NARROW_OR_CORRECT, "reviewer:test", NOW, "narrowed", first.evidence_locator_ids, corrected_candidate=corrected)
    ScaleS0Preflight.register_durable_review_decision(catalog, correction, candidate_id=first.candidate_id)
    assert catalog.effective_scale_s0_review(first.candidate_id)["corrected_candidate_id"] == corrected.candidate_id
