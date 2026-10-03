"""Closed, provider-free projection compatibility policy.

This boundary consumes declared governed values and identifiers only; it never
classifies prose.  Binding and composition facts must already exist upstream.
"""
from __future__ import annotations
from enum import StrEnum
from typing import Any, Mapping
from pydantic import BaseModel, ConfigDict

POLICY_VERSION = "projection-compatibility.v1"
POLICY_DIMENSIONS = ("answer_intent", "claim_family", "authority_source_role", "currentness", "scope", "coverage")
INTENTS = frozenset({"historical_notice", "factual_summary", "service_information", "evaluation_summary", "regulatory_history", "assurance_notice", "programme_context", "hosted_submission_notice", "cta", "recommendation", "personal_decision", "current_availability"})
FAMILIES = frozenset({"tax_guidance", "appeal", "service_capacity", "service_process", "evaluation", "regulatory", "assurance", "resource_flow", "cash_assistance", "programme", "hosted_submission"})

class Disposition(StrEnum): ALLOW="ALLOW"; ALLOW_WITH_QUALIFICATION="ALLOW_WITH_QUALIFICATION"; ABSTAIN="ABSTAIN"
class EvaluationGrain(StrEnum): PROPOSITION="proposition"; CLAUSE="clause"; SECTION_CARD="section_card"; WHOLE_ANSWER="whole_answer"
class TypedBinding(BaseModel):
    """A governed, inspectable binding used by a claim family.

    ``governed_ref`` supplies lineage; it is deliberately insufficient on its
    own.  The declared components carry the family-specific truth conditions.
    """
    model_config=ConfigDict(extra="forbid", frozen=True)
    family: str
    governed_ref: str
    components: tuple[str, ...]
class PolicyInput(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    answer_intent:str|None=None; claim_family:str|None=None; authority_source_role:str|None=None
    currentness:str|None=None; scope:str|None=None; coverage:str|None=None
    governed_input_refs:tuple[str,...]=(); typed_bindings:tuple[TypedBinding,...]=()
    claimant_ref:str|None=None; host_ref:str|None=None; composition:str|None=None
class RequiredQualifier(BaseModel): model_config=ConfigDict(extra="forbid", frozen=True); code:str; text:str
class CompatibilityAudit(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    policy_version:str=POLICY_VERSION; disposition:Disposition; grain:EvaluationGrain; reason_codes:tuple[str,...]=()
    governed_inputs:PolicyInput; governed_input_refs:tuple[str,...]=(); required_qualifiers:tuple[RequiredQualifier,...]=()
    def with_wording_review(self,_review:Mapping[str,Any])->"CompatibilityAudit": return self

def _q(code:str,text:str)->RequiredQualifier: return RequiredQualifier(code=code,text=text)
_BINDING_ALTERNATIVES = {
    "service_capacity": (frozenset({"capacity_context"}), frozenset({"access_context"})),
    "service_process": (frozenset({"process_context"}),),
    "evaluation": (frozenset({"population", "comparator", "horizon"}), frozenset({"arm", "outcome", "unit", "estimand"})),
    "assurance": (frozenset({"subject", "period", "limitation"}),),
    "resource_flow": (frozenset({"pool", "programme"}),),
    "cash_assistance": (frozenset({"arrangement"}),),
}
def _has_complete_binding(x: PolicyInput) -> bool:
    alternatives = _BINDING_ALTERNATIVES.get(x.claim_family)
    if alternatives is None: return True
    return any(
        binding.family == x.claim_family and bool(binding.governed_ref)
        and any(required <= set(binding.components) for required in alternatives)
        for binding in x.typed_bindings
    )
def evaluate_compatibility(inputs:PolicyInput|Mapping[str,Any],*,grain:EvaluationGrain=EvaluationGrain.PROPOSITION)->CompatibilityAudit:
    x=inputs if isinstance(inputs,PolicyInput) else PolicyInput.model_validate(inputs); reasons=[]; qualifiers=[]
    for name in POLICY_DIMENSIONS:
        if getattr(x,name) in (None,""): reasons.append("MISSING_"+name.upper())
    if x.answer_intent not in INTENTS: reasons.append("UNDECLARED_INTENT")
    if x.claim_family not in FAMILIES: reasons.append("UNKNOWN_FAMILY")
    if not x.governed_input_refs: reasons.append("MISSING_PROVENANCE")
    if x.currentness in {"unknown","superseded","incompatible"}: reasons.append("STALE_OR_INCOMPATIBLE_TIME")
    elif x.currentness=="stale": qualifiers.append(_q("CURRENTNESS_LIMIT","Historical or captured-time framing is required."))
    if x.scope in {"uplift","leakage","unknown"}: reasons.append("SCOPE_UPLIFT")
    if x.coverage in {"unknown","retrieval_failed"}: reasons.append("COVERAGE_UNKNOWN")
    elif x.coverage in {"not_found_in_source","not_available_from_source"}: qualifiers.append(_q("COVERAGE_LIMIT","Source coverage is bounded."))
    if x.authority_source_role in {"unknown","unverified","host_only"}: reasons.append("AUTHORITY_UPLIFT")
    if x.host_ref and x.host_ref != x.claimant_ref: reasons.append("HOST_IS_NOT_CLAIMANT")
    if x.answer_intent in {"cta","recommendation","personal_decision","current_availability"}: reasons.append("CTA_OR_LINK_CONFLICT")
    if x.composition in {"section_conflict","cta_link_conflict"}: reasons.append("SECTION_COMPOSITION_CONFLICT" if x.composition=="section_conflict" else "CTA_OR_LINK_CONFLICT")
    # Binding completeness is evaluated only inside an otherwise compatible
    # factual envelope.  A decisive CTA/coverage/composition refusal must not
    # pretend to diagnose unrelated archived binding absence.
    if not reasons and not _has_complete_binding(x): reasons.append("MISSING_TYPED_BINDING")
    return CompatibilityAudit(disposition=Disposition.ABSTAIN if reasons else (Disposition.ALLOW_WITH_QUALIFICATION if qualifiers else Disposition.ALLOW),grain=grain,reason_codes=tuple(dict.fromkeys(reasons)),governed_inputs=x,governed_input_refs=x.governed_input_refs,required_qualifiers=tuple(dict.fromkeys(qualifiers)))

def compose_audits(audits:tuple[CompatibilityAudit,...],*,grain:EvaluationGrain)->CompatibilityAudit:
    if not audits: return evaluate_compatibility({},grain=grain)
    first=audits[0]; ds={a.disposition for a in audits}; disposition=Disposition.ABSTAIN if Disposition.ABSTAIN in ds else Disposition.ALLOW_WITH_QUALIFICATION if Disposition.ALLOW_WITH_QUALIFICATION in ds else Disposition.ALLOW
    return CompatibilityAudit(disposition=disposition,grain=grain,governed_inputs=first.governed_inputs,reason_codes=tuple(dict.fromkeys(c for a in audits for c in a.reason_codes)),governed_input_refs=tuple(dict.fromkeys(v for a in audits for v in a.governed_input_refs)),required_qualifiers=tuple(dict.fromkeys(v for a in audits for v in a.required_qualifiers)))

__all__=["CompatibilityAudit","Disposition","EvaluationGrain","POLICY_DIMENSIONS","POLICY_VERSION","PolicyInput","RequiredQualifier","TypedBinding","compose_audits","evaluate_compatibility"]
