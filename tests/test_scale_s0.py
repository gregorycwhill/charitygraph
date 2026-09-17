from datetime import datetime, timezone
import pytest

from charitygraph.scale_s0 import (
    Candidate, DecisionDisposition, DocumentRepresentation, HaltController, HaltReason, HaltRecord, HaltScope,
    ProcessingDisposition, RepresentationPolicy, ReviewDecision, ReviewItem, ReviewRequirement, RoutingClass,
    RoutingPolicy, SamplingPolicy, ScaleMandate, ScalePreflightError, ScaleS0Preflight, SendRequest,
    SourceAuthorisation, default_s0_registry,
)


NOW = datetime(2026, 9, 17, tzinfo=timezone.utc).isoformat()
REGISTRY = default_s0_registry()
TASK = REGISTRY.contracts[0]


def mandate(**overrides):
    value = dict(
        mandate_id="mandate:synthetic-s0", mandate_version="1", slice_id="slice:synthetic", created_at=NOW,
        authorizing_actor_ref="actor:test", population_ref="population:synthetic-frozen", subject_ids=("subject:a",),
        snapshot_as_of="2026-09-17", ranking_policy_id="ranking:test:1", group_entity_policy_id="group:test:1",
        source_universe_policy_id="sources:test", source_universe_policy_version="1", mandatory_source_families=("annual_report",), applicable_source_families=("annual_report",),
        specialist_source_policy_id="specialist:test", rights_transmission_policy_id="rights:test", task_registry_version=REGISTRY.version,
        enabled_task_ids=tuple(item.task_id for item in REGISTRY.contracts), disabled_task_ids=(), routing_policy_id="routing:test", routing_policy_version="1",
        provider_spend_ceiling="0", strong_model_spend_ceiling="0", provider_call_ceiling=0, reservation_policy_id="reservation:test", currency_basis="AUD",
        review_policy_id="review:test", review_policy_version="1", promotion_policy_id="promotion:test", promotion_policy_version="1",
        sampling_policy_id="sampling:test", sampling_policy_version="1", halt_policy_id="halt:test", halt_policy_version="1",
        allowed_outputs=("source_evidence_records", "candidates", "review_items", "governed_observations", "north_star_projection", "execution_accounting_artifacts"),
    )
    value.update(overrides)
    return ScaleMandate(**value)


def harness(**kwargs):
    policy = RoutingPolicy("routing:test", "1", frozenset(RoutingClass), {trigger: RoutingClass.STRONG_REASONING for trigger in {"source_conflict", "scope_ambiguity"}})
    source = SourceAuthorisation("source:one", "annual_report", "https://example.invalid/report", "official", "permitted", "acquired", "parsed", "a" * 64, (TASK.family,))
    return ScaleS0Preflight(mandate(), REGISTRY, policy, {source.source_id: source}, HaltController(), active_reservation_ids={"reservation:one"}, **kwargs)


def candidate(**overrides):
    value = dict(candidate_id="candidate:one", task_id=TASK.task_id, task_version=TASK.version, subject_id="subject:a", scope_id="scope:a", source_ids=("source:one",), lineage_ids=("lineage:one",), mechanically_validated=True, claim_family=TASK.family, routing_class=RoutingClass.LOW_COST_THEN_ESCALATE, representation_policy=RepresentationPolicy(DocumentRepresentation.RELIABLE_TEXT, "text_extraction_only"))
    value.update(overrides)
    return Candidate(**value)


def test_valid_mandate_and_packet_preflight_pass_without_provider_call():
    h = harness()
    assert h.provider_send(SendRequest("physical:one", TASK.task_id, TASK.version, "subject:a", "scope:a", "packet" * 10, True, RoutingClass.LOW_COST_THEN_ESCALATE, "reservation:one", ("source:one",), False)) == TASK


@pytest.mark.parametrize("field,value", [("population_ref", ""), ("rights_transmission_policy_id", ""), ("routing_policy_id", ""), ("provider_spend_ceiling", ""), ("enabled_task_ids", ())])
def test_mandate_fails_closed_for_missing_controls(field, value):
    with pytest.raises(ScalePreflightError):
        mandate(**{field: value}).validate()


def test_send_preflight_blocks_disabled_task_unknown_subject_unfrozen_packet_duplicate_and_halt():
    h = harness()
    request = SendRequest("physical:one", TASK.task_id, TASK.version, "subject:a", "scope:a", "h" * 64, True, RoutingClass.LOW_COST_THEN_ESCALATE, "reservation:one", ("source:one",), False)
    h.provider_send(request)
    for changed in ({"physical_attempt_id": "physical:one"}, {"subject_id": "subject:outside"}, {"packet_frozen": False}):
        with pytest.raises(ScalePreflightError): h.provider_send(SendRequest(**{**request.__dict__, **changed}))
    halted = harness()
    halted.halts.records.append(HaltRecord("halt:one", HaltReason.AMBIGUOUS_PROVIDER_SEND_OR_BILLING, HaltScope.SLICE, "slice:synthetic", None, None, NOW))
    with pytest.raises(ScalePreflightError): halted.provider_send(request)
    with pytest.raises(ScalePreflightError): harness().provider_send(SendRequest(**{**request.__dict__, "physical_attempt_id": "physical:inactive", "reservation_id": "reservation:inactive"}))


def test_source_policy_and_triggered_escalation_fail_closed():
    h = harness()
    request = SendRequest("physical:source", TASK.task_id, TASK.version, "subject:a", "scope:a", "h" * 64, True, RoutingClass.LOW_COST_THEN_ESCALATE, "reservation:one", ("source:missing",), False)
    with pytest.raises(ScalePreflightError): h.provider_send(request)
    request = SendRequest(**{**request.__dict__, "physical_attempt_id": "physical:route", "source_ids": ("source:one",)})
    with pytest.raises(ScalePreflightError): h.provider_send(request, triggered_escalations=("source_conflict",))


def test_review_and_promotion_are_bound_to_exact_candidate_version_scope_and_evidence():
    h, c = harness(), candidate()
    sampling = SamplingPolicy("sampling:test", "1", "seed", ("claim_family",), {"default": 1.0})
    requirement = h.review_requirement(c, sampling, ())
    assert requirement == ReviewRequirement.SAMPLED
    with pytest.raises(ScalePreflightError): h.promote(c, review_requirement=requirement, review_item=None, decision=None)
    item = ReviewItem("review:one", c.candidate_id, c.binding_hash, c.task_id, c.task_version, c.subject_id, c.scope_id, c.source_ids, c.lineage_ids, (), "normal", NOW)
    decision = ReviewDecision("decision:one", item.review_id, c.binding_hash, DecisionDisposition.PROMOTE, "reviewer:test", NOW, "evidence supports bounded claim", c.source_ids)
    assert h.promote(c, review_requirement=requirement, review_item=item, decision=decision).startswith("observation:")
    changed = Candidate(**{**c.__dict__, "scope_id": "scope:changed"})
    with pytest.raises(ScalePreflightError): h.promote(changed, review_requirement=requirement, review_item=item, decision=decision)


def test_mandatory_review_cannot_be_sampled_away_and_rejection_cannot_promote():
    h, c = harness(), candidate()
    policy = SamplingPolicy("sampling:test", "1", "seed", ("claim_family",), {"default": 0})
    requirement = h.review_requirement(c, policy, ("source_conflict",))
    assert requirement == ReviewRequirement.MANDATORY
    item = ReviewItem("review:one", c.candidate_id, c.binding_hash, c.task_id, c.task_version, c.subject_id, c.scope_id, c.source_ids, c.lineage_ids, ("source_conflict",), "conflict", NOW)
    rejected = ReviewDecision("decision:one", item.review_id, c.binding_hash, DecisionDisposition.REJECT, "reviewer:test", NOW, "conflict unresolved", c.source_ids)
    with pytest.raises(ScalePreflightError): h.promote(c, review_requirement=requirement, review_item=item, decision=rejected)


def test_visual_document_and_processing_failure_cannot_silently_be_not_found_or_promoted():
    h = harness()
    with pytest.raises(ScalePreflightError): h.review_requirement(candidate(representation_policy=RepresentationPolicy(DocumentRepresentation.VISUALLY_MATERIAL_PDF, "text_extraction_only", True)), SamplingPolicy("s", "1", "seed", (), {}), ())
    broken = candidate(processing_disposition=ProcessingDisposition.PROCESSING_FAILED)
    with pytest.raises(ScalePreflightError): h.promote(broken, review_requirement=ReviewRequirement.NONE, review_item=None, decision=None)


def test_registry_covers_active_families_and_preserves_distinct_logical_identities():
    families = {item.family for item in REGISTRY.contracts}
    assert {"program_service", "direct_service", "finance_source_native", "funding_dependency", "conduct_adverse", "outcomes_evaluation", "taxonomy", "discovery_signals"} <= families
    assert len({item.key for item in REGISTRY.contracts}) == len(REGISTRY.contracts)
