"""Experiment-local Whole-Card Semantic Knowledge Production v0.2 contract.

This module is deliberately separate from the public semantic contract.  It
accepts compact packet-local citations so a model never needs to reproduce
opaque repository identifiers or source quotations.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SectionAssessment(_Strict):
    section_id: int = Field(ge=1, le=20)
    status: Literal["observations_found", "insufficient_evidence", "not_applicable", "deferred"]
    note: str | None = None


class Scope(_Strict):
    kind: Literal["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]
    label: str | None = None


class TemporalScope(_Strict):
    kind: Literal["current", "as_of", "reporting_period", "historical", "undated", "mixed"]
    value: str | None = None


class CompactEvidence(_Strict):
    source: str = Field(pattern=r"^S[0-9]{3}$")
    locator: str = Field(pattern=r"^L[0-9]{4}(?:-L[0-9]{4})?$")
    role: Literal["supporting", "corroborating", "context"]


class Observation(_Strict):
    section_id: int = Field(ge=1, le=20)
    scope: Scope
    proposition: str = Field(min_length=1, max_length=500)
    epistemic_status: Literal["supported", "explicit_absence"]
    temporal_scope: TemporalScope
    evidence: tuple[CompactEvidence, ...] = ()
    qualifications: tuple[str, ...] = ()

    @model_validator(mode="after")
    def supporting_subject_fact(self) -> "Observation":
        if not any(item.role == "supporting" for item in self.evidence):
            raise ValueError("every emitted observation requires supporting evidence")
        return self


class Assignment(_Strict):
    kind: Literal["subject", "reporting_group", "named_program_or_service", "other_named_scope", "uncertain"]
    label: str | None = None


class SemanticAssignment(_Strict):
    target_scope: Assignment
    scheme: str = Field(min_length=1)
    scheme_version: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    concept_label_if_permitted: str | None = None
    evidence: tuple[CompactEvidence, ...] = ()
    rationale: str = Field(min_length=1)
    alternatives: tuple[str, ...] = ()
    qualification: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_required(self) -> "SemanticAssignment":
        if not any(item.role == "supporting" for item in self.evidence):
            raise ValueError("assignments require supporting packet evidence")
        return self


class Relationship(_Strict):
    source_scope: Scope
    target_source_native_name: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    direction: Literal["source_to_target", "target_to_source", "bidirectional", "uncertain"]
    temporal_scope: TemporalScope
    evidence: tuple[CompactEvidence, ...] = ()
    qualification: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_required(self) -> "Relationship":
        if not any(item.role == "supporting" for item in self.evidence):
            raise ValueError("relationships require supporting packet evidence")
        return self


class CrossSourceIssue(_Strict):
    issue_type: Literal[
        "contradiction", "materially_different_characterisation", "scope_reporting_mismatch",
        "temporal_conflict", "identity_binding_ambiguity"
    ]
    description: str = Field(min_length=1)
    evidence: tuple[CompactEvidence, ...] = ()
    qualification: tuple[str, ...] = ()


class WholeCardExtractionOutputV02(_Strict):
    section_assessments: tuple[SectionAssessment, ...]
    observations: tuple[Observation, ...] = ()
    assignments: tuple[SemanticAssignment, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    cross_source_issues: tuple[CrossSourceIssue, ...] = ()

    @model_validator(mode="after")
    def exactly_twenty_sections(self) -> "WholeCardExtractionOutputV02":
        ids = [item.section_id for item in self.section_assessments]
        if len(ids) != 20 or set(ids) != set(range(1, 21)):
            raise ValueError("exactly one section assessment is required for sections 1 through 20")
        return self


def _strictify(node: Any) -> Any:
    """Make Pydantic's nullable/default-friendly schema OpenAI strict-safe."""
    if isinstance(node, dict):
        node.pop("default", None)
        if node.get("type") == "object" and isinstance(node.get("properties"), dict):
            node["required"] = list(node["properties"])
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for value in node:
            _strictify(value)
    return node


# Pydantic's generated schema is used by the runner so the wire contract and
# validation contract cannot drift. All fields are required (nullable fields
# represent optional values) as required by strict Structured Outputs.
STRICT_SCHEMA: dict[str, Any] = _strictify(WholeCardExtractionOutputV02.model_json_schema())


_LOCATOR = re.compile(r"^L(?P<start>[0-9]{4})(?:-L(?P<end>[0-9]{4}))?$")


def locator_resolves(locator: str, valid: set[str]) -> bool:
    if locator in valid:
        return True
    match = _LOCATOR.fullmatch(locator)
    if not match:
        return False
    start = int(match.group("start")); end = int(match.group("end") or match.group("start"))
    return start <= end and all(f"L{line:04d}" in valid for line in range(start, end + 1))


def duplicate_count(items: tuple[BaseModel, ...]) -> int:
    encoded = [json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) for item in items]
    return len(encoded) - len(set(encoded))


def validate_output(value: dict[str, Any], packet: dict[str, Any]) -> WholeCardExtractionOutputV02:
    result = WholeCardExtractionOutputV02.model_validate(value)
    spaces = {item["source_key"]: {loc["locator"].split(":", 1)[-1] for loc in item["locators"]} for item in packet["sources"]}

    def check_evidence(evidence: tuple[CompactEvidence, ...]) -> None:
        for ref in evidence:
            if ref.source not in spaces or not locator_resolves(ref.locator, spaces[ref.source]):
                raise ValueError(f"citation does not resolve: {ref.source}/{ref.locator}")

    for observation in result.observations:
        check_evidence(observation.evidence)
    for assignment in result.assignments:
        check_evidence(assignment.evidence)
    for relationship in result.relationships:
        check_evidence(relationship.evidence)
    for issue in result.cross_source_issues:
        check_evidence(issue.evidence)
    encoded = json.dumps(value, ensure_ascii=False)
    if any(token in encoded for token in ("subject:", "srcrec:", "srcblob:", "causebase:")):
        raise ValueError("model output must not generate CharityGraph or opaque source IDs")
    return result
