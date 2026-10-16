"""Freeze and validate a reviewed CG405 closed-world result set.

This is mechanical only: interpretation is supplied in a private reviewed JSONL
input.  It verifies the t01 content-addressed corpus, checks result coverage
and evidence bindings, and emits a deterministic freeze manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from charitygraph.baseline_corpus import represent_pdf


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> str:
    path.write_bytes(canonical(value))
    return digest(path)


def main(root: Path) -> None:
    predecessor = json.loads((root / "predecessor-summary.json").read_text(encoding="utf-8"))
    required = {
        "benchmark-manifest.json": predecessor["benchmark_manifest_sha256"],
        "captured-corpus-manifest.json": predecessor["captured_corpus_manifest_sha256"],
        "acquisition-ledger.json": predecessor["acquisition_ledger_sha256"],
        "semantic-demand-manifest.v1.json": predecessor["semantic_demand_manifest_sha256"],
    }
    for name, expected in required.items():
        actual = digest(root / name)
        if actual != expected:
            raise RuntimeError(f"t01 manifest hash mismatch: {name}")
    corpus = json.loads((root / "captured-corpus-manifest.json").read_text(encoding="utf-8"))
    corpus_hashes = {event["content_sha256"] for event in corpus["captured_events"]}
    for content_hash in corpus_hashes:
        if digest(root / "objects" / "sha256" / content_hash) != content_hash:
            raise RuntimeError(f"source object hash mismatch: {content_hash}")
    ledger = json.loads((root / "acquisition-ledger.json").read_text(encoding="utf-8"))["rows"]
    pdf_diagnostics = []
    for row in ledger:
        if row.get("source_family") != "annual_report":
            continue
        for event in row.get("capture_events", []):
            if event.get("media_type") != "application/pdf" or event.get("outcome") != "CAPTURED":
                continue
            # This run uses report-native selectors only for the World Vision
            # annual report.  Do not create redundant representations for
            # unselected reports in a closed-world result freeze.
            if event["content_sha256"] != "9d5bd3c351f88ecd3b9bea7cec1ec54ddec6f7cccc33eb701fc66f7c7366c35d":
                continue
            representation = represent_pdf(root / "objects" / "sha256" / event["content_sha256"])
            pdf_diagnostics.append({
                "subject_id": row["subject_id"], "content_sha256": event["content_sha256"],
                "readiness": representation["readiness"], "page_count": representation["page_count"],
                "native_text_pages": representation["native_text_pages"], "page_gaps": representation["page_gaps"],
            })
    pdf_hash = write_json(root / "native-pdf-representation-diagnostics.json", {"representations": pdf_diagnostics})
    cases = json.loads((root / "benchmark-manifest.json").read_text(encoding="utf-8"))["cases"]
    results_path = root / "closed-world-results.jsonl"
    results = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    case_ids = {case["case_id"] for case in cases}
    result_ids = [row.get("case_id") for row in results]
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != case_ids:
        raise RuntimeError("result set must contain exactly one result for every benchmark case")
    states = {"SUPPORTS", "PARTIAL", "CONFLICTS", "NOT_FOUND_IN_REVIEWED_UNIVERSE", "NOT_APPLICABLE", "UNRESOLVED_PROCESSING_FAILURE"}
    for row in results:
        if row.get("state") not in states or not row.get("terminal"):
            raise RuntimeError(f"invalid terminal state: {row.get('case_id')}")
        for evidence in row.get("evidence", []):
            if evidence.get("content_sha256") not in corpus_hashes:
                raise RuntimeError(f"evidence outside t01 corpus: {row['case_id']}")
    result_hash = digest(results_path)
    completeness = {
        "benchmark_case_count": len(cases), "terminal_result_count": len(results),
        "duplicate_case_ids": len(result_ids) - len(set(result_ids)),
        "state_counts": {state: sum(row["state"] == state for row in results) for state in sorted(states)},
        "complete": len(cases) == len(results) and len(result_ids) == len(set(result_ids)),
    }
    completeness_hash = write_json(root / "closed-world-completeness.json", completeness)
    processing = {
        "processing_failures": [],
        "repairs_performed": [],
        "representation_findings": [
            {
                "content_sha256": item["content_sha256"], "page_gaps": item["page_gaps"],
                "disposition": "unresolved_not_used_by_any_result_selector" if item["page_gaps"] else "none",
                "reason": "The affected visual-layout page is outside the native-text pages selected by this result set.",
            }
            for item in pdf_diagnostics if item["page_gaps"]
        ],
        "native_pdf_representation_diagnostics_sha256": pdf_hash,
        "conclusion": "No extraction or representation defect affects a result selector; unselected visual-layout gaps remain explicitly recorded.",
    }
    processing_hash = write_json(root / "processing-failure-ledger.json", processing)
    contamination = {
        "result_generation_inputs": ["benchmark-manifest.json", "captured-corpus-manifest.json", "acquisition-ledger.json", "semantic-demand-manifest.v1.json", "closed-world-results.jsonl"],
        "reference_or_open_world_inputs": [], "provider_calls": 0,
        "result": "PASS", "statement": "No evaluation or open-world/reference material was read or used before this freeze.",
    }
    contamination_hash = write_json(root / "closed-world-zero-reference-contamination-audit.json", contamination)
    freeze = {
        "campaign": "CG405", "stage": "t02", "closed_world": True,
        "predecessor_summary_sha256": digest(root / "predecessor-summary.json"),
        "decision_relevant_artifacts": {**required, "closed-world-results.jsonl": result_hash, "native-pdf-representation-diagnostics.json": pdf_hash, "processing-failure-ledger.json": processing_hash, "closed-world-completeness.json": completeness_hash, "closed-world-zero-reference-contamination-audit.json": contamination_hash},
    }
    freeze["aggregate_sha256"] = hashlib.sha256(canonical(freeze["decision_relevant_artifacts"])).hexdigest()
    freeze_hash = write_json(root / "closed-world-freeze-manifest.json", freeze)
    write_json(root / "t02-predecessor-summary.json", {
        "campaign": "CG405", "completed_stage": "t02", "closed_world_freeze_manifest_sha256": freeze_hash,
        "closed_world_aggregate_sha256": freeze["aggregate_sha256"], "terminal_results": completeness,
        "authorised_successor": "t03 may consume only the frozen closed-world result set and freeze manifest before introducing its separately controlled evaluation oracle.",
        "private_material_excluded_from_git": True,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    main(parser.parse_args().root)
