"""Package a local-only, post-result CG406 v1.2 forensic handoff.

This script is diagnostic only.  It never calls a provider, mutates a frozen
input, or feeds oracle material into an execution packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from charitygraph.frozen_experiment import demand_requirements


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def source_locators(catalog: Path, record_ids: set[str]) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{catalog.as_posix()}?mode=ro", uri=True)
    try:
        return {str(row[0]): str(row[1]) for row in conn.execute(
            "SELECT source_record_id, source_locator FROM source_records WHERE source_record_id IN (%s)" % ",".join("?" for _ in record_ids),
            tuple(sorted(record_ids)),
        )} if record_ids else {}
    finally:
        conn.close()


def disposition(result: dict[str, Any], oracle: dict[str, Any], matched_visible: set[str], selected: set[str]) -> str:
    if result["mechanical_validation"] != "valid":
        return "correct_semantics_or_partial_support_mechanically_rejected"
    if result["outcome"] in {"supported", "resolved"} and oracle["reference_status"] == "NOT_ESTABLISHED":
        return "false_positive_accepted_mechanically"
    if not matched_visible:
        return "oracle_cited_source_not_acquired_or_not_packet_bound"
    if not (matched_visible & selected):
        return "acquired_represented_but_not_selected"
    if result["outcome"] in {"supported", "resolved"}:
        return "selected_requires_semantic_adjudication"
    return "selected_but_not_established_by_v12_assessment"


def main(args: argparse.Namespace) -> None:
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    results = {row["instance_id"]: row for row in load(args.v12_ledger)["rows"]}
    oracle = {row["instance_id"]: row for row in load(args.oracle_ledger)["rows"]}
    demands = {row["instance_id"]: row for row in load(args.demand_manifest)["instances"]}
    if set(results) != set(oracle) or set(results) != set(demands):
        raise RuntimeError("frozen result, oracle, and demand instance IDs do not exactly align")
    all_record_ids = {item for row in results.values() for item in row["provider_visible_evidence_ids"]}
    locators = source_locators(args.v12_catalog, all_record_ids)
    forensic, relevance, contracts = [], [], []
    for instance_id in sorted(results):
        result, reference, demand = results[instance_id], oracle[instance_id], demands[instance_id]
        visible = set(result["provider_visible_evidence_ids"])
        selected = set(result["selected_evidence_ids"])
        reference_urls = {canonical_url(item["url"]) for item in reference["sources"]}
        matched = {record_id for record_id in visible if canonical_url(locators.get(record_id, "")) in reference_urls}
        row_disposition = disposition(result, reference, matched, selected)
        forensic.append({
            "instance_id": instance_id,
            "demand_id": result["demand_id"],
            "subject_id": result["subject_id"],
            "frozen_signature": json.loads(demand["semantic_signature"]),
            "v12": {"outcome": result["outcome"], "mechanical_validation": result["mechanical_validation"], "mechanical_validation_error": result["mechanical_validation_error"], "selected_evidence_ids": sorted(selected), "proposition_support": result["proposition_support"], "conclusion": result["conclusion"]},
            "oracle_post_result_diagnosis": {"reference_status": reference["reference_status"], "demand_interpretation": reference["demand_interpretation"], "scope_type_distinctions": reference["scope_type_distinctions"], "sources": reference["sources"]},
            "forensic_disposition": row_disposition,
            "source_passage_citation_method": "The v1.2 result's exact cited evidence IDs and proposition qualifications are retained above. Source locators are retained separately; no raw source body is copied into this packet.",
        })
        relevance.append({"instance_id": instance_id, "provider_visible_families": result["provider_visible_evidence_families"], "provider_visible_evidence_ids": sorted(visible), "selected_evidence_ids": sorted(selected), "oracle_source_urls": sorted(reference_urls), "oracle_source_record_ids_matched_to_v12_packet": sorted(matched), "disposition": row_disposition})
        contracts.append({"instance_id": instance_id, "demand_id": demand["demand_id"], "requirements": demand_requirements(demand["semantic_signature"])})
    prepared = load(args.prepared_run)
    prep = {"request_count": len(prepared["rows"]), "prepared_run_sha256": sha(args.prepared_run), "contract_versions": sorted({row["contract_version"] for row in prepared["rows"]}), "schema_versions": sorted({row["schema_version"] for row in prepared["rows"]}), "packet_hashes": {row["instance_id"]: row["packet_hash"] for row in prepared["rows"]}, "provider_calls": 0}
    dump(out / "forensic-diagnosis.json", {"rows": forensic})
    dump(out / "source-relevance-matrix.json", {"rows": relevance})
    dump(out / "typed-demand-contract.json", {"rows": contracts})
    dump(out / "preparation-summary.json", prep)
    dump(out / "test-results.json", {"provider_free_tests_passed": args.tests, "provider_calls": 0})
    summary = "# CG406 v1.2 inference-integrity forensic handoff\n\n"
    summary += "Post-result oracle comparison only. No oracle material is supplied to candidate request packets. Frozen v1.2 inputs/results are read-only; no provider call occurred.\n\n"
    summary += f"- Rows: {len(forensic)}\n- Candidate prepared requests: {prep['request_count']}\n- Candidate contract/schema: {prep['contract_versions']} / {prep['schema_versions']}\n- Provider-free tests: {args.tests}\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")
    dump(out / "handoff.json", {"status": "READY_FOR_G3_INFERENCE_INTEGRITY_REVIEW", "provider_calls": 0, "false_positive_validation_bypass": "v1.2 positive validation covered proposition labels/scope/time but not every typed frozen demand requirement", "generic_repair": "v1.3 exact demand-requirement identity coverage plus positive fail-closed validation", "prepared": prep})
    inventory = {path.name: sha(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "artifact-inventory.json"}
    dump(out / "artifact-inventory.json", {"artifacts": inventory})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v12-ledger", type=Path, required=True)
    parser.add_argument("--v12-catalog", type=Path, required=True)
    parser.add_argument("--oracle-ledger", type=Path, required=True)
    parser.add_argument("--demand-manifest", type=Path, required=True)
    parser.add_argument("--prepared-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tests", type=int, required=True)
    main(parser.parse_args())
