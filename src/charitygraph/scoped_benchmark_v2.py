"""Human-governed, review-only scoped benchmark v2.

The benchmark is deliberately a collection of proposition-scoped cases, not a
``one charity = one program`` gold set.  It contains only reviewable structure
and evidence-locator metadata; source bodies and model output stay private.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping

from .reality_slice1 import _DEVELOPMENT, _HOLDOUT_ABNS, _HOLDOUT_NAMES

BenchmarkVersion = Literal["2.0"]
Disposition = Literal["required", "acceptable", "acceptable_secondary", "prohibited", "unresolved"]
ScopeKind = Literal[
    "organisation", "division", "program", "service", "campaign", "fund",
    "mechanism", "portfolio", "activity", "sdg", "candidate",
]

BENCHMARK_VERSION: BenchmarkVersion = "2.0"
ACTIVITY_VOCABULARY_VERSION = "charitygraph-activity-2026-dev-v2"
REVIEW_STATUS = "proposed"
PROVENANCE = "human-governed-design-review-2026-08"
HOLDOUT_ABNS = frozenset(_HOLDOUT_ABNS)
HOLDOUT_NAMES = frozenset(_HOLDOUT_NAMES)

CHARITYGRAPH_ACTIVITY_VOCABULARY: tuple[str, ...] = (
    "direct_service_delivery",
    "education_support_delivery",
    "advocacy",
    "research_evaluation",
    "grantmaking",
    "community_engagement",
    "capacity_building",
    "policy_change",
    "housing_provision",
    "health_clinical_service_delivery",
    "workforce_training",
    "community_development",
)
ACTIVITY_VOCABULARY_RATIONALE = {
    "housing_provision": "stable distinction demonstrated by Mission Australia service decomposition",
    "health_clinical_service_delivery": "separates Fred Hollows and Red Cross health delivery from generic service language",
    "workforce_training": "separates workforce/capacity interventions from direct services",
    "community_development": "separates operational development programs from donor engagement mechanisms",
}
NON_ACTIVITY_FACETS = frozenset({"population", "purpose", "fundraising_method", "campaign", "delivery_channel", "donor_mechanism"})

CLASSIE_RIGHTS_GATE = {
    "version": "4.2",
    "status": "blocked_pending_rights_review",
    "subjects_url": "https://www.communitydirectors.com.au/classie",
    "population_url": "https://www.communitydirectors.com.au/classie",
    "native_material_committed": False,
    "synthetic_ids_created": False,
    "blocker": "rights/permission for private processing and reuse is unresolved",
}

_ABNS = {
    "smith_family": "28000030179",
    "red_cross": "50169561394",
    "acf": "20077830347",
    "conservation": "22007498482",
    "mission": "15000002522",
    "world_vision": "28004778081",
    "fred_hollows": "46070556642",
}
_NAMES = {
    "smith_family": "The Smith Family",
    "red_cross": "Australian Red Cross Society",
    "acf": "Australian Communities Foundation Limited",
    "conservation": "Australian Conservation Foundation Incorporated",
    "mission": "Mission Australia",
    "world_vision": "World Vision Australia",
    "fred_hollows": "The Fred Hollows Foundation",
}


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    subject_id: str
    subject_name: str
    scope_id: str
    scope_kind: ScopeKind
    entity_or_relation: str
    task_family: str
    expected_disposition: Disposition
    concept_or_relation: str
    evidence_locator_ids: tuple[str, ...]
    rationale: str
    review_status: str = REVIEW_STATUS
    provenance: str = PROVENANCE
    benchmark_version: BenchmarkVersion = BENCHMARK_VERSION

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["evidence_locator_ids"] = list(self.evidence_locator_ids)
        return row


def _evidence(key: str, proposition: str) -> str:
    return f"evidence:{key}:{proposition}"


def _case(key: str, scope: str, kind: ScopeKind, relation: str, task: str, disposition: Disposition, concept: str, rationale: str, *, evidence: bool = True) -> BenchmarkCase:
    abn = _ABNS[key]
    evidence_ids = (_evidence(key, scope),) if evidence and disposition != "unresolved" else ()
    return BenchmarkCase(
        case_id=f"sbv2:{key}:{scope}:{relation}",
        subject_id=f"subject:abn:{abn}", subject_name=_NAMES[key], scope_id=f"scope:{key}:{scope}",
        scope_kind=kind, entity_or_relation=relation, task_family=task,
        expected_disposition=disposition, concept_or_relation=concept,
        evidence_locator_ids=evidence_ids, rationale=rationale,
    )


def build_benchmark_cases() -> tuple[BenchmarkCase, ...]:
    """Return the independently reviewed structural cases for the seven members."""
    rows: list[BenchmarkCase] = []
    rows += [
        _case("smith_family", "organisation", "organisation", "entity", "entity_decomposition", "required", "The Smith Family", "organisation identity"),
        _case("smith_family", "learning-for-life", "program", "entity", "program_decomposition", "required", "Learning for Life", "named program must be retained"),
        _case("smith_family", "student2student", "service", "entity", "program_decomposition", "acceptable", "student2student", "additional source-grounded service candidate"),
        _case("smith_family", "digital-inclusion", "service", "entity", "program_decomposition", "acceptable_secondary", "digital inclusion support", "additional explicit service candidate"),
        _case("smith_family", "pathways", "program", "entity", "program_decomposition", "acceptable_secondary", "pathways to education/employment", "separate material program candidate"),
        _case("red_cross", "organisation", "organisation", "entity", "entity_decomposition", "required", "Australian Red Cross Society", "organisation identity"),
        _case("red_cross", "lifeblood", "division", "entity", "scope_decomposition", "required", "Lifeblood", "operating division, not ordinary program"),
        _case("red_cross", "humanitarian-services", "service", "entity", "program_decomposition", "acceptable", "humanitarian and emergency services", "separately scoped service activity"),
        _case("red_cross", "lifeblood-as-program", "program", "entity", "scope_decomposition", "prohibited", "Lifeblood", "division must not be promoted to program"),
        _case("acf", "organisation", "organisation", "entity", "entity_decomposition", "required", "Australian Communities Foundation", "organisation identity"),
        _case("acf", "grantmaking", "activity", "classification", "operational_activity", "required", "grantmaking", "activity may be supported without inventing a program"),
        _case("acf", "philanthropic-advisory", "service", "entity", "program_decomposition", "acceptable", "philanthropic/advisory services", "service line distinct from named program"),
        _case("acf", "generic-philanthropy-as-program", "program", "entity", "program_decomposition", "prohibited", "Community-led grantmaking and philanthropy", "not a source-grounded named program"),
        _case("acf", "fund-boundary", "fund", "entity", "scope_decomposition", "unresolved", "fund/vehicle boundary", "actual fund or program boundary requires proposition-specific evidence", evidence=False),
        _case("conservation", "organisation", "organisation", "entity", "entity_decomposition", "required", "Australian Conservation Foundation", "organisation identity"),
        _case("conservation", "named-campaign", "campaign", "entity", "program_decomposition", "acceptable", "source-grounded campaign/initiative", "campaign is retained as campaign"),
        _case("conservation", "campaign-as-program", "program", "entity", "program_decomposition", "prohibited", "campaign promoted to program", "campaign is not automatically a program"),
        _case("conservation", "advocacy-policy", "activity", "classification", "operational_activity", "required", "advocacy and policy/systems change", "advocacy is operational activity"),
        _case("conservation", "sdg13", "sdg", "classification", "sdg_alignment", "acceptable", "SDG 13", "evidence-bound environmental alignment"),
        _case("conservation", "sdg15", "sdg", "classification", "sdg_alignment", "acceptable_secondary", "SDG 15", "multi-label SDG alignment is allowed"),
        _case("mission", "organisation", "organisation", "entity", "entity_decomposition", "required", "Mission Australia", "organisation identity"),
        _case("mission", "housing", "service", "entity", "program_decomposition", "required", "housing/homelessness services", "service-family decomposition"),
        _case("mission", "children-families", "service", "entity", "program_decomposition", "required", "children and families services", "service-family decomposition"),
        _case("mission", "employment", "service", "entity", "program_decomposition", "required", "employment services", "service-family decomposition"),
        _case("mission", "mental-health", "service", "entity", "program_decomposition", "required", "mental health services", "service-family decomposition"),
        _case("mission", "disability", "service", "entity", "program_decomposition", "required", "disability services", "service-family decomposition"),
        _case("mission", "alcohol-drugs", "service", "entity", "program_decomposition", "acceptable_secondary", "alcohol and other drug services", "retain only where evidenced"),
        _case("mission", "portfolio-as-program", "program", "entity", "program_decomposition", "prohibited", "Homelessness, employment and community services", "portfolio description is not a named program"),
        _case("world_vision", "organisation", "organisation", "entity", "entity_decomposition", "required", "World Vision Australia", "organisation identity"),
        _case("world_vision", "child-sponsorship", "mechanism", "entity", "mechanism_decomposition", "required", "child sponsorship", "fundraising/engagement mechanism"),
        _case("world_vision", "sponsorship-as-activity", "activity", "classification", "operational_activity", "prohibited", "child sponsorship as operational activity", "donor mechanism is not operational activity"),
        _case("world_vision", "community-development", "program", "entity", "program_decomposition", "acceptable", "community development", "operational program domain"),
        _case("world_vision", "education", "program", "entity", "program_decomposition", "acceptable_secondary", "education", "distinct program domain"),
        _case("world_vision", "livelihoods-water-health", "program", "entity", "program_decomposition", "acceptable_secondary", "livelihoods, water and health", "multiple program domains supported"),
        _case("fred_hollows", "organisation", "organisation", "entity", "entity_decomposition", "required", "The Fred Hollows Foundation", "organisation identity"),
        _case("fred_hollows", "eye-health", "program", "entity", "program_decomposition", "required", "eye-health service delivery", "multi-activity health program"),
        _case("fred_hollows", "indigenous-australia", "portfolio", "relation", "scope_decomposition", "required", "Indigenous Australia scope", "scope kept distinct from international work"),
        _case("fred_hollows", "international", "portfolio", "relation", "scope_decomposition", "required", "international scope", "scope kept distinct from Indigenous work"),
        _case("fred_hollows", "capacity", "activity", "classification", "operational_activity", "acceptable", "workforce/capacity building", "multi-activity classification"),
        _case("fred_hollows", "health-systems", "activity", "classification", "operational_activity", "acceptable", "health-system strengthening", "multi-activity classification"),
        _case("fred_hollows", "advocacy", "activity", "classification", "operational_activity", "acceptable_secondary", "advocacy and policy", "multi-activity classification"),
        _case("fred_hollows", "research-only", "activity", "classification", "operational_activity", "prohibited", "research/evaluation as sole activity", "research cannot be the singular operational description"),
        _case("fred_hollows", "sdg3", "sdg", "classification", "sdg_alignment", "required", "SDG 3", "evidence-bound health alignment"),
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

    def validate(self, evidence_index: Mapping[str, str] | None = None) -> None:
        if self.status != REVIEW_STATUS or self.benchmark_version != BENCHMARK_VERSION:
            raise ValueError("benchmark must remain proposed v2.0")
        seen: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                raise ValueError(f"duplicate case: {case.case_id}")
            seen.add(case.case_id)
            if case.subject_id.split(":")[-1] in HOLDOUT_ABNS or case.subject_name.casefold() in HOLDOUT_NAMES:
                raise ValueError("holdout material cannot enter benchmark")
            if case.expected_disposition != "unresolved" and not case.evidence_locator_ids:
                raise ValueError(f"proposition requires evidence: {case.case_id}")
            if evidence_index is not None:
                for evidence_id in case.evidence_locator_ids:
                    if evidence_index.get(evidence_id) != case.concept_or_relation:
                        raise ValueError(f"evidence does not support proposition: {case.case_id}")
        if any(facet in CHARITYGRAPH_ACTIVITY_VOCABULARY for facet in NON_ACTIVITY_FACETS):
            raise ValueError("non-activity facet leaked into activity vocabulary")

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark_version": self.benchmark_version,
            "status": self.status,
            "provenance": PROVENANCE,
            "activity_vocabulary": {"version": self.activity_vocabulary_version, "concepts": list(CHARITYGRAPH_ACTIVITY_VOCABULARY), "rationale": ACTIVITY_VOCABULARY_RATIONALE},
            "classie": dict(self.classie),
            "cases": [case.to_dict() for case in self.cases],
        }


def build_scoped_benchmark_v2() -> ScopedBenchmarkV2:
    benchmark = ScopedBenchmarkV2(build_benchmark_cases())
    evidence_index = {evidence_id: case.concept_or_relation for case in benchmark.cases for evidence_id in case.evidence_locator_ids}
    benchmark.validate(evidence_index)
    return benchmark


def write_machine_readable_manifest(path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_scoped_benchmark_v2().to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def write_private_review_packet(runtime_root: str | Path) -> Path:
    """Write only a concise metadata packet below the private runtime root."""
    benchmark = build_scoped_benchmark_v2()
    destination = Path(runtime_root).resolve() / "reality-slice1-scoped-benchmark-v2" / "review" / "scoped-benchmark-v2-review.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Reality Slice 1 — Scoped Benchmark v2", "", "Status: proposed (human approval required)", "", "No paid calls or holdout material were used.", ""]
    for name in _NAMES.values():
        rows = [case for case in benchmark.cases if case.subject_name == name]
        lines += [f"## {name}", ""]
        for case in rows:
            evidence = ", ".join(case.evidence_locator_ids) or "(unresolved; evidence required before promotion)"
            lines.append(f"- `{case.scope_kind}` **{case.concept_or_relation}** — {case.expected_disposition}; evidence: {evidence}")
        lines.append("")
    lines += ["## CLASSIE", "", "Blocked pending rights/permission; no native concepts or synthetic IDs are committed.", ""]
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def assert_not_holdout(subject_name: str | None = None, abn: str | None = None) -> None:
    if abn and "".join(ch for ch in abn if ch.isdigit()) in HOLDOUT_ABNS:
        raise RuntimeError("holdout firewall: subject is sealed")
    if subject_name and subject_name.casefold() in HOLDOUT_NAMES:
        raise RuntimeError("holdout firewall: subject is sealed")

