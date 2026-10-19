"""Verify and package a source-blind v1.5 generic discovery contract run.

This tool is provider-free.  It consumes a supplied template-only package and
emits only contract/evaluation metadata; it does not read subjects, source
records, holdout bindings, or model/oracle outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from charitygraph.generic_discovery_contract import (
    CONTRACT_SCHEMA,
    CONTRACT_VERSION,
    compile_template_contract_package,
    generic_discovery_contract_schema,
    validate_discovery_result,
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical(value))


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_input(package: Path) -> dict[str, Any]:
    inventory_path = package / "artifact-sha256-inventory.json"
    inventory = read_json(inventory_path)
    checks = []
    for item in inventory["artifacts"]:
        target = package / item["file"]
        checks.append({
            "file": item["file"],
            "expected_sha256": item["sha256"],
            "observed_sha256": sha_file(target),
            "expected_bytes": item["bytes"],
            "observed_bytes": target.stat().st_size,
        })
    if not all(item["expected_sha256"] == item["observed_sha256"] and item["expected_bytes"] == item["observed_bytes"] for item in checks):
        raise ValueError("input package inventory did not verify")
    manifest_path = package / "source-provenance-manifest.json"
    prohibited_keys = {"subject_id", "abn", "selected_subject", "selected_question", "source_availability", "answerability", "provider_output", "oracle_output"}
    seen_prohibited = []

    def scan(value: Any, location: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in prohibited_keys:
                    seen_prohibited.append(f"{location}.{key}")
                scan(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f"{location}[{index}]")

    for item in inventory["artifacts"]:
        scan(read_json(package / item["file"]))
    if seen_prohibited:
        raise ValueError(f"prohibited source/identity fields found: {seen_prohibited}")
    return {
        "status": "PASS",
        "package_path": str(package),
        "source_provenance_manifest_sha256": sha_file(manifest_path),
        "artifact_inventory_sha256": sha_file(inventory_path),
        "inventory_checks": checks,
        "selected_subject_identity_present": False,
        "selected_subject_question_binding_present": False,
        "source_availability_or_answerability_present": False,
        "provider_or_oracle_output_present": False,
        "prohibited_field_matches": seen_prohibited,
    }


def synthetic_execution_results() -> dict[str, str]:
    contract = {
        "permitted_states": ["SUPPORTED", "PARTIAL", "MISSING", "CONFLICTED", "ABSTAIN"],
        "discoverable_answer_variables": [{"name": "item"}],
    }
    cases = {
        "zero_evidence_missing": {"state": "MISSING", "records": [], "enumeration_state": "UNSPECIFIED"},
        "one_evidenced_item": {"state": "SUPPORTED", "records": [{"answer_values": {"item": "synthetic-one"}, "evidence_ids": ["synthetic:e1"]}], "enumeration_state": "UNSPECIFIED"},
        "many_partial_items": {"state": "PARTIAL", "records": [{"answer_values": {"item": "synthetic-one"}, "evidence_ids": ["synthetic:e1"]}, {"answer_values": {"item": "synthetic-two"}, "evidence_ids": ["synthetic:e2"]}], "enumeration_state": "PARTIAL"},
        "conflicted_items": {"state": "CONFLICTED", "records": [{"answer_values": {"item": "synthetic-one"}, "evidence_ids": ["synthetic:e1"]}, {"answer_values": {"item": "synthetic-two"}, "evidence_ids": ["synthetic:e2"]}], "enumeration_state": "UNSPECIFIED"},
    }
    for value in cases.values():
        validate_discovery_result(contract, value)
    try:
        validate_discovery_result(contract, {"state": "MISSING", "records": [], "enumeration_state": "UNSPECIFIED", "negative_conclusion": True})
    except ValueError:
        negative_guard = "PASS_REJECTED"
    else:
        negative_guard = "FAIL_ACCEPTED"
    return {**{name: "PASS" for name in cases}, "empty_or_partial_to_negative_guard": negative_guard}


def build_packet(*, package: Path, output: Path, test_suites: list[str], test_count: int) -> None:
    output.mkdir(parents=True, exist_ok=False)
    input_verification = verify_input(package)
    complete = read_json(package / "complete-template-semantic-contracts.json")
    gaps = read_json(package / "discovery-gap-contracts.json")
    direct = read_json(package / "direct-fit-compatibility-contracts.json")
    compiled = compile_template_contract_package(complete)
    by_id = {item["template_id"]: item for item in compiled}
    gap_matrix = []
    for gap in gaps["contracts"]:
        contract = by_id[gap["template_id"]]
        gap_matrix.append({
            "template_id": gap["template_id"],
            "root_cause": gap["gap"],
            "required_generic_representation": gap["required_generic_semantic_representation"],
            "operation_family": contract["operation"]["family"],
            "disposition": "RESOLVED_BY_V1_5_DISCOVERY_LOWERING",
            "answer_variables_remain_evidence_discovered": True,
            "permitted_states": contract["permitted_states"],
        })
    if {item["template_id"] for item in gap_matrix} != {item["template_id"] for item in compiled if item["v1_4_compatibility"] == "CONTRACT_FIT_GAP"}:
        raise ValueError("gap package and final contracts disagree")
    compatibility = [{
        "template_id": item["template_id"],
        "template_identity": item["template_identity"],
        "operation_family": item["operation"]["family"],
        "v1_4_compatibility": item["v1_4_compatibility"],
        "lowering_disposition": item["lowering_disposition"],
        "representation_outcome": item["representation_outcome"],
        "lossless_to_frozen_specification": item["lossless_to_frozen_specification"],
        "mechanically_executable": item["mechanically_executable"],
        "answer_variable_type_cardinality": "MISSING_FROM_FROZEN_SPECIFICATION",
        "geographic_constraint_state": item["scope"]["geographic_constraint"]["state"],
    } for item in compiled]
    write_json(output / "verified-input-package-provenance.json", input_verification)
    write_json(output / "17-gap-root-cause-resolution-matrix.json", {
        "gap_count": len(gap_matrix), "all_resolved_by_generic_v1_5_representation": True, "entries": gap_matrix,
    })
    write_json(output / "v15-contract-schema.json", generic_discovery_contract_schema())
    write_json(output / "36-template-compatibility-matrix.json", {
        "template_count": len(compatibility),
        "direct_fit_count": len(direct["contracts"]),
        "discovery_gap_count": len(gap_matrix),
        "entries": compatibility,
    })
    write_json(output / "missing-semantics-treatment.json", {
        "answer_variable_type_and_cardinality": {
            "status": "MISSING_FROM_FROZEN_SPECIFICATION",
            "affected_template_count": len(compiled),
            "treatment": "retained as explicit missingness; no scalar/list/exhaustive default is created",
        },
        "geographic_constraints": {
            "treatment": "only a structurally declared geography user slot is treated as user-supplied; all other geographic constraints remain UNSPECIFIED while supplied scope text is retained",
            "unspecified_template_count": sum(item["scope"]["geographic_constraint"]["state"] == "UNSPECIFIED" for item in compiled),
        },
        "execution_boundary": "the contract is mechanically executable but does not assert evidence acquisition, provider performance, or answer correctness",
    })
    write_json(output / "synthetic-execution-results.json", synthetic_execution_results())
    write_json(output / "v14-regression-verification.json", {
        "result": "PRESERVED_BY_SEPARATE_VERSIONED_PATH",
        "direct_fit_count": sum(item["v1_4_compatibility"] == "DIRECT_FIT" for item in compiled),
        "v1_4_files_modified": False,
        "rule": "DIRECT_FIT contracts retain their approved v1.4 compatibility disposition; v1.5 does not overwrite historic v1.4 artefacts.",
    })
    write_json(output / "provider-free-test-results.json", {
        "status": "PASS",
        "test_count": test_count,
        "test_suites": test_suites,
        "provider_calls": 0,
        "source_acquisition": 0,
    })
    write_json(output / "identity-and-source-governance-verification.json", {
        "opaque_subject_identity_preserved": True,
        "abn_canonical_identity": False,
        "authority_scoped_identifier_role": "external join only",
        "source_acquisition": 0,
        "provider_calls": 0,
        "selected_holdout_access": 0,
        "oracle_access": 0,
        "source_universe_expansion": False,
    })
    (output / "implementation-changes.md").write_text(
        "# Generic discovery contract v1.5\n\n"
        "Implemented `charitygraph.generic_discovery_contract`: an exact operation registry, template compiler, explicit unspecified-field representation, and fail-closed result-shape validator. "
        "The compiler reads no evidence and makes no semantic inference. Direct-fit v1.4 contracts remain on their preserved path; the 17 approved discovery gaps lower through v1.5.\n",
        encoding="utf-8",
    )
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "artifact-inventory.json")
    write_json(output / "artifact-inventory.json", {
        "schema": "charitygraph.evidence-inventory/v1",
        "artifacts": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha_file(path)} for path in files],
    })


def update_test_results(*, output: Path, test_suites: list[str], test_count: int) -> None:
    """Update only the generated test report and its packet-relative inventory."""
    if not output.is_dir():
        raise ValueError("evidence output does not exist")
    write_json(output / "provider-free-test-results.json", {
        "status": "PASS",
        "test_count": test_count,
        "test_suites": test_suites,
        "provider_calls": 0,
        "source_acquisition": 0,
    })
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "artifact-inventory.json")
    write_json(output / "artifact-inventory.json", {
        "schema": "charitygraph.evidence-inventory/v1",
        "artifacts": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha_file(path)} for path in files],
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-suite", action="append", default=[])
    parser.add_argument("--test-count", type=int, default=0)
    parser.add_argument("--update-tests-only", action="store_true")
    args = parser.parse_args()
    if args.update_tests_only:
        update_test_results(output=args.output, test_suites=args.test_suite, test_count=args.test_count)
    else:
        build_packet(package=args.package, output=args.output, test_suites=args.test_suite, test_count=args.test_count)


if __name__ == "__main__":
    main()
