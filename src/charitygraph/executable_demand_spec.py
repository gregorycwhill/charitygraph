"""Lossless candidate executable-demand specifications.

The Semantic Demand Catalogue describes question families.  This module makes
the boundary explicit when a selected subject and a catalogue definition do
not yet constitute an executable, instance-specific demand.  It is purely
structural: it never reads evidence, interprets prose, or supplies a default
for a missing semantic parameter.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping


SPECIFICATION_SCHEMA = "charitygraph.executable-demand-specification/v1"
SPECIFICATION_VERSION = "1"

CATALOGUE_FIELDS = (
    "id", "short_name", "family", "semantic_definition",
    "allowed_subject_types", "required_parameters", "optional_parameters",
    "scope_semantics", "temporal_semantics", "applicability_preconditions",
    "positive_proposition", "evidence_role_expectations", "answer_states",
    "missingness_cautions", "current_canonical_provenance",
)


class DemandSpecificationError(ValueError):
    """Raised when frozen catalogue/selection lineage is not exact."""


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _frozen_catalogue_signature(definition: Mapping[str, Any]) -> dict[str, Any]:
    result = {field: copy.deepcopy(definition[field]) for field in CATALOGUE_FIELDS}
    result["semantic_signature_sha256"] = _sha(result)
    return result


def specification_identity(specification: Mapping[str, Any]) -> str:
    """Return an identity for the complete proposed demand bytes.

    Deliberately include unresolved fields and choice status so an edited
    question cannot accidentally retain an earlier candidate identity.
    """
    body = {key: value for key, value in specification.items() if key != "specification_id"}
    return "demand-spec:" + _sha(body)


def compile_candidate_specification(
    *,
    selection_instance: Mapping[str, Any],
    catalogue_definition: Mapping[str, Any],
    selection_manifest_sha256: str,
) -> dict[str, Any]:
    """Map frozen inputs to an incomplete-or-complete candidate specification.

    A value is resolved only if it is already present in the frozen subject or
    the catalogue itself.  Catalogue prose is preserved as a catalogue
    constraint; it is never promoted into a concrete instance parameter.
    """
    if not isinstance(selection_manifest_sha256, str) or len(selection_manifest_sha256) != 64:
        raise DemandSpecificationError("selection manifest identity must be a SHA-256")
    demand_id = selection_instance.get("demand_definition_id")
    if demand_id != catalogue_definition.get("id"):
        raise DemandSpecificationError("selection demand identity does not match catalogue definition")
    subject = selection_instance.get("subject")
    if not isinstance(subject, Mapping) or not isinstance(subject.get("subject_id"), str):
        raise DemandSpecificationError("selection instance lacks governed subject identity")
    signature = selection_instance.get("semantic_signature")
    expected_signature = _frozen_catalogue_signature(catalogue_definition)
    if signature != expected_signature:
        raise DemandSpecificationError("selection semantic signature is not an exact frozen catalogue projection")
    if selection_instance.get("semantic_signature_sha256") != expected_signature["semantic_signature_sha256"]:
        raise DemandSpecificationError("selection semantic signature hash is not exact")

    required_parameters = tuple(catalogue_definition["required_parameters"])
    resolved_parameters: list[dict[str, Any]] = []
    unresolved_parameters: list[dict[str, str]] = []
    for parameter in required_parameters:
        if parameter == "subject":
            resolved_parameters.append({
                "parameter": "subject",
                "value": copy.deepcopy(dict(subject)),
                "provenance": "frozen_selection.subject",
            })
        else:
            unresolved_parameters.append({
                "parameter": parameter,
                "reason": "not_bound_by_frozen_catalogue_or_selection",
            })

    inherited = {
        "catalogue_demand_identity": catalogue_definition["id"],
        "catalogue_short_name": catalogue_definition["short_name"],
        "catalogue_family": catalogue_definition["family"],
        "catalogue_proposition_template": catalogue_definition["positive_proposition"],
        "catalogue_proposition_template_sha256": _sha(catalogue_definition["positive_proposition"]),
        "scope_constraints": catalogue_definition["scope_semantics"],
        "temporal_constraints": catalogue_definition["temporal_semantics"],
        "evidence_standard": copy.deepcopy(catalogue_definition["evidence_role_expectations"]),
        "catalogue_intent": catalogue_definition["semantic_definition"],
        "forbidden_inference_constraints": [catalogue_definition["missingness_cautions"]],
        "applicability_preconditions": copy.deepcopy(catalogue_definition["applicability_preconditions"]),
        "allowed_subject_types": copy.deepcopy(catalogue_definition["allowed_subject_types"]),
        "answer_states": copy.deepcopy(catalogue_definition["answer_states"]),
    }
    required_choices = [
        {"field": "exact_referent_and_scope", "reason": "catalogue permits types and states scope constraints but does not bind an instance scope"},
        {"field": "concrete_proposition", "reason": "catalogue provides a proposition template, not an instance proposition"},
        {"field": "relationship_or_operation", "reason": "catalogue family/definition does not bind an instance operation or relationship"},
        {"field": "semantic_joins", "reason": "no instance-specific joins are frozen in the selection"},
        {"field": "temporal_anchor", "reason": "catalogue temporal semantics do not supply a period, as-of date, or event window"},
    ]
    v14_lowering = {
        "status": "NOT_EXECUTABLE",
        "lossless_serialization_available": {
            "intent": "catalogue_intent",
            "evidence_standard": "evidence_standard",
            "forbidden_inferences": "forbidden_inference_constraints",
            "scope_constraints": "scope_constraints",
            "temporal_constraints": "temporal_constraints",
        },
        "materially_unbound_v1_4_fields": [
            "propositions", "subjects_at_instance_scope", "joins", "operations", "temporal_instance_requirement",
        ],
        "reason": "v1.4 requires concrete proposition and typed demand requirements; structural serialization cannot create their missing instance values",
    }
    specification: dict[str, Any] = {
        "schema": SPECIFICATION_SCHEMA,
        "specification_version": SPECIFICATION_VERSION,
        "state": "CANDIDATE_INCOMPLETE",
        "selection_manifest_sha256": selection_manifest_sha256,
        "selection_instance_id": selection_instance["instance_id"],
        "domain_stratum": selection_instance["domain_stratum"],
        "catalogue_signature_sha256": expected_signature["semantic_signature_sha256"],
        "catalogue_fields_explicitly_supplied": copy.deepcopy(expected_signature),
        "resolved_subject": copy.deepcopy(dict(subject)),
        "resolved_required_parameters": resolved_parameters,
        "unresolved_required_parameters": unresolved_parameters,
        "deterministically_derived": inherited,
        "required_semantic_choices": required_choices,
        "unresolved_specification_parameters": [item["parameter"] for item in unresolved_parameters] + [item["field"] for item in required_choices],
        "semantic_equivalence": "CATALOGUE_MEANING_PRESERVED_BUT_INSTANCE_QUESTION_UNSPECIFIED",
        "material_question_change_made": False,
        "executable_under_v1_4": False,
        "v1_4_lowering": v14_lowering,
        "source_availability_consulted": False,
        "oracle_content_consulted": False,
    }
    specification["specification_id"] = specification_identity(specification)
    return specification


def oracle_compatibility(specification: Mapping[str, Any]) -> dict[str, str | bool]:
    """State the oracle consequence without examining oracle content."""
    material_change = bool(specification.get("material_question_change_made"))
    executable = bool(specification.get("executable_under_v1_4"))
    if material_change:
        status = "INDEPENDENT_ORACLE_RECONSTRUCTION_OR_REVALIDATION_REQUIRED"
    elif not executable:
        status = "ORACLE_CANNOT_BE_APPLIED_UNTIL_INSTANCE_QUESTION_IS_FROZEN"
    else:
        status = "COMPATIBILITY_REQUIRES_INDEPENDENT_CONFIRMATION"
    return {
        "status": status,
        "existing_oracle_automatically_reusable": False,
        "reason": "candidate identity is not a substitute for an independently frozen question and oracle alignment review",
    }


def proposed_material_revision_identity(
    *,
    base_specification: Mapping[str, Any],
    chosen_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    """Identify, but do not approve or execute, a material question revision."""
    if not chosen_parameters:
        raise DemandSpecificationError("a material revision must name its chosen parameters")
    revision = {
        "schema": SPECIFICATION_SCHEMA,
        "revision_kind": "PROPOSED_MATERIAL_QUESTION_REVISION",
        "base_specification_id": base_specification.get("specification_id"),
        "chosen_parameters": copy.deepcopy(dict(chosen_parameters)),
        "product_owner_review_required": True,
        "oracle_status": "INDEPENDENT_ORACLE_RECONSTRUCTION_OR_REVALIDATION_REQUIRED",
        "not_executable": True,
    }
    revision["revision_id"] = "demand-spec-revision:" + _sha(revision)
    return revision
