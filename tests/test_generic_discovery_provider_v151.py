from __future__ import annotations

import copy

import pytest

from charitygraph.generic_discovery_contract import (
    GenericDiscoveryContractError,
    UNSPECIFIED,
    compile_template_contract,
)
from charitygraph.generic_discovery_provider_v151 import (
    PROVIDER_INTERFACE,
    assert_same_selected_subjects,
    render_prompt,
    response_schema,
    schema_sha256,
    validate_provider_result,
)
from test_generic_discovery_contract import _template


def _contract():
    return compile_template_contract(_template())


def _result(state="SUPPORTED", *, answer_variable="event", evidence_ids=None, qualification=None):
    return {
        "state": state,
        "records": [] if evidence_ids is None else [{
            "answer_variable": answer_variable,
            "answer_text": "A synthetic dated event",
            "evidence_ids": evidence_ids,
            "qualification": qualification,
        }],
        "qualification": qualification,
        "enumeration_state": UNSPECIFIED,
        "exhaustiveness_evidence_ids": [],
        "negative_conclusion": False,
    }


def test_v151_strict_schema_binds_variables_states_and_all_nested_packet_ids():
    contract = _contract()
    schema = response_schema(contract, ["ev:a", "ev:b"])
    assert schema["additionalProperties"] is False
    assert schema["properties"]["state"]["enum"] == contract["permitted_states"]
    record = schema["properties"]["records"]["items"]
    assert record["properties"]["answer_variable"]["enum"] == ["event", "event_time"]
    assert record["properties"]["evidence_ids"]["items"]["enum"] == ["ev:a", "ev:b"]
    assert schema["properties"]["exhaustiveness_evidence_ids"]["items"]["enum"] == ["ev:a", "ev:b"]
    assert len(schema_sha256(contract, ["ev:a", "ev:b"])) == 64
    assert PROVIDER_INTERFACE.endswith("v1.5.1")


def test_supported_partial_and_not_established_results_remain_distinct():
    contract = _contract()
    validate_provider_result(contract, _result(evidence_ids=["ev:a"]), ["ev:a"])
    partial = _result("PARTIAL", evidence_ids=["ev:a"], qualification="Only the dated event is established.")
    validate_provider_result(contract, partial, ["ev:a"])
    missing = _result("MISSING")
    missing["state"] = "MISSING"
    validate_provider_result(contract, missing, ["ev:a"])


def test_partial_requires_qualification_and_cited_records():
    contract = _contract()
    with pytest.raises(GenericDiscoveryContractError, match="qualification"):
        validate_provider_result(contract, _result("PARTIAL", evidence_ids=["ev:a"]), ["ev:a"])
    empty_partial = _result("PARTIAL", qualification="Bounded partial.")
    with pytest.raises(GenericDiscoveryContractError, match="requires evidence-backed records"):
        validate_provider_result(contract, empty_partial, ["ev:a"])


def test_packet_evidence_ids_are_checked_for_records_and_exhaustiveness():
    contract = _contract()
    with pytest.raises(GenericDiscoveryContractError, match="outside this packet"):
        validate_provider_result(contract, _result(evidence_ids=["ev:outside"]), ["ev:a"])
    result = _result("MISSING")
    result["enumeration_state"] = "EXHAUSTIVE"
    result["exhaustiveness_evidence_ids"] = ["ev:outside"]
    with pytest.raises(GenericDiscoveryContractError, match="exhaustiveness evidence ID"):
        validate_provider_result(contract, result, ["ev:a"])


def test_unsupported_positive_or_negative_certainty_fails_closed():
    contract = _contract()
    with pytest.raises(GenericDiscoveryContractError, match="outside this packet"):
        validate_provider_result(contract, _result(evidence_ids=["ev:outside"]), ["ev:a"])
    negative = _result("MISSING")
    negative["negative_conclusion"] = True
    with pytest.raises(GenericDiscoveryContractError, match="negative conclusions"):
        validate_provider_result(contract, negative, ["ev:a"])
    exhaustive = copy.deepcopy(negative)
    exhaustive["enumeration_state"] = "EXHAUSTIVE"
    exhaustive["exhaustiveness_evidence_ids"] = ["ev:a"]
    validate_provider_result(contract, exhaustive, ["ev:a"])


def test_empty_packet_schema_allows_only_not_established_empty_response():
    contract = _contract()
    schema = response_schema(contract, [])
    assert schema["properties"]["records"]["maxItems"] == 0
    assert schema["properties"]["exhaustiveness_evidence_ids"]["maxItems"] == 0
    validate_provider_result(contract, _result("MISSING"), [])
    with pytest.raises(GenericDiscoveryContractError, match="outside this packet"):
        validate_provider_result(contract, _result(evidence_ids=["ev:invented"]), [])


def test_prompt_is_generic_and_preserves_frozen_question_contract_and_identity():
    contract = _contract()
    prompt = render_prompt(
        contract=contract,
        question_text="Frozen synthetic question?",
        subject={"governed_subject_id": "opaque:subject-1"},
        identity_bindings=[{"authority": "synthetic", "identifier": "S-1"}],
        evidence=[{"evidence_id": "ev:a", "representation": "synthetic fact", "sha256": "a" * 64}],
    )
    assert "Frozen synthetic question?" in prompt
    assert "opaque:subject-1" in prompt
    assert "generic" in prompt.lower()
    assert "outside knowledge" in prompt


def test_preparation_refuses_subject_set_drift_before_packet_compilation():
    selection = {"instances": [{"subject": {"abn": f"{index:011d}"}} for index in range(36)]}
    packets = {"packets": [{"envelope": {"subject": {
        "external_authority_identifiers": [{"authority": "ACNC", "scheme": "ABN", "value": f"{index:011d}"}]
    }}} for index in range(36)]}
    assert_same_selected_subjects(selection, packets)
    changed = copy.deepcopy(packets)
    changed["packets"][0]["envelope"]["subject"]["external_authority_identifiers"][0]["value"] = "99999999999"
    with pytest.raises(ValueError, match="overlap=35"):
        assert_same_selected_subjects(selection, changed)
