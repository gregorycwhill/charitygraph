from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.scale_s0 import (
    ACTIVE_OWNERSHIP, Candidate, DecisionDisposition, DocumentRepresentation,
    EconomicState, FrozenPacket, HaltController, HaltReason, HaltRecord,
    HaltScope, PolicyArtifact, PriorAttempt, ProcessingDisposition,
    RepresentationPolicy, ReviewDecision, ReviewItem, ReviewRequirement,
    ReviewStatus, RoutingClass, RoutingPolicy, SamplingPolicy, ScaleMandate,
    ScalePreflightError, ScaleS0Preflight, SendRequest, SourceAuthorisation,
    default_s0_registry,
)


NOW = datetime(2026, 9, 17, tzinfo=timezone.utc).isoformat()
REGISTRY = default_s0_registry()
TASK = next(item for item in REGISTRY.contracts if item.family == "program_service")


def policies(routing):
    ids = {
        "sampling": ("sampling:test", "1"), "review": ("review:test", "1"),
        "promotion": ("promotion:test", "1"), "halt": ("halt:test", "1"),
        "reservation": ("reservation:test", "1"), "source_universe": ("sources:test", "1"),
        "specialist_source": ("specialist:test", "1"), "rights_transmission": ("rights:test", "1"),
    }
    result = {name: PolicyArtifact(policy_id, version, (name[0] * 64)) for name, (policy_id, version) in ids.items()}
    result["routing"] = PolicyArtifact(routing.policy_id, routing.version, routing.immutable_hash)
    return result


def mandate(policy_hashes, **overrides):
    value = dict(
        mandate_id="mandate:synthetic-s0", mandate_version="1", slice_id="slice:synthetic", created_at=NOW,
        authorizing_actor_ref="actor:test", population_ref="population:synthetic-frozen", subject_ids=("subject:a",),
        snapshot_as_of="2026-09-17", ranking_policy_id="ranking:test:1", group_entity_policy_id="group:test:1",
        source_universe_policy_id="sources:test", source_universe_policy_version="1", mandatory_source_families=("annual_report",), applicable_source_families=("annual_report",),
        specialist_source_policy_id="specialist:test", rights_transmission_policy_id="rights:test", task_registry_version=REGISTRY.version,
        enabled_task_ids=tuple(item.task_id for item in REGISTRY.contracts), disabled_task_ids=(), routing_policy_id="routing:test", routing_policy_version="1",
        provider_spend_ceiling="10", strong_model_spend_ceiling="10", provider_call_ceiling=10, reservation_policy_id="reservation:test", currency_basis="AUD",
        review_policy_id="review:test", review_policy_version="1", promotion_policy_id="promotion:test", promotion_policy_version="1",
        sampling_policy_id="sampling:test", sampling_policy_version="1", halt_policy_id="halt:test", halt_policy_version="1",
        allowed_outputs=("source_evidence_records", "candidates", "review_items", "governed_observations", "execution_accounting_artifacts"),
        policy_hashes={**{name: item.content_hash for name, item in policy_hashes.items()}, "logical_task_registry": REGISTRY.immutable_hash},
    )
    value.update(overrides)
    return ScaleMandate(**value)


def harness(**overrides):
    routing = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {trigger: RoutingClass.STRONG_REASONING for trigger in TASK.escalation_triggers})
    artifact_policies = policies(routing)
    source = SourceAuthorisation("source:one", "annual_report", "https://example.invalid/report", "official", "permitted", "acquired", "parsed", "a" * 64, (TASK.family,), "source-record:one")
    packet = FrozenPacket("packet:one", TASK.task_id, TASK.version, "subject:a", "scope:a", (source.source_id,), (source.snapshot_hash,), TASK.input_profile_id, TASK.output_schema_id, TASK.default_routing, "provider-request:one", "b" * 64)
    economics = EconomicState(0, Decimal("0"), Decimal("0"), "reservation:one", True, "mandate:synthetic-s0", "slice:synthetic", TASK.key, Decimal("2"), "AUD", Decimal("1"), Decimal("0"))
    return ScaleS0Preflight(mandate(artifact_policies), REGISTRY, routing, {source.source_id: source}, HaltController(), packets={packet.binding_hash: packet}, policies=artifact_policies, economics=economics, **overrides), packet, source, artifact_policies


def request(packet, **overrides):
    value = dict(physical_attempt_id="physical:one", task_id=TASK.task_id, task_version=TASK.version, subject_id="subject:a", scope_id="scope:a", packet_hash=packet.binding_hash, packet_frozen=True, route=TASK.default_routing, reservation_id="reservation:one", source_ids=("source:one",), retry_permitted=False)
    value.update(overrides)
    return SendRequest(**value)


def candidate(**overrides):
    value = dict(candidate_id="candidate:one", task_id=TASK.task_id, task_version=TASK.version, subject_id="subject:a", scope_id="scope:a", source_ids=("source:one",), lineage_ids=("lineage:one",), mechanically_validated=True, claim_family=TASK.family, routing_class=TASK.default_routing, representation_policy=RepresentationPolicy(DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only"), semantic_payload={"program": "bounded"}, predicate="program_described", evidence_locator_ids=("locator:one",), source_record_ids=("source-record:one",), epistemic_basis="model_candidate", observation_time=NOW)
    value.update(overrides)
    return Candidate(**value)


def decided(candidate, disposition=DecisionDisposition.PROMOTE, **overrides):
    item = ReviewItem("review:one", candidate.candidate_id, candidate.binding_hash, candidate.task_id, candidate.task_version, candidate.subject_id, candidate.scope_id, candidate.source_ids, candidate.lineage_ids, (), "normal", NOW, ReviewStatus.DECIDED)
    value = dict(decision_id="decision:one", review_id=item.review_id, candidate_binding_hash=candidate.binding_hash, disposition=disposition, reviewer_or_policy="reviewer:test", decided_at=NOW, rationale="evidence supports bounded claim", evidence_basis=candidate.evidence_locator_ids)
    value.update(overrides)
    return item, ReviewDecision(**value)


def test_registry_is_explicit_v02_ownership_not_numeric_offset():
    assert ACTIVE_OWNERSHIP == {
        "identity_regulatory": (1,), "purpose_cause": (2,), "program_service": (3,), "activity_source_reported": (4,), "population_geography": (5,), "participation": (6,), "direct_service": (7,), "fundraising": (8,), "governance": (9,), "workforce": (10,), "scale_capability": (11,), "relationships": (12,), "finance_source_native": (13,), "funding_dependency": (14,), "ethos_commitments": (15,), "conduct_adverse": (16,), "notable_history": (17,), "outcomes_evaluation": (18,), "assessed_taxonomy": (19,), "discovery_signals": (19,), "evidence_coverage": (20,),
    }
    assert REGISTRY.get("urn:charitygraph:scale-s0:program_service", "1.0").allowed_sections == (3,)
    assert REGISTRY.get("urn:charitygraph:scale-s0:participation", "1.0").allowed_sections == (6,)
    assert REGISTRY.get("urn:charitygraph:scale-s0:governance", "1.0").allowed_sections == (9,)


def test_policy_substitution_and_mandatory_source_leakage_fail_closed():
    h, _, _, artifacts = harness()
    assert h
    tampered = dict(artifacts); tampered["routing"] = PolicyArtifact("routing:other", "1", artifacts["routing"].content_hash)
    with pytest.raises(ScalePreflightError):
        ScaleS0Preflight(mandate(tampered), REGISTRY, h.routing, h.sources, HaltController(), packets=h.packets, policies=tampered, economics=h.economics)
    with pytest.raises(ScalePreflightError): mandate(artifacts, mandatory_source_families=("central",)).validate()


def test_zero_and_exhausted_economic_ceilings_forbid_paid_crossing():
    h, packet, _, artifacts = harness()
    for changes in ({"provider_call_ceiling": 0}, {"provider_spend_ceiling": "0"}, {"provider_call_ceiling": 1}):
        m = mandate(artifacts, **changes)
        economics = replace(h.economics, provider_calls=1) if changes.get("provider_call_ceiling") == 1 else h.economics
        with pytest.raises(ScalePreflightError): ScaleS0Preflight(m, REGISTRY, h.routing, h.sources, HaltController(), packets=h.packets, policies=artifacts, economics=economics).provider_send(request(packet))
    with pytest.raises(ScalePreflightError): ScaleS0Preflight(mandate(artifacts, strong_model_spend_ceiling="0"), REGISTRY, h.routing, h.sources, HaltController(), packets=h.packets, policies=artifacts, economics=h.economics).provider_send(request(packet, route=RoutingClass.STRONG_REASONING), triggered_escalations=("source_conflict",))


def test_packet_source_profile_schema_and_route_substitution_fail():
    h, packet, source, _ = harness()
    assert h.provider_send(request(packet)) == TASK
    for changed in (replace(packet, subject_id="subject:b"), replace(packet, source_ids=("source:two",)), replace(packet, input_profile_id="other"), replace(packet, content_hash="")):
        with pytest.raises(ScalePreflightError): h.provider_send(request(changed, packet_hash=changed.binding_hash))
    with pytest.raises(ScalePreflightError): h.provider_send(request(packet, route=RoutingClass.STRONG_REASONING))
    h.sources[source.source_id] = replace(source, snapshot_hash="c" * 64)
    with pytest.raises(ScalePreflightError): h.provider_send(request(packet))


@pytest.mark.parametrize("state", ["completed", "transmitted", "ambiguous", "send_started"])
def test_retry_requires_pre_send_failure_and_same_durable_request_identity(state):
    h, packet, _, _ = harness()
    with pytest.raises(ScalePreflightError): h.provider_send(request(packet, retry_permitted=True, prior_attempt=PriorAttempt(state, packet.provider_request_identity, "physical:old")))
    assert h.provider_send(request(packet, retry_permitted=True, prior_attempt=PriorAttempt("pre_send_failed", packet.provider_request_identity, "physical:old"))) == TASK
    with pytest.raises(ScalePreflightError): h.provider_send(request(packet, retry_permitted=False, prior_attempt=PriorAttempt("pre_send_failed", packet.provider_request_identity, "physical:old")))


def test_restart_replay_uses_durable_provider_request_identity_not_memory():
    h, packet, _, artifacts = harness()
    class Catalog:
        def get_provider_request_item(self, request_id): return {"provider_request_item_id": request_id}
        def active_scale_s0_halt(self, **_): return None
    restarted = ScaleS0Preflight(mandate(artifacts), REGISTRY, h.routing, h.sources, HaltController(), packets=h.packets, policies=artifacts, economics=h.economics, catalog=Catalog())
    with pytest.raises(ScalePreflightError): restarted.provider_send(request(packet, physical_attempt_id="physical:replay"))


def test_semantic_candidate_content_locator_scope_and_review_lifecycle_bindings():
    h, _, _, artifacts = harness(); c = candidate(); sampling = SamplingPolicy("sampling:test", "1", "seed", (), {"default": 1}, artifacts["sampling"].content_hash)
    requirement = h.review_requirement(c, sampling, ())
    item, decision = decided(c)
    assert h.promote(c, review_requirement=requirement, review_item=item, decision=decision) == "observation:candidate:one"
    for altered in (replace(c, semantic_payload={"program": "changed"}), replace(c, evidence_locator_ids=("locator:two",)), replace(c, scope_id="scope:b"), replace(c, task_version="2")):
        with pytest.raises(ScalePreflightError): h.promote(altered, review_requirement=requirement, review_item=item, decision=decision)
    with pytest.raises(ScalePreflightError): h.promote(c, review_requirement=requirement, review_item=replace(item, status=ReviewStatus.OPEN), decision=decision)


def test_rejection_conflict_and_narrow_correct_cannot_promote_original_candidate():
    h, _, _, artifacts = harness(); c = candidate(); sampling = SamplingPolicy("sampling:test", "1", "seed", (), {"default": 1}, artifacts["sampling"].content_hash); requirement = h.review_requirement(c, sampling, ())
    item, rejected = decided(c, DecisionDisposition.REJECT)
    with pytest.raises(ScalePreflightError): h.promote(c, review_requirement=requirement, review_item=item, decision=rejected)
    _, naked_correct = decided(c, DecisionDisposition.NARROW_OR_CORRECT)
    with pytest.raises(ScalePreflightError): h.promote(c, review_requirement=requirement, review_item=item, decision=naked_correct)
    replacement = replace(c, candidate_id="candidate:corrected", semantic_payload={"program": "narrowed"})
    _, corrected = decided(c, DecisionDisposition.NARROW_OR_CORRECT, corrected_candidate=replacement, target_governed_artifact_id="observation:corrected")
    assert h.promote(c, review_requirement=requirement, review_item=item, decision=corrected) == "observation:corrected"


def test_deterministic_is_contract_and_provenance_not_caller_flag_and_processing_is_not_absence():
    h, _, _, artifacts = harness(); c = candidate(deterministic_source_native=True)
    sampling = SamplingPolicy("sampling:test", "1", "seed", (), {"default": 0}, artifacts["sampling"].content_hash)
    with pytest.raises(ScalePreflightError): h.review_requirement(c, sampling, ())
    for disposition in (ProcessingDisposition.PARSING_FAILED, ProcessingDisposition.PROCESSING_FAILED, ProcessingDisposition.NOT_PROCESSED, ProcessingDisposition.UNAVAILABLE):
        with pytest.raises(ScalePreflightError): h.promote(replace(candidate(), processing_disposition=disposition), review_requirement=ReviewRequirement.NONE, review_item=None, decision=None)
    with pytest.raises(ScalePreflightError): h.review_requirement(candidate(representation_policy=RepresentationPolicy(DocumentRepresentation.VISUALLY_MATERIAL_PDF, "text_extraction_only", True)), sampling, ())


def test_halts_and_review_backlog_block_send_and_promotion():
    h, packet, _, artifacts = harness()
    h.halts.records.append(HaltRecord("halt:one", HaltReason.AMBIGUOUS_PROVIDER_SEND_OR_BILLING, HaltScope.SLICE, "slice:synthetic", None, None, NOW))
    with pytest.raises(ScalePreflightError): h.provider_send(request(packet))
    with pytest.raises(ScalePreflightError): ScaleS0Preflight(mandate(artifacts), REGISTRY, h.routing, h.sources, HaltController(), packets=h.packets, policies=artifacts, economics=h.economics, review_backlog=2, review_backlog_limit=1)
