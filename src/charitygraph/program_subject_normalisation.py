"""Private Stage-B program/service subject-normalisation contracts.

Stage-A rich semantic proposals remain hypotheses. Stage-B explicitly resolves
those proposals into zero, one, or many resolved candidates while retaining
mechanical proposal-to-candidate lineage. This module contains no lexical
semantic classifier and is not a public Data schema.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from pydantic import field_validator, model_validator

from .contracts.common import SchemaRef, Sha256, StrictModel, VersionedPolicy, require_nonblank
from .contracts.ids import deterministic_id
from .contracts.tasks import EvidenceInput, ModelTask, model_task_cache_key
from .llm_semantic_economics import (
    EvidenceBundle,
    RichSemanticOutput,
    SemanticAssertion,
    SemanticProposal,
)

ResolutionClass = Literal[
    "durable_program",
    "durable_service",
    "project",
    "campaign",
    "organisational_unit",
    "semantic_domain_or_activity_category",
    "organisational_capability_or_practice",
    "umbrella_or_portfolio",
    "unresolved",
    "exclude_not_subject",
]
ProposalDisposition = Literal["resolved", "split", "unresolved", "exclude_not_subject"]
ReviewRecommendation = Literal["required", "acceptable", "unresolved", "exclude"]


def _stage_a_hash(proposals: tuple[SemanticProposal, ...], assertions: tuple[SemanticAssertion, ...]) -> str:
    material = {
        "proposals": [item.model_dump(mode="json") for item in proposals],
        "assertions": [item.model_dump(mode="json") for item in assertions],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class ProgramSubjectNormalisationInput(StrictModel):
    subject_id: str
    charity_name: str
    evidence_bundle_id: str
    evidence_content_hash: Sha256
    evidence_selection_hash: Sha256
    evidence_ids: tuple[str, ...]
    stage_a_output_hash: Sha256
    stage_a_proposals: tuple[SemanticProposal, ...]
    stage_a_assertions: tuple[SemanticAssertion, ...] = ()

    @field_validator("subject_id", "charity_name", "evidence_bundle_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence_ids")
    @classmethod
    def _evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError("Stage-B evidence IDs must be nonblank and unique")
        return value

    @field_validator("stage_a_proposals")
    @classmethod
    def _proposals(cls, value: tuple[SemanticProposal, ...]) -> tuple[SemanticProposal, ...]:
        ids = [item.proposal_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Stage-A proposal IDs must be unique")
        return value

    @model_validator(mode="after")
    def _hash(self) -> "ProgramSubjectNormalisationInput":
        expected = _stage_a_hash(self.stage_a_proposals, self.stage_a_assertions)
        if expected != self.stage_a_output_hash:
            raise ValueError("stage_a_output_hash does not match the exact Stage-A output")
        return self


class ProposalResolution(StrictModel):
    stage_a_proposal_id: str
    disposition: ProposalDisposition
    resolved_candidate_ids: tuple[str, ...]
    rationale: str
    confidence: str
    competing_interpretation: str | None = None
    evidence_refs: tuple[str, ...]
    model_review_recommendation: ReviewRecommendation | None = None

    @field_validator("stage_a_proposal_id")
    @classmethod
    def _proposal_id(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("resolved_candidate_ids", "evidence_refs")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError("Stage-B candidate/evidence IDs must be nonblank and unique")
        return value

    @field_validator("rationale", "confidence")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _split_shape(self) -> "ProposalResolution":
        if self.disposition == "split" and len(self.resolved_candidate_ids) < 2:
            raise ValueError("split resolutions must reference at least two resolved candidates")
        return self


class ResolvedCandidate(StrictModel):
    resolved_candidate_id: str
    canonical_candidate_label: str
    resolution_class: ResolutionClass
    durable: bool | None
    parent_resolved_candidate_id: str | None = None
    evidence_refs: tuple[str, ...]
    rationale: str
    confidence: str
    competing_interpretation: str | None = None

    @field_validator("resolved_candidate_id", "canonical_candidate_label")
    @classmethod
    def _identity(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError("resolved candidate evidence_refs must be nonblank and unique")
        return value

    @field_validator("rationale", "confidence")
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("parent_resolved_candidate_id")
    @classmethod
    def _parent(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _durability(self) -> "ResolvedCandidate":
        durable_classes = {"durable_program", "durable_service"}
        if self.resolution_class in durable_classes and self.durable is not True:
            raise ValueError("durable program/service candidates require durable=true")
        if self.resolution_class not in durable_classes and self.durable is True:
            raise ValueError("non-durable resolution classes cannot be durable=true")
        return self


class ProgramSubjectNormalisationOutput(StrictModel):
    proposal_resolutions: tuple[ProposalResolution, ...]
    resolved_candidates: tuple[ResolvedCandidate, ...]
    semantic_outcome: str
    blockers: tuple[str, ...] = ()

    @field_validator("semantic_outcome")
    @classmethod
    def _outcome(cls, value: str) -> str:
        return require_nonblank(value)


class ProgramSubjectNormalisationCase(StrictModel):
    charity_name: str
    stage_a: ProgramSubjectNormalisationInput
    stage_b: ProgramSubjectNormalisationOutput

    @field_validator("charity_name")
    @classmethod
    def _charity(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _same_subject(self) -> "ProgramSubjectNormalisationCase":
        if self.stage_a.charity_name != self.charity_name:
            raise ValueError("Stage-A charity must match case charity")
        validate_stage_b_output(self.stage_b, self.stage_a)
        return self


class NormalisedSubjectLineage(StrictModel):
    stage_a_proposal_id: str
    resolved_candidate_id: str
    resolution_disposition: ProposalDisposition

    @field_validator("stage_a_proposal_id", "resolved_candidate_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)


class NormalisedSubjectProjection(StrictModel):
    resolved_candidate_id: str
    canonical_candidate_label: str
    resolution_class: Literal["durable_program", "durable_service"]
    stage_a_proposal_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    lineage: tuple[NormalisedSubjectLineage, ...]


def validate_stage_b_output(
    output: ProgramSubjectNormalisationOutput,
    stage_a: ProgramSubjectNormalisationInput,
    *,
    permitted_evidence_ids: Iterable[str] | None = None,
) -> ProgramSubjectNormalisationOutput:
    known_proposals = {item.proposal_id for item in stage_a.stage_a_proposals}
    proposal_resolutions = output.proposal_resolutions
    seen_proposals = [item.stage_a_proposal_id for item in proposal_resolutions]
    if set(seen_proposals) != known_proposals or len(seen_proposals) != len(set(seen_proposals)):
        missing = sorted(known_proposals - set(seen_proposals))
        duplicate = sorted({item for item in seen_proposals if seen_proposals.count(item) > 1})
        raise ValueError(f"Stage-B must resolve every Stage-A proposal exactly once; missing={missing}, duplicate={duplicate}")

    candidates = output.resolved_candidates
    candidate_ids = [item.resolved_candidate_id for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("resolved candidate IDs must be unique")
    candidate_id_set = set(candidate_ids)
    referenced = {candidate_id for item in proposal_resolutions for candidate_id in item.resolved_candidate_ids}
    unknown_candidates = sorted(referenced - candidate_id_set)
    if unknown_candidates:
        raise ValueError(f"Stage-B references unknown resolved candidate IDs: {unknown_candidates}")
    orphaned = sorted(candidate_id_set - referenced)
    if orphaned:
        raise ValueError(f"resolved candidates require at least one Stage-A lineage edge: {orphaned}")
    for candidate in candidates:
        if candidate.parent_resolved_candidate_id and candidate.parent_resolved_candidate_id not in candidate_id_set:
            raise ValueError(f"resolved candidate references unknown parent: {candidate.parent_resolved_candidate_id}")

    allowed_evidence = set(permitted_evidence_ids or stage_a.evidence_ids)
    for item in proposal_resolutions:
        unknown_refs = sorted(set(item.evidence_refs) - allowed_evidence)
        if unknown_refs:
            raise ValueError(f"Stage-B proposal resolution references unknown evidence IDs: {unknown_refs}")
    for item in candidates:
        unknown_refs = sorted(set(item.evidence_refs) - allowed_evidence)
        if unknown_refs:
            raise ValueError(f"Stage-B resolved candidate references unknown evidence IDs: {unknown_refs}")
    return output


def build_normalisation_input(
    subject_id: str,
    charity_name: str,
    bundle: EvidenceBundle,
    stage_a: RichSemanticOutput,
) -> ProgramSubjectNormalisationInput:
    proposals = (*stage_a.programs, *stage_a.services, *stage_a.projects, *stage_a.campaigns, *stage_a.organisational_units)
    assertions = (*stage_a.activities, *stage_a.populations, *stage_a.geographies, *stage_a.sdg_alignments, *stage_a.assertions)
    return ProgramSubjectNormalisationInput(
        subject_id=subject_id,
        charity_name=charity_name,
        evidence_bundle_id=bundle.bundle_id,
        evidence_content_hash=bundle.evidence_content_hash,
        evidence_selection_hash=bundle.selection_hash,
        evidence_ids=tuple(segment.evidence_id for segment in bundle.source_segments),
        stage_a_output_hash=_stage_a_hash(proposals, assertions),
        stage_a_proposals=proposals,
        stage_a_assertions=assertions,
    )


NORMALISATION_PROMPT_TEMPLATE_ID = "charitygraph-program-subject-normalisation-v2"
NORMALISATION_PROMPT_TEMPLATE_VERSION = "2"


def normalisation_prompt(task_input: ProgramSubjectNormalisationInput, bundle: EvidenceBundle) -> str:
    proposals = json.dumps([item.model_dump(mode="json") for item in task_input.stage_a_proposals], ensure_ascii=False, sort_keys=True)
    assertions = json.dumps([item.model_dump(mode="json") for item in task_input.stage_a_assertions], ensure_ascii=False, sort_keys=True)
    evidence = "\n\n".join(f"[{segment.evidence_id}] SOURCE {segment.source_url}\n{segment.text}" for segment in bundle.source_segments)
    return (
        f"You are performing Stage-B program/service subject normalisation for {task_input.charity_name}. "
        "Stage-A items are hypotheses, not durable subjects. Return proposal_resolutions and resolved_candidates. "
        "Every Stage-A proposal must receive exactly one proposal resolution; a resolution may reference zero, one, "
        "or many resolved candidates, and multiple resolutions may reference the same candidate. Use only these "
        "candidate classes: durable_program, durable_service, project, campaign, organisational_unit, "
        "semantic_domain_or_activity_category, organisational_capability_or_practice, umbrella_or_portfolio, "
        "unresolved, exclude_not_subject. Merge or split only where the evidence supports the distinction. "
        "Preserve every Stage-A ID, evidence reference, rationale, confidence, competing interpretation and review "
        "recommendation. Do not use keyword, regex or lexical rules. Do not discard candidates or create durable "
        "subjects to satisfy a benchmark. Do not include or infer any human gold disposition. Return JSON matching "
        "the supplied strict schema.\n\n"
        f"Stage-A proposals: {proposals}\nStage-A assertions: {assertions}\n\n"
        f"Evidence bundle {bundle.bundle_id} content hash {bundle.evidence_content_hash}:\n{evidence}"
    )


def program_subject_normalisation_schema(
    *,
    permitted_evidence_ids: Iterable[str],
    permitted_stage_a_proposal_ids: Iterable[str],
) -> dict[str, Any]:
    evidence_ids = tuple(dict.fromkeys(str(item) for item in permitted_evidence_ids if str(item)))
    proposal_ids = tuple(dict.fromkeys(str(item) for item in permitted_stage_a_proposal_ids if str(item)))
    if not evidence_ids or not proposal_ids:
        raise ValueError("Stage-B strict schema requires evidence and Stage-A proposal IDs")
    schema = deepcopy(ProgramSubjectNormalisationOutput.model_json_schema())
    resolution = schema["$defs"]["ProposalResolution"]
    resolution["properties"]["stage_a_proposal_id"] = {"type": "string", "enum": list(proposal_ids)}
    resolution["properties"]["evidence_refs"]["items"] = {"type": "string", "enum": list(evidence_ids)}
    candidate = schema["$defs"]["ResolvedCandidate"]
    candidate["properties"]["evidence_refs"]["items"] = {"type": "string", "enum": list(evidence_ids)}
    schema["properties"]["proposal_resolutions"]["maxItems"] = len(proposal_ids)
    schema["properties"]["resolved_candidates"]["maxItems"] = min(256, max(1, len(proposal_ids) * 3))

    def force_strict(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                force_strict(value)
        elif isinstance(node, list):
            for value in node:
                force_strict(value)

    force_strict(schema)
    return schema


def normalisation_text_format(*, permitted_evidence_ids: Iterable[str], permitted_stage_a_proposal_ids: Iterable[str]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "program_subject_normalisation",
        "strict": True,
        "schema": program_subject_normalisation_schema(
            permitted_evidence_ids=permitted_evidence_ids,
            permitted_stage_a_proposal_ids=permitted_stage_a_proposal_ids,
        ),
    }


def _strict_schema_violations(node: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            if node.get("additionalProperties") is not False:
                violations.append(f"{path}: object must forbid additionalProperties")
            properties = set(node.get("properties", {}))
            required = set(node.get("required", []))
            if properties != required:
                violations.append(f"{path}: required must equal properties")
        for key, value in node.items():
            violations.extend(_strict_schema_violations(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            violations.extend(_strict_schema_violations(value, f"{path}[{index}]"))
    return violations


def validate_normalisation_schema(schema: dict[str, Any]) -> None:
    violations = _strict_schema_violations(schema)
    if violations:
        raise ValueError("invalid strict Stage-B schema: " + "; ".join(violations))
    if schema.get("type") != "object" or "proposal_resolutions" not in schema.get("properties", {}):
        raise ValueError("Stage-B schema has the wrong top-level shape")


def build_normalisation_task(
    task_input: ProgramSubjectNormalisationInput,
    bundle: EvidenceBundle,
    *,
    provider_id: str,
    model_snapshot: str,
) -> ModelTask[Any]:
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:program-subject-normalisation-task:2.0", schema_version="2.0")
    output_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:program-subject-normalisation-output:2.0", schema_version="2.0")
    evidence_inputs = tuple(
        EvidenceInput(evidence_id=segment.evidence_id, content_hash=segment.content_hash, selection_hash=bundle.selection_hash)
        for segment in bundle.source_segments
    )
    parameters = {
        "evidence_bundle_id": bundle.bundle_id,
        "evidence_content_hash": bundle.evidence_content_hash,
        "stage_a_output_hash": task_input.stage_a_output_hash,
        "stage_a_proposal_ids": [proposal.proposal_id for proposal in task_input.stage_a_proposals],
    }
    policies = (VersionedPolicy(policy_id="CG-D027", version="1"),)
    cache = model_task_cache_key(
        task_type="program_subject_normalisation",
        task_schema=task_schema,
        output_schema=output_schema,
        evidence_inputs=evidence_inputs,
        prompt_template_id=NORMALISATION_PROMPT_TEMPLATE_ID,
        prompt_template_version=NORMALISATION_PROMPT_TEMPLATE_VERSION,
        policy_refs=policies,
        provider_id=provider_id,
        model_snapshot=model_snapshot,
        parameters=parameters,
        material_tool_versions=(),
    )
    record_id = deterministic_id(
        "modeltask:",
        {
            "subject_id": task_input.subject_id,
            "scope_id": None,
            "task_type": "program_subject_normalisation",
            "cache_key": cache,
            "output_schema": output_schema,
        },
    )
    return ModelTask(
        record_id=record_id,
        created_at=datetime.now(timezone.utc),
        producer={"kind": "code", "producer_id": "charitygraph-program-subject-normalisation", "version": NORMALISATION_PROMPT_TEMPLATE_VERSION},
        subject_id=task_input.subject_id,
        task_type="program_subject_normalisation",
        task_schema=task_schema,
        output_schema=output_schema,
        evidence_inputs=evidence_inputs,
        prompt_template_id=NORMALISATION_PROMPT_TEMPLATE_ID,
        prompt_template_version=NORMALISATION_PROMPT_TEMPLATE_VERSION,
        policy_refs=policies,
        provider_id=provider_id,
        model_snapshot=model_snapshot,
        parameters=parameters,
        paid_output_categories=("semantic_judgement",),
    )


def project_normalised_subjects(
    stage_a: RichSemanticOutput,
    stage_b: ProgramSubjectNormalisationOutput,
) -> tuple[NormalisedSubjectProjection, ...]:
    known_proposals = {proposal.proposal_id for proposal in (*stage_a.programs, *stage_a.services, *stage_a.projects, *stage_a.campaigns, *stage_a.organisational_units)}
    seen_proposals = [resolution.stage_a_proposal_id for resolution in stage_b.proposal_resolutions]
    if set(seen_proposals) != known_proposals or len(seen_proposals) != len(set(seen_proposals)):
        raise ValueError("Stage-B must resolve every Stage-A proposal exactly once before projection")
    candidate_by_id = {candidate.resolved_candidate_id: candidate for candidate in stage_b.resolved_candidates}
    referenced = {candidate_id for resolution in stage_b.proposal_resolutions for candidate_id in resolution.resolved_candidate_ids}
    if set(candidate_by_id) != referenced:
        raise ValueError("Stage-B candidate lineage is incomplete before projection")
    resolution_by_candidate: dict[str, list[ProposalResolution]] = {}
    for resolution in stage_b.proposal_resolutions:
        for candidate_id in resolution.resolved_candidate_ids:
            resolution_by_candidate.setdefault(candidate_id, []).append(resolution)
    projections: list[NormalisedSubjectProjection] = []
    for candidate in stage_b.resolved_candidates:
        if candidate.resolution_class not in {"durable_program", "durable_service"}:
            continue
        resolutions = resolution_by_candidate[candidate.resolved_candidate_id]
        lineage = tuple(
            NormalisedSubjectLineage(
                stage_a_proposal_id=resolution.stage_a_proposal_id,
                resolved_candidate_id=candidate.resolved_candidate_id,
                resolution_disposition=resolution.disposition,
            )
            for resolution in resolutions
        )
        projections.append(
            NormalisedSubjectProjection(
                resolved_candidate_id=candidate.resolved_candidate_id,
                canonical_candidate_label=candidate.canonical_candidate_label,
                resolution_class=candidate.resolution_class,
                stage_a_proposal_ids=tuple(resolution.stage_a_proposal_id for resolution in resolutions),
                evidence_refs=candidate.evidence_refs,
                lineage=lineage,
            )
        )
    return tuple(projections)
