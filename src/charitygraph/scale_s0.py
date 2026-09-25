"""Fail-closed offline authority checks for a future Scale S0 slice.

This is deliberately a guard around the established runtime catalogue. It does
not acquire, call a provider, or create public projections. All inputs to a
paid boundary are immutable material identities, never caller assertions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from .runtime.catalog import (
    S0_LIVE_SEND_ATTESTER, S0_LIVE_SEND_OBSERVED_VALUE, S0_LIVE_SEND_SETTING_NAME,
    canonical_execution_configuration_hash, canonical_utc_timestamp,
)


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ScalePreflightError(ValueError):
    """A required S0 authority, immutable identity, or durable state is absent."""


class RoutingClass(StrEnum):
    DETERMINISTIC = "deterministic"
    LOW_COST_SEMANTIC = "low_cost_semantic"
    LOW_COST_THEN_ESCALATE = "low_cost_then_escalate"
    STRONG_REASONING = "strong_reasoning"
    HUMAN_DECISION = "human_decision"


LOCATOR_SEARCH_OPERATION_KIND = "locator_search"
LOCATOR_SEARCH_MAX_QUERIES_PER_SUBJECT = 5
LOCATOR_SEARCH_TASK_ID = "urn:charitygraph:scale-s0:locator_search"
LOCATOR_SEARCH_TASK_VERSION = "1.0"
LOCATOR_SEARCH_INPUT_PROFILE_ID = "profile:locator-search:1"
LOCATOR_SEARCH_OUTPUT_SCHEMA_ID = "urn:charitygraph:builder:schema:locator-search-discovery-metadata:1.0"
LOCATOR_SEARCH_PROVIDER_REQUEST = {
    "model": "gpt-5.6-luna",
    "tools": [{"type": "web_search"}],
    "tool_choice": {"type": "web_search"},
    "store": False,
    "include": ["web_search_call.action.sources"],
}


def locator_search_request_body(query: str) -> dict[str, Any]:
    """Build the sole canonical locator POST body from frozen public input."""
    return {"model": LOCATOR_SEARCH_PROVIDER_REQUEST["model"], "input": query,
            "tools": [{"type": "web_search"}],
            "tool_choice": {"type": "web_search"}, "store": False,
            "include": ["web_search_call.action.sources"]}


def locator_search_request_identity(*, subject_id: str, query: str, query_index: int,
                                    execution_attempt_id: str,
                                    provider_account_project: str,
                                    execution_authority: str) -> str:
    """Return the durable identity for one bounded, public-identity search.

    This is an operational identity, never an evidence or semantic-task identity.
    Keeping it in the S0 control plane lets the frozen packet, reservation, and
    exactly-once boundary independently recompute the same value.
    """
    if (not subject_id or not query or not execution_attempt_id
            or not provider_account_project or not execution_authority
            or not isinstance(query_index, int)
            or isinstance(query_index, bool)
            or not 0 <= query_index < LOCATOR_SEARCH_MAX_QUERIES_PER_SUBJECT):
        raise ScalePreflightError("locator search identity requires a subject, query, and bounded query index")
    # The durable exactly-once identity deliberately includes every provider
    # material field.  A later contract repair (for example, a required
    # Responses ``include``) must never collide with an earlier request.
    return "locator-search:" + _digest({"execution_attempt": execution_attempt_id,
                                         "provider_account_project": provider_account_project,
                                         "execution_authority": execution_authority,
                                         "subject": subject_id, "query": query, "index": query_index,
                                         "body": locator_search_request_body(query)})


class ReviewRequirement(StrEnum): NONE = "none"; SAMPLED = "sampled"; MANDATORY = "mandatory"
class ReviewStatus(StrEnum): OPEN = "open"; DECIDED = "decided"; SUPERSEDED = "superseded"
class DecisionDisposition(StrEnum):
    PROMOTE = "promote"; NARROW_OR_CORRECT = "narrow_or_correct"; REJECT = "reject"; ESCALATE = "escalate"; DEFER_UNKNOWN = "defer_unknown"; DUPLICATE_SUPERSEDED = "duplicate_superseded"
class HaltScope(StrEnum): TASK = "task"; SUBJECT = "subject"; SLICE = "slice"
class HaltReason(StrEnum):
    RIGHTS_TRANSMISSION_VIOLATION = "rights_transmission_violation"; AMBIGUOUS_PROVIDER_SEND_OR_BILLING = "ambiguous_provider_send_or_billing"; BUDGET_RESERVATION_VIOLATION = "budget_reservation_violation"; PROVIDER_MODEL_PROMPT_SCHEMA_DRIFT = "provider_model_prompt_schema_drift"; CANDIDATE_TO_GOVERNED_BYPASS = "candidate_to_governed_bypass"; RAW_OUTPUT_TO_CARD_BYPASS = "raw_output_to_card_bypass"; REVIEW_BACKLOG_THRESHOLD = "review_backlog_threshold"
class DocumentRepresentation(StrEnum):
    NATIVE_STRUCTURED = "native_structured_document"; RELIABLE_TEXT = "reliable_extracted_text"; VISUALLY_MATERIAL_PDF = "visually_material_pdf"; IMAGE_SCANNED_PDF = "image_scanned_pdf"; PARSING_FAILURE = "parsing_failure"; UNSUPPORTED = "unsupported_representation"
class ProcessingDisposition(StrEnum):
    NOT_ATTEMPTED = "not_attempted"; UNAVAILABLE = "unavailable"; ACQUIRED = "acquired"; PARSING_FAILED = "parsing_failed"; NOT_PROCESSED = "not_processed"; PROCESSING_FAILED = "processing_failed"; SOURCE_SILENT = "source_silent"; NOT_FOUND_IN_FINITE_REVIEWED_UNIVERSE = "not_found_in_finite_reviewed_universe"; UNKNOWN = "unknown"; STALE = "stale"


MANDATORY_REVIEW_REASONS = frozenset({"adverse_positive", "complex_relationship", "taxonomy_boundary", "causation_or_contribution", "dependency_assessment", "source_conflict", "stale_current_state", "correction_or_supersession"})
ESCALATION_PRIORITY = ("repeated_contract_schema_failure", "outcome_causation_ambiguity", "taxonomy_narrow_reject_boundary", "scope_ambiguity", "unresolved_relationship_endpoint", "source_conflict")


@dataclass(frozen=True)
class PolicyArtifact:
    policy_id: str; version: str; content_hash: str
    def validate(self) -> None:
        if not self.policy_id or not self.version or len(self.content_hash) != 64: raise ScalePreflightError("policy artifact must have an immutable identity")


@dataclass(frozen=True)
class TaskContract:
    task_id: str; version: str; family: str; allowed_sections: tuple[int, ...]; input_profile_id: str; output_schema_id: str; validation_policy_id: str; candidate_disposition: str; default_routing: RoutingClass
    escalation_triggers: frozenset[str] = frozenset(); allowed_escalation_routes: tuple[RoutingClass, ...] = (); promotion_policy_class: str = "review_required"; current_state_sensitive: bool = False; physical_bundling_permitted: bool = False; available: bool = True
    @property
    def key(self) -> str: return f"{self.task_id}@{self.version}"


@dataclass(frozen=True)
class LogicalTaskRegistry:
    version: str; contracts: tuple[TaskContract, ...]; content_hash: str = ""
    @property
    def immutable_hash(self) -> str: return self.content_hash or _digest(_material({"version": self.version, "contracts": self.contracts}))
    def get(self, task_id: str, version: str) -> TaskContract:
        for item in self.contracts:
            if item.task_id == task_id and item.version == version: return item
        raise ScalePreflightError("unregistered logical task contract")


@dataclass(frozen=True)
class RoutingPolicy:
    policy_id: str; version: str; permitted: frozenset[RoutingClass]; escalation_routes: Mapping[str, RoutingClass]; content_hash: str = ""
    @property
    def immutable_hash(self) -> str: return self.content_hash or _digest(_material({"policy_id": self.policy_id, "version": self.version, "permitted": sorted(self.permitted), "escalation_routes": self.escalation_routes}))
    def route_for(self, task: TaskContract, triggers: Iterable[str]) -> RoutingClass:
        triggered = set(triggers)
        if not triggered: return task.default_routing
        if not triggered <= task.escalation_triggers: raise ScalePreflightError("task does not authorise an escalation trigger")
        for trigger in ESCALATION_PRIORITY:
            if trigger in triggered:
                route = self.escalation_routes.get(trigger)
                if route is None or route not in self.permitted or route not in task.allowed_escalation_routes: raise ScalePreflightError("task escalation route is not authorised")
                return route
        raise ScalePreflightError("unknown escalation trigger")


@dataclass(frozen=True)
class SamplingPolicy:
    policy_id: str; version: str; seed: str; strata: tuple[str, ...]; sample_rates: Mapping[str, float] = field(default_factory=dict); content_hash: str = ""
    @property
    def immutable_hash(self) -> str: return self.content_hash or _digest(_material(self))
    def requirement(self, *, candidate_id: str, task_key: str, reasons: Iterable[str], deterministic_source_native: bool) -> ReviewRequirement:
        if set(reasons) & MANDATORY_REVIEW_REASONS: return ReviewRequirement.MANDATORY
        if deterministic_source_native: return ReviewRequirement.NONE
        rate = self.sample_rates.get(task_key, self.sample_rates.get("default", 0.0))
        if not 0 <= rate <= 1: raise ScalePreflightError("sampling rate is outside [0,1]")
        return ReviewRequirement.SAMPLED if int(_digest(f"{self.seed}|{self.version}|{candidate_id}|{task_key}")[:12], 16) / float(16**12) < rate else ReviewRequirement.NONE


@dataclass(frozen=True)
class ScaleMandate:
    mandate_id: str; mandate_version: str; slice_id: str; created_at: str; authorizing_actor_ref: str; population_ref: str; subject_ids: tuple[str, ...]; snapshot_as_of: str; ranking_policy_id: str; group_entity_policy_id: str; source_universe_policy_id: str; source_universe_policy_version: str; mandatory_source_families: tuple[str, ...]; applicable_source_families: tuple[str, ...]; specialist_source_policy_id: str; rights_transmission_policy_id: str; task_registry_version: str; enabled_task_ids: tuple[str, ...]; disabled_task_ids: tuple[str, ...]; routing_policy_id: str; routing_policy_version: str; provider_spend_ceiling: str; strong_model_spend_ceiling: str; provider_call_ceiling: int; reservation_policy_id: str; currency_basis: str; review_policy_id: str; review_policy_version: str; promotion_policy_id: str; promotion_policy_version: str; sampling_policy_id: str; sampling_policy_version: str; halt_policy_id: str; halt_policy_version: str; allowed_outputs: tuple[str, ...]
    parent_product_contract: str = "north-star-v0.2"; automatically_publishable: bool = False; policy_hashes: Mapping[str, str] = field(default_factory=dict); per_request_reservation_cap: str = ""
    @property
    def identity_hash(self) -> str: return _digest(_material(self))
    def validate(self) -> None:
        required = (self.mandate_id,self.mandate_version,self.slice_id,self.created_at,self.authorizing_actor_ref,self.population_ref,self.snapshot_as_of,self.ranking_policy_id,self.group_entity_policy_id,self.source_universe_policy_id,self.rights_transmission_policy_id,self.task_registry_version,self.routing_policy_id,self.reservation_policy_id,self.review_policy_id,self.promotion_policy_id,self.sampling_policy_id,self.halt_policy_id,self.currency_basis)
        if any(not x or str(x).startswith("UNAPPROVED_") for x in required) or not self.subject_ids or not self.mandatory_source_families or not self.enabled_task_ids: raise ScalePreflightError("mandate is missing required frozen policy/reference")
        if not set(self.mandatory_source_families) <= set(self.applicable_source_families): raise ScalePreflightError("mandatory source family is outside authorised universe")
        if self.parent_product_contract != "north-star-v0.2" or self.automatically_publishable: raise ScalePreflightError("mandate does not preserve product/publication boundary")
        try:
            if any(Decimal(x) < 0 for x in (self.provider_spend_ceiling,self.strong_model_spend_ceiling,self.per_request_reservation_cap or self.provider_spend_ceiling)) or self.provider_call_ceiling < 0: raise ValueError
        except (InvalidOperation, ValueError): raise ScalePreflightError("mandate economics must be explicit non-negative ceilings") from None


@dataclass(frozen=True)
class ExecutionAttemptIdentity:
    """Immutable implementation binding for one live S0 execution attempt."""
    attempt_id: str; mandate_id: str; mandate_hash: str; slice_id: str; run_id: str
    builder_repository: str; builder_commit_sha: str; data_repository: str; data_commit_sha: str
    bridge_certification: str; bridge_version: str; schema_version: int
    recovery_authority_ref: str; configuration_hash: str; status: str; created_at: str
    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", canonical_utc_timestamp(self.created_at, "created_at"))
    @property
    def material_hash(self) -> str: return _digest(_material(self))

    @property
    def canonical_configuration_hash(self) -> str:
        return canonical_execution_configuration_hash(
            mandate_hash=self.mandate_hash, slice_id=self.slice_id, run_id=self.run_id,
            builder_repository=self.builder_repository, builder_commit_sha=self.builder_commit_sha,
            data_repository=self.data_repository, data_commit_sha=self.data_commit_sha,
            bridge_certification=self.bridge_certification, bridge_version=self.bridge_version,
            schema_version=self.schema_version, recovery_authority_ref=self.recovery_authority_ref,
        )


@dataclass(frozen=True)
class OwnerAttestation:
    """Product-owner approval bound to one frozen S0 provider request."""
    attestation_id: str; execution_attempt_id: str; mandate_id: str; mandate_hash: str; slice_id: str; run_id: str
    builder_commit_sha: str; data_commit_sha: str; configuration_hash: str; attempt_material_hash: str
    packet_id: str; packet_binding_hash: str; task_key: str; reservation_id: str; provider_request_identity: str
    setting_name: str; observed_value: str; attested_by: str; owner_attestation_hash: str; observed_at: str; recorded_at: str


@dataclass(frozen=True)
class SourceAuthorisation:
    source_id: str; source_family: str; url_or_identity: str; authority_role: str; rights_transmission_status: str; acquisition_state: str; parsing_state: str; snapshot_hash: str; claim_families: tuple[str, ...]; source_record_id: str = ""; rights_policy_version: str = ""; specialist_authorisation_id: str | None = None; access_classification: str = "SEPARATELY_LICENSED_OR_CONTROLLED"; technical_access_state: str = "unknown"
    # The fields below are deliberately optional only for explicit offline
    # fixtures.  Live registration requires every one of them and persists the
    # record in migration 22 before a source can reach transport or a packet.
    source_authority_id: str = ""; mandate_id: str = ""; mandate_hash: str = ""; slice_id: str = ""; execution_attempt_id: str = ""; subject_id: str = ""; exact_resource_id: str = ""; rights_policy_id: str = ""; rights_decision_id: str = ""; authority_material: Mapping[str, object] = field(default_factory=dict); created_at: str = ""
    def permits(self, task: TaskContract, mandate: ScaleMandate) -> bool:
        open_web = self.access_classification == "OPEN_WEB_PUBLIC" and self.technical_access_state == "accessible" and self.rights_transmission_status in {"permitted", "permitted_open_web_policy"}
        controlled = self.access_classification == "SEPARATELY_LICENSED_OR_CONTROLLED" and self.rights_transmission_status == "permitted"
        return (open_web or controlled) and self.acquisition_state == "acquired" and self.parsing_state in {"parsed","structured"} and bool(self.snapshot_hash) and bool(self.source_record_id) and task.family in self.claim_families and (self.specialist_authorisation_id is None or self.specialist_authorisation_id == mandate.specialist_source_policy_id)


@dataclass(frozen=True)
class RepresentationPolicy:
    representation: DocumentRepresentation; authorised_mode: str; materially_relevant_visual_content: bool = False
    def validate(self) -> None:
        allowed = {DocumentRepresentation.NATIVE_STRUCTURED:{"structured_source_native_data"},DocumentRepresentation.RELIABLE_TEXT:{"text_extraction_only","page_rendered_visual"},DocumentRepresentation.VISUALLY_MATERIAL_PDF:{"page_rendered_visual"},DocumentRepresentation.IMAGE_SCANNED_PDF:{"page_rendered_visual","not_processable"},DocumentRepresentation.PARSING_FAILURE:{"not_processable"},DocumentRepresentation.UNSUPPORTED:{"not_processable"}}
        if self.authorised_mode not in allowed[self.representation] or self.materially_relevant_visual_content and self.authorised_mode == "text_extraction_only": raise ScalePreflightError("document representation is inadequate for authorised processing")


@dataclass(frozen=True)
class FrozenPacket:
    packet_id: str; task_id: str; task_version: str; subject_id: str; scope_id: str; source_ids: tuple[str, ...]; source_snapshot_hashes: tuple[str, ...]; input_profile_id: str; output_schema_id: str; routing_class: RoutingClass; provider_request_identity: str; content_hash: str; contract_version: str = "north-star-v0.2"; mandate_id: str = ""; slice_id: str = ""; frozen_at: str = ""; corpus_id: str = ""; operation_kind: str = "semantic"; locator_query: str = ""; locator_query_index: int = -1; pricing_snapshot_id: str = ""; estimated_provider_cost: str = ""; locator_execution_attempt_id: str = ""; provider_account_project: str = ""; execution_authority: str = ""
    def __post_init__(self) -> None:
        if self.frozen_at:
            object.__setattr__(self, "frozen_at", canonical_utc_timestamp(self.frozen_at, "frozen_at"))
        if self.operation_kind not in {"semantic", LOCATOR_SEARCH_OPERATION_KIND}:
            raise ScalePreflightError("frozen packet has an unknown operation kind")
        if self.operation_kind == LOCATOR_SEARCH_OPERATION_KIND:
            expected = locator_search_request_identity(subject_id=self.subject_id, query=self.locator_query,
                                                       query_index=self.locator_query_index,
                                                       execution_attempt_id=self.locator_execution_attempt_id,
                                                       provider_account_project=self.provider_account_project,
                                                       execution_authority=self.execution_authority)
            if (self.task_id, self.task_version, self.input_profile_id, self.output_schema_id,
                self.routing_class, self.provider_request_identity) != (
                    LOCATOR_SEARCH_TASK_ID, LOCATOR_SEARCH_TASK_VERSION,
                    LOCATOR_SEARCH_INPUT_PROFILE_ID, LOCATOR_SEARCH_OUTPUT_SCHEMA_ID,
                    RoutingClass.LOW_COST_SEMANTIC, expected):
                raise ScalePreflightError("locator search packet does not bind its canonical operational contract")
            if self.source_ids or self.source_snapshot_hashes or self.corpus_id:
                raise ScalePreflightError("locator search packet must remain source-free and corpus-free")
            if not self.locator_execution_attempt_id or not self.provider_account_project or not self.execution_authority:
                raise ScalePreflightError("locator search packet lacks immutable execution and A3 bindings")
            try:
                estimate = Decimal(self.estimated_provider_cost)
            except (InvalidOperation, ValueError) as error:
                raise ScalePreflightError("locator search packet lacks a decimal price estimate") from error
            if not self.pricing_snapshot_id or not estimate.is_finite() or estimate <= 0:
                raise ScalePreflightError("locator search packet requires a positive immutable pricing estimate")
    @property
    def binding_hash(self) -> str: return _digest(_material(self))


@dataclass(frozen=True)
class Candidate:
    candidate_id: str; task_id: str; task_version: str; subject_id: str; scope_id: str; source_ids: tuple[str, ...]; lineage_ids: tuple[str, ...]; mechanically_validated: bool; claim_family: str; routing_class: RoutingClass; representation_policy: RepresentationPolicy; deterministic_source_native: bool = False; processing_disposition: ProcessingDisposition = ProcessingDisposition.ACQUIRED; semantic_payload: object = None; predicate: str = ""; evidence_locator_ids: tuple[str, ...] = (); source_record_ids: tuple[str, ...] = (); epistemic_basis: str = ""; observation_time: str = ""; effective_time: str = ""; classification_authority: str = ""; mandate_id: str = ""; packet_id: str = ""; created_at: str = ""; supersedes_candidate_id: str | None = None
    def __post_init__(self) -> None:
        if self.created_at:
            object.__setattr__(self, "created_at", canonical_utc_timestamp(self.created_at, "created_at"))
    @property
    def binding_hash(self) -> str: return _digest(_material(self))


def _material(value: object) -> object:
    """Canonical, JSON-safe material for the durable control-plane boundary."""
    if is_dataclass(value):
        return _material(asdict(value))
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _material(item) for key, item in value.items()}
    if isinstance(value, (frozenset, set)):
        return [_material(item) for item in sorted(value, key=str)]
    if isinstance(value, (tuple, list)):
        return [_material(item) for item in value]
    return value


def _tuple_material(value: object) -> tuple[str, ...]:
    return tuple(value or ())


@dataclass(frozen=True)
class ReviewItem:
    review_id: str; candidate_id: str; candidate_binding_hash: str; task_id: str; task_version: str; subject_id: str; scope_id: str; evidence_source_ids: tuple[str, ...]; lineage_ids: tuple[str, ...]; reasons: tuple[str, ...]; risk_category: str; created_at: str; status: ReviewStatus = ReviewStatus.OPEN
@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str; review_id: str; candidate_binding_hash: str; disposition: DecisionDisposition; reviewer_or_policy: str; decided_at: str; rationale: str; evidence_basis: tuple[str, ...]; target_governed_artifact_id: str | None = None; corrected_candidate: Candidate | None = None; supersedes: str | None = None
@dataclass(frozen=True)
class HaltRecord:
    halt_id: str; reason: HaltReason; scope: HaltScope; slice_id: str; task_key: str | None; subject_id: str | None; created_at: str; hard: bool = True; recovered_at: str | None = None
    def applies(self, *, slice_id: str, task_key: str, subject_id: str) -> bool: return not self.recovered_at and self.slice_id == slice_id and (self.scope == HaltScope.SLICE or self.scope == HaltScope.TASK and self.task_key == task_key or self.scope == HaltScope.SUBJECT and self.subject_id == subject_id)
@dataclass
class HaltController:
    records: list[HaltRecord] = field(default_factory=list)
    def active(self, **key: str) -> HaltRecord | None: return next((x for x in reversed(self.records) if x.hard and x.applies(**key)), None)
@dataclass(frozen=True)
class EconomicState:
    provider_calls: int = 0; provider_spend: Decimal = Decimal("0"); strong_model_spend: Decimal = Decimal("0"); reservation_id: str | None = None; reservation_active: bool = False; reservation_mandate_id: str | None = None; reservation_slice_id: str | None = None; reservation_task_key: str | None = None; reservation_remaining: Decimal = Decimal("0"); reservation_currency: str = ""; estimated_provider_cost: Decimal = Decimal("0"); estimated_strong_cost: Decimal = Decimal("0"); pricing_snapshot_id: str = ""
@dataclass(frozen=True)
class PriorAttempt:
    state: str; provider_request_identity: str; physical_attempt_id: str
@dataclass(frozen=True)
class SendRequest:
    physical_attempt_id: str; task_id: str; task_version: str; subject_id: str; scope_id: str; packet_hash: str | None; packet_frozen: bool; route: RoutingClass; reservation_id: str | None; source_ids: tuple[str, ...]; retry_permitted: bool; prior_attempt: PriorAttempt | None = None; provider_account_project: str | None = None; execution_authority: str | None = None


def locator_search_task_contract() -> TaskContract:
    """The approved locator operation is intentionally outside semantic tasks.

    It has no output eligible for candidate or evidence processing.  It merely
    supplies the operational contract used by the same routing/economics/send
    gates that apply to semantic packets.
    """
    return TaskContract(LOCATOR_SEARCH_TASK_ID, LOCATOR_SEARCH_TASK_VERSION,
                        LOCATOR_SEARCH_OPERATION_KIND, (),
                        LOCATOR_SEARCH_INPUT_PROFILE_ID,
                        LOCATOR_SEARCH_OUTPUT_SCHEMA_ID,
                        "validation:locator-search:1", "discovery_metadata_only",
                        RoutingClass.LOW_COST_SEMANTIC, available=True)


def _validate_locator_search_packet(packet: FrozenPacket, mandate: ScaleMandate) -> None:
    if packet.operation_kind != LOCATOR_SEARCH_OPERATION_KIND:
        raise ScalePreflightError("expected a locator search packet")
    # FrozenPacket validates deterministic identity, source/corpus exclusion and
    # positive price.  These mandate-scoped checks keep it inside S0 economics.
    try:
        estimate = Decimal(packet.estimated_provider_cost)
    except (InvalidOperation, ValueError) as error:
        raise ScalePreflightError("locator search price estimate is invalid") from error
    if packet.subject_id not in mandate.subject_ids or not packet.scope_id:
        raise ScalePreflightError("locator search packet is outside the frozen population or scope")
    if estimate > Decimal(mandate.per_request_reservation_cap or mandate.provider_spend_ceiling):
        raise ScalePreflightError("locator search packet exceeds the per-request reservation cap")
    if packet.contract_version != mandate.parent_product_contract:
        raise ScalePreflightError("locator search packet contract is outside the mandate")


def packet_task_key(packet: FrozenPacket) -> str:
    """Return the reservation/task identity for a frozen packet.

    Semantic tasks use their immutable task contract.  Locator calls need a
    unique per-query operational task so a reservation and provider lifecycle
    cannot be shared accidentally by two queries for the same subject.
    """
    return packet.provider_request_identity if packet.operation_kind == LOCATOR_SEARCH_OPERATION_KIND else f"{packet.task_id}@{packet.task_version}"


class ScaleS0Preflight:
    def __init__(self, mandate: ScaleMandate, registry: LogicalTaskRegistry, routing: RoutingPolicy, sources: Mapping[str, SourceAuthorisation], halts: HaltController, *, packets: Mapping[str,FrozenPacket], policies: Mapping[str,PolicyArtifact], economics: EconomicState | None, catalog: object | None = None, review_backlog: int = 0, review_backlog_limit: int | None = None, execution_attempt: ExecutionAttemptIdentity | None = None) -> None:
        mandate.validate(); self.mandate,self.registry,self.routing,self.sources,self.halts,self.packets,self.policies,self.economics,self.catalog,self.execution_attempt = mandate,registry,routing,sources,halts,packets,policies,economics,catalog,execution_attempt
        if catalog is not None and execution_attempt is not None and economics is not None:
            raise ScalePreflightError("live S0 economics must be reconstructed from durable reservation state")
        if execution_attempt is not None and catalog is not None:
            catalog.require_scale_s0_execution_attempt(attempt_id=execution_attempt.attempt_id, mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash, slice_id=mandate.slice_id, run_id=execution_attempt.run_id, builder_commit_sha=execution_attempt.builder_commit_sha, data_commit_sha=execution_attempt.data_commit_sha, bridge_certification=execution_attempt.bridge_certification, schema_version=execution_attempt.schema_version)
        if review_backlog_limit is not None and review_backlog > review_backlog_limit: raise ScalePreflightError("review backlog threshold halts execution")
        self._bind_policies()

    @staticmethod
    def register_durable_mandate(catalog: object, mandate: ScaleMandate, registry: LogicalTaskRegistry, routing: RoutingPolicy, policies: Mapping[str, PolicyArtifact], sources: Mapping[str, SourceAuthorisation] | None = None, *, offline: bool = False) -> dict:
        """Persist immutable policy authority, never a concrete source decision."""
        mandate.validate()
        if sources and not offline:
            raise ScalePreflightError("live concrete source authority must be registered separately from the mandate")
        authority = {"registry": _material(registry), "routing": _material(routing), "policies": _material(policies)}
        return catalog.register_scale_s0_mandate(_material(mandate), authority=authority)

    @staticmethod
    def register_durable_execution_attempt(catalog: object, attempt: ExecutionAttemptIdentity) -> dict:
        return catalog.register_scale_s0_execution_attempt(_material(attempt))

    @staticmethod
    def register_durable_source_authority(catalog: object, authority: SourceAuthorisation) -> dict:
        """Persist the concrete, attempt-bound decision that authorises one resource."""
        material = _material(authority)
        assert isinstance(material, dict)
        return catalog.register_scale_s0_source_authority(material)

    @staticmethod
    def register_durable_owner_attestation(catalog: object, attestation: OwnerAttestation) -> dict:
        """Record the exact owner approval that the catalogue must re-check at send time."""
        return catalog.register_scale_s0_owner_attestation(_material(attestation))

    @classmethod
    def from_catalog(cls, catalog: object, *, mandate_id: str, packet_id: str, economics: EconomicState | None = None, offline: bool = False) -> "ScaleS0Preflight":
        """Rebuild preflight from durable authority, never a caller replacement."""
        if economics is not None and not offline:
            raise ScalePreflightError("live S0 economics must be reconstructed from durable reservation state")
        stored = catalog.get_scale_s0_mandate(mandate_id)
        packet_row = catalog.get_scale_s0_frozen_packet(packet_id)
        if stored is None or packet_row is None:
            raise ScalePreflightError("durable S0 authority is absent")
        mandate_data, authority = stored["material"], stored["authority"]
        mandate = ScaleMandate(**{**mandate_data, "subject_ids": _tuple_material(mandate_data.get("subject_ids")), "mandatory_source_families": _tuple_material(mandate_data.get("mandatory_source_families")), "applicable_source_families": _tuple_material(mandate_data.get("applicable_source_families")), "enabled_task_ids": _tuple_material(mandate_data.get("enabled_task_ids")), "disabled_task_ids": _tuple_material(mandate_data.get("disabled_task_ids"))})
        registry_data = authority["registry"]
        contracts = tuple(TaskContract(**{**item, "allowed_sections": tuple(item["allowed_sections"]), "default_routing": RoutingClass(item["default_routing"]), "escalation_triggers": frozenset(item.get("escalation_triggers", ())), "allowed_escalation_routes": tuple(RoutingClass(route) for route in item.get("allowed_escalation_routes", ()))} ) for item in registry_data["contracts"])
        registry = LogicalTaskRegistry(registry_data["version"], contracts, registry_data.get("content_hash", ""))
        routing_data = authority["routing"]
        routing = RoutingPolicy(routing_data["policy_id"], routing_data["version"], frozenset(RoutingClass(item) for item in routing_data["permitted"]), {key: RoutingClass(value) for key, value in routing_data["escalation_routes"].items()}, routing_data.get("content_hash", ""))
        policies = {key: PolicyArtifact(**value) for key, value in authority["policies"].items()}
        packet_data = packet_row["material"]
        attempt = None
        if not offline:
            attempt_id = packet_data.get("execution_attempt_id")
            if not attempt_id:
                raise ScalePreflightError("live S0 preflight requires an execution-attempt-bound packet")
            stored_attempt = catalog.get_scale_s0_execution_attempt(attempt_id)
            if stored_attempt is None or stored_attempt["mandate_id"] != mandate.mandate_id or stored_attempt["slice_id"] != mandate.slice_id or stored_attempt["run_id"] != packet_data.get("run_id"):
                raise ScalePreflightError("packet execution-attempt lineage is absent or inconsistent")
            attempt = ExecutionAttemptIdentity(**{key: stored_attempt[key] for key in ExecutionAttemptIdentity.__dataclass_fields__})
        packet_fields = {key: packet_data[key] for key in FrozenPacket.__dataclass_fields__ if key in packet_data}
        packet = FrozenPacket(**{**packet_fields, "source_ids": _tuple_material(packet_data.get("source_ids")), "source_snapshot_hashes": _tuple_material(packet_data.get("source_snapshot_hashes")), "routing_class": RoutingClass(packet_data["routing_class"])})
        if packet.mandate_id != mandate.mandate_id or packet.binding_hash != packet_data.get("binding_hash"):
            raise ScalePreflightError("durable packet identity is corrupt or substituted")
        if packet.operation_kind == LOCATOR_SEARCH_OPERATION_KIND:
            _validate_locator_search_packet(packet, mandate)
        sources: dict[str, SourceAuthorisation] = {}
        if not offline:
            if attempt is None:
                raise ScalePreflightError("live S0 source authority requires an execution attempt")
            for source_id, snapshot_hash in zip(packet.source_ids, packet.source_snapshot_hashes, strict=True):
                source_row = catalog.get_scale_s0_source_authority_for_source(execution_attempt_id=attempt.attempt_id, source_id=source_id)
                snapshot_row = catalog.get_scale_s0_source_snapshot(source_id)
                representation_row = catalog.get_scale_s0_representation_for_snapshot(execution_attempt_id=attempt.attempt_id, snapshot_id=source_id)
                if source_row is None or snapshot_row is None or representation_row is None:
                    raise ScalePreflightError("live S0 source authority, snapshot, or representation is absent")
                source_data = dict(source_row["material"])
                snapshot_data = dict(snapshot_row["material"])
                indexed_source = (source_row.get("source_authority_id"), source_row.get("mandate_id"), source_row.get("mandate_hash"), source_row.get("slice_id"), source_row.get("execution_attempt_id"), source_row.get("source_id"), source_row.get("source_family"), source_row.get("subject_id"), source_row.get("locator"), source_row.get("exact_resource_id"), source_row.get("rights_policy_id"), source_row.get("rights_policy_version"), source_row.get("rights_decision_id"), source_row.get("rights_transmission_status"), source_row.get("access_classification"), source_row.get("technical_access_state"), source_row.get("authority_role"))
                material_source = (source_data.get("source_authority_id"), source_data.get("mandate_id"), source_data.get("mandate_hash"), source_data.get("slice_id"), source_data.get("execution_attempt_id"), source_data.get("source_id"), source_data.get("source_family"), source_data.get("subject_id"), source_data.get("url_or_identity"), source_data.get("exact_resource_id"), source_data.get("rights_policy_id"), source_data.get("rights_policy_version"), source_data.get("rights_decision_id"), source_data.get("rights_transmission_status"), source_data.get("access_classification"), source_data.get("technical_access_state"), source_data.get("authority_role"))
                if indexed_source != material_source or source_row.get("authority_material") != source_data.get("authority_material") or _digest(_material(source_data.get("authority_material"))) != source_row.get("authority_material_hash") or _digest(_material(source_data)) != source_row["material_hash"] or _digest(_material(snapshot_data)) != snapshot_row["material_hash"]:
                    raise ScalePreflightError("durable source authority or snapshot integrity is invalid")
                if (source_data.get("source_id"), source_data.get("execution_attempt_id"), source_data.get("mandate_id"), source_data.get("mandate_hash"), source_data.get("slice_id"), source_data.get("subject_id"), source_data.get("source_family")) != (source_id, attempt.attempt_id, mandate.mandate_id, mandate.identity_hash, mandate.slice_id, packet.subject_id, source_data.get("source_family")):
                    raise ScalePreflightError("durable source authority is outside the packet attempt, mandate, or subject")
                if snapshot_row.get("execution_attempt_id") != attempt.attempt_id or snapshot_data.get("snapshot_hash") != snapshot_hash or snapshot_data.get("source_record_id") in (None, ""):
                    raise ScalePreflightError("durable source snapshot is substituted or incomplete")
                source_data.update({"snapshot_hash": snapshot_hash, "source_record_id": snapshot_data["source_record_id"], "acquisition_state": "acquired", "parsing_state": "parsed"})
                source_data["claim_families"] = _tuple_material(source_data.get("claim_families"))
                sources[source_id] = SourceAuthorisation(**source_data)
        if economics is None:
            reservation = catalog.get_scale_s0_reservation_binding(mandate_id=mandate.mandate_id, slice_id=mandate.slice_id, task_key=packet_task_key(packet), execution_attempt_id=attempt.attempt_id if attempt else None, offline=offline)
            if reservation is not None:
                state = dict(reservation["state"])
                for key in ("provider_spend", "strong_model_spend", "reservation_remaining", "estimated_provider_cost", "estimated_strong_cost"):
                    state[key] = Decimal(str(state[key]))
                economics = EconomicState(**{key: state[key] for key in EconomicState.__dataclass_fields__})
            elif not offline:
                raise ScalePreflightError("live S0 packet has no attempt-scoped durable reservation binding")
        rebuilt = cls(mandate, registry, routing, sources, HaltController(), packets={packet.binding_hash: packet}, policies=policies, economics=None, catalog=catalog, execution_attempt=attempt)
        rebuilt.economics = economics
        return rebuilt

    @staticmethod
    def register_durable_packet(catalog: object, mandate: ScaleMandate, packet: FrozenPacket, *, execution_attempt_id: str | None = None, offline: bool = False) -> dict:
        if not packet.mandate_id or packet.mandate_id != mandate.mandate_id or packet.slice_id != mandate.slice_id or not packet.frozen_at:
            raise ScalePreflightError("frozen packet must bind a registered mandate, slice, and freeze time")
        if execution_attempt_id is None and not offline:
            raise ScalePreflightError("live S0 packets require an execution-attempt binding")
        material = _material(packet)
        assert isinstance(material, dict)
        attempt_material = {}
        if execution_attempt_id:
            attempt_row = catalog.get_scale_s0_execution_attempt(execution_attempt_id)
            if attempt_row is None or attempt_row["mandate_id"] != mandate.mandate_id or attempt_row["slice_id"] != mandate.slice_id:
                raise ScalePreflightError("packet execution attempt is absent or mismatched")
            attempt_material = {"execution_attempt_id": execution_attempt_id, "run_id": attempt_row["run_id"]}
            if packet.operation_kind == LOCATOR_SEARCH_OPERATION_KIND:
                _validate_locator_search_packet(packet, mandate)
            else:
                if not packet.corpus_id or not hasattr(catalog, "get_scale_s0_frozen_corpus"):
                    raise ScalePreflightError("live packet requires durable corpus ownership")
                corpus_row = catalog.get_scale_s0_frozen_corpus(packet.corpus_id)
                if corpus_row is None or corpus_row.get("execution_attempt_id") != execution_attempt_id or corpus_row.get("subject_id") != packet.subject_id:
                    raise ScalePreflightError("packet corpus ownership is absent or mismatched")
                for source_id in packet.source_ids:
                    source_authority = catalog.get_scale_s0_source_authority_for_source(execution_attempt_id=execution_attempt_id, source_id=source_id)
                    if source_authority is None or source_authority.get("mandate_id") != mandate.mandate_id or source_authority.get("subject_id") != packet.subject_id:
                        raise ScalePreflightError("live packet requires durable source authority for every frozen source")
        material.update({"mandate_hash": mandate.identity_hash, "task_key": packet_task_key(packet), "frozen_at": packet.frozen_at, "binding_hash": packet.binding_hash, **attempt_material})
        return catalog.register_scale_s0_frozen_packet(material)

    @staticmethod
    def record_durable_reservation(catalog: object, economics: EconomicState, *, recorded_at: str, execution_attempt_id: str | None = None, offline: bool = False) -> dict:
        material = _material(economics)
        assert isinstance(material, dict)
        return catalog.record_scale_s0_reservation_binding(material, recorded_at=recorded_at, execution_attempt_id=execution_attempt_id, offline=offline)

    @staticmethod
    def register_durable_candidate(catalog: object, candidate: Candidate) -> dict:
        if not candidate.mandate_id or not candidate.packet_id or not candidate.created_at:
            raise ScalePreflightError("candidate must bind durable mandate, packet, and creation time")
        material = _material(candidate)
        assert isinstance(material, dict)
        material.update({"task_key": f"{candidate.task_id}@{candidate.task_version}", "material_hash": candidate.binding_hash})
        return catalog.register_scale_s0_candidate(material)

    @staticmethod
    def register_durable_review_item(catalog: object, item: ReviewItem) -> dict:
        candidate = catalog.get_scale_s0_candidate(item.candidate_id)
        if candidate is None:
            raise ScalePreflightError("review candidate is absent from durable catalogue")
        material = _material(item)
        assert isinstance(material, dict)
        material["candidate_material_hash"] = candidate["material_hash"]
        return catalog.register_scale_s0_review_item(material)

    @staticmethod
    def register_durable_review_decision(catalog: object, decision: ReviewDecision, *, candidate_id: str) -> dict:
        candidate = catalog.get_scale_s0_candidate(candidate_id)
        if candidate is None:
            raise ScalePreflightError("review decision candidate is absent from durable catalogue")
        material = _material(decision)
        assert isinstance(material, dict)
        material.update({"candidate_id": candidate_id, "candidate_material_hash": candidate["material_hash"], "corrected_candidate_id": decision.corrected_candidate.candidate_id if decision.corrected_candidate else None})
        return catalog.register_scale_s0_review_decision(material)

    @staticmethod
    def _candidate_from_material(material: Mapping[str, object]) -> Candidate:
        fields = {key: material[key] for key in Candidate.__dataclass_fields__ if key in material}
        representation = fields.get("representation_policy")
        if isinstance(representation, Mapping):
            fields["representation_policy"] = RepresentationPolicy(DocumentRepresentation(str(representation["representation"])), str(representation["authorised_mode"]), bool(representation.get("materially_relevant_visual_content", False)))
        fields["routing_class"] = RoutingClass(str(fields["routing_class"]))
        fields["processing_disposition"] = ProcessingDisposition(str(fields.get("processing_disposition", ProcessingDisposition.ACQUIRED)))
        for key in ("source_ids", "lineage_ids", "evidence_locator_ids", "source_record_ids"):
            fields[key] = _tuple_material(fields.get(key))
        return Candidate(**fields)  # type: ignore[arg-type]

    def promote_durably(self, *, candidate_id: str, authorisation_id: str, persisted_at: str) -> str:
        """Resume-safe promotion: durable authority first, deterministic result second."""
        if self.catalog is None:
            raise ScalePreflightError("durable catalogue is required for promotion")
        stored = self.catalog.get_scale_s0_candidate(candidate_id)
        if stored is None:
            raise ScalePreflightError("candidate is not durably registered")
        candidate = self._candidate_from_material(stored["material"])
        if candidate.mandate_id != self.mandate.mandate_id or candidate.binding_hash != stored["material"].get("material_hash"):
            raise ScalePreflightError("candidate durable material is corrupt or substituted")
        existing = self.catalog.get_scale_s0_promotion_result(candidate_id)
        if existing is not None:
            return existing["governed_artifact_id"]
        decision_row = self.catalog.effective_scale_s0_review(candidate_id)
        task = self._task(candidate.task_id, candidate.task_version)
        deterministic = task.promotion_policy_class == "deterministic_source_native_audited" and candidate.deterministic_source_native and candidate.epistemic_basis == "source_fact" and candidate.routing_class == RoutingClass.DETERMINISTIC
        decision_id: str | None = None
        if deterministic:
            artifact_id = f"observation:{candidate.candidate_id}"
        else:
            if decision_row is None or decision_row["disposition"] != DecisionDisposition.PROMOTE.value:
                raise ScalePreflightError("only an effective durable promotion decision may promote")
            decision_id = decision_row["decision_id"]
            artifact_id = decision_row["material"].get("target_governed_artifact_id") or f"observation:{candidate.candidate_id}"
        self.authorise_promotion(candidate, decision_id=decision_id, authorisation_id=authorisation_id, governed_artifact_id=artifact_id, persisted_at=persisted_at)
        result = self.catalog.record_scale_s0_promotion_result(candidate_id=candidate_id, authorisation_id=authorisation_id, governed_artifact_id=artifact_id, persisted_at=persisted_at)
        return result["governed_artifact_id"]

    def authorise_promotion(self, candidate: Candidate, *, decision_id: str | None, authorisation_id: str, governed_artifact_id: str, persisted_at: str) -> dict:
        if self.catalog is None:
            raise ScalePreflightError("durable catalogue is required for promotion")
        task = self._task(candidate.task_id, candidate.task_version)
        if self.halts.active(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=candidate.subject_id) or self.catalog.active_scale_s0_halt(slice_id=self.mandate.slice_id, task_key=task.key, subject_id=candidate.subject_id):
            raise ScalePreflightError("hard halt prevents promotion")
        return self.catalog.authorise_scale_s0_promotion(authorisation_id=authorisation_id, candidate_id=candidate.candidate_id, decision_id=decision_id, governed_artifact_id=governed_artifact_id, authorised_at=persisted_at)
    def _bind_policies(self) -> None:
        bindings = {"routing":(self.mandate.routing_policy_id,self.mandate.routing_policy_version,self.routing.immutable_hash),"sampling":(self.mandate.sampling_policy_id,self.mandate.sampling_policy_version,None),"review":(self.mandate.review_policy_id,self.mandate.review_policy_version,None),"promotion":(self.mandate.promotion_policy_id,self.mandate.promotion_policy_version,None),"halt":(self.mandate.halt_policy_id,self.mandate.halt_policy_version,None),"reservation":(self.mandate.reservation_policy_id,None,None),"source_universe":(self.mandate.source_universe_policy_id,self.mandate.source_universe_policy_version,None),"specialist_source":(self.mandate.specialist_source_policy_id,None,None),"rights_transmission":(self.mandate.rights_transmission_policy_id,None,None)}
        for name,(policy_id,version,actual_hash) in bindings.items():
            item = self.policies.get(name)
            if item is None or item.policy_id != policy_id or version is not None and item.version != version or item.content_hash != self.mandate.policy_hashes.get(name) or actual_hash is not None and item.content_hash != actual_hash: raise ScalePreflightError("runtime policy is not the mandate-authorised immutable artifact")
        if self.mandate.policy_hashes.get("logical_task_registry") != self.registry.immutable_hash: raise ScalePreflightError("task registry substitution")
    def _task(self, task_id: str, version: str) -> TaskContract:
        task=self.registry.get(task_id,version)
        if not task.available or task_id not in self.mandate.enabled_task_ids or task_id in self.mandate.disabled_task_ids or self.registry.version != self.mandate.task_registry_version: raise ScalePreflightError("task is not authorised by frozen mandate")
        return task
    def _packet(self, request: SendRequest, task: TaskContract) -> FrozenPacket:
        packet=self.packets.get(request.packet_hash or "")
        if not request.packet_frozen or packet is None or packet.binding_hash != request.packet_hash or not packet.content_hash: raise ScalePreflightError("provider send requires a registered frozen packet")
        if (packet.task_id,packet.task_version,packet.subject_id,packet.scope_id,packet.source_ids,packet.input_profile_id,packet.output_schema_id)!=(task.task_id,task.version,request.subject_id,request.scope_id,request.source_ids,task.input_profile_id,task.output_schema_id): raise ScalePreflightError("frozen packet does not bind this exact request")
        if len(packet.source_ids)!=len(packet.source_snapshot_hashes) or packet.contract_version!=self.mandate.parent_product_contract: raise ScalePreflightError("packet provenance is incomplete")
        return packet
    def _economics(self, request: SendRequest, task: TaskContract, route: RoutingClass, packet: FrozenPacket) -> None:
        e=self.economics
        if e is None or not request.reservation_id or request.reservation_id!=e.reservation_id or not e.reservation_active or (e.reservation_mandate_id,e.reservation_slice_id,e.reservation_task_key,e.reservation_currency)!=(self.mandate.mandate_id,self.mandate.slice_id,packet_task_key(packet),self.mandate.currency_basis): raise ScalePreflightError("active durable reservation is not bound to this mandate/slice/task")
        if self.mandate.provider_call_ceiling<=e.provider_calls or Decimal(self.mandate.provider_spend_ceiling)<=e.provider_spend+e.estimated_provider_cost or e.reservation_remaining<e.estimated_provider_cost: raise ScalePreflightError("provider call or spend ceiling exhausted")
        if self.mandate.per_request_reservation_cap and e.estimated_provider_cost > Decimal(self.mandate.per_request_reservation_cap): raise ScalePreflightError("provider request exceeds reservation cap")
        if route==RoutingClass.STRONG_REASONING and Decimal(self.mandate.strong_model_spend_ceiling)<=e.strong_model_spend+e.estimated_strong_cost: raise ScalePreflightError("strong-model ceiling exhausted")
        if packet.operation_kind == LOCATOR_SEARCH_OPERATION_KIND and (e.pricing_snapshot_id != packet.pricing_snapshot_id or e.estimated_provider_cost != Decimal(packet.estimated_provider_cost)):
            raise ScalePreflightError("locator search reservation is not bound to its frozen price")
    def provider_send(self, request: SendRequest, *, triggered_escalations: Iterable[str] = (), now: datetime | None = None, allow_prepared_lifecycle: bool = False) -> TaskContract:
        if self.catalog is not None and self.execution_attempt is None:
            raise ScalePreflightError("live provider send requires a durable execution-attempt binding")
        candidate_packet = self.packets.get(request.packet_hash or "")
        if candidate_packet is not None and candidate_packet.operation_kind == LOCATOR_SEARCH_OPERATION_KIND:
            _validate_locator_search_packet(candidate_packet, self.mandate)
            task = locator_search_task_contract()
            if tuple(triggered_escalations):
                raise ScalePreflightError("locator search has no semantic escalation route")
            if task.default_routing not in self.routing.permitted:
                raise ScalePreflightError("locator search route is outside the frozen routing policy")
        else:
            task=self._task(request.task_id,request.task_version)
        if request.subject_id not in self.mandate.subject_ids or not request.scope_id: raise ScalePreflightError("request is outside frozen population or scope")
        packet=self._packet(request,task); route=self.routing.route_for(task,triggered_escalations)
        if request.route!=route or packet.routing_class!=route: raise ScalePreflightError("caller cannot choose a route")
        if self.catalog is not None:
            existing = self.catalog.get_provider_request_item(packet.provider_request_identity)
            if existing is not None and not (allow_prepared_lifecycle and existing.get("status") == "prepared") and (packet.operation_kind != LOCATOR_SEARCH_OPERATION_KIND or existing.get("status") != "prepared"):
                raise ScalePreflightError("durable provider-request identity already exists")
        if self.halts.active(slice_id=self.mandate.slice_id,task_key=task.key,subject_id=request.subject_id) or self.catalog and self.catalog.active_scale_s0_halt(slice_id=self.mandate.slice_id,task_key=task.key,subject_id=request.subject_id): raise ScalePreflightError("applicable hard halt prevents provider send")
        if packet.operation_kind != LOCATOR_SEARCH_OPERATION_KIND:
            for source_id,snapshot_hash in zip(request.source_ids,packet.source_snapshot_hashes,strict=True):
                source=self.sources.get(source_id)
                if source is None or source.source_family not in self.mandate.applicable_source_families or source.snapshot_hash!=snapshot_hash or not source.permits(task,self.mandate): raise ScalePreflightError("source is unauthorised or changed after freeze")
        if request.prior_attempt is not None and (not request.retry_permitted or request.prior_attempt.provider_request_identity!=packet.provider_request_identity or request.prior_attempt.state not in {"pre_send_failed","prepared"}): raise ScalePreflightError("retry is not ambiguity-safe")
        self._economics(request,task,route,packet)
        if self.catalog is not None and self.execution_attempt is not None and hasattr(self.catalog, "validate_scale_s0_provider_send"):
            self.catalog.validate_scale_s0_provider_send(packet_id=packet.packet_id, execution_attempt_id=self.execution_attempt.attempt_id, mandate_id=self.mandate.mandate_id, slice_id=self.mandate.slice_id, task_id=task.task_id, task_version=task.version, task_key=packet_task_key(packet), route=route.value, source_ids=request.source_ids, source_snapshot_hashes=packet.source_snapshot_hashes, input_profile_id=task.input_profile_id, output_schema_id=task.output_schema_id, reservation_id=request.reservation_id, observed_at=now or datetime.now(timezone.utc), provider_account_project=request.provider_account_project, execution_authority=request.execution_authority, operation_kind=packet.operation_kind, allow_prepared_lifecycle=allow_prepared_lifecycle)
        return task
    def review_requirement(self,candidate:Candidate,sampling:SamplingPolicy,reasons:Iterable[str])->ReviewRequirement:
        task=self._task(candidate.task_id,candidate.task_version)
        if candidate.subject_id not in self.mandate.subject_ids or candidate.claim_family!=task.family: raise ScalePreflightError("candidate is outside authorised subject or semantic family")
        if sampling.policy_id!=self.mandate.sampling_policy_id or sampling.version!=self.mandate.sampling_policy_version or sampling.immutable_hash!=self.mandate.policy_hashes.get("sampling"): raise ScalePreflightError("sampling policy substitution")
        candidate.representation_policy.validate(); deterministic=task.promotion_policy_class=="deterministic_source_native_audited" and task.default_routing==RoutingClass.DETERMINISTIC and candidate.routing_class==RoutingClass.DETERMINISTIC and candidate.deterministic_source_native and candidate.epistemic_basis=="source_fact"
        if candidate.deterministic_source_native!=deterministic: raise ScalePreflightError("deterministic status is contract- and provenance-derived")
        return sampling.requirement(candidate_id=candidate.candidate_id,task_key=task.key,reasons=reasons,deterministic_source_native=deterministic)
    def promote(self,candidate:Candidate,*,review_requirement:ReviewRequirement,review_item:ReviewItem|None,decision:ReviewDecision|None)->str:
        task=self._task(candidate.task_id,candidate.task_version)
        if not candidate.mechanically_validated or not candidate.source_ids or not candidate.source_record_ids or not candidate.evidence_locator_ids or not candidate.lineage_ids or not candidate.scope_id or not candidate.predicate or candidate.semantic_payload is None: raise ScalePreflightError("candidate lacks immutable semantic/evidence binding")
        candidate.representation_policy.validate()
        if candidate.processing_disposition in {ProcessingDisposition.PARSING_FAILED,ProcessingDisposition.PROCESSING_FAILED,ProcessingDisposition.NOT_PROCESSED,ProcessingDisposition.UNAVAILABLE}: raise ScalePreflightError("processing state cannot become substantive absence")
        if self.halts.active(slice_id=self.mandate.slice_id,task_key=task.key,subject_id=candidate.subject_id) or self.catalog and self.catalog.active_scale_s0_halt(slice_id=self.mandate.slice_id,task_key=task.key,subject_id=candidate.subject_id): raise ScalePreflightError("hard halt prevents promotion")
        if "governed_observations" not in self.mandate.allowed_outputs: raise ScalePreflightError("mandate does not authorise governed observations")
        deterministic=task.promotion_policy_class=="deterministic_source_native_audited" and candidate.deterministic_source_native and candidate.epistemic_basis=="source_fact" and candidate.routing_class==RoutingClass.DETERMINISTIC
        if deterministic: return f"observation:{candidate.candidate_id}"
        if review_requirement==ReviewRequirement.NONE or review_item is None or decision is None: raise ScalePreflightError("semantic candidate requires a completed review")
        fields=(review_item.candidate_id,review_item.candidate_binding_hash,review_item.task_id,review_item.task_version,review_item.subject_id,review_item.scope_id,review_item.evidence_source_ids,review_item.lineage_ids)
        expected=(candidate.candidate_id,candidate.binding_hash,candidate.task_id,candidate.task_version,candidate.subject_id,candidate.scope_id,candidate.source_ids,candidate.lineage_ids)
        if review_item.status!=ReviewStatus.DECIDED or fields!=expected: raise ScalePreflightError("review item is stale or not bound to candidate")
        if decision.review_id!=review_item.review_id or decision.candidate_binding_hash!=candidate.binding_hash or not decision.reviewer_or_policy or not decision.rationale or not decision.evidence_basis: raise ScalePreflightError("decision is not bound and auditable")
        if decision.disposition==DecisionDisposition.NARROW_OR_CORRECT:
            if decision.corrected_candidate is None or decision.corrected_candidate.binding_hash==candidate.binding_hash or decision.corrected_candidate.candidate_id==candidate.candidate_id or not decision.target_governed_artifact_id: raise ScalePreflightError("narrow/correct requires an immutable replacement candidate")
            return decision.target_governed_artifact_id
        if decision.disposition!=DecisionDisposition.PROMOTE: raise ScalePreflightError("review disposition does not permit promotion")
        return decision.target_governed_artifact_id or f"observation:{candidate.candidate_id}"


ACTIVE_OWNERSHIP: Mapping[str,tuple[int,...]]={"identity_regulatory":(1,),"purpose_cause":(2,),"program_service":(3,),"activity_source_reported":(4,),"population_geography":(5,),"participation":(6,),"direct_service":(7,),"fundraising":(8,),"governance":(9,),"workforce":(10,),"scale_capability":(11,),"relationships":(12,),"finance_source_native":(13,),"funding_dependency":(14,),"ethos_commitments":(15,),"conduct_adverse":(16,),"notable_history":(17,),"outcomes_evaluation":(18,),"assessed_taxonomy":(19,),"discovery_signals":(19,),"evidence_coverage":(20,)}
def default_s0_registry()->LogicalTaskRegistry:
    special={"identity_regulatory":RoutingClass.DETERMINISTIC,"finance_source_native":RoutingClass.DETERMINISTIC,"discovery_signals":RoutingClass.DETERMINISTIC,"conduct_adverse":RoutingClass.HUMAN_DECISION,"funding_dependency":RoutingClass.STRONG_REASONING,"outcomes_evaluation":RoutingClass.STRONG_REASONING}; contracts=[]
    for family,sections in ACTIVE_OWNERSHIP.items():
        route=special.get(family,RoutingClass.LOW_COST_THEN_ESCALATE); deterministic=route==RoutingClass.DETERMINISTIC
        contracts.append(TaskContract(f"urn:charitygraph:scale-s0:{family}","1.0",family,sections,f"profile:{family}:1",f"urn:charitygraph:builder:schema:{family}:1.0",f"validation:{family}:1","source_native" if deterministic else "semantic_candidate",route,frozenset() if deterministic else frozenset(ESCALATION_PRIORITY),() if deterministic else (RoutingClass.STRONG_REASONING,),"deterministic_source_native_audited" if deterministic else "review_required",family in {"direct_service","conduct_adverse","funding_dependency"},family in {"program_service","activity_source_reported","population_geography","participation","governance","workforce","scale_capability","relationships","ethos_commitments"}))
    return LogicalTaskRegistry("scale-s0-logical-registry-2",tuple(contracts))

__all__=[name for name in globals() if not name.startswith("_")]
