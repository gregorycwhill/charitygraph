"""Private Stage-B program/service subject normalization contracts.

Stage-A rich semantic proposals remain model hypotheses.  This module defines
a second model-assisted task that explicitly resolves every Stage-A proposal
into a durable subject, project, category, practice, umbrella or unresolved
class.  No lexical classification is performed here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Literal, Mapping
from datetime import datetime, timezone

from pydantic import Field, field_validator, model_validator

from .contracts.common import SchemaRef, Sha256, StrictModel, VersionedPolicy, require_nonblank
from .contracts.ids import deterministic_id
from .contracts.tasks import EvidenceInput, ModelTask, model_task_cache_key
from .llm_semantic_economics import EvidenceBundle, RichSemanticOutput, SemanticAssertion, SemanticProposal

ResolutionClass = Literal[
    "durable_program", "durable_service", "project", "campaign",
    "organisational_unit", "semantic_domain_or_activity_category",
    "organisational_capability_or_practice", "umbrella_or_portfolio",
    "unresolved", "exclude_not_subject",
]
ReviewRecommendation = Literal["required", "acceptable", "unresolved", "exclude"]


class ProgramSubjectNormalisationInput(StrictModel):
    subject_id: str
    charity_name: str
    evidence_bundle_id: str
    evidence_content_hash: Sha256
    evidence_selection_hash: Sha256
    stage_a_proposals: tuple[SemanticProposal, ...]
    stage_a_assertions: tuple[SemanticAssertion, ...] = ()

    @field_validator("subject_id", "charity_name", "evidence_bundle_id")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("stage_a_proposals")
    @classmethod
    def _proposals(cls, value: tuple[SemanticProposal, ...]) -> tuple[SemanticProposal, ...]:
        ids = [item.proposal_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Stage-A proposal IDs must be unique")
        return value


class ProgramSubjectNormalisationDecision(StrictModel):
    stage_a_proposal_ids: tuple[str, ...]
    resolved_candidate_id: str | None = None
    canonical_candidate_label: str | None = None
    resolution_class: ResolutionClass
    durable: bool | None
    parent_resolved_candidate_id: str | None = None
    evidence_refs: tuple[str, ...]
    rationale: str
    confidence: str
    competing_interpretation: str | None = None
    model_review_recommendation: ReviewRecommendation | None = None

    @field_validator("stage_a_proposal_ids", "evidence_refs")
    @classmethod
    def _ids_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("Stage-B IDs and evidence_refs must be nonblank")
        if len(value) != len(set(value)):
            raise ValueError("Stage-B IDs must be unique within a decision")
        return value

    @field_validator("rationale", "confidence")
    @classmethod
    def _text_nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("canonical_candidate_label", "resolved_candidate_id", "parent_resolved_candidate_id")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _durability_and_candidate(self) -> "ProgramSubjectNormalisationDecision":
        durable_classes = {"durable_program", "durable_service"}
        if self.resolution_class in durable_classes and self.durable is not True:
            raise ValueError("durable program/service resolutions require durable=true")
        if self.resolution_class not in durable_classes and self.durable is True:
            raise ValueError("non-durable resolution classes cannot be durable=true")
        if self.resolution_class in durable_classes and not self.resolved_candidate_id:
            raise ValueError("durable resolutions require resolved_candidate_id")
        return self


class ProgramSubjectNormalisationOutput(StrictModel):
    resolutions: tuple[ProgramSubjectNormalisationDecision, ...]
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
    resolution_class: ResolutionClass

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


def validate_stage_b_output(output: ProgramSubjectNormalisationOutput, stage_a: ProgramSubjectNormalisationInput, *, permitted_evidence_ids: Iterable[str] | None = None) -> ProgramSubjectNormalisationOutput:
    known = {item.proposal_id for item in stage_a.stage_a_proposals}
    seen: list[str] = []
    for decision in output.resolutions:
        unknown = sorted(set(decision.stage_a_proposal_ids) - known)
        if unknown:
            raise ValueError(f"Stage-B references unknown Stage-A proposal IDs: {unknown}")
        seen.extend(decision.stage_a_proposal_ids)
        if permitted_evidence_ids is not None:
            allowed = set(permitted_evidence_ids)
            unknown_refs = sorted(set(decision.evidence_refs) - allowed)
            if unknown_refs:
                raise ValueError(f"Stage-B references unknown evidence IDs: {unknown_refs}")
    if set(seen) != known or len(seen) != len(set(seen)):
        missing = sorted(known - set(seen))
        duplicate = sorted({item for item in seen if seen.count(item) > 1})
        raise ValueError(f"Stage-B must disposition every Stage-A proposal exactly once; missing={missing}, duplicate={duplicate}")
    return output


def build_normalisation_input(subject_id: str, charity_name: str, bundle: EvidenceBundle, stage_a: RichSemanticOutput) -> ProgramSubjectNormalisationInput:
    proposals = (*stage_a.programs, *stage_a.services, *stage_a.projects, *stage_a.campaigns, *stage_a.organisational_units)
    assertions = (*stage_a.activities, *stage_a.populations, *stage_a.geographies, *stage_a.sdg_alignments, *stage_a.assertions)
    return ProgramSubjectNormalisationInput(subject_id=subject_id, charity_name=charity_name, evidence_bundle_id=bundle.bundle_id, evidence_content_hash=bundle.evidence_content_hash, evidence_selection_hash=bundle.selection_hash, stage_a_proposals=proposals, stage_a_assertions=assertions)


NORMALISATION_PROMPT_TEMPLATE_ID = "charitygraph-program-subject-normalisation-v1"
NORMALISATION_PROMPT_TEMPLATE_VERSION = "1"

def normalisation_prompt(task_input: ProgramSubjectNormalisationInput, bundle: EvidenceBundle) -> str:
    proposals = json.dumps([item.model_dump(mode="json") for item in task_input.stage_a_proposals], ensure_ascii=False, sort_keys=True)
    assertions = json.dumps([item.model_dump(mode="json") for item in task_input.stage_a_assertions], ensure_ascii=False, sort_keys=True)
    evidence = "\n\n".join(f"[{segment.evidence_id}] SOURCE {segment.source_url}\n{segment.text}" for segment in bundle.source_segments)
    return f"""You are performing Stage-B program/service subject normalisation for {task_input.charity_name}. Stage-A items are model hypotheses, not durable subjects. Resolve every Stage-A proposal exactly once into one explicit resolution_class: durable_program, durable_service, project, campaign, organisational_unit, semantic_domain_or_activity_category, organisational_capability_or_practice, umbrella_or_portfolio, unresolved, or exclude_not_subject. You may merge Stage-A aliases only when evidence supports the same identifiable subject; you may split a combined proposal only when evidence supports separate subjects. Preserve every Stage-A proposal ID, evidence reference, rationale, confidence, competing interpretation and review recommendation. Do not use keyword, regex or lexical rules. Do not discard a candidate or create a durable subject merely to satisfy a benchmark. Do not include or infer any human gold disposition. Return JSON matching the supplied schema.\n\nStage-A proposals: {proposals}\nStage-A assertions: {assertions}\n\nEvidence bundle {bundle.bundle_id} content hash {bundle.evidence_content_hash}:\n{evidence}"""


def build_normalisation_task(task_input: ProgramSubjectNormalisationInput, bundle: EvidenceBundle, *, provider_id: str, model_snapshot: str) -> ModelTask[Any]:
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:program-subject-normalisation-task:1.0", schema_version="1.0")
    output_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:program-subject-normalisation-output:1.0", schema_version="1.0")
    evidence_inputs = tuple(EvidenceInput(evidence_id=s.evidence_id, content_hash=s.content_hash, selection_hash=bundle.selection_hash) for s in bundle.source_segments)
    parameters = {"evidence_bundle_id": bundle.bundle_id, "evidence_content_hash": bundle.evidence_content_hash, "stage_a_proposal_ids": [p.proposal_id for p in task_input.stage_a_proposals]}
    policies = (VersionedPolicy(policy_id="CG-D027", version="1"),)
    cache = model_task_cache_key(task_type="program_subject_normalisation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=evidence_inputs, prompt_template_id=NORMALISATION_PROMPT_TEMPLATE_ID, prompt_template_version=NORMALISATION_PROMPT_TEMPLATE_VERSION, policy_refs=policies, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, material_tool_versions=())
    record_id = deterministic_id("modeltask:", {"subject_id": task_input.subject_id, "scope_id": None, "task_type": "program_subject_normalisation", "cache_key": cache, "output_schema": output_schema})
    return ModelTask(record_id=record_id, created_at=datetime.now(timezone.utc), producer={"kind":"code","producer_id":"charitygraph-program-subject-normalisation","version":NORMALISATION_PROMPT_TEMPLATE_VERSION}, subject_id=task_input.subject_id, task_type="program_subject_normalisation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=evidence_inputs, prompt_template_id=NORMALISATION_PROMPT_TEMPLATE_ID, prompt_template_version=NORMALISATION_PROMPT_TEMPLATE_VERSION, policy_refs=policies, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, paid_output_categories=("semantic_judgement",))


def project_normalised_subjects(stage_a: RichSemanticOutput, stage_b: ProgramSubjectNormalisationOutput) -> tuple[NormalisedSubjectProjection, ...]:
    by_id = {p.proposal_id: p for p in (*stage_a.programs, *stage_a.services, *stage_a.projects, *stage_a.campaigns, *stage_a.organisational_units)}
    projections: list[NormalisedSubjectProjection] = []
    for decision in stage_b.resolutions:
        if decision.resolution_class not in {"durable_program", "durable_service"}:
            continue
        assert decision.resolved_candidate_id is not None
        label = decision.canonical_candidate_label or by_id[decision.stage_a_proposal_ids[0]].label
        lineage = tuple(NormalisedSubjectLineage(stage_a_proposal_id=proposal_id, resolved_candidate_id=decision.resolved_candidate_id, resolution_class=decision.resolution_class) for proposal_id in decision.stage_a_proposal_ids)
        projections.append(NormalisedSubjectProjection(resolved_candidate_id=decision.resolved_candidate_id, canonical_candidate_label=label, resolution_class=decision.resolution_class, stage_a_proposal_ids=decision.stage_a_proposal_ids, evidence_refs=decision.evidence_refs, lineage=lineage))
    return tuple(projections)
