from __future__ import annotations

import copy
import hashlib
import json

import pytest

from charitygraph.executable_demand_spec import (
    CATALOGUE_FIELDS,
    DemandSpecificationError,
    compile_candidate_specification,
    oracle_compatibility,
    proposed_material_revision_identity,
    specification_identity,
)


def _definition(*, required_parameters: list[str] | None = None) -> dict:
    return {
        "id": "SDC-TEST", "short_name": "test_demand", "family": "test",
        "semantic_definition": "Assess the supplied test demand without adding facts.",
        "allowed_subject_types": ["organisation", "service"],
        "required_parameters": required_parameters or ["subject", "scope", "period"],
        "optional_parameters": ["metric"],
        "scope_semantics": "Scope remains exact and is not broadened.",
        "temporal_semantics": "Use the specified period only.",
        "applicability_preconditions": ["a concrete proposition is specified"],
        "positive_proposition": "What concrete test proposition is evidenced?",
        "evidence_role_expectations": ["first-party source"],
        "answer_states": ["SUPPORTED", "MISSING"],
        "missingness_cautions": "No record is not proof of absence.",
        "current_canonical_provenance": ["TEST"],
    }


def _signature(definition: dict) -> dict:
    result = {field: copy.deepcopy(definition[field]) for field in CATALOGUE_FIELDS}
    result["semantic_signature_sha256"] = hashlib.sha256(
        (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    return result


def _instance(definition: dict) -> dict:
    signature = _signature(definition)
    return {
        "instance_id": "instance:fixture", "domain_stratum": 1,
        "demand_definition_id": definition["id"],
        "semantic_signature": signature,
        "semantic_signature_sha256": signature["semantic_signature_sha256"],
        "subject": {
            "subject_id": "subject:fixture", "abn": "12345678901",
            "display_name": "Fixture Charity", "identity_authority_source_record_id": "srcrec:fixture",
            "identity_authority_artifact_sha256": "a" * 64,
        },
    }


def _candidate(definition: dict | None = None) -> dict:
    definition = definition or _definition()
    return compile_candidate_specification(
        selection_instance=_instance(definition), catalogue_definition=definition,
        selection_manifest_sha256="b" * 64,
    )


def test_lossless_catalogue_to_candidate_mapping_and_resolved_subject() -> None:
    definition = _definition()
    candidate = _candidate(definition)
    supplied = candidate["catalogue_fields_explicitly_supplied"]
    assert supplied == _signature(definition)
    assert candidate["resolved_subject"]["subject_id"] == "subject:fixture"
    assert candidate["resolved_required_parameters"] == [{
        "parameter": "subject", "value": _instance(definition)["subject"],
        "provenance": "frozen_selection.subject",
    }]


def test_candidate_identity_is_deterministic_and_covers_full_content() -> None:
    candidate = _candidate()
    repeated = _candidate()
    assert candidate["specification_id"] == repeated["specification_id"]
    changed = copy.deepcopy(candidate)
    changed["unresolved_specification_parameters"].append("new_parameter")
    assert specification_identity(changed) != candidate["specification_id"]


def test_required_parameter_missingness_is_explicit_without_defaults() -> None:
    candidate = _candidate(_definition(required_parameters=["service", "population", "period"]))
    assert candidate["resolved_required_parameters"] == []
    assert [item["parameter"] for item in candidate["unresolved_required_parameters"]] == ["service", "population", "period"]
    assert candidate["executable_under_v1_4"] is False


def test_signature_mismatch_rejects_an_unsupported_default() -> None:
    definition = _definition()
    instance = _instance(definition)
    instance["semantic_signature"]["scope_semantics"] = "Default scope: organisation."
    with pytest.raises(DemandSpecificationError, match="exact frozen catalogue projection"):
        compile_candidate_specification(
            selection_instance=instance, catalogue_definition=definition,
            selection_manifest_sha256="b" * 64,
        )


def test_referent_relation_and_temporal_meaning_remain_unresolved_not_rewritten() -> None:
    candidate = _candidate()
    derived = candidate["deterministically_derived"]
    assert derived["scope_constraints"] == "Scope remains exact and is not broadened."
    assert derived["temporal_constraints"] == "Use the specified period only."
    assert {item["field"] for item in candidate["required_semantic_choices"]} >= {
        "exact_referent_and_scope", "relationship_or_operation", "temporal_anchor",
    }


def test_source_availability_cannot_change_candidate_specification() -> None:
    definition = _definition()
    instance = _instance(definition)
    source_marked = copy.deepcopy(instance)
    source_marked["untrusted_source_availability"] = {"annual_report": "available"}
    ordinary = compile_candidate_specification(
        selection_instance=instance, catalogue_definition=definition,
        selection_manifest_sha256="b" * 64,
    )
    marked = compile_candidate_specification(
        selection_instance=source_marked, catalogue_definition=definition,
        selection_manifest_sha256="b" * 64,
    )
    assert marked == ordinary
    assert marked["source_availability_consulted"] is False


def test_material_revision_gets_new_identity_and_blocks_oracle_reuse() -> None:
    candidate = _candidate()
    revision = proposed_material_revision_identity(
        base_specification=candidate,
        chosen_parameters={"scope": "a newly chosen scope"},
    )
    assert revision["revision_id"] != candidate["specification_id"]
    assert revision["oracle_status"] == "INDEPENDENT_ORACLE_RECONSTRUCTION_OR_REVALIDATION_REQUIRED"
    assert oracle_compatibility(candidate)["existing_oracle_automatically_reusable"] is False
