"""First-class Phase-5 semantic contracts.

This module is deliberately provider-free.  It separates semantic authority
from transport serialization: a provider adapter may serialize only a
production-bound contract, never a task-profile name alone.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from .contracts.discovery import discovery_schema_v2
from .native_discovery_executor import DISCOVERY_PROMPT_V2, PROMPT_TEMPLATE_VERSION_V2


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class SemanticContract:
    contract_id: str
    contract_version: str
    task_profile: str
    task_profile_version: str
    claim_families: tuple[str, ...]
    prompt_template: str
    prompt_id: str
    output_schema: dict[str, Any] | None
    schema_id: str
    schema_version: str
    evidence_policy: dict[str, Any]
    grounding_requirements: tuple[str, ...]
    adapter_id: str
    adapter_version: str
    route_class: str
    reasoning_policy: str
    authority_state: str
    publication_boundary: str
    planner_prompt_policy_version: str
    planner_schema_version: str
    schema_factory_id: str | None = None
    schema_factory: Callable[[tuple[str, ...]], dict[str, Any]] | None = None
    source_refs: tuple[str, ...] = ()
    unresolved_design_questions: tuple[str, ...] = ()

    @property
    def prompt_sha256(self) -> str:
        return sha256_text(self.prompt_template)

    @property
    def output_schema_sha256(self) -> str | None:
        return None if self.output_schema is None else sha256_json(self.output_schema)

    @property
    def executable(self) -> bool:
        return self.authority_state in {"production_adopted", "production_bound"}

    def schema_for_evidence(self, evidence_ids: tuple[str, ...] = ()) -> dict[str, Any]:
        if self.schema_factory is not None:
            return self.schema_factory(evidence_ids)
        if self.output_schema is None:
            raise ValueError(f"contract {self.contract_id} has no output schema")
        return self.output_schema

    def schema_hash_for_evidence(self, evidence_ids: tuple[str, ...] = ()) -> str:
        return sha256_json(self.schema_for_evidence(evidence_ids))

    def assert_complete(self) -> None:
        if not self.prompt_template.strip():
            raise ValueError(f"contract {self.contract_id} has no immutable prompt content")
        if self.output_schema is None and self.schema_factory is None:
            raise ValueError(f"contract {self.contract_id} has no output schema or schema generator")
        if not self.adapter_id.strip() or not self.adapter_version.strip():
            raise ValueError(f"contract {self.contract_id} has no deterministic adapter")

    def identity_payload(self, evidence_ids: tuple[str, ...] = ()) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "task_profile": self.task_profile,
            "task_profile_version": self.task_profile_version,
            "prompt_sha256": self.prompt_sha256,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "output_schema_sha256": self.schema_hash_for_evidence(evidence_ids),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
        }

    def identity_hash(self, evidence_ids: tuple[str, ...] = ()) -> str:
        return sha256_json(self.identity_payload(evidence_ids))

    def as_review_row(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "task_profile": self.task_profile,
            "task_profile_version": self.task_profile_version,
            "claim_families": list(self.claim_families),
            "authority_state": self.authority_state,
            "prompt_id": self.prompt_id,
            "prompt_template": self.prompt_template,
            "prompt_sha256": self.prompt_sha256,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "schema": self.output_schema,
            "schema_factory_id": self.schema_factory_id,
            "schema_hash_without_evidence": self.output_schema_sha256,
            "evidence_policy": self.evidence_policy,
            "grounding_requirements": list(self.grounding_requirements),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "route_class": self.route_class,
            "reasoning_policy": self.reasoning_policy,
            "publication_boundary": self.publication_boundary,
            "planner_prompt_policy_version": self.planner_prompt_policy_version,
            "planner_schema_version": self.planner_schema_version,
            "source_refs": list(self.source_refs),
            "unresolved_design_questions": list(self.unresolved_design_questions),
            "executable": self.executable,
        }


def _closed(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required or list(properties)}


def _evidence_items() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string", "minLength": 1}}


def _draft_schema(family: str) -> dict[str, Any]:
    evidence = _evidence_items()
    if family == "taxonomy-assignment-v1":
        selection = _closed({"concept_id": {"type": "string"}, "role": {"enum": ["primary", "secondary"]}, "evidence_refs": evidence, "rationale": {"type": "string"}, "confidence": {"enum": ["low", "medium", "high", "unknown"]}})
        return _closed({"outcome": {"enum": ["resolved", "supported", "insufficient_evidence", "ambiguous", "not_applicable"]}, "selections": {"type": "array", "items": selection}, "rationale": {"type": "string"}})
    if family == "typed-relationship-role-v1":
        rel = _closed({"source_scope_id": {"type": "string"}, "target_scope_id": {"type": "string"}, "role": {"enum": ["operator", "deliverer", "funder", "sponsor", "partner", "auspice", "network_context", "unknown"]}, "direction": {"enum": ["source_to_target", "target_to_source", "bidirectional", "uncertain"]}, "evidence_refs": evidence, "observation_time": {"type": ["object", "null"]}, "unresolved_endpoint": {"type": "boolean"}})
        return _closed({"relationships": {"type": "array", "items": rel}, "outcome": {"enum": ["resolved", "supported", "insufficient_evidence", "ambiguous", "not_applicable"]}})
    if family == "fundraising-practice-proposed-v1":
        observation = _closed({"practice": {"type": "string"}, "source_role": {"enum": ["regulator_accounting_fact", "charity_first_party_claim", "independently_observed_fact"]}, "status": {"enum": ["reported", "observed", "not_found", "unknown"]}, "evidence_refs": evidence, "qualification": {"type": "string"}})
        return _closed({"observations": {"type": "array", "items": observation}, "outcome": {"enum": ["resolved", "supported", "insufficient_evidence", "ambiguous", "not_applicable"]}})
    shapes = {
        "purpose-cause-mandate-proposed-v1": ("claim_type", ["purpose", "cause", "mandate"]),
        "population-beneficiary-proposed-v1": ("population_relation", ["beneficiary", "participant", "community", "unknown"]),
        "geography-footprint-proposed-v1": ("geography_role", ["operating_area", "service_location", "registered_location", "unknown"]),
        "participation-engagement-proposed-v1": ("participation_type", ["opportunity", "measure", "engagement", "unknown"]),
        "governance-proposed-v1": ("governance_role", ["responsible_person", "board", "committee", "policy", "unknown"]),
        "workforce-proposed-v1": ("workforce_dimension", ["employees", "volunteers", "workforce_structure", "unknown"]),
        "notable-context-history-proposed-v1": ("context_type", ["historical_event", "institutional_context", "public_context", "unknown"]),
        "scheme-participation-v1": ("participation_state", ["member", "participant", "accredited", "registered", "unknown"]),
    }
    field, values = shapes[family]
    item = _closed({field: {"enum": values}, "statement": {"type": "string"}, "evidence_refs": evidence, "qualification": {"type": "string"}})
    return _closed({"observations": {"type": "array", "items": item}, "outcome": {"enum": ["resolved", "supported", "insufficient_evidence", "ambiguous", "not_applicable"]}})


def _draft_prompt(family: str, label: str) -> str:
    return f"""You are performing the review-only CharityGraph Phase-5 {label} task.\nUse only the supplied governed evidence and the supplied allowed vocabulary. Do not use outside knowledge, infer unsupported outcomes, invent identifiers, or resolve ambiguous identity. Every proposed observation must cite one or more supplied evidence IDs. Preserve insufficient evidence, uncertainty, absence, and source-role distinctions. Return only the strict JSON object matching the task-specific schema.\n\nTASK PROFILE: {family}\nSUBJECT: {{subject_id}}\nALLOWED CONCEPTS OR VOCABULARY: {{allowed_vocabulary}}\nGOVERNED EVIDENCE: {{evidence}}"""


def _draft(family: str, profile: str, label: str, route: str, reasoning: str, source: str) -> SemanticContract:
    schema = _draft_schema(family)
    return SemanticContract(
        contract_id=f"urn:charitygraph:phase5:semantic-contract:{family}", contract_version="1.0-draft",
        task_profile=profile, task_profile_version="1", claim_families=(family,),
        prompt_template=_draft_prompt(family, label), prompt_id=f"{family}:prompt:v1-draft",
        output_schema=schema, schema_id=f"urn:charitygraph:phase5:wire:{profile}:v1-draft", schema_version="1.0-draft",
        evidence_policy={"mode": "frozen_governed_evidence_only", "outside_knowledge": False, "allowed_reference_field": "evidence_refs"},
        grounding_requirements=("every observation cites supplied evidence_refs", "unsupported outcomes remain unresolved"),
        adapter_id=f"phase5.draft_adapter.{profile}", adapter_version="1.0-draft",
        route_class=route, reasoning_policy=reasoning, authority_state="draft_for_review",
        publication_boundary="no provider execution or governed promotion until semantic review", source_refs=(source,),
        planner_prompt_policy_version=f"{family}:prompt-policy:v1",
        planner_schema_version=f"urn:charitygraph:phase5:planned:{profile}:v1",
        unresolved_design_questions=("Sol/human semantic approval required before promotion",),
    )


def _production_discovery() -> SemanticContract:
    return SemanticContract(
        contract_id="urn:charitygraph:builder:semantic-contract:program-service-discovery-v2", contract_version="2.0",
        # Phase-5 keeps its planner profile version at 1, but this explicit
        # binding selects the existing production discovery V2 machinery.
        task_profile="program_service_discovery", task_profile_version="1", claim_families=("program-service-discovery-v2",),
        prompt_template=DISCOVERY_PROMPT_V2, prompt_id="program_service_discovery", output_schema=None,
        schema_id="urn:charitygraph:builder:schema:program-service-discovery-output:2.0", schema_version="2.0-evidence-bound",
        evidence_policy={"mode": "task_ordered_frozen_evidence", "outside_knowledge": False, "allowed_reference_field": "evidence_ids"},
        grounding_requirements=("every proposal cites supplied evidence IDs", "preserve operational status uncertainty"),
        adapter_id="charitygraph.native_discovery_executor._parse_discovery_output", adapter_version="2.0",
        route_class="lower_cost_constrained_semantic", reasoning_policy="low", authority_state="production_bound",
        publication_boundary="validated candidate only; downstream governance required", schema_factory_id="charitygraph.contracts.discovery.discovery_schema_v2",
        planner_prompt_policy_version="program-service-discovery-v2:prompt-policy:v1",
        planner_schema_version="urn:charitygraph:phase5:planned:program_service_discovery:v1",
        schema_factory=discovery_schema_v2, source_refs=("src/charitygraph/contracts/discovery.py", "src/charitygraph/native_discovery_executor.py"),
    )


def _production_direct_service() -> SemanticContract:
    from .contracts.direct_service_wire import DirectServiceWireOutput
    from .strict_schema import strictify_schema
    prompt = """You are performing the bounded CharityGraph Phase 3 direct-service semantics task.
Return only the strict JSON object matching the supplied schema. Use ONLY the supplied evidence.
The target subject is {subject_id}. Emit sparse propositions only where the evidence supports them.
Use one of the task-visible scope IDs below exactly; never invent IDs or bind by fuzzy label matching.
Keep participation opportunity distinct from participation measure; service offer distinct from
availability/capacity; eligibility/access distinct from scheme membership/accreditation. Do not make
quality, effectiveness, compliance or outcome claims. Coverage states such as source_silent,
not_found and unknown must remain distinct. Cite supplied packet locators in every supported or
asserted-absence proposition. Relationships are directed and must preserve operator, deliverer,
funder, sponsor, partner, auspice and network_context as distinct roles. Do not inherit or propagate
claims from parent, network, partner or funder scopes. Cite evidence for each relationship.

TASK-VISIBLE SCOPES:
{scope_text}

PACKET EVIDENCE:
{evidence}
"""
    return SemanticContract(
        contract_id="urn:charitygraph:builder:semantic-contract:direct-service-v1", contract_version="1.0",
        task_profile="direct_service_semantics", task_profile_version="1", claim_families=("direct-service-access-v1",),
        prompt_template=prompt, prompt_id="direct-service-real-phase3:prompt:v1", output_schema=strictify_schema(DirectServiceWireOutput.model_json_schema()),
        schema_id="urn:charitygraph:builder:schema:direct-service-wire-output:1.0", schema_version="1.0",
        evidence_policy={"mode": "frozen_packet_locators", "outside_knowledge": False, "allowed_reference_field": "evidence.locator"},
        grounding_requirements=("evidence locator must be in frozen packet", "scope IDs must be task-visible", "supported states require evidence"),
        adapter_id="charitygraph.contracts.direct_service_wire.wire_to_domain", adapter_version="1.0",
        route_class="lower_cost_constrained_semantic", reasoning_policy="low", authority_state="production_bound",
        publication_boundary="domain validation and downstream governance required", source_refs=("src/charitygraph/contracts/direct_service_wire.py", "src/charitygraph/contracts/direct_service.py", "scripts/run_direct_service_real_phase3.py"),
        planner_prompt_policy_version="direct-service-access-v1:prompt-policy:v1",
        planner_schema_version="urn:charitygraph:phase5:planned:direct_service_semantics:v1",
    )


def build_registry() -> tuple[SemanticContract, ...]:
    contracts = [
        _production_discovery(), _production_direct_service(),
        _draft("taxonomy-assignment-v1", "taxonomy_assignment", "taxonomy assignment", "lower_cost_constrained_semantic", "low", "src/charitygraph/contracts/semantic.py"),
        _draft("typed-relationship-role-v1", "relationship_role_extraction", "typed relationship-role extraction", "stronger_semantic_judgement", "high", "src/charitygraph/contracts/knowledge.py"),
        _draft("fundraising-practice-proposed-v1", "fundraising-practice-proposed-v1", "source-faithful fundraising practice", "stronger_semantic_judgement", "high", "src/charitygraph/phase5_preflight.py"),
    ]
    for family, profile, label in (
        ("purpose-cause-mandate-proposed-v1", "purpose_cause_mandate", "purpose, cause and mandate"),
        ("population-beneficiary-proposed-v1", "population_beneficiary", "population and beneficiary"),
        ("geography-footprint-proposed-v1", "geography_footprint", "geography and footprint"),
        ("participation-engagement-proposed-v1", "participation_engagement", "participation and engagement"),
        ("governance-proposed-v1", "governance", "governance"),
        ("workforce-proposed-v1", "workforce", "workforce"),
        ("notable-context-history-proposed-v1", "notable_context_history", "notable context and history"),
        ("scheme-participation-v1", "scheme_participation", "scheme participation"),
    ):
        contracts.append(_draft(family, family, label, "lower_cost_constrained_semantic", "low", "src/charitygraph/phase5_preflight.py"))
    return tuple(contracts)


REGISTRY = build_registry()
_BY_FAMILY = {family: contract for contract in REGISTRY for family in contract.claim_families}
_BY_PROFILE = {(contract.task_profile, contract.task_profile_version): contract for contract in REGISTRY}


def resolve_contract(task: dict[str, Any]) -> SemanticContract:
    contract = _BY_PROFILE.get((task["task_profile"], str(task.get("task_profile_version", "1"))))
    if contract is None:
        raise ValueError(f"no semantic contract for profile/version: {task.get('task_profile')}/{task.get('task_profile_version')}")
    if task.get("claim_family_id") not in contract.claim_families:
        raise ValueError(f"contract/family mismatch for {task.get('logical_task_id')}")
    if task.get("prompt_policy_version") != contract.planner_prompt_policy_version:
        raise ValueError(f"prompt-policy binding mismatch for {task.get('logical_task_id')}")
    if task.get("schema_version") != contract.planner_schema_version:
        raise ValueError(f"schema-version binding mismatch for {task.get('logical_task_id')}")
    return contract


def registry_rows() -> list[dict[str, Any]]:
    return [contract.as_review_row() for contract in REGISTRY]


def executable_contract_for(task: dict[str, Any]) -> SemanticContract:
    contract = resolve_contract(task)
    contract.assert_complete()
    if not contract.executable:
        raise PermissionError(f"semantic contract is not production-bound: {contract.contract_id}")
    return contract


def validate_evidence_refs(refs: list[str] | tuple[str, ...], allowed_evidence_ids: set[str]) -> None:
    if not set(refs).issubset(allowed_evidence_ids):
        raise ValueError("semantic output references evidence outside the supplied governed evidence")


def validate_taxonomy_output(output: dict[str, Any], *, allowed_concept_ids: set[str], allowed_evidence_ids: set[str]) -> None:
    for selection in output.get("selections", []):
        if selection.get("concept_id") not in allowed_concept_ids:
            raise ValueError("taxonomy output invented a concept outside the supplied universe")
        validate_evidence_refs(selection.get("evidence_refs", []), allowed_evidence_ids)


def validate_relationship_output(output: dict[str, Any], *, allowed_scope_ids: set[str], allowed_evidence_ids: set[str]) -> None:
    for relationship in output.get("relationships", []):
        if relationship.get("source_scope_id") not in allowed_scope_ids or relationship.get("target_scope_id") not in allowed_scope_ids:
            if not relationship.get("unresolved_endpoint"):
                raise ValueError("relationship output invented an endpoint")
        validate_evidence_refs(relationship.get("evidence_refs", []), allowed_evidence_ids)


def provider_request_identity(task: dict[str, Any], contract: SemanticContract, *, model: str, service_tier: str, evidence_ids: tuple[str, ...] = ()) -> str:
    payload = {"logical_task_id": task["logical_task_id"], "model": model, "service_tier": service_tier, "evidence_corpus_hash": task["evidence_corpus_hash"], "semantic_contract_hash": contract.identity_hash(evidence_ids)}
    return "requestitem:" + sha256_json(payload)


__all__ = ["SemanticContract", "REGISTRY", "build_registry", "resolve_contract", "executable_contract_for", "registry_rows", "provider_request_identity", "validate_evidence_refs", "validate_taxonomy_output", "validate_relationship_output", "sha256_text", "sha256_json", "PROMPT_TEMPLATE_VERSION_V2"]
