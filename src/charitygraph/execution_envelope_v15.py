"""Deterministic bridge from frozen question bindings to v1.5 contracts."""
from __future__ import annotations
import copy
import hashlib
import json
from typing import Any, Mapping

from .generic_discovery_contract import compile_template_contract

SCHEMA = "charitygraph.gate3.execution-envelope/v1"
VERSION = "1.1"

# These are deliberately a closed, reviewed compatibility ledger rather than a
# normalisation rule.  A version spelling is accepted only where the frozen
# binding records the approved successor identity in ``source_record`` and the
# contract subsequently passes the usual operation and parameter checks.
_TEMPLATE_VERSION_ALIASES: dict[str, str] = {
    "QFT-D05B@v2": "QFT-D05B-v2",
    "QFT-D13B@v2": "QFT-D13B-v2",
    "QFT-D17B@v2": "QFT-D17B-v2",
    "QFT-D18B@v2": "QFT-D18B-v2",
}

# This is an exact frozen rendering compatibility decision, not a prose
# interpretation.  It is limited to the approved template slot and retains
# the original bound value and question text in the execution envelope.
_PARAMETER_RENDERING_ALIASES: dict[tuple[str, str, str], str] = {
    ("QFT-D08B@v1", "channel", "an online donation page"): "online donation page",
}

class ExecutionEnvelopeError(ValueError): pass

def _sha(value: Any) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))+"\n").encode()).hexdigest()

def _operation(value: Any) -> str:
    if isinstance(value, Mapping): value = value.get("operation")
    if not isinstance(value, str): raise ExecutionEnvelopeError("bound requested operation is not machine-readable")
    return value

def _approved_template_identity(instance: Mapping[str, Any], template: Mapping[str, Any]) -> tuple[str, str | None]:
    frozen_identity = instance.get("final_template_identity")
    contract_identity = template.get("final_template_identity")
    if frozen_identity == contract_identity:
        return str(contract_identity), None
    expected = _TEMPLATE_VERSION_ALIASES.get(str(frozen_identity))
    if expected != contract_identity:
        raise ExecutionEnvelopeError("template version identity mismatch")
    if template.get("template_id") != expected.rsplit("-", 1)[0]:
        raise ExecutionEnvelopeError("template version alias has a different template lineage")
    bindings = instance.get("bound_user_choice_parameters")
    source_records = {item.get("source_record") for item in bindings if isinstance(item, Mapping)} if isinstance(bindings, list) else set()
    if expected not in source_records:
        raise ExecutionEnvelopeError("template version alias lacks frozen successor lineage")
    return str(contract_identity), "VERSION_SERIALIZATION_ALIAS"

def _canonical_parameter_bindings(instance: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frozen_identity = str(instance.get("final_template_identity"))
    bindings = instance.get("bound_user_choice_parameters")
    if not isinstance(bindings, list):
        raise ExecutionEnvelopeError("bound user parameters must be a list")
    canonical: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []
    for item in bindings:
        if not isinstance(item, Mapping) or not isinstance(item.get("slot_id"), str):
            raise ExecutionEnvelopeError("bound user parameter is not machine-readable")
        slot_id = item["slot_id"]
        frozen_value = item.get("exact_value")
        canonical_value = _PARAMETER_RENDERING_ALIASES.get((frozen_identity, slot_id, str(frozen_value)), frozen_value)
        canonical[slot_id] = canonical_value
        if canonical_value != frozen_value:
            decisions.append({"type": "GRAMMATICAL_RENDERING_ALIAS", "slot_id": slot_id,
                              "frozen_value": frozen_value, "semantic_input_value": canonical_value})
    if len(canonical) != len(bindings):
        raise ExecutionEnvelopeError("duplicate bound user parameter slot")
    return canonical, decisions

def compatibility_audit_ledger() -> list[dict[str, str]]:
    """The five approved mechanical decisions, suitable for evidence packaging."""
    rows = [{"decision_id": "COMPAT-VERSION-" + key.split("@")[0], "type": "VERSION_SERIALIZATION_ALIAS",
             "frozen_identity": key, "approved_successor_identity": value,
             "verification": "lineage, operation, parameters, constraints and semantic contract must match"}
            for key, value in sorted(_TEMPLATE_VERSION_ALIASES.items())]
    rows.append({"decision_id": "COMPAT-D08B-ARTICLE", "type": "GRAMMATICAL_RENDERING_ALIAS",
                 "frozen_identity": "QFT-D08B@v1", "slot_id": "channel",
                 "frozen_value": "an online donation page", "semantic_input_value": "online donation page",
                 "verification": "exact approved template-slot mapping; frozen question text is preserved"})
    return rows

def build_envelope(instance: Mapping[str, Any], template: Mapping[str, Any]) -> dict[str, Any]:
    """Join exact frozen contracts; no prose parsing or selected-case policy."""
    _, version_decision = _approved_template_identity(instance, template)
    if _operation(instance.get("requested_operation")) != template.get("operation"):
        raise ExecutionEnvelopeError("frozen operation mismatch")
    compiled = compile_template_contract(template)
    bindings = instance.get("bound_user_choice_parameters")
    observed, parameter_decisions = _canonical_parameter_bindings(instance)
    expected = {item["slot_id"]: item["exact_value"] for item in compiled["user_inputs"]}
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
        "frozen_user_parameters": copy.deepcopy(bindings), "semantic_user_parameters": observed,
        "compatibility_decisions": parameter_decisions + ([{"type": version_decision}] if version_decision else []),
        "outcome": "LOSSLESSLY_ENVELOPED", "mechanically_executable": True}
    envelope["envelope_identity"] = "envelope:" + _sha(envelope)
    return envelope

def build_envelopes(instances: list[Mapping[str, Any]], templates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    index = {item.get("final_template_identity"): item for item in templates}
    if len(index) != 36 or len(instances) != 36: raise ExecutionEnvelopeError("exactly 36 template contracts and bound instances are required")
    result=[]
    for instance in instances:
        frozen_identity = instance.get("final_template_identity")
        template=index.get(frozen_identity) or index.get(_TEMPLATE_VERSION_ALIASES.get(str(frozen_identity)))
        if template is None: raise ExecutionEnvelopeError("no exact template version match")
        result.append(build_envelope(instance, template))
    if len({row["bound_question_identity"] for row in result}) != 36: raise ExecutionEnvelopeError("duplicate bound question identity")
    return result
