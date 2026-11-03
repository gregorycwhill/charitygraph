"""Fail-closed, provider-free governance controls for a future Scale S0 slice.

This module is deliberately an intercept and policy evaluator.  It does not
acquire sources, call providers, create a second execution ledger, or project
cards.  The existing runtime catalog remains the authority for reservations,
physical attempts, receipts and restart safety.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class ScalePreflightError(ValueError):
    """A required Scale S0 control is missing, stale, or incompatible."""


class RoutingClass(StrEnum):
    DETERMINISTIC = "deterministic"
    LOW_COST_SEMANTIC = "low_cost_semantic"
    LOW_COST_THEN_ESCALATE = "low_cost_then_escalate"
    STRONG_REASONING = "strong_reasoning"
    HUMAN_DECISION = "human_decision"


class ReviewRequirement(StrEnum):
    NONE = "none"
    SAMPLED = "sampled"
    MANDATORY = "mandatory"


class ReviewStatus(StrEnum):
    OPEN = "open"
    DECIDED = "decided"
    SUPERSEDED = "superseded"


class DecisionDisposition(StrEnum):
    PROMOTE = "promote"
    NARROW_OR_CORRECT = "narrow_or_correct"
    REJECT = "reject"
    ESCALATE = "escalate"
    DEFER_UNKNOWN = "defer_unknown"
    DUPLICATE_SUPERSEDED = "duplicate_superseded"


class HaltScope(StrEnum):
    TASK = "task"
    SUBJECT = "subject"
    SLICE = "slice"


class HaltReason(StrEnum):
    RIGHTS_TRANSMISSION_VIOLATION = "rights_transmission_violation"
    AMBIGUOUS_PROVIDER_SEND_OR_BILLING = "ambiguous_provider_send_or_billing"
    BUDGET_RESERVATION_VIOLATION = "budget_reservation_violation"
    PROVIDER_MODEL_PROMPT_SCHEMA_DRIFT = "provider_model_prompt_schema_drift"
    IDENTITY_GROUP_POLICY_VIOLATION = "identity_group_policy_violation"
    SUBJECT_SCOPE_CONTAMINATION = "subject_scope_contamination"
    SYSTEMATIC_RELATIONSHIP_ERROR = "systematic_relationship_error"
    TAXONOMY_AUTHORITY_CONTAMINATION = "taxonomy_authority_contamination"
    FINANCE_FUNDING_SEMANTIC_COLLAPSE = "finance_funding_semantic_collapse"
    CURRENT_STATE_OVERCLAIM = "current_state_overclaim"
    CANDIDATE_TO_GOVERNED_BYPASS = "candidate_to_governed_bypass"
    RAW_OUTPUT_TO_CARD_BYPASS = "raw_output_to_card_bypass"
    CORRUPTED_SOURCE_EVIDENCE_LINEAGE = "corrupted_source_evidence_lineage"
    REVIEW_BACKLOG_THRESHOLD = "review_backlog_threshold"
    REPEATED_SCHEMA_CONTRACT_FAILURE = "repeated_schema_contract_failure"


class DocumentRepresentation(StrEnum):
    NATIVE_STRUCTURED = "native_structured_document"
    RELIABLE_TEXT = "reliable_extracted_text"
    VISUALLY_MATERIAL_PDF = "visually_material_pdf"
    IMAGE_SCANNED_PDF = "image_scanned_pdf"
    PARSING_FAILURE = "parsing_failure"
    UNSUPPORTED = "unsupported_representation"


class ProcessingDisposition(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    UNAVAILABLE = "unavailable"
    ACQUIRED = "acquired"
    PARSING_FAILED = "parsing_failed"
    NOT_PROCESSED = "not_processed"
    PROCESSING_FAILED = "processing_failed"
    SOURCE_SILENT = "source_silent"
    NOT_FOUND_IN_FINITE_REVIEWED_UNIVERSE = "not_found_in_finite_reviewed_universe"
    UNKNOWN = "unknown"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


MANDATORY_REVIEW_REASONS = frozenset({
    "adverse_positive", "complex_relationship", "taxonomy_boundary", "causation_or_contribution",
    "dependency_assessment", "source_conflict", "stale_current_state", "correction_or_supersession",
})

ESCALATION_TRIGGERS = frozenset({
    "unresolved_relationship_endpoint", "scope_ambiguity", "source_conflict", "taxonomy_narrow_reject_boundary",
    "outcome_causation_ambiguity", "commitment_implementation_ambiguity",
    "first_party_independent_evidence_ambiguity", "repeated_contract_schema_failure",
})


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    version: str
    family: str
    allowed_sections: tuple[int, ...]
    input_profile_id: str
    output_schema_id: str
    validation_policy_id: str
    candidate_disposition: str
    default_routing: RoutingClass
    escalation_triggers: frozenset[str] = frozenset()
    promotion_policy_class: str = "review_required"
    current_state_sensitive: bool = False
    physical_bundling_permitted: bool = False
    available: bool = True

    @property
    def key(self) -> str:
        return f"{self.task_id}@{self.version}"


@dataclass(frozen=True)
class LogicalTaskRegistry:
    version: str
    contracts: tuple[TaskContract, ...]

    def get(self, task_id: str, version: str) -> TaskContract:
        for item in self.contracts:
            if item.task_id == task_id and item.version == version:
                return item
        raise ScalePreflightError("unregistered logical task contract")


@dataclass(frozen=True)
class RoutingPolicy:
    policy_id: str
    version: str
    permitted: frozenset[RoutingClass]
    escalation_routes: Mapping[str, RoutingClass]

    def route(self, requested: RoutingClass, triggers: Iterable[str] = ()) -> RoutingClass:
        if requested not in self.permitted:
            raise ScalePreflightError("routing class is not authorised by routing policy")
        triggered = set(triggers)
        unknown = triggered - ESCALATION_TRIGGERS
        if unknown:
            raise ScalePreflightError("unknown escalation trigger")
        choices = [self.escalation_routes[item] for item in triggered if item in self.escalation_routes]
        route = RoutingClass.STRONG_REASONING if RoutingClass.STRONG_REASONING in choices else (choices[0] if choices else requested)
        if route not in self.permitted:
            raise ScalePreflightError("triggered routing escalation is not authorised")
        return route


@dataclass(frozen=True)
class SamplingPolicy:
    policy_id: str
    version: str
    seed: str
    strata: tuple[str, ...]
    sample_rates: Mapping[str, float] = field(default_factory=dict)

    def requirement(self, *, candidate_id: str, task_key: str, reasons: Iterable[str], deterministic_source_native: bool) -> ReviewRequirement:
        reasons = set(reasons)
        if reasons & MANDATORY_REVIEW_REASONS:
            return ReviewRequirement.MANDATORY
        if deterministic_source_native:
            return ReviewRequirement.NONE
        key = f"{self.seed}|{self.version}|{candidate_id}|{task_key}"
        rate = self.sample_rates.get(task_key, self.sample_rates.get("default", 0.0))
        if not 0 <= rate <= 1:
            raise ScalePreflightError("sampling rate is outside [0,1]")
        selected = int(_digest(key)[:12], 16) / float(16**12) < rate
        return ReviewRequirement.SAMPLED if selected else ReviewRequirement.NONE


@dataclass(frozen=True)
class ScaleMandate:
    mandate_id: str
    mandate_version: str
    slice_id: str
    created_at: str
    authorizing_actor_ref: str
    population_ref: str
    subject_ids: tuple[str, ...]
    snapshot_as_of: str
    ranking_policy_id: str
    group_entity_policy_id: str
    source_universe_policy_id: str
    source_universe_policy_version: str
    mandatory_source_families: tuple[str, ...]
    applicable_source_families: tuple[str, ...]
    specialist_source_policy_id: str
    rights_transmission_policy_id: str
    task_registry_version: str
    enabled_task_ids: tuple[str, ...]
    disabled_task_ids: tuple[str, ...]
    routing_policy_id: str
    routing_policy_version: str
    provider_spend_ceiling: str
    strong_model_spend_ceiling: str
    provider_call_ceiling: int
    reservation_policy_id: str
    currency_basis: str
    review_policy_id: str
    review_policy_version: str
    promotion_policy_id: str
    promotion_policy_version: str
    sampling_policy_id: str
    sampling_policy_version: str
    halt_policy_id: str
    halt_policy_version: str
    allowed_outputs: tuple[str, ...]
    parent_product_contract: str = "north-star-v0.2"
    automatically_publishable: bool = False

    @property
    def identity_hash(self) -> str:
        return _digest(self.__dict__)

    def validate(self) -> None:
        required = {
            "mandate_id": self.mandate_id, "mandate_version": self.mandate_version, "slice_id": self.slice_id,
            "created_at": self.created_at, "authorizing_actor_ref": self.authorizing_actor_ref,
            "population_ref": self.population_ref, "snapshot_as_of": self.snapshot_as_of,
            "ranking_policy_id": self.ranking_policy_id, "group_entity_policy_id": self.group_entity_policy_id,
            "source_universe_policy_id": self.source_universe_policy_id, "rights_transmission_policy_id": self.rights_transmission_policy_id,
            "task_registry_version": self.task_registry_version, "routing_policy_id": self.routing_policy_id,
            "reservation_policy_id": self.reservation_policy_id, "review_policy_id": self.review_policy_id,
            "promotion_policy_id": self.promotion_policy_id, "sampling_policy_id": self.sampling_policy_id,
            "halt_policy_id": self.halt_policy_id, "currency_basis": self.currency_basis,
        }
        absent = [name for name, value in required.items() if not value or str(value).startswith("UNAPPROVED_")]
        if absent or not self.subject_ids or not self.mandatory_source_families or not self.enabled_task_ids:
            raise ScalePreflightError("mandate is missing required frozen policy/reference")
        if self.parent_product_contract != "north-star-v0.2" or self.automatically_publishable:
            raise ScalePreflightError("mandate does not preserve product/publication boundary")
        try:
            if float(self.provider_spend_ceiling) < 0 or float(self.strong_model_spend_ceiling) < 0 or self.provider_call_ceiling < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ScalePreflightError("mandate economics must be explicit non-negative ceilings") from None
        prohibited = {"public_release", "card_direct_write"}
        if prohibited & set(self.allowed_outputs):
            raise ScalePreflightError("mandate permits an unauthorised public output")


@dataclass(frozen=True)
class SourceAuthorisation:
    source_id: str
    source_family: str
    url_or_identity: str
    authority_role: str
    rights_transmission_status: str
    acquisition_state: str
    parsing_state: str
    snapshot_hash: str
    claim_families: tuple[str, ...]
    specialist_authorisation_id: str | None = None

    def permits(self, task: TaskContract) -> bool:
        return (self.rights_transmission_status == "permitted" and self.acquisition_state == "acquired"
                and self.parsing_state in {"parsed", "structured"} and bool(self.snapshot_hash)
                and task.family in self.claim_families)


@dataclass(frozen=True)
class RepresentationPolicy:
    representation: DocumentRepresentation
    authorised_mode: str
    materially_relevant_visual_content: bool = False

    def validate(self) -> None:
        allowed = {
            DocumentRepresentation.NATIVE_STRUCTURED: {"structured_source_native_data"},
            DocumentRepresentation.RELIABLE_TEXT: {"text_extraction_only", "page_rendered_visual"},
            DocumentRepresentation.VISUALLY_MATERIAL_PDF: {"page_rendered_visual"},
            DocumentRepresentation.IMAGE_SCANNED_PDF: {"page_rendered_visual", "not_processable"},
            DocumentRepresentation.PARSING_FAILURE: {"not_processable"},
            DocumentRepresentation.UNSUPPORTED: {"not_processable"},
        }
        if self.authorised_mode not in allowed[self.representation]:
            raise ScalePreflightError("document representation is inadequate for authorised processing")
        if self.materially_relevant_visual_content and self.authorised_mode == "text_extraction_only":
            raise ScalePreflightError("material visual content cannot silently use text-only processing")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    task_id: str
    task_version: str
    subject_id: str
    scope_id: str
    source_ids: tuple[str, ...]
    lineage_ids: tuple[str, ...]
    mechanically_validated: bool
    claim_family: str
    routing_class: RoutingClass
    representation_policy: RepresentationPolicy
    deterministic_source_native: bool = False
    processing_disposition: ProcessingDisposition = ProcessingDisposition.ACQUIRED

    @property
    def binding_hash(self) -> str:
        return _digest({"candidate_id": self.candidate_id, "task": [self.task_id, self.task_version], "subject": self.subject_id, "scope": self.scope_id, "sources": self.source_ids, "lineage": self.lineage_ids})


@dataclass(frozen=True)
class ReviewItem:
    review_id: str
    candidate_id: str
    candidate_binding_hash: str
    task_id: str
    task_version: str
    subject_id: str
    scope_id: str
    evidence_source_ids: tuple[str, ...]
    lineage_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    risk_category: str
    created_at: str
    status: ReviewStatus = ReviewStatus.OPEN


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    review_id: str
    candidate_binding_hash: str
    disposition: DecisionDisposition
    reviewer_or_policy: str
    decided_at: str
    rationale: str
    evidence_basis: tuple[str, ...]
    target_governed_artifact_id: str | None = None
    supersedes: str | None = None


@dataclass(frozen=True)
class HaltRecord:
    halt_id: str
    reason: HaltReason
    scope: HaltScope
    slice_id: str
    task_key: str | None
    subject_id: str | None
    created_at: str
    hard: bool = True
    recovered_at: str | None = None
    recovery_actor: str | None = None
    recovery_rationale: str | None = None

    def applies(self, *, slice_id: str, task_key: str, subject_id: str) -> bool:
        if self.recovered_at or self.slice_id != slice_id:
            return False
        return (self.scope == HaltScope.SLICE or (self.scope == HaltScope.TASK and self.task_key == task_key)
                or (self.scope == HaltScope.SUBJECT and self.subject_id == subject_id))


@dataclass
class HaltController:
    records: list[HaltRecord] = field(default_factory=list)

    def active(self, *, slice_id: str, task_key: str, subject_id: str) -> HaltRecord | None:
        return next((item for item in reversed(self.records) if item.hard and item.applies(slice_id=slice_id, task_key=task_key, subject_id=subject_id)), None)

    def recover(self, halt_id: str, *, actor: str, rationale: str, at: str) -> None:
        if not actor or not rationale:
            raise ScalePreflightError("halt recovery requires explicit actor and rationale")
        for index, item in enumerate(self.records):
            if item.halt_id == halt_id:
                if item.recovered_at:
                    raise ScalePreflightError("halt already recovered")
                self.records[index] = HaltRecord(**{**item.__dict__, "recovered_at": at, "recovery_actor": actor, "recovery_rationale": rationale})
                return
        raise ScalePreflightError("unknown halt")


@dataclass(frozen=True)
class SendRequest:
    physical_attempt_id: str
    task_id: str
    task_version: str
    subject_id: str
    scope_id: str
    packet_hash: str | None
    packet_frozen: bool
    route: RoutingClass
    reservation_id: str | None
    source_ids: tuple[str, ...]
    retry_permitted: bool


class ScaleS0Preflight:
    """Offline guard used before any future provider boundary is crossed."""
    def __init__(self, mandate: ScaleMandate, registry: LogicalTaskRegistry, routing: RoutingPolicy,
                 sources: Mapping[str, SourceAuthorisation], halts: HaltController, reserved_attempt_ids: Iterable[str] = (),
                 active_reservation_ids: Iterable[str] | None = None, catalog: object | None = None) -> None:
        mandate.validate()
        self.mandate, self.registry, self.routing, self.sources, self.halts = mandate, registry, routing, sources, halts
        self.reserved_attempt_ids = set(reserved_attempt_ids)
        self.active_reservation_ids = None if active_reservation_ids is None else set(active_reservation_ids)
        self.catalog = catalog

    def _task(self, task_id: str, version: str) -> TaskContract:
        task = self.registry.get(task_id, version)
        if not task.available or task_id not in self.mandate.enabled_task_ids or task_id in self.mandate.disabled_task_ids:
            raise ScalePreflightError("task is disabled or unavailable under mandate")
        if self.registry.version != self.mandate.task_registry_version:
            raise ScalePreflightError("task registry version differs from mandate")
        return task

    def provider_send(self, request: SendRequest, *, triggered_escalations: Iterable[str] = ()) -> TaskContract:
        task = self._task(request.task_id, request.task_version)
        if request.subject_id not in self.mandate.subject_ids:
            raise ScalePreflightError("subject is outside frozen population")
        if not request.scope_id or not request.packet_frozen or not request.packet_hash:
            raise ScalePreflightError("provider send requires a frozen bound packet")
        if not request.reservation_id:
            raise ScalePreflightError("provider send requires an explicit reservation")
        if self.active_reservation_ids is not None and request.reservation_id not in self.active_reservation_ids:
            raise ScalePreflightError("provider send reservation is not active")
        if request.physical_attempt_id in self.reserved_attempt_ids:
            raise ScalePreflightError("duplicate paid physical attempt")
        if self.halts.active(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=request.subject_id) or (self.catalog is not None and self.catalog.active_scale_s0_halt(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=request.subject_id)):
            raise ScalePreflightError("applicable hard halt prevents provider send")
        actual_route = self.routing.route(request.route, triggered_escalations)
        if actual_route != request.route:
            raise ScalePreflightError("request route does not reflect required triggered escalation")
        for source_id in request.source_ids:
            source = self.sources.get(source_id)
            if source is None or source.source_family not in self.mandate.applicable_source_families or not source.permits(task):
                raise ScalePreflightError("source is unauthorised for this task/provider transmission")
        self.reserved_attempt_ids.add(request.physical_attempt_id)
        return task

    def review_requirement(self, candidate: Candidate, sampling: SamplingPolicy, reasons: Iterable[str]) -> ReviewRequirement:
        task = self._task(candidate.task_id, candidate.task_version)
        if candidate.subject_id not in self.mandate.subject_ids or candidate.claim_family != task.family:
            raise ScalePreflightError("candidate is outside authorised subject or semantic family")
        candidate.representation_policy.validate()
        return sampling.requirement(candidate_id=candidate.candidate_id, task_key=task.key, reasons=reasons, deterministic_source_native=candidate.deterministic_source_native)

    def promote(self, candidate: Candidate, *, review_requirement: ReviewRequirement,
                review_item: ReviewItem | None, decision: ReviewDecision | None) -> str:
        task = self._task(candidate.task_id, candidate.task_version)
        if not candidate.mechanically_validated or not candidate.source_ids or not candidate.lineage_ids or not candidate.scope_id:
            raise ScalePreflightError("candidate lacks mechanical validation, evidence, lineage, subject, or scope")
        candidate.representation_policy.validate()
        if candidate.processing_disposition in {ProcessingDisposition.PARSING_FAILED, ProcessingDisposition.PROCESSING_FAILED, ProcessingDisposition.NOT_PROCESSED}:
            raise ScalePreflightError("processing failure cannot be promoted or treated as not found")
        if self.halts.active(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=candidate.subject_id) or (self.catalog is not None and self.catalog.active_scale_s0_halt(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=candidate.subject_id)):
            raise ScalePreflightError("hard halt prevents promotion")
        if "governed_observations" not in self.mandate.allowed_outputs:
            raise ScalePreflightError("mandate does not authorise governed observations")
        if candidate.deterministic_source_native:
            if task.promotion_policy_class != "deterministic_source_native_audited":
                raise ScalePreflightError("deterministic path is not authorised for semantic candidate")
            return f"observation:{candidate.candidate_id}"
        if review_requirement == ReviewRequirement.NONE:
            raise ScalePreflightError("semantic candidate cannot become governed without an applicable review decision")
        if review_item is None or decision is None:
            raise ScalePreflightError("required review is missing")
        if review_item.status != ReviewStatus.OPEN or review_item.candidate_id != candidate.candidate_id or review_item.candidate_binding_hash != candidate.binding_hash:
            raise ScalePreflightError("review item is not bound to this exact candidate version/scope")
        if decision.review_id != review_item.review_id or decision.candidate_binding_hash != candidate.binding_hash:
            raise ScalePreflightError("review decision is not bound to this exact candidate version/scope")
        if decision.disposition not in {DecisionDisposition.PROMOTE, DecisionDisposition.NARROW_OR_CORRECT}:
            raise ScalePreflightError("review disposition does not permit promotion")
        if not decision.reviewer_or_policy or not decision.rationale or not decision.evidence_basis:
            raise ScalePreflightError("decision is not auditable")
        return decision.target_governed_artifact_id or f"observation:{candidate.candidate_id}"


def default_s0_registry() -> LogicalTaskRegistry:
    """Logical task identity; physical bundling never erases these contracts."""
    rows = (
        ("program_service", (2,), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("activity_classification", (3, 19), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("population_geography", (5, 6), RoutingClass.LOW_COST_SEMANTIC, True),
        ("participation", (10,), RoutingClass.LOW_COST_SEMANTIC, True),
        ("direct_service", (7,), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("fundraising", (8,), RoutingClass.LOW_COST_SEMANTIC, True),
        ("governance_workforce", (11,), RoutingClass.LOW_COST_SEMANTIC, True),
        ("relationships", (12,), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("finance_source_native", (13,), RoutingClass.DETERMINISTIC, False),
        ("funding_dependency", (14,), RoutingClass.STRONG_REASONING, False),
        ("ethos_commitments", (15,), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("conduct_adverse", (16,), RoutingClass.HUMAN_DECISION, False),
        ("notable_history", (17,), RoutingClass.LOW_COST_SEMANTIC, True),
        ("outcomes_evaluation", (18,), RoutingClass.STRONG_REASONING, False),
        ("taxonomy", (4, 19), RoutingClass.LOW_COST_THEN_ESCALATE, True),
        ("discovery_signals", (19,), RoutingClass.DETERMINISTIC, False),
    )
    contracts = []
    for family, sections, route, bundle in rows:
        deterministic = family in {"finance_source_native", "discovery_signals"}
        contracts.append(TaskContract(
            task_id=f"urn:charitygraph:scale-s0:{family}", version="1.0", family=family,
            allowed_sections=sections, input_profile_id=f"profile:{family}:1", output_schema_id=f"urn:charitygraph:builder:schema:{family}:1.0",
            validation_policy_id=f"validation:{family}:1", candidate_disposition="source_native" if deterministic else "semantic_candidate",
            default_routing=route, escalation_triggers=ESCALATION_TRIGGERS if route != RoutingClass.DETERMINISTIC else frozenset(),
            promotion_policy_class="deterministic_source_native_audited" if deterministic else "review_required",
            current_state_sensitive=family in {"direct_service", "conduct_adverse", "funding_dependency"}, physical_bundling_permitted=bundle,
        ))
    return LogicalTaskRegistry(version="scale-s0-logical-registry-1", contracts=tuple(contracts))


__all__ = [name for name in globals() if not name.startswith("_")]
