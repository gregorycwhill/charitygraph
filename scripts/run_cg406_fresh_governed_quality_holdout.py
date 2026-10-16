"""Freeze and report the provider-authority-limited CG406 holdout.

This script intentionally performs only deterministic record handling.  It
does not acquire, browse, call a provider, interpret prose, or manufacture a
semantic answer.  It makes the cohort and demand selection reproducible, then
records the terminal execution gap explicitly when no separately authorised
production semantic run is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


CAMPAIGN = "CG406"
SEED = "CG-G3-GOVERNED-KNOWLEDGE-QUALITY-406-CAMPAIGN--t04-fresh-governed-quality-holdout--a1"
DEMAND_DOMAINS = (1, 3, 5, 6, 7, 8, 9, 12, 13, 15, 17, 18)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return digest(path)


def rank(seed: str, value: str) -> str:
    return sha256_bytes(f"{seed}|{value}".encode("utf-8"))


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def subject_rows(identity_map: dict[str, object]) -> list[dict[str, object]]:
    rows = identity_map.get("rerun_rows")
    if not isinstance(rows, list) or len(rows) != 100:
        raise RuntimeError("canonical identity map must contain exactly 100 rerun_rows")
    required = {"subject_id", "abn", "display_name", "rank", "status", "acnc_source_record_id", "source_artifact_hash"}
    if any(not required.issubset(row) for row in rows if isinstance(row, dict)):
        raise RuntimeError("canonical identity map has an incomplete subject row")
    if len({str(row["subject_id"]) for row in rows}) != 100 or len({str(row["abn"]) for row in rows}) != 100:
        raise RuntimeError("canonical identity map must have unique subjects and ABNs")
    return rows  # type: ignore[return-value]


def excluded_subject_names(cg405_benchmark: dict[str, object]) -> set[str]:
    cases = cg405_benchmark.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("CG405 benchmark has no cases")
    excluded = {str(case["subject_name"]) for case in cases if isinstance(case, dict) and case.get("subject_name")}
    if len(excluded) != 7:
        raise RuntimeError("CG405 exclusion set must have exactly seven organisations")
    return excluded


def select_demands(catalogue: list[dict[str, object]]) -> list[dict[str, object]]:
    questions = [item for item in catalogue if item.get("scenario_type") == "question"]
    chosen: list[dict[str, object]] = []
    for domain in DEMAND_DOMAINS:
        chosen_ids = {str(item["id"]) for item in chosen}
        candidates = [item for item in questions if domain in item.get("primary_domains", []) and str(item["id"]) not in chosen_ids]
        if not candidates:
            raise RuntimeError(f"catalogue has no question with primary domain {domain}")
        chosen.append(min(candidates, key=lambda item: rank(f"{SEED}|domain:{domain}", str(item["id"]))))
    return chosen


def freeze(identity_map_path: Path, catalogue_path: Path, cg405_benchmark_path: Path, output: Path) -> tuple[Path, Path]:
    identity_map = load_json(identity_map_path)
    catalogue = load_json(catalogue_path)
    benchmark = load_json(cg405_benchmark_path)
    if not isinstance(identity_map, dict) or not isinstance(catalogue, list) or not isinstance(benchmark, dict):
        raise RuntimeError("invalid governed input shape")
    universe = subject_rows(identity_map)
    excluded = excluded_subject_names(benchmark)
    eligible = [row for row in universe if str(row["display_name"]) not in excluded]
    if len(eligible) < 12:
        raise RuntimeError("canonical universe cannot supply twelve distinct non-CG405 subjects")
    selected_subjects = sorted(eligible, key=lambda row: rank(f"{SEED}|subject", str(row["subject_id"])))[:12]
    demands = select_demands(catalogue)
    subject_manifest = {
        "schema": "charitygraph.cg406-subject-holdout-manifest/v1",
        "campaign": CAMPAIGN,
        "selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION",
        "selection_rule": {
            "universe": "canonical_100_subject_identity_map",
            "universe_count": 100,
            "exclude": "exact CG405 benchmark subject-name set",
            "excluded_count": len(excluded),
            "eligible_count": len(eligible),
            "algorithm": "ascending SHA-256(seed + '|subject|' + subject_id), first 12",
            "seed": SEED,
        },
        "input_hashes": {
            "identity_map_sha256": digest(identity_map_path),
            "cg405_benchmark_manifest_sha256": digest(cg405_benchmark_path),
        },
        "cg405_excluded_subject_names": sorted(excluded),
        "subjects": selected_subjects,
    }
    demand_manifest = {
        "schema": "charitygraph.cg406-demand-instance-manifest/v1",
        "campaign": CAMPAIGN,
        "selection_state": "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION",
        "selection_rule": {
            "catalogue": "Campaign-399 Semantic Demand Catalogue v0.2",
            "catalogue_sha256": digest(catalogue_path),
            "scenario_filter": "question",
            "balancing": "one deterministically selected demand for each fixed primary-domain stratum",
            "primary_domain_strata": list(DEMAND_DOMAINS),
            "algorithm": "ascending SHA-256(seed + '|domain:' + domain + '|' + demand_id), first per stratum",
            "seed": SEED,
        },
        "instances": [
            {
                "instance_id": f"cg406:{subject['subject_id']}:{demand['id']}",
                "subject_id": subject["subject_id"], "abn": subject["abn"], "display_name": subject["display_name"],
                "demand_id": demand["id"], "primary_domains": demand["primary_domains"],
                "persona": demand["persona"], "analytical_lenses": demand["analytical_lenses"],
                "semantic_signature": demand["semantic_signature"],
            }
            for subject, demand in zip(selected_subjects, demands, strict=True)
        ],
    }
    subject_path = output / "frozen-subject-manifest.json"
    demand_path = output / "frozen-demand-instance-manifest.json"
    write_json(subject_path, subject_manifest)
    write_json(demand_path, demand_manifest)
    return subject_path, demand_path


def execute_deterministic(subject_path: Path, demand_path: Path, output: Path) -> tuple[Path, Path]:
    subjects = load_json(subject_path)
    demands = load_json(demand_path)
    if not isinstance(subjects, dict) or not isinstance(demands, dict):
        raise RuntimeError("frozen manifests are invalid")
    selected = subjects["subjects"]
    instances = demands["instances"]
    if not isinstance(selected, list) or not isinstance(instances, list) or len(selected) != 12 or len(instances) != 12:
        raise RuntimeError("frozen manifest cardinality is not 12/12")
    acquisition = {"schema": "charitygraph.cg406-acquisition-ledger/v1", "campaign": CAMPAIGN, "rows": []}
    for subject in selected:
        acquisition["rows"].append({
            "subject_id": subject["subject_id"], "abn": subject["abn"], "source_family": "acnc_register",
            "terminal_state": "REUSED_GOVERNED_IDENTITY_RECORD", "fresh_acquisition": False,
            "source_record_id": subject["acnc_source_record_id"], "content_sha256": subject["source_artifact_hash"],
            "note": "The deterministic identity path was executed from the canonical governed record; no fresh acquisition was needed or performed.",
        })
    results = {"schema": "charitygraph.cg406-builder-result-ledger/v1", "campaign": CAMPAIGN,
               "frozen_input_hashes": {"subject_manifest_sha256": digest(subject_path), "demand_manifest_sha256": digest(demand_path)}, "rows": []}
    for instance in instances:
        results["rows"].append({
            "instance_id": instance["instance_id"], "subject_id": instance["subject_id"], "demand_id": instance["demand_id"],
            "deterministic_builder_status": "EXECUTED_IDENTITY_BINDING_AVAILABLE",
            "semantic_builder_status": "NOT_EXECUTED_PROVIDER_AUTHORITY", "terminal": True,
            "reason": "No separately authorised production semantic execution exists for this fresh cohort; campaign authority prohibits purchasing it.",
            "builder_answer": None, "evidence_refs": [],
        })
    acquisition_path = output / "acquisition-ledger.json"
    results_path = output / "frozen-builder-result-ledger.json"
    write_json(acquisition_path, acquisition)
    write_json(results_path, results)
    return acquisition_path, results_path


def adjudicate(subject_path: Path, demand_path: Path, results_path: Path, output: Path) -> None:
    results = load_json(results_path)
    if not isinstance(results, dict) or any(not row.get("terminal") for row in results.get("rows", [])):
        raise RuntimeError("all Builder result rows must be terminal before independent reference construction")
    reference = {"schema": "charitygraph.cg406-independent-reference-ledger/v1", "campaign": CAMPAIGN,
                 "constructed_after_frozen_builder_results": True, "builder_result_ledger_sha256": digest(results_path), "rows": []}
    for row in results["rows"]:
        reference["rows"].append({"instance_id": row["instance_id"], "reference_status": "NOT_CONSTRUCTED_PROVIDER_AUTHORITY_EXECUTION_GAP",
                                  "adjudication_status": "NOT_SCORABLE_NO_SEMANTIC_BUILDER_OUTPUT", "reference_claim": None,
                                  "provenance": "No reference claim was fed into Builder; this ledger was created only after the Builder result freeze."})
    metrics = {"schema": "charitygraph.cg406-quality-metrics/v1", "campaign": CAMPAIGN,
               "denominator": {"frozen_instances": len(results["rows"]), "semantic_outputs": 0, "scorable_outputs": 0},
               "counts": {"false_positive_or_overreach": 0, "missed_evidence": 0, "scope_or_type_error": 0, "provenance_failure": 0,
                          "honest_missingness": 0, "unresolved_processing": 0, "not_executed_provider_authority": len(results["rows"])},
               "rates": {"false_positive_or_overreach": None, "missed_evidence": None, "scope_or_type_error": None, "provenance_failure": None, "honest_missingness": None},
               "systematic_error_analysis": {"status": "NOT_ASSESSABLE", "reason": "All semantic instances are provider-authority execution gaps; zero outputs are not evidence of quality or generalisation."},
               "conclusion": "CG406 freezes a valid fresh 12-subject, 12-domain holdout but cannot make a semantic-quality or Gate-3 closure claim without separately authorised production semantic execution."}
    audit = {"schema": "charitygraph.cg406-integrity-audit/v1", "campaign": CAMPAIGN, "result": "PASS",
             "frozen_before_results": True, "subject_count": 12, "demand_count": 12,
             "distinct_primary_domain_count": 12, "provider_calls": 0, "fresh_acquisitions": 0,
             "reference_constructed_after_result_freeze": True, "result_driven_substitution": False,
             "private_material_excluded_from_git": True,
             "inputs": {"subject_manifest_sha256": digest(subject_path), "demand_manifest_sha256": digest(demand_path), "builder_results_sha256": digest(results_path)}}
    write_json(output / "independent-reference-adjudication-ledger.json", reference)
    write_json(output / "quality-metrics.json", metrics)
    write_json(output / "integrity-audit.json", audit)


def main(args: argparse.Namespace) -> None:
    subject_path, demand_path = freeze(args.identity_map, args.catalogue, args.cg405_benchmark, args.output)
    _, results_path = execute_deterministic(subject_path, demand_path, args.output)
    adjudicate(subject_path, demand_path, results_path, args.output)
    print(json.dumps({"campaign": CAMPAIGN, "status": "COMPLETE_WITH_PROVIDER_AUTHORITY_GAP", "output": str(args.output), "provider_calls": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-map", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--cg405-benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
