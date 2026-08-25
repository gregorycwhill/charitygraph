from __future__ import annotations

"""Evidence-bound, proposed scoped benchmark v2 for Reality Slice 1.

This module contains review metadata only.  It never embeds source bodies or
model output; evidence bindings are independently built from PR #11 source
outcome metadata.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping

from .phase1 import deterministic_subject_id

BenchmarkVersion = Literal["2.0"]
Disposition = Literal["required", "acceptable", "acceptable_secondary", "prohibited", "unresolved"]

BENCHMARK_VERSION: BenchmarkVersion = "2.0"
REVIEW_STATUS = "proposed"
PROVENANCE = "human-directed-design-machine-source-assisted-proposed"
ACTIVITY_VOCABULARY_VERSION = "charitygraph-activity-2026-dev-v2"
ACTIVITY_CONCEPT_IDS = (
    "activity.direct_service_delivery", "activity.education_support_delivery",
    "activity.advocacy", "activity.research_evaluation", "activity.grantmaking",
    "activity.community_engagement", "activity.capacity_building", "activity.policy_change",
    "activity.housing_provision", "activity.health_clinical_service_delivery",
    "activity.workforce_training", "activity.community_development",
)
NON_ACTIVITY_FACETS = frozenset({"population", "purpose", "fundraising_method", "campaign", "delivery_channel", "donor_mechanism"})
CLASSIE_RIGHTS_GATE = {
    "version": "4.2",
    "status": "blocked_pending_rights_review",
    "subjects_url": "https://www.communitydirectors.com.au/classie",
    "population_url": "https://www.communitydirectors.com.au/classie",
    "material_discoverable": True,
    "native_subject_population_files_exist": True,
    "native_material_committed": False,
    "synthetic_ids_created": False,
    "blocker": "lawful private processing, reuse and redistribution permission is unresolved",
}

ABNS = {
    "smith_family": "28000030179", "red_cross": "50169561394", "acf": "20077830347",
    "conservation": "22007498482", "mission": "15000002522", "world_vision": "28004778081",
    "fred_hollows": "46070556642",
}
NAMES = {
    "smith_family": "The Smith Family", "red_cross": "Australian Red Cross Society",
    "acf": "Australian Communities Foundation Limited", "conservation": "Australian Conservation Foundation Incorporated",
    "mission": "Mission Australia", "world_vision": "World Vision Australia", "fred_hollows": "The Fred Hollows Foundation",
}
SUBJECT_IDS = {key: deterministic_subject_id(identifier_scheme="abn", identifier_value=abn) for key, abn in ABNS.items()}
HOLDOUT_ABNS = frozenset(("67649417658", "45146631843", "15101252171"))
HOLDOUT_NAMES = frozenset(("landscape recovery foundation ltd.", "indigenous literacy foundation ltd.", "life without barriers"))


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_locator_id: str
    source_record_id: str
    member_abn: str
    source_family: str
    source_locator: str
    content_hash: str
    selector: str
    supported_propositions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["supported_propositions"] = list(self.supported_propositions)
        return row


# Safe metadata copied from the latest private run9 source-outcomes inventory.
# The registry is independent of benchmark cases and contains no source bodies.
_EVIDENCE_METADATA = (
    {"member_abn":"28000030179","family":"acnc","source_record_id":"srcrec:4c6b1cf0478bfb09c5248e982d3ba830377dc4984681f126696d4d69ed03112e","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=28000030179","hash":"5754a3314a6be6a3fae85902c20aae8fb25d4df9d0cc6376adc17ecb0fd055c8","selector":"structured_field:display_name","propositions":["organisation_identity"]},
    {"member_abn":"28000030179","family":"official-website","source_record_id":"srcrec:a7f1589c2890b7bcba6134e76438be2502897ad3b33989dca20de5df7938f4d6","url":"https://www.thesmithfamily.com.au/programs","hash":"2a0f3d95d9e19b79dd5711bf26ac57e108dbf930e93224a83467b6bcb5f9fffd","selector":"text:Learning for Life;Literacy programs;Numeracy programs","propositions":["smith_learning_for_life","smith_program_domains","smith_sdg4"]},
    {"member_abn":"50169561394","family":"acnc","source_record_id":"srcrec:652ac6ee1dd850a78bdc97cefc5a7123a64d13856bbb3e1f2657017030bbfcd8","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=50169561394","hash":"b07e3f21ad53fb2789301d55cf6d2da3b43e5b6fc30561a7cbc69a6b695050f0","selector":"structured_field:display_name","propositions":["organisation_identity"]},
    {"member_abn":"50169561394","family":"official-website","source_record_id":"srcrec:a69080c0e0dcde793aae15d728da2d3b1cd75075a5e0015fd5ae4fb0043a4682","url":"https://www.redcross.org.au/about/what-we-do/","hash":"8deaee2436e6f4fed462572d9f0a7e8acb6c3aa7e2e6bd4f1d7879255a6d7c36","selector":"heading:Australian Red Cross Lifeblood;heading:Community activities and programs","propositions":["redcross_lifeblood_division","redcross_humanitarian_service","redcross_sdg3"]},
    {"member_abn":"20077830347","family":"acnc","source_record_id":"srcrec:662df54f07f918035ae3a3ebeec5be7e442ee4f4d77fd0fd3b1997a7a8f07135","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=20077830347","hash":"419b19d2297851f9b8c78aef0edcf2c6ff0c84879dd227c9df195f0ec18dc737","selector":"structured_field:display_name","propositions":["organisation_identity"]},
    {"member_abn":"20077830347","family":"official-website","source_record_id":"srcrec:486706d6577bdf9f85229b66a1cccbac2898bd713d24469d02e963d3f9ed5131","url":"https://communityfoundation.org.au/philanthropic-services/","hash":"9642000757f521cd9221622d4aa6441cbc43e76ea5b1da9d86e26276ada52a39","selector":"text:Corporate Fund;heading:Philanthropic Services","propositions":["acf_philanthropic_services","acf_fund_boundary"]},
    {"member_abn":"22007498482","family":"acnc","source_record_id":"srcrec:7adf694673e8cf471dc703c1f7359dbc4506ab91d87df87bbf0727a6d36c85d1","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=22007498482","hash":"bad1d991f9322dbf4ea28b4236a0797c71766510bf667a6be2601069723bb55a","selector":"structured_field:display_name","propositions":["organisation_identity"]},
    {"member_abn":"22007498482","family":"official-website","source_record_id":"srcrec:27dbb6e6de02cfb63f5c1862c88ef0df436ab7bf094aff27587761090b493671","url":"https://www.acf.org.au/our-work","hash":"72ae3653a7acbd1f66beec05970ec1bd030bb35a4cc8cfb59e048cb58e63c7be","selector":"heading:Save our big backyard;heading:Corporate campaigns;heading:Environmental investigations","propositions":["acf_campaign","acf_advocacy","acf_policy_change","acf_sdg13","acf_sdg15"]},
    {"member_abn":"15000002522","family":"acnc","source_record_id":"srcrec:0a20a4a2251fa19e34c948c1fe07abf55533ddfae945cfef2bab0c94dee205af","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=15000002522","hash":"41ad91ea63e074c5d85cfbaaa368772a91d0bbd472c8dc774fa70277dfb8ccea","selector":"structured_field:display_name","propositions":["organisation_identity","identity_only"]},
    {"member_abn":"28004778081","family":"acnc","source_record_id":"srcrec:805f0dc884bfc229ef31c66225a21980fa917a5703a0c3d4cf5bc5f31dde96a4","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=28004778081","hash":"4250ef9627230fb2525801f8e508f756bfdc250946c65e085a3f894fc4a92c51","selector":"structured_field:display_name","propositions":["organisation_identity","identity_only"]},
    {"member_abn":"28004778081","family":"official-website","source_record_id":"srcrec:af91b017da310fbd11b06e25290167dc8e93830d2a5fbcac448c0c6e80975b0a","url":"https://www.worldvision.com.au/about-child-sponsorship","hash":"bf244653e878e289a43ce90333fbb4fb13771a4f217add5195a94fa27d757812","selector":"text:child sponsorship;text:healthcare, education, water, sanitation and food","propositions":["worldvision_child_sponsorship","worldvision_activity_domains","worldvision_sdg4"]},
    {"member_abn":"46070556642","family":"acnc","source_record_id":"srcrec:919df45fbbc01fa5bc8738fa055c186afaa0cafee0492c4a89a7ce11cb8296b0","url":"https://www.acnc.gov.au/charity/charities/charity-details?charity=46070556642","hash":"6d01ae40390c30ebd64e6068fe33623b4150abd9e4160e25d56eb0df2669baf4","selector":"structured_field:display_name","propositions":["organisation_identity"]},
    {"member_abn":"46070556642","family":"official-website","source_record_id":"srcrec:d73bdb88fd4e2ac0b5ea416473b75ab1560915cc01c07c2dea061f0019157966","url":"https://www.hollows.org/what-we-do/","hash":"57103b0ceae5fd23f38293b2965e55bf02cd51ba4f0951c6a3c4972e57f54855","selector":"heading:Ending Avoidable Blindness;heading:Research and Technology;heading:Advocacy;heading:Training;heading:Indigenous Australia","propositions":["fred_eye_health","fred_research","fred_advocacy","fred_training","fred_indigenous_scope"]},
)


def build_evidence_registry(metadata: Iterable[Mapping[str, object]] | None = None) -> dict[str, EvidenceRecord]:
    """Build an evidence registry from source-outcome metadata, independently of cases."""
    rows = metadata if metadata is not None else _EVIDENCE_METADATA
    registry: dict[str, EvidenceRecord] = {}
    for row in rows:
        source_record_id = str(row.get("source_record_id", ""))
        content_hash = str(row.get("content_hash", row.get("hash", "")))
        if not source_record_id or len(content_hash) != 64:
            continue
        locator_id = str(row.get("evidence_locator_id", f"evidence_locator:{source_record_id}"))
        propositions = row.get("supported_propositions", row.get("propositions", ()))
        registry[locator_id] = EvidenceRecord(locator_id, source_record_id, str(row["member_abn"]), str(row.get("source_family", row.get("family", ""))), str(row.get("source_locator", row.get("url", ""))), content_hash, str(row.get("selector", "source-record")), tuple(str(x) for x in propositions))
    return registry


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    subject_id: str
    subject_name: str
    benchmark_scope_ref: str | None
    expected_subject_kind: str
    durability_expectation: str
    parent_subject_id: str | None
    target_ref: str | None
    relationship_type: str | None
    scope_kind: str
    task_family: str
    expected_disposition: Disposition
    concept_or_relation: str
    proposition_key: str
    evidence_locator_ids: tuple[str, ...]
    rationale: str
    correct_interpretation: str | None = None
    review_status: str = REVIEW_STATUS
    provenance: str = PROVENANCE
    benchmark_version: BenchmarkVersion = BENCHMARK_VERSION

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["evidence_locator_ids"] = list(self.evidence_locator_ids)
        return row


def _ev(key: str, proposition: str) -> str:
    for row in _EVIDENCE_METADATA:
        if row["member_abn"] == ABNS[key] and proposition in row["propositions"]:
            return f"evidence_locator:{row['source_record_id']}"
    raise KeyError(f"no governed evidence for {key}/{proposition}")


def _case(key: str, ref: str, kind: str, durability: str, task: str, disposition: Disposition, concept: str, proposition: str, rationale: str, *, relation: str | None = None, target: str | None = None, parent: str | None = None, evidence: bool = True, correct: str | None = None) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=f"sbv2:{key}:{ref}:{concept}", subject_id=SUBJECT_IDS[key], subject_name=NAMES[key],
        benchmark_scope_ref=(f"benchmark_scope_ref:{key}:{ref}" if kind != "organisation" else None), expected_subject_kind=kind,
        durability_expectation=durability, parent_subject_id=parent, target_ref=target,
        relationship_type=relation, scope_kind=kind, task_family=task + "_v2",
        expected_disposition=disposition, concept_or_relation=concept, proposition_key=proposition,
        evidence_locator_ids=(_ev(key, proposition),) if evidence else (), rationale=rationale,
        correct_interpretation=correct,
    )


def build_benchmark_cases() -> tuple[BenchmarkCase, ...]:
    rows: list[BenchmarkCase] = []
    rows += [
        _case("smith_family", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "The Smith Family", "organisation_identity", "governed organisation identity"),
        _case("smith_family", "learning-for-life", "program", "durable_subject", "entity_decomposition", "required", "Learning for Life", "smith_learning_for_life", "actual named program on the official programs page", relation="has_program", target="benchmark_candidate_ref:smith:learning-for-life"),
        _case("smith_family", "literacy-programs", "service_domain", "semantic_domain", "entity_decomposition", "acceptable", "Literacy programs", "smith_program_domains", "source names a program domain; no durable SubjectRecord is asserted", evidence=True),
        _case("smith_family", "numeracy-programs", "service_domain", "semantic_domain", "entity_decomposition", "acceptable_secondary", "Numeracy programs", "smith_program_domains", "source names a program domain; no durable SubjectRecord is asserted", evidence=True),
        _case("smith_family", "education-support", "activity", "semantic_domain", "operational_activity", "required", "activity.education_support_delivery", "smith_program_domains", "Learning for Life and the named literacy/numeracy programs establish education-support delivery"),
        _case("smith_family", "learning-for-life-sdg4", "sdg", "semantic_domain", "sdg_alignment", "required", "sdg:4", "smith_sdg4", "SDG 4 is scoped to the evidenced Learning for Life education-support scope, not mechanically to every organisation claim"),
        _case("red_cross", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "Australian Red Cross Society", "organisation_identity", "governed organisation identity"),
        _case("red_cross", "lifeblood", "division", "organisational_scope", "relationship", "required", "Lifeblood", "redcross_lifeblood_division", "official page names Lifeblood as an operating division", relation="has_division", target="benchmark_candidate_ref:red-cross:lifeblood"),
        _case("red_cross", "humanitarian-services", "service_domain", "semantic_domain", "entity_decomposition", "acceptable", "humanitarian and community services", "redcross_humanitarian_service", "official page supports separately scoped service domains"),
        _case("red_cross", "humanitarian-service-activity", "activity", "semantic_domain", "operational_activity", "required", "activity.direct_service_delivery", "redcross_humanitarian_service", "humanitarian and community service scope supports direct service delivery"),
        _case("red_cross", "lifeblood-sdg3", "sdg", "semantic_domain", "sdg_alignment", "required", "sdg:3", "redcross_sdg3", "SDG 3 is scoped specifically to Lifeblood, not asserted for all Red Cross activity"),
        _case("red_cross", "lifeblood-as-program", "program", "benchmark_candidate_ref", "entity_decomposition", "prohibited", "Lifeblood as ordinary program", "redcross_lifeblood_division", "same evidence establishes division; ontology rule prohibits program promotion", correct="Lifeblood is a division/operating scope", evidence=True),
        _case("acf", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "Australian Communities Foundation", "organisation_identity", "governed organisation identity"),
        _case("acf", "philanthropic-services", "service_domain", "semantic_domain", "entity_decomposition", "acceptable", "Philanthropic Services", "acf_philanthropic_services", "official service page names a service line, not a durable program"),
        _case("acf", "grantmaking", "activity", "semantic_domain", "operational_activity", "required", "activity.grantmaking", "acf_philanthropic_services", "grantmaking is an activity, not an invented umbrella program"),
        _case("acf", "corporate-fund", "candidate", "benchmark_candidate_ref", "scope_decomposition", "unresolved", "Corporate Fund durable boundary", "acf_fund_boundary", "the service page names Corporate Fund but does not establish whether it is a durable subject, vehicle or service construct"),
        _case("conservation", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "Australian Conservation Foundation", "organisation_identity", "governed organisation identity"),
        _case("conservation", "save-our-big-backyard", "campaign", "benchmark_candidate_ref", "entity_decomposition", "acceptable", "Save our big backyard", "acf_campaign", "actual named campaign/initiative; not a program"),
        _case("conservation", "campaign-as-program", "program", "benchmark_candidate_ref", "entity_decomposition", "prohibited", "campaign promoted to program", "acf_campaign", "campaign evidence does not establish a durable program", correct="retain campaign type", evidence=True),
        _case("conservation", "advocacy", "activity", "semantic_domain", "operational_activity", "required", "activity.advocacy", "acf_advocacy", "official work page supports advocacy"),
        _case("conservation", "policy-change", "activity", "semantic_domain", "operational_activity", "acceptable", "activity.policy_change", "acf_policy_change", "official work page supports policy/systems action"),
        _case("conservation", "sdg15", "sdg", "semantic_domain", "sdg_alignment", "required", "sdg:15", "acf_sdg15", "the environmental campaign/investigation evidence supports a scoped Life on Land alignment"),
        _case("conservation", "sdg13", "sdg", "semantic_domain", "sdg_alignment", "acceptable_secondary", "sdg:13", "acf_sdg13", "the environmental campaign/investigation evidence supports a secondary Climate Action alignment"),
        _case("mission", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "Mission Australia", "organisation_identity", "governed organisation identity"),
        _case("mission", "program-service-decomposition", "coverage_gap", "benchmark_coverage", "scope_decomposition", "unresolved", "Mission Australia program/service decomposition", "mission_service_decomposition_unavailable", "bounded official-site attempt was blocked and acquired evidence establishes identity only; no specific service family is asserted; attempted homepage: https://www.missionaustralia.com.au", evidence=False),
        _case("world_vision", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "World Vision Australia", "organisation_identity", "governed organisation identity"),
        _case("world_vision", "child-sponsorship", "mechanism", "semantic_domain", "mechanism_decomposition", "required", "child sponsorship", "worldvision_child_sponsorship", "official page describes child sponsorship as donor engagement", relation="has_engagement_mechanism", target="benchmark_candidate_ref:world-vision:child-sponsorship"),
        _case("world_vision", "sponsorship-as-activity", "activity", "benchmark_candidate_ref", "operational_activity", "prohibited", "activity.community_engagement", "worldvision_child_sponsorship", "same evidence establishes the mechanism; it is not an operational activity", correct="child sponsorship is a fundraising/engagement mechanism", evidence=True),
        _case("world_vision", "community-development", "activity", "semantic_domain", "operational_activity", "acceptable", "activity.community_development", "worldvision_activity_domains", "source describes work in sponsorship communities; no durable program is asserted"),
        _case("world_vision", "education", "activity", "semantic_domain", "operational_activity", "acceptable_secondary", "activity.education_support_delivery", "worldvision_activity_domains", "source names education as a work domain, not a named durable program"),
        _case("world_vision", "health", "activity", "semantic_domain", "operational_activity", "acceptable_secondary", "activity.health_clinical_service_delivery", "worldvision_activity_domains", "source names healthcare as a work domain, not a named durable program"),
        _case("world_vision", "community-development-sdg4", "sdg", "semantic_domain", "sdg_alignment", "acceptable", "sdg:4", "worldvision_sdg4", "education is scoped to the evidenced community work domain, not to the donor mechanism"),
        _case("fred_hollows", "organisation", "organisation", "durable_subject", "entity_decomposition", "required", "The Fred Hollows Foundation", "organisation_identity", "governed organisation identity"),
        _case("fred_hollows", "eye-health", "activity", "semantic_domain", "operational_activity", "required", "activity.health_clinical_service_delivery", "fred_eye_health", "Ending Avoidable Blindness and eye-care evidence require clinical health activity"),
        _case("fred_hollows", "training", "activity", "semantic_domain", "operational_activity", "acceptable", "activity.workforce_training", "fred_training", "official page names Training"),
        _case("fred_hollows", "capacity", "activity", "semantic_domain", "operational_activity", "acceptable_secondary", "activity.capacity_building", "fred_training", "training supports a capacity-building interpretation where evidence warrants it"),
        _case("fred_hollows", "advocacy", "activity", "semantic_domain", "operational_activity", "acceptable", "activity.advocacy", "fred_advocacy", "official page names Advocacy"),
        _case("fred_hollows", "research", "activity", "semantic_domain", "operational_activity", "acceptable_secondary", "activity.research_evaluation", "fred_research", "official page names Research and Technology"),
        _case("fred_hollows", "research-only", "activity", "benchmark_candidate_ref", "operational_activity", "prohibited", "activity.research_evaluation", "fred_eye_health", "clinical evidence demonstrates why research-only is incomplete", correct="retain clinical health plus other supported activities", evidence=True),
        _case("fred_hollows", "indigenous-australia", "portfolio_scope", "organisational_scope", "scope_decomposition", "required", "Indigenous Australia scope", "fred_indigenous_scope", "official page names Indigenous Australia separately", relation="has_operating_scope", target="benchmark_candidate_ref:fred:indigenous-australia"),
        _case("fred_hollows", "sdg3", "sdg", "semantic_domain", "sdg_alignment", "required", "sdg:3", "fred_eye_health", "health alignment is evidence-bound"),
    ]
    return tuple(rows)


@dataclass(frozen=True)
class ScopedBenchmarkV2:
    cases: tuple[BenchmarkCase, ...]
    benchmark_version: BenchmarkVersion = BENCHMARK_VERSION
    status: str = REVIEW_STATUS
    activity_vocabulary_version: str = ACTIVITY_VOCABULARY_VERSION
    classie: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.classie is None:
            object.__setattr__(self, "classie", CLASSIE_RIGHTS_GATE)

    def validate(self, evidence_registry: Mapping[str, EvidenceRecord] | None = None) -> None:
        registry = evidence_registry or build_evidence_registry()
        if self.status != REVIEW_STATUS or self.benchmark_version != BENCHMARK_VERSION:
            raise ValueError("benchmark must remain proposed v2.0")
        ids: set[str] = set()
        for case in self.cases:
            if case.case_id in ids:
                raise ValueError(f"duplicate case: {case.case_id}")
            ids.add(case.case_id)
            if case.subject_id.split(":")[-1] in HOLDOUT_ABNS or case.subject_name.casefold() in HOLDOUT_NAMES:
                raise ValueError("holdout material cannot enter benchmark")
            if case.concept_or_relation.startswith("activity.") and case.concept_or_relation not in ACTIVITY_CONCEPT_IDS:
                raise ValueError(f"unknown activity concept: {case.concept_or_relation}")
            if case.expected_subject_kind == "activity" and not case.concept_or_relation.startswith("activity."):
                raise ValueError(f"activity case is not a governed concept ID: {case.case_id}")
            if case.expected_disposition != "unresolved" and not case.evidence_locator_ids:
                raise ValueError(f"evidence required: {case.case_id}")
            subject_abn = next((abn for key, abn in ABNS.items() if SUBJECT_IDS[key] == case.subject_id), None)
            for locator_id in case.evidence_locator_ids:
                record = registry.get(locator_id)
                if record is None:
                    raise ValueError(f"unknown evidence locator: {case.case_id}")
                if not locator_id.endswith(record.source_record_id):
                    raise ValueError(f"evidence locator binding mismatch: {case.case_id}")
                if record.member_abn != subject_abn:
                    raise ValueError(f"evidence subject mismatch: {case.case_id}")
                if case.proposition_key not in record.supported_propositions:
                    raise ValueError(f"evidence does not support proposition: {case.case_id}")
            if case.expected_subject_kind != "organisation" and case.benchmark_scope_ref is None:
                raise ValueError(f"non-organisation case needs benchmark candidate/scope ref: {case.case_id}")
        if set(ACTIVITY_CONCEPT_IDS) & NON_ACTIVITY_FACETS:
            raise ValueError("non-activity facet leaked into activity vocabulary")

    def to_dict(self, evidence_registry: Mapping[str, EvidenceRecord] | None = None) -> dict[str, object]:
        registry = evidence_registry or build_evidence_registry()
        return {"benchmark_version": self.benchmark_version, "status": self.status, "provenance": PROVENANCE, "activity_vocabulary": {"version": self.activity_vocabulary_version, "concept_ids": list(ACTIVITY_CONCEPT_IDS)}, "classie": dict(self.classie), "evidence_registry": [record.to_dict() for record in registry.values()], "cases": [case.to_dict() for case in self.cases], "completeness": benchmark_completeness(self)}


def benchmark_completeness(benchmark: ScopedBenchmarkV2 | None = None) -> dict[str, object]:
    """Report deterministic benchmark coverage before any paid execution."""
    benchmark = benchmark or ScopedBenchmarkV2(build_benchmark_cases())
    cases = benchmark.cases
    development_subjects = set(SUBJECT_IDS.values())
    identity_subjects = {c.subject_id for c in cases if c.expected_subject_kind == "organisation" and c.expected_disposition == "required"}
    durable_program_subjects = {c.subject_id for c in cases if c.expected_subject_kind in {"program", "service"} and c.durability_expectation == "durable_subject" and c.expected_disposition != "prohibited"}
    activity_subjects = {c.subject_id for c in cases if c.expected_subject_kind == "activity" and c.expected_disposition in {"required", "acceptable", "acceptable_secondary"} and c.concept_or_relation in ACTIVITY_CONCEPT_IDS}
    sdg_subjects = {c.subject_id for c in cases if c.expected_subject_kind == "sdg" and c.expected_disposition in {"required", "acceptable", "acceptable_secondary"} and c.evidence_locator_ids}
    scope_cases = [c for c in cases if c.task_family in {"scope_decomposition_v2", "relationship_v2"}]
    unresolved_cases = [c for c in cases if c.expected_disposition == "unresolved"]
    accepted_cases = [c for c in cases if c.expected_disposition not in {"unresolved", "prohibited"}]
    program_adequate = len(durable_program_subjects) >= 2
    result = {
        "identity_evaluable": development_subjects <= identity_subjects,
        "program_service_recall_precision_evaluable": program_adequate,
        "program_benchmark_adequacy": "adequate" if program_adequate else "insufficient",
        "scope_accuracy_evaluable": bool(scope_cases),
        "operational_activity_evaluable": len(activity_subjects) >= 6,
        "operational_activity_denominator": len(activity_subjects),
        "operational_activity_subject_ids": sorted(activity_subjects),
        "sdg_evaluable": len(sdg_subjects) >= 5,
        "sdg_denominator": len(sdg_subjects),
        "sdg_subject_ids": sorted(sdg_subjects),
        "classie_rights_disabled_path_evaluable": benchmark.classie.get("status") == "blocked_pending_rights_review" and benchmark.classie.get("native_material_committed") is False,
        "classie_semantic_assignment_evaluation": "blocked_until_rights_permit",
        "abstention_insufficient_evidence_evaluable": bool(unresolved_cases),
        "provenance_lineage_evaluable": all(c.evidence_locator_ids for c in accepted_cases),
        "economics_replay_evaluable": True,
        "blocked_task_families": ([] if program_adequate else ["program_service"]),
    }
    result["paid_execution_allowed"] = not result["blocked_task_families"]
    return result


check_benchmark_completeness = benchmark_completeness

def build_scoped_benchmark_v2(evidence_registry: Mapping[str, EvidenceRecord] | None = None) -> ScopedBenchmarkV2:
    registry = evidence_registry or build_evidence_registry()
    benchmark = ScopedBenchmarkV2(build_benchmark_cases())
    benchmark.validate(registry)
    return benchmark


def write_machine_readable_manifest(path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_scoped_benchmark_v2().to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def write_private_review_packet(runtime_root: str | Path) -> Path:
    benchmark = build_scoped_benchmark_v2()
    registry = build_evidence_registry()
    destination = Path(runtime_root).resolve() / "reality-slice1-scoped-benchmark-v2" / "review" / "scoped-benchmark-v2-review.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Reality Slice 1 ? Scoped Benchmark v2", "", "Status: proposed (human approval required)", "", "No paid calls or holdout material were used.", ""]
    for name in NAMES.values():
        lines += [f"## {name}", ""]
        for case in (c for c in benchmark.cases if c.subject_name == name):
            refs = []
            for locator_id in case.evidence_locator_ids:
                record = registry[locator_id]
                refs.append(f"{record.source_locator} [{record.selector}]")
            lines.append(f"- `{case.expected_subject_kind}` / `{case.durability_expectation}` ? **{case.concept_or_relation}** ? {case.expected_disposition}; relation: {case.relationship_type or 'none'}; evidence: {'; '.join(refs) or '(none)'}; {case.rationale}")
        lines.append("")
    lines += ["## CLASSIE", "", "Authoritative 4.2 Subject/Population material is discoverable and exists, but lawful private processing/reuse/redistribution permission is unresolved. Native material is not committed.", ""]
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def assert_not_holdout(subject_name: str | None = None, abn: str | None = None) -> None:
    if abn and "".join(ch for ch in abn if ch.isdigit()) in HOLDOUT_ABNS:
        raise RuntimeError("holdout firewall: subject is sealed")
    if subject_name and subject_name.casefold() in HOLDOUT_NAMES:
        raise RuntimeError("holdout firewall: subject is sealed")
