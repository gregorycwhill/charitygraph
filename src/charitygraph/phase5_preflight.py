"""Provider-free Phase 5 Top-100 planning contracts and preflight.

This module describes work; it does not acquire evidence, create governed
knowledge, create runtime tasks, or call a model provider.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from charitygraph.contracts import canonical_sha256, deterministic_id
from charitygraph.identity_bootstrap import identity_map_hash


COHORT_HASH = "704d105c9b8b9dda05dba1ac8285f5f01ba92a1b22775a8d92c8236ddcf09e00"
IDENTITY_MAP_HASH = "55dc192a4d226fc3769f8408d5fdf6467f11710b9687f8f72c3f2a0ba10024aa"
BUILD_ID = "phase5-top100-factory-preflight-v1"
BUILD_VERSION = "1"
SOURCE_FAMILIES = (
    "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
    "annual_report", "wikipedia_wikimedia", "pfra",
)
SECTIONS = {
    1: "Identity & regulatory status", 2: "Purpose, mandate & cause",
    3: "Programs, services, projects & campaigns", 4: "Populations & beneficiaries",
    5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
    8: "Finance & resource flows", 9: "Governance", 10: "Workforce",
    11: "Capability, capacity, access & availability", 12: "Relationships & ecosystem",
    13: "Memberships, schemes, registrations & accreditations", 14: "Ethos & institutional identity",
    15: "Positions, commitments & implementation", 16: "Conduct, adverse matters & compliance",
    17: "Notable context & institutional history", 18: "Outcomes, impact & evaluation",
    19: "Classifications & semantic lenses", 20: "Evidence, coverage, freshness & corrections",
}
CoverageState = Literal[
    "acquired_available", "attempted_unavailable", "access_failed", "parsing_failed",
    "representation_not_ready", "stale", "not_applicable", "not_attempted", "unknown",
    "provenance_unresolved",
]
MethodClass = Literal[
    "deterministic", "constrained_semantic", "stronger_semantic_judgement",
    "human_reviewed", "deferred",
]
PlanningState = Literal[
    "governed_knowledge_reusable", "reusable_validated_semantic_result",
    "source_ready_deterministic_required", "source_ready_constrained_required",
    "stronger_semantic_required", "human_risk_review_required", "source_missing_not_acquired",
    "representation_not_ready", "policy_unresolved", "processing_failure_known",
    "deferred_phase6", "blocked_execution_ambiguity", "not_applicable", "unknown_unresolved",
]


class StrictPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimFamilyPolicy(StrictPlanModel):
    family_id: str
    label: str
    version: str
    north_star_sections: tuple[int, ...]
    domain_profile: str
    applicability_state: str
    applicability_rule_ref: str
    expected_source_family_refs: tuple[str, ...]
    source_authority_policy_ref: str
    method_class: MethodClass
    automation_eligibility: str
    human_risk_review_trigger: str
    freshness_policy_ref: str
    evidence_sufficiency_policy_ref: str
    conflict_handling_policy_ref: str
    privacy_publication_policy_ref: str
    correction_policy_ref: str
    phase5_treatment_depth: str
    maturity: Literal["implemented", "reality_tested", "phase5_planning_accepted", "high_risk_depth_deferred", "unresolved"] = "implemented"
    default_publication_state: Literal["private_review_only", "withheld"] = "private_review_only"

    @model_validator(mode="after")
    def _sections(self) -> "ClaimFamilyPolicy":
        if not self.north_star_sections or any(section not in SECTIONS for section in self.north_star_sections):
            raise ValueError("claim families require valid North Star section references")
        if self.family_id in {f"section-{section}" for section in self.north_star_sections}:
            raise ValueError("a North Star section is not itself a claim family")
        return self


class SourceCoverageItem(StrictPlanModel):
    subject_id: str
    abn: str
    source_family: str
    state: CoverageState
    source_record_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def resolve_governed_source_material(*, bundle: dict[str, Any], source_family: str, failures: dict[tuple[str, str], str]) -> dict[str, Any]:
    """Resolve only material whose frozen provenance is mechanically usable.

    `available_source_families` records historical presence, not a reusable
    byte-level source.  It cannot be promoted to `acquired_available` without
    an exact evidence record carrying a content hash and retained material.
    """
    historical_name = {"acnc_register": "acnc-profile", "acnc_ais_bundle": "acnc-profile-ais", "ato_abr_dgr": "abr", "official_website": "official-homepage"}.get(source_family)
    abn = str(bundle["abn"])
    if historical_name is None:
        return {"state": "not_attempted", "records": (), "reason": "no_prior_material_contract"}
    records = tuple(record for record in bundle.get("evidence_records", ()) if record.get("source_family") == historical_name)
    exact = tuple(record for record in records if record.get("content_hash") and (isinstance(record.get("text"), str) or record.get("raw_path")))
    if len(exact) == 1:
        return {"state": "acquired_available", "records": exact, "reason": "exact_frozen_evidence_material"}
    if len(exact) > 1:
        return {"state": "provenance_unresolved", "records": exact, "reason": "multiple_exact_materials_require_selection_policy"}
    if historical_name in set(bundle.get("available_source_families", ())):
        return {"state": "provenance_unresolved", "records": (), "reason": "historical_presence_without_recoverable_material"}
    if (abn, historical_name) in failures:
        return {"state": "attempted_unavailable", "records": (), "reason": failures[(abn, historical_name)]}
    return {"state": "not_attempted", "records": (), "reason": "no_governed_attempt_or_material"}


class SemanticReuseItem(StrictPlanModel):
    subject_id: str
    abn: str
    rank: int
    scope: str
    original_task_profile: str
    evidence_identity: str
    provider_model_run_identity: str
    validation_state: str
    governed_candidate_state: str
    lineage: tuple[str, ...]
    exact_reuse_status: Literal[
        "exact_reusable_validated_candidate", "exact_reusable_prior_result",
        "structural_valid_grounding_failed", "structurally_invalid",
        "blocked_ambiguous_transmission", "no_prior_result",
    ]
    result_hash: str | None = None


class PlanningUnit(StrictPlanModel):
    subject_id: str
    abn: str
    rank: int
    family_id: str
    north_star_sections: tuple[int, ...]
    applicability: str
    state: PlanningState
    method_class: MethodClass
    source_families: tuple[str, ...]
    evidence_identity: str | None = None
    rationale: str


class PlannedLogicalTask(StrictPlanModel):
    logical_task_id: str
    build_id: str
    subject_id: str
    scope_id: str | None
    claim_family_id: str
    task_profile: str
    task_profile_version: str
    schema_version: str
    evidence_corpus_hash: str
    prompt_policy_version: str
    route_policy_version: str
    difficulty: Literal["deterministic", "lower_cost_constrained_semantic", "stronger_semantic_judgement", "human_risk_review"]
    physical_bundle_opportunity: str | None = None


def _policy_refs(prefix: str) -> dict[str, str]:
    return {
        "applicability_rule_ref": f"{prefix}:applicability:v1",
        "source_authority_policy_ref": f"{prefix}:authority:v1",
        "freshness_policy_ref": "source-freshness-policy:v1",
        "evidence_sufficiency_policy_ref": "evidence-sufficiency-policy:v1",
        "conflict_handling_policy_ref": "knowledge-conflict-policy:v1",
        "privacy_publication_policy_ref": "private-review-publication-policy:v1",
        "correction_policy_ref": "correction-and-contestability-policy:v1",
    }


def implemented_claim_families() -> tuple[ClaimFamilyPolicy, ...]:
    specs = [
        ("identity-regulatory-status-v1", "Identity and regulatory status", (1,), "identity_regulatory", "deterministic", ("acnc_register", "ato_abr_dgr"), "reality_tested", "Exact authority-scoped identifiers and source-native regulatory fields."),
        ("source-coverage-provenance-v1", "Evidence, coverage, freshness and corrections", (20,), "source_evidence_coverage", "deterministic", SOURCE_FAMILIES, "implemented", "Coverage and provenance are explicit operational knowledge, not card completeness."),
        ("program-service-discovery-v2", "Programs, services, projects and campaigns", (3,), "programs_services", "constrained_semantic", ("acnc_ais_bundle", "official_website"), "reality_tested", "Existing program/service candidate contract and bounded semantic runner establish this boundary."),
        ("taxonomy-assignment-v1", "Classification and semantic-lens assignment", (19,), "classification_lenses", "constrained_semantic", ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr"), "implemented", "Taxonomy assignments are independent, evidence-bound outputs rather than arbitrary card fields."),
        ("direct-service-access-v1", "Capability, access and availability", (11,), "direct_service", "constrained_semantic", ("acnc_ais_bundle", "official_website"), "reality_tested", "Direct-service proposition and explicit coverage states are implemented contracts."),
        ("typed-relationship-role-v1", "Relationships and ecosystem roles", (12,), "relationships", "stronger_semantic_judgement", ("acnc_ais_bundle", "official_website", "pfra"), "reality_tested", "Typed directed role statements require scope, time, evidence and boundary judgement."),
    ]
    result = []
    for family_id, label, sections, profile, method, sources, maturity, reason in specs:
        refs = _policy_refs(family_id)
        result.append(ClaimFamilyPolicy(family_id=family_id, label=label, version="1", north_star_sections=sections, domain_profile=profile, applicability_state="rule_defined", method_class=method, expected_source_family_refs=sources, automation_eligibility="bounded_contract_only", human_risk_review_trigger="conflict_or_high_consequence", phase5_treatment_depth=reason, maturity=maturity, **refs))
    return tuple(result)


def proposed_claim_families() -> tuple[ClaimFamilyPolicy, ...]:
    specs = [
        ("purpose-cause-mandate-proposed-v1", "Purpose, mandate and cause", (2,), "purpose_cause", "constrained_semantic", ("acnc_ais_bundle", "official_website"), "Purpose, cause and mandate need a reviewed boundary distinct from classification."),
        ("population-beneficiary-proposed-v1", "Populations and beneficiaries", (4,), "populations_beneficiaries", "constrained_semantic", ("acnc_ais_bundle", "official_website"), "Beneficiary populations are distinct from activities and outcomes."),
        ("geography-footprint-proposed-v1", "Operating geography and footprint", (5,), "geography", "constrained_semantic", ("acnc_register", "acnc_ais_bundle", "official_website"), "Place, operating area and program location have separate scope semantics."),
        ("participation-engagement-proposed-v1", "Participation and engagement", (6,), "participation", "constrained_semantic", ("official_website", "acnc_ais_bundle"), "Participation is a distinct user question and is not implied by fundraising."),
        ("fundraising-practice-proposed-v1", "Fundraising practice and resource mobilisation", (7,), "fundraising", "stronger_semantic_judgement", ("acnc_ais_bundle", "official_website", "pfra"), "Fundraising practice, expenditure and actors require independent source-role boundaries."),
        ("finance-resource-flow-proposed-v1", "Finance and resource flows", (8,), "finance", "deterministic", ("acnc_ais_bundle", "ato_abr_dgr"), "Source-faithful financial periods and flows are not yet a Builder claim-family contract."),
        ("governance-proposed-v1", "Governance and responsible persons", (9,), "governance", "constrained_semantic", ("acnc_ais_bundle", "annual_report"), "Governance structure and responsible-person claims need scope and privacy rules."),
        ("workforce-proposed-v1", "Workforce", (10,), "workforce", "constrained_semantic", ("acnc_ais_bundle", "annual_report"), "Workforce structure is a Phase-5 planning family; sensitive depth remains review-controlled."),
        ("ethos-institutional-identity-proposed-v1", "Ethos and institutional identity", (14,), "ethos", "human_reviewed", ("acnc_ais_bundle", "official_website", "annual_report"), "High-consequence identity and religious/philosophical claims require consequence-aware review."),
        ("positions-commitments-implementation-proposed-v1", "Positions, commitments and implementation", (15,), "positions_commitments", "human_reviewed", ("official_website", "annual_report"), "Statement, commitment, implementation and observed practice are separate stages."),
        ("conduct-compliance-proposed-v1", "Conduct, adverse matters and compliance", (16,), "conduct_compliance", "human_reviewed", ("acnc_ais_bundle", "official_website"), "Formal findings, allegations, responses and correction states require specialist controls."),
        ("notable-context-history-proposed-v1", "Notable context and institutional history", (17,), "institutional_history", "constrained_semantic", ("wikipedia_wikimedia", "official_website", "annual_report"), "Context must not become unsupported reputation or significance scoring."),
        ("outcomes-evaluation-proposed-v1", "Outcomes, impact and evaluation", (18,), "outcomes_evaluation", "human_reviewed", ("annual_report", "official_website"), "Evaluation design, attribution and limitations require deeper Phase 6 treatment."),
        ("scheme-participation-v1", "Scheme participation, registrations and accreditations", (13,), "scheme_participation", "constrained_semantic", ("ato_abr_dgr", "pfra", "acnc_ais_bundle"), "Scheme/body participation is distinct from identity, taxonomy and generic relationships."),
    ]
    deferred = {"ethos-institutional-identity-proposed-v1", "positions-commitments-implementation-proposed-v1", "conduct-compliance-proposed-v1", "outcomes-evaluation-proposed-v1"}
    result = []
    for family_id, label, sections, profile, method, sources, reason in specs:
        refs = _policy_refs(family_id)
        depth = "Phase-6 depth deferred; reuse existing governed material only." if family_id in deferred else reason
        result.append(ClaimFamilyPolicy(family_id=family_id, label=label, version="1", north_star_sections=sections, domain_profile=profile, method_class=method, expected_source_family_refs=sources, applicability_state="eligible_for_attempt", automation_eligibility="planning_only_bounded_contract", human_risk_review_trigger="human_or_policy_review_when_triggered", phase5_treatment_depth=depth, maturity="high_risk_depth_deferred" if family_id in deferred else "phase5_planning_accepted", **refs))
    return tuple(result)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _subject_map(catalog_path: Path, cohort: list[dict[str, Any]], identity_report: Path) -> dict[str, str]:
    checkpoint = _read_json(identity_report)
    if identity_map_hash(checkpoint["rows"]) != IDENTITY_MAP_HASH or checkpoint["identity_map_hash"] != IDENTITY_MAP_HASH:
        raise RuntimeError("P5-A0 identity-map checkpoint hash changed")
    expected = {row["abn"]: row["subject_id"] for row in checkpoint["rows"]}
    if set(expected) != {row["abn"] for row in cohort} or len(set(expected.values())) != 100:
        raise RuntimeError("identity checkpoint does not cover exactly 100 unique subjects")
    conn = sqlite3.connect(f"file:{catalog_path}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" for _ in expected)
        rows = conn.execute(f"SELECT e.identifier_value, e.subject_id, e.status, e.issuing_authority FROM external_identifiers e WHERE e.scheme='ABN' AND e.identifier_value IN ({placeholders})", tuple(expected)).fetchall()
    finally:
        conn.close()
    if len(rows) != 100 or len({row[0] for row in rows}) != 100 or len({row[1] for row in rows}) != 100 or any(row[2] != "active" or row[3] != "Australian Business Register" for row in rows):
        raise RuntimeError("current governed catalogue failed the 100/100 identity checkpoint")
    if {row[0]: row[1] for row in rows} != expected:
        raise RuntimeError("current governed catalogue differs from the completed identity checkpoint")
    return expected


def _evidence_identity(bundle: dict[str, Any]) -> str:
    return canonical_sha256({"abn": bundle["abn"], "evidence_ids": bundle.get("available_evidence_ids", []), "evidence_hashes": [item.get("content_hash") for item in bundle.get("evidence_records", [])]})


def classify_reuse_status(abn: str, result: dict[str, Any] | None) -> str:
    if abn == "48321126727":
        return "blocked_ambiguous_transmission"
    if result is None:
        return "no_prior_result"
    structural = bool(result.get("structural_output_valid"))
    grounded = bool(result.get("quote_grounding_valid"))
    if structural and grounded:
        if result.get("action") in {"exact_prior_reuse", "reused_exact_terra_A"}:
            return "exact_reusable_prior_result"
        return "exact_reusable_validated_candidate"
    if structural:
        return "structural_valid_grounding_failed"
    return "structurally_invalid"


def build_source_inventory(cohort: list[dict[str, Any]], subject_ids: dict[str, str], bundles: list[dict[str, Any]], source_records: dict[str, list[str]]) -> list[SourceCoverageItem]:
    bundle_by_abn = {str(item["abn"]): item for item in bundles}
    failures = {(str(item["abn"]), item["source_family"]): item.get("reason", "historical attempt failed") for item in _read_json(Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829\evidence-bundles.json")).get("failures", [])}
    rows: list[SourceCoverageItem] = []
    for member in sorted(cohort, key=lambda item: item["donation_rank_2024_public"]):
        abn = str(member["abn"]); bundle = bundle_by_abn[abn]
        available = set(bundle.get("available_source_families", []))
        for family in SOURCE_FAMILIES:
            resolved = resolve_governed_source_material(bundle=bundle, source_family=family, failures=failures)
            state: CoverageState = resolved["state"]
            records = resolved["records"]
            ids = tuple(source_records.get(abn, ())) if family == "acnc_register" else ()
            evidence_ids = tuple(item["evidence_id"] for item in records)
            evidence_hashes = tuple(item["content_hash"] for item in records)
            notes = (resolved["reason"],)
            rows.append(SourceCoverageItem(subject_id=subject_ids[abn], abn=abn, source_family=family, state=state, source_record_ids=ids, evidence_ids=evidence_ids, evidence_hashes=evidence_hashes, notes=notes))
    return rows


def build_reuse_inventory(cohort: list[dict[str, Any]], subject_ids: dict[str, str], manifest: dict[str, Any], results: dict[str, Any], closeout: dict[str, Any], bundles: list[dict[str, Any]]) -> list[SemanticReuseItem]:
    charities = {str(item["abn"]): item for item in manifest["charities"]}
    result_by_abn = {str(item["abn"]): item for item in results["results"]}
    bundle_by_abn = {str(item["abn"]): item for item in bundles}
    rows = []
    for member in sorted(cohort, key=lambda item: item["donation_rank_2024_public"]):
        abn = str(member["abn"]); item = charities[abn]; result = result_by_abn.get(abn); bundle = bundle_by_abn[abn]
        status = classify_reuse_status(abn, result)
        structural = bool(result and result.get("structural_output_valid"))
        grounded = bool(result and result.get("quote_grounding_valid"))
        validation_state = "structural_valid_quote_valid" if structural and grounded else "structural_valid_quote_invalid" if structural else "indeterminate_no_response" if result and result.get("status") == "indeterminate_no_response_artifact" else "structural_invalid" if result else "no_result"
        candidate_state = "candidate_requires_downstream_governance" if structural and grounded else "candidate_requires_grounding_review" if structural else "none"
        rows.append(SemanticReuseItem(subject_id=subject_ids[abn], abn=abn, rank=member["donation_rank_2024_public"], scope="organisation/program-service-discovery", original_task_profile=f"{manifest['prompt_version']}:{manifest['schema_version']}", evidence_identity=_evidence_identity(bundle), provider_model_run_identity=f"{manifest['model']}:{manifest['reasoning_effort']}:{manifest['builder_commit']}:{manifest['cohort_manifest_sha256']}", validation_state=validation_state, governed_candidate_state=candidate_state, lineage=("top100-cohort-manifest", "evidence-bundles", "semantic-run-manifest", "call-results-partial"), exact_reuse_status=status, result_hash=result.get("output_text_sha256") if result else None))
    return rows


def _unit(subject: dict[str, Any], family: ClaimFamilyPolicy, state: PlanningState, rationale: str, evidence_identity: str | None = None) -> PlanningUnit:
    return PlanningUnit(subject_id=subject["subject_id"], abn=subject["abn"], rank=subject["rank"], family_id=family.family_id, north_star_sections=family.north_star_sections, applicability="applicable" if state != "not_applicable" else "not_applicable", state=state, method_class=family.method_class, source_families=family.expected_source_family_refs, evidence_identity=evidence_identity, rationale=rationale)


def build_planning_matrix(cohort: list[dict[str, Any]], subject_ids: dict[str, str], policies: tuple[ClaimFamilyPolicy, ...], reuse: list[SemanticReuseItem], source_inventory: list[SourceCoverageItem]) -> list[PlanningUnit]:
    reuse_by_abn = {row.abn: row for row in reuse}; coverage = {(row.abn, row.source_family): row for row in source_inventory}; units = []
    for member in sorted(cohort, key=lambda item: item["donation_rank_2024_public"]):
        subject = {"abn": str(member["abn"]), "rank": member["donation_rank_2024_public"], "subject_id": subject_ids[str(member["abn"])]}; abn = subject["abn"]; evidence = reuse_by_abn[abn].evidence_identity
        for family in policies:
            if family.family_id == "identity-regulatory-status-v1": state, reason = "governed_knowledge_reusable", "identity checkpoint is satisfied"
            elif family.family_id == "source-coverage-provenance-v1": state, reason = "governed_knowledge_reusable", "coverage inventory is the planned deterministic provenance view"
            elif family.family_id == "program-service-discovery-v2":
                if abn == "48321126727": state, reason = "blocked_execution_ambiguity", "historical rank-62 transmission/billing ambiguity blocks only colliding program-task identity"
                elif reuse_by_abn[abn].exact_reuse_status in {"exact_reusable_validated_candidate", "exact_reusable_prior_result"}: state, reason = "reusable_validated_semantic_result", "exact prior program result is reusable as a candidate, not canonical knowledge"
                elif reuse_by_abn[abn].exact_reuse_status in {"structural_valid_grounding_failed", "structurally_invalid"}: state, reason = "processing_failure_known", "historical program result is not reusable because validation did not establish a grounded, structurally valid output"
                else: state, reason = "source_ready_constrained_required", "no exact prior result; frozen evidence is available"
            elif family.maturity == "high_risk_depth_deferred": state, reason = "deferred_phase6", "accepted policy explicitly defers new semantic depth to Phase 6; existing governed material remains reusable"
            else:
                available = [coverage.get((abn, source)) for source in family.expected_source_family_refs]
                has_source = any(item is not None and item.state == "acquired_available" for item in available)
                if not has_source:
                    state, reason = "source_missing_not_acquired", "accepted Phase-5 family is eligible, but every expected source family remains unacquired for this subject"
                elif family.method_class == "deterministic":
                    state, reason = "source_ready_deterministic_required", "accepted source-native Phase-5 policy supports deterministic processing"
                elif family.method_class == "stronger_semantic_judgement":
                    state, reason = "stronger_semantic_required", "accepted source-ready family routes to stronger semantic judgement"
                else:
                    state, reason = "source_ready_constrained_required", "accepted Phase-5 planning family is eligible and frozen source evidence is available"
            units.append(_unit(subject, family, state, reason, evidence))
    return units


def build_planned_tasks(units: list[PlanningUnit], route_policy: str = "phase4-hybrid-bundle-by-difficulty-v1") -> list[PlannedLogicalTask]:
    tasks = []
    for unit in units:
        if unit.state not in {"source_ready_constrained_required", "stronger_semantic_required", "source_ready_deterministic_required"}:
            continue
        difficulty = "lower_cost_constrained_semantic" if unit.method_class == "constrained_semantic" else "stronger_semantic_judgement" if unit.method_class == "stronger_semantic_judgement" else "deterministic"
        profile = {"program-service-discovery-v2": "program_service_discovery", "taxonomy-assignment-v1": "taxonomy_assignment", "direct-service-access-v1": "direct_service_semantics", "typed-relationship-role-v1": "relationship_role_extraction"}.get(unit.family_id, unit.family_id)
        schema = f"urn:charitygraph:phase5:planned:{profile}:v1"
        identity = {"build_id": BUILD_ID, "subject_id": unit.subject_id, "scope_id": None, "claim_family_id": unit.family_id, "task_profile": profile, "task_profile_version": "1", "schema_version": schema, "evidence_corpus_hash": unit.evidence_identity, "prompt_policy_version": f"{unit.family_id}:prompt-policy:v1", "route_policy_version": route_policy}
        task_id = deterministic_id("semtask:", identity)
        bundle_key = f"bundle-opportunity:{unit.subject_id}:{difficulty}" if difficulty == "lower_cost_constrained_semantic" else None
        tasks.append(PlannedLogicalTask(logical_task_id=task_id, **identity, difficulty=difficulty, physical_bundle_opportunity=bundle_key))
    return tasks


def preflight_interruption_safety() -> dict[str, Any]:
    return {"provider_calls": 0, "source_acquisition": 0, "semantic_executions": 0, "planned_state": "representable", "transmission_boundary_state": "representable", "provider_receipt_state": "representable", "usage_cost_state": "representable", "validation_states": ["structural_validation", "evidence_grounding_validation"], "ambiguous_transmission_state": "representable", "ambiguous_resend_default": "blocked", "rank62_collision_scope": "only_matching_historical_program-task-identity", "unrelated_claim_family_tasks": "not_globally_blocked"}


def summarize(items: list[PlanningUnit]) -> dict[str, int]:
    return dict(sorted(Counter(item.state for item in items).items()))


def workload_summary(items: list[PlanningUnit]) -> dict[str, int]:
    return dict(sorted(Counter(item.method_class for item in items if item.state not in {"governed_knowledge_reusable", "reusable_validated_semantic_result", "not_applicable"}).items()))


def baseline_readiness(coverage: list[SourceCoverageItem]) -> dict[str, Any]:
    gaps: dict[str, dict[str, int]] = {}
    for family in SOURCE_FAMILIES:
        states = Counter(item.state for item in coverage if item.source_family == family)
        gaps[family] = dict(sorted(states.items()))
    material_gaps = {family: states for family, states in gaps.items() if any(state != "acquired_available" for state in states)}
    return {
        "ready_for_semantic_execution": not material_gaps,
        "recommendation": "SEMANTIC_EXECUTION" if not material_gaps else "BASELINE_ACQUISITION/FREEZE",
        "gaps": material_gaps,
        "reason": "baseline source-universe obligations remain materially unattempted or unavailable" if material_gaps else "all planned baseline source families are available",
    }
