"""Deterministic bridge from frozen question bindings to v1.5 contracts."""
from __future__ import annotations
import copy
import hashlib
import json
from typing import Any, Mapping

from .generic_discovery_contract import compile_template_contract

SCHEMA = "charitygraph.gate3.execution-envelope/v1"
VERSION = "1.0"

class ExecutionEnvelopeError(ValueError): pass

def _sha(value: Any) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))+"\n").encode()).hexdigest()

def _operation(value: Any) -> str:
    if isinstance(value, Mapping): value = value.get("operation")
    if not isinstance(value, str): raise ExecutionEnvelopeError("bound requested operation is not machine-readable")
    return value

def build_envelope(instance: Mapping[str, Any], template: Mapping[str, Any]) -> dict[str, Any]:
    """Join exact frozen contracts; no prose parsing or selected-case policy."""
    if instance.get("final_template_identity") != template.get("final_template_identity"):
        raise ExecutionEnvelopeError("template version identity mismatch")
    if _operation(instance.get("requested_operation")) != template.get("operation"):
        raise ExecutionEnvelopeError("frozen operation mismatch")
    compiled = compile_template_contract(template)
    bindings = instance.get("bound_user_choice_parameters")
    if not isinstance(bindings, list): raise ExecutionEnvelopeError("bound user parameters must be a list")
    expected = {item["slot_id"]: item["exact_value"] for item in compiled["user_inputs"]}
    observed = {item.get("slot_id"): item.get("exact_value") for item in bindings}
    if observed != expected: raise ExecutionEnvelopeError("bound user parameters do not exactly match the frozen template contract")
    subject = instance.get("governed_subject")
    if not isinstance(subject, Mapping) or not isinstance(subject.get("governed_subject_id"), str):
        raise ExecutionEnvelopeError("governed opaque subject identity is missing")
    envelope = {"schema": SCHEMA, "version": VERSION, "bound_question_identity": instance["bound_question_identity"],
        "question_text": instance["question_text"], "subject": copy.deepcopy(dict(subject)),
        "diagnostic_classification": instance.get("diagnostic_classification"), "template_contract": compiled,
        "frozen_scope": instance["referent_and_scope"], "frozen_time": instance["temporal_constraints"],
        "frozen_evidence_obligations": copy.deepcopy(instance["evidence_obligations"]),
        "frozen_partial_answer_behaviour": copy.deepcopy(instance["valid_partial_answer_behaviour"]),
        "contract_fit_status": instance["contract_fit_status"],
        "outcome": "LOSSLESSLY_ENVELOPED", "mechanically_executable": True}
    envelope["envelope_identity"] = "envelope:" + _sha(envelope)
    return envelope

def build_envelopes(instances: list[Mapping[str, Any]], templates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    index = {item.get("final_template_identity"): item for item in templates}
    if len(index) != 36 or len(instances) != 36: raise ExecutionEnvelopeError("exactly 36 template contracts and bound instances are required")
    result=[]
    for instance in instances:
        template=index.get(instance.get("final_template_identity"))
        if template is None: raise ExecutionEnvelopeError("no exact template version match")
        result.append(build_envelope(instance, template))
    if len({row["bound_question_identity"] for row in result}) != 36: raise ExecutionEnvelopeError("duplicate bound question identity")
    return result
