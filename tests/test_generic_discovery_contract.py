from __future__ import annotations

import copy

import pytest

from charitygraph.generic_discovery_contract import (
    GenericDiscoveryContractError,
    MISSING_FROM_FROZEN_SPECIFICATION,
    UNSPECIFIED,
    compile_template_contract,
    compile_template_contract_package,
    generic_discovery_contract_schema,
    validate_discovery_result,
)


def _template(*, direct_fit: bool = False) -> dict:
    return {
        "template_id": "SYNTHETIC-DISCOVERY-01",
        "final_template_identity": "SYNTHETIC-DISCOVERY-01@v1",
        "question": "Which examples did {subject} report during the stated period?",
        "operation": "Return dated historical events or metric changes with succession and scope preserved.",
        "scope": "The synthetic subject only; no geographic coverage is supplied.",
        "time": "The stated synthetic period.",
        "user_parameter_slots": None,
        "approved_fixture_bindings": {},
        "discoverable_answer_variables": ["event", "event_time"],
        "evidence": {"expected_roles": ["synthetic primary record"], "obligation": "Direct synthetic evidence only."},
        "permitted_states": ["SUPPORTED", "PARTIAL", "MISSING", "CONFLICTED", "ABSTAIN"],
        "template_specific_forbidden_inference": "No observed record is not proof that no event occurred.",
        "successor_forbidden_inferences": [],
        "v1_4_compatibility": "DIRECT_FIT" if direct_fit else "CONTRACT_FIT_GAP",
        "provenance": "synthetic fixture",
    }


def test_discoverable_variables_are_not_promoted_to_inputs_and_missingness_is_explicit() -> None:
    contract = compile_template_contract(_template())
    assert contract["user_inputs"] == []
    assert {item["name"] for item in contract["discoverable_answer_variables"]} == {"event", "event_time"}
    assert {item["type"] for item in contract["discoverable_answer_variables"]} == {MISSING_FROM_FROZEN_SPECIFICATION}
    assert {item["cardinality"] for item in contract["discoverable_answer_variables"]} == {MISSING_FROM_FROZEN_SPECIFICATION}
    assert contract["scope"]["geographic_constraint"]["state"] == UNSPECIFIED
    assert contract["lowering_disposition"] == "V1_5_DISCOVERY_LOWERING"


def test_bound_user_geography_is_retained_only_as_user_constraint() -> None:
    fixture = _template()
    fixture["user_parameter_slots"] = ["geography"]
    fixture["approved_fixture_bindings"] = [{"slot_id": "geography", "exact_value": "Synthetic State", "selection_rule": "synthetic"}]
    compiled = compile_template_contract(fixture)
    assert compiled["scope"]["geographic_constraint"] == {
        "state": "USER_SUPPLIED_CONSTRAINT", "slot_id": "geography", "exact_value": "Synthetic State"
    }


def test_answer_variable_cannot_be_reclassified_as_user_input() -> None:
    fixture = _template()
    fixture["user_parameter_slots"] = "event"
    fixture["approved_fixture_bindings"] = {"slot_id": "event", "exact_value": "synthetic event"}
    with pytest.raises(GenericDiscoveryContractError, match="discoverable answer variable"):
        compile_template_contract(fixture)


def test_unknown_operation_fails_closed() -> None:
    fixture = _template()
    fixture["operation"] = "Infer a new unrestricted operation from prose."
    with pytest.raises(GenericDiscoveryContractError, match="approved v1.5 operation registry"):
        compile_template_contract(fixture)


def test_direct_fit_is_preserved_without_mutating_v14() -> None:
    compiled = compile_template_contract(_template(direct_fit=True))
    assert compiled["lowering_disposition"] == "V1_4_DIRECT_FIT_PRESERVED"


def test_scope_time_relationship_evidence_and_opaque_identity_survive_lowering() -> None:
    fixture = _template()
    fixture["operation"] = "Map evidenced funder, partner and delivery dependencies, distinguishing commitment, receipt and recognised revenue."
    fixture["scope"] = "Synthetic relationships only; direction and delivery role remain distinct."
    fixture["time"] = "Synthetic event, publication, and effective times remain distinct."
    fixture["evidence"] = {"expected_roles": ["synthetic agreement", "synthetic delivery record"], "obligation": "Direct relationship evidence only."}
    compiled = compile_template_contract(fixture)
    assert compiled["operation"]["family"] == "RELATIONSHIP_DISCOVERY"
    assert compiled["scope"]["source_text"] == fixture["scope"]
    assert compiled["time"]["source_text"] == fixture["time"]
    assert compiled["evidence_obligations"] == fixture["evidence"]
    assert compiled["subject_binding"] == {
        "state": "OPAQUE_SUBJECT_REQUIRED_AT_EXECUTION",
        "external_identifier_role": "AUTHORITY_SCOPED_JOIN_ONLY",
    }


def test_zero_one_many_conflicted_and_partial_results_are_safe() -> None:
    contract = compile_template_contract(_template())
    validate_discovery_result(contract, {"state": "MISSING", "records": [], "enumeration_state": UNSPECIFIED})
    validate_discovery_result(contract, {"state": "SUPPORTED", "records": [{"answer_values": {"event": "synthetic event"}, "evidence_ids": ["ev:1"]}], "enumeration_state": UNSPECIFIED})
    validate_discovery_result(contract, {"state": "PARTIAL", "records": [{"answer_values": {"event": "one"}, "evidence_ids": ["ev:1"]}, {"answer_values": {"event": "two"}, "evidence_ids": ["ev:2"]}], "enumeration_state": "PARTIAL"})
    validate_discovery_result(contract, {"state": "CONFLICTED", "records": [{"answer_values": {"event": "one"}, "evidence_ids": ["ev:1"]}, {"answer_values": {"event": "two"}, "evidence_ids": ["ev:2"]}], "enumeration_state": UNSPECIFIED})


def test_empty_or_partial_discovery_cannot_become_a_negative_conclusion() -> None:
    contract = compile_template_contract(_template())
    with pytest.raises(GenericDiscoveryContractError, match="negative conclusions"):
        validate_discovery_result(contract, {"state": "MISSING", "records": [], "enumeration_state": UNSPECIFIED, "negative_conclusion": True})
    with pytest.raises(GenericDiscoveryContractError, match="exhaustive conclusion"):
        validate_discovery_result(contract, {"state": "MISSING", "records": [], "enumeration_state": "EXHAUSTIVE"})


def test_all_36_shape_guard_requires_19_direct_and_17_discovery_contracts() -> None:
    contracts = [_template(direct_fit=index < 19) for index in range(36)]
    for index, item in enumerate(contracts):
        item["template_id"] = f"SYNTHETIC-{index:02d}"
        item["final_template_identity"] = f"SYNTHETIC-{index:02d}@v1"
    compiled = compile_template_contract_package({"contract_count": 36, "contracts": contracts})
    assert len(compiled) == 36
    changed = copy.deepcopy(contracts)
    changed[19]["v1_4_compatibility"] = "DIRECT_FIT"
    with pytest.raises(GenericDiscoveryContractError, match="exactly 19"):
        compile_template_contract_package({"contract_count": 36, "contracts": changed})


def test_schema_declares_unknowns_and_safe_non_negative_behaviour() -> None:
    schema = generic_discovery_contract_schema()
    assert schema["unspecified_semantics"]["answer_variable_type"] == MISSING_FROM_FROZEN_SPECIFICATION
    assert "absence of evidence is not a negative fact" in schema["safe_result_rule"]
