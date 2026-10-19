"""Versioned generic template-demand contract for source-blind question design.

This module is intentionally structural.  It accepts the independently
authored template-contract artefacts, preserves their supplied natural-language
semantics, and validates mechanical result boundaries.  It does not infer an
operation from prose, read evidence, resolve a subject, or manufacture a user
input from a discoverable answer variable.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping, Sequence


CONTRACT_SCHEMA = "charitygraph.generic-discovery-demand-contract/v1.5"
CONTRACT_VERSION = "1.5"
UNKNOWN = "UNKNOWN"
UNSPECIFIED = "UNSPECIFIED"
MISSING_FROM_FROZEN_SPECIFICATION = "MISSING_FROM_FROZEN_SPECIFICATION"


class GenericDiscoveryContractError(ValueError):
    """Raised when an approved contract cannot be lowered without alteration."""


# This is a closed mapping of exact, independently supplied operation strings
# to versioned mechanical families.  It is not lexical classification: a new
# operation requires an explicit contract/version change.
_OPERATION_FAMILIES = {
    "Resolve the legal or operating subject and reporting scope used by a proposition.": "SUBJECT_SCOPE_DISCOVERY",
    "Return an authority-scoped designation or governed classification without extending it into quality or restriction claims.": "AUTHORITY_SCOPED_DESIGNATION",
    "Test an evidenced purpose, cause or beneficiary proposition for a subject.": "PURPOSE_BENEFICIARY_DISCOVERY",
    "Find a service and its evidenced delivery geography for a population and period.": "SERVICE_DELIVERY_DISCOVERY",
    "Assess whether a population can access a service, including eligibility, route and current availability.": "SERVICE_ACCESS_DISCOVERY",
    "Describe attributed activity or output and refuse unsupported conversion into outcome or causal-effect claims.": "ACTIVITY_OUTPUT_DISCOVERY",
    "Conditionally identify evidence of delivery geography and population for the named service, without presupposing that the future governed subject operated or delivered it.": "CONDITIONAL_SERVICE_DELIVERY_DISCOVERY",
    "Describe evidenced participation, volunteer or member contribution separately from employment and service delivery.": "PARTICIPATION_DISCOVERY",
    "Describe a fundraising appeal or actionable giving offer and its attributed activity without converting total revenue into method-specific proceeds.": "GIVING_OFFER_DISCOVERY",
    "Report evidenced operational capacity, constraints and scale with metric definition and denominator.": "CAPACITY_DISCOVERY",
    "Return evidenced leadership roles, governance arrangements and organisational capability within stated scope and time.": "ROLE_CAPABILITY_DISCOVERY",
    "Compare or aggregate a financial measure only after scope, currency, denominator and accounting basis are reconciled.": "FINANCIAL_COMPARISON",
    "Reproduce the user-selected analytical method with source, filter, denominator, release, and compatibility lineage for the future governed subject.": "ANALYTICAL_REPRODUCTION",
    "Map evidenced funder, partner and delivery dependencies, distinguishing commitment, receipt and recognised revenue.": "RELATIONSHIP_DISCOVERY",
    "Return authority-scoped conduct, restriction, allegation, correction and supersession states, separating findings from claims.": "AUTHORITY_RECORD_DISCOVERY",
    "Test a stated values, ethos or mandate commitment without treating it as proof of conduct or outcome.": "COMMITMENT_IMPLEMENTATION_DISCOVERY",
    "Return dated historical events or metric changes with succession and scope preserved.": "HISTORICAL_CHANGE_DISCOVERY",
    "Return dated historical metric/event change between the stated calendar years with predecessor and successor scope preserved.": "HISTORICAL_COMPARISON",
    "Compare evaluation evidence for an intervention and population, preserving design, comparator, outcome and limitations.": "EVALUATION_DISCOVERY",
    "Conditionally assess evaluation evidence for the future governed subject's defined intervention and population, preserving outcome, design, comparator, and limitations.": "CONDITIONAL_EVALUATION_DISCOVERY",
}

_REQUIRED_TEMPLATE_FIELDS = frozenset({
    "template_id", "final_template_identity", "question", "operation", "scope",
    "time", "user_parameter_slots", "approved_fixture_bindings",
    "discoverable_answer_variables", "evidence", "permitted_states",
    "template_specific_forbidden_inference", "v1_4_compatibility", "provenance",
})
_RESULT_ENUMERATION_STATES = frozenset({UNSPECIFIED, "PARTIAL", "EXHAUSTIVE"})
_NON_NEGATIVE_STATES = frozenset({"MISSING", "ABSTAIN", "TESTED_MISSINGNESS"})


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _slots(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)) and all(isinstance(item, str) for item in value):
        return list(value)
    raise GenericDiscoveryContractError("user_parameter_slots must be null, a string, or a list of strings")


def _bindings(value: Any) -> list[dict[str, Any]]:
    if value in (None, {}):
        return []
    raw = [value] if isinstance(value, Mapping) else value
    if not isinstance(raw, Sequence) or isinstance(raw, (bytes, bytearray, str)):
        raise GenericDiscoveryContractError("approved_fixture_bindings must be an object, list, or null")
    result = []
    for item in raw:
        if not isinstance(item, Mapping) or not isinstance(item.get("slot_id"), str) or "exact_value" not in item:
            raise GenericDiscoveryContractError("each approved parameter binding requires slot_id and exact_value")
        result.append(copy.deepcopy(dict(item)))
    return result


def _answer_variables(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)) or not all(isinstance(item, str) and item for item in value):
        raise GenericDiscoveryContractError("discoverable_answer_variables must be a non-empty list of strings")
    return [{
        "name": item,
        "value_source": "EVIDENCE_DISCOVERED",
        "type": MISSING_FROM_FROZEN_SPECIFICATION,
        "cardinality": MISSING_FROM_FROZEN_SPECIFICATION,
        "enumeration": UNSPECIFIED,
    } for item in value]


def generic_discovery_contract_schema() -> dict[str, Any]:
    """Return a compact, serialisable schema description for v1.5 outputs."""
    return {
        "schema": CONTRACT_SCHEMA,
        "version": CONTRACT_VERSION,
        "identity": "opaque CharityGraph subject binding is supplied only at execution; ABN is an external authority-scoped join key, never the subject identity",
        "input_output_separation": {
            "user_inputs": "only frozen approved user-parameter slots",
            "answer_variables": "evidence-discovered values; they must never be promoted to inputs",
        },
        "unspecified_semantics": {
            "answer_variable_type": MISSING_FROM_FROZEN_SPECIFICATION,
            "answer_variable_cardinality": MISSING_FROM_FROZEN_SPECIFICATION,
            "geographic_constraint": UNSPECIFIED,
            "behaviour": "no default cardinality, exhaustiveness, national coverage, unrestricted coverage, or geographic irrelevance",
        },
        "enumeration_states": sorted(_RESULT_ENUMERATION_STATES),
        "safe_result_rule": "absence of evidence is not a negative fact; exhaustive/negative conclusions require explicit exhaustive evidence",
        "operation_families": sorted(set(_OPERATION_FAMILIES.values())),
    }


def compile_template_contract(template: Mapping[str, Any]) -> dict[str, Any]:
    """Lower one approved template without interpreting or supplementing it."""
    missing = _REQUIRED_TEMPLATE_FIELDS - set(template)
    if missing:
        raise GenericDiscoveryContractError(f"template omits required fields: {sorted(missing)}")
    operation = template["operation"]
    if operation not in _OPERATION_FAMILIES:
        raise GenericDiscoveryContractError("template operation is not in the approved v1.5 operation registry")
    compatibility = template["v1_4_compatibility"]
    if compatibility not in {"DIRECT_FIT", "CONTRACT_FIT_GAP"}:
        raise GenericDiscoveryContractError("v1_4_compatibility must be DIRECT_FIT or CONTRACT_FIT_GAP")

    slots = _slots(template["user_parameter_slots"])
    bindings = _bindings(template["approved_fixture_bindings"])
    binding_slots = [item["slot_id"] for item in bindings]
    if set(slots) != set(binding_slots) or len(slots) != len(set(slots)) or len(binding_slots) != len(set(binding_slots)):
        raise GenericDiscoveryContractError("approved bindings must exactly cover the declared user parameter slots")
    answer_variables = _answer_variables(template["discoverable_answer_variables"])
    answer_names = {item["name"] for item in answer_variables}
    if answer_names & set(slots):
        raise GenericDiscoveryContractError("a discoverable answer variable may not become a user input")
    evidence = template["evidence"]
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("expected_roles"), list) or not isinstance(evidence.get("obligation"), str):
        raise GenericDiscoveryContractError("template evidence must provide expected_roles and obligation")
    permitted_states = template["permitted_states"]
    if not isinstance(permitted_states, list) or not permitted_states or not all(isinstance(item, str) for item in permitted_states):
        raise GenericDiscoveryContractError("permitted_states must be a non-empty list of strings")

    geography_binding = next((item for item in bindings if item["slot_id"] == "geography"), None)
    compiled = {
        "schema": CONTRACT_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "template_id": template["template_id"],
        "template_identity": template["final_template_identity"],
        "question_template": template["question"],
        "operation": {"source_text": operation, "family": _OPERATION_FAMILIES[operation]},
        "subject_binding": {"state": "OPAQUE_SUBJECT_REQUIRED_AT_EXECUTION", "external_identifier_role": "AUTHORITY_SCOPED_JOIN_ONLY"},
        "user_inputs": bindings,
        "discoverable_answer_variables": answer_variables,
        "scope": {
            "source_text": template["scope"],
            "geographic_constraint": (
                {"state": "USER_SUPPLIED_CONSTRAINT", "slot_id": "geography", "exact_value": geography_binding["exact_value"]}
                if geography_binding else
                {"state": UNSPECIFIED, "behaviour": "do_not_assume_national_or_unrestricted_coverage"}
            ),
        },
        "time": {"source_text": template["time"], "event_publication_effective_distinction": "RETAIN_SOURCE_SEMANTICS"},
        "evidence_obligations": copy.deepcopy(dict(evidence)),
        "permitted_states": copy.deepcopy(permitted_states),
        "partial_and_enumeration": {
            "partial_answer_allowed": "PARTIAL" in permitted_states,
            "enumeration_state": UNSPECIFIED,
            "exhaustive_conclusion_requires": "explicit evidence of coverage/exhaustiveness",
            "empty_evidenced_set": "not proof of an empty real-world set",
        },
        "forbidden_inferences": [template["template_specific_forbidden_inference"], *(
            copy.deepcopy(template.get("successor_forbidden_inferences") or [])
        )],
        "provenance": copy.deepcopy(template["provenance"]),
        "v1_4_compatibility": compatibility,
        "lowering_disposition": "V1_4_DIRECT_FIT_PRESERVED" if compatibility == "DIRECT_FIT" else "V1_5_DISCOVERY_LOWERING",
        "representation_outcome": "REPRESENTABLE_WITH_EXPLICIT_UNSPECIFIED_FIELDS",
        "lossless_to_frozen_specification": True,
        "mechanically_executable": True,
    }
    compiled["contract_identity"] = "generic-demand:" + _sha(compiled)
    return compiled


def compile_template_contract_package(package: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compile an exact 36-contract package, failing closed on a changed shape."""
    contracts = package.get("contracts")
    if not isinstance(contracts, list) or package.get("contract_count") != 36 or len(contracts) != 36:
        raise GenericDiscoveryContractError("v1.5 requires exactly 36 final template contracts")
    compiled = [compile_template_contract(item) for item in contracts]
    template_ids = [item["template_id"] for item in compiled]
    if len(template_ids) != len(set(template_ids)):
        raise GenericDiscoveryContractError("template IDs must be unique")
    if sum(item["v1_4_compatibility"] == "DIRECT_FIT" for item in compiled) != 19:
        raise GenericDiscoveryContractError("the package must preserve exactly 19 direct-fit contracts")
    if sum(item["v1_4_compatibility"] == "CONTRACT_FIT_GAP" for item in compiled) != 17:
        raise GenericDiscoveryContractError("the package must contain exactly 17 discovery-gap contracts")
    return compiled


def validate_discovery_result(contract: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    """Mechanically reject unsafe discovery/enumeration result shapes.

    This validates a model or reviewer supplied assessment; it never decides
    whether a proposition is true.  In particular, it prevents an empty list
    or incomplete enumeration from becoming a negative conclusion.
    """
    state = result.get("state")
    if state not in contract.get("permitted_states", []):
        raise GenericDiscoveryContractError("result state is not permitted by the template contract")
    records = result.get("records", [])
    if not isinstance(records, list):
        raise GenericDiscoveryContractError("records must be a list")
    enumeration = result.get("enumeration_state", UNSPECIFIED)
    if enumeration not in _RESULT_ENUMERATION_STATES:
        raise GenericDiscoveryContractError("enumeration_state is invalid")
    exhaustive_evidence = result.get("exhaustiveness_evidence_ids", [])
    if enumeration == "EXHAUSTIVE" and (not isinstance(exhaustive_evidence, list) or not exhaustive_evidence):
        raise GenericDiscoveryContractError("an exhaustive conclusion requires explicit exhaustive evidence")
    if result.get("negative_conclusion", False) and enumeration != "EXHAUSTIVE":
        raise GenericDiscoveryContractError("negative conclusions require explicit exhaustive evidence")
    if not records and state not in _NON_NEGATIVE_STATES:
        raise GenericDiscoveryContractError("a positive, partial, or conflicted result requires evidence-backed records")
    allowed_names = {item["name"] for item in contract.get("discoverable_answer_variables", [])}
    for record in records:
        if not isinstance(record, Mapping):
            raise GenericDiscoveryContractError("each discovery record must be an object")
        values = record.get("answer_values", {})
        evidence_ids = record.get("evidence_ids", [])
        if not isinstance(values, Mapping) or not set(values).issubset(allowed_names):
            raise GenericDiscoveryContractError("record answer values must use declared discoverable variables")
        if values and (not isinstance(evidence_ids, list) or not evidence_ids):
            raise GenericDiscoveryContractError("evidence-discovered answer values require evidence IDs")
