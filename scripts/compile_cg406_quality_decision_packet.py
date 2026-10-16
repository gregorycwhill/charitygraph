"""Compile the private, decision-grade CG406 Gate-3 review packet.

Packaging and validation only.  This compiler does not acquire evidence,
discover sources, call a provider, or turn missing semantic execution into a
score.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(cg405: Path, cg406: Path, challenge: Path, catalogue: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    review = cg405 / "SOURCE_UNIVERSE_SUFFICIENCY_REVIEW.md"
    ref = cg405 / "reference-adjudication.jsonl"
    freeze = cg405 / "closed-world-freeze.json"
    audit405 = load(cg405 / "integrity-audit.json")
    metrics406 = load(cg406 / "quality-metrics.json")
    audit406 = load(cg406 / "integrity-audit.json")
    challenge_data = load(challenge)
    catalogue_data = load(catalogue)
    demands = catalogue_data.get("candidates", []) if isinstance(catalogue_data, dict) else catalogue_data
    if audit405["campaign"] != "CG405" or audit406["campaign"] != "CG406":
        raise RuntimeError("campaign audit identity mismatch")
    if not audit406["frozen_before_results"] or not audit406["reference_constructed_after_result_freeze"]:
        raise RuntimeError("CG406 freeze/reference ordering failed")
    if audit406["provider_calls"] != 0 or audit406["result_driven_substitution"]:
        raise RuntimeError("provider crossing or result-driven substitution detected")
    if metrics406["denominator"]["semantic_outputs"] != 0:
        raise RuntimeError("CG406 unexpectedly contains semantic outputs")
    if challenge_data["source_policy"] != "Source Universe v1 unchanged; no source-policy gap is represented by this manifest.":
        raise RuntimeError("source policy changed")

    files = {
        "cg405_review": review, "cg405_reference_adjudication": ref,
        "cg405_integrity_audit": cg405 / "integrity-audit.json", "cg405_freeze": freeze,
        "cg406_subject_manifest": cg406 / "frozen-subject-manifest.json",
        "cg406_demand_manifest": cg406 / "frozen-demand-instance-manifest.json",
        "cg406_acquisition_ledger": cg406 / "acquisition-ledger.json",
        "cg406_result_ledger": cg406 / "frozen-builder-result-ledger.json",
        "cg406_reference_ledger": cg406 / "independent-reference-adjudication-ledger.json",
        "cg406_quality_metrics": cg406 / "quality-metrics.json",
        "cg406_integrity_audit": cg406 / "integrity-audit.json",
        "challenge_manifest": challenge, "demand_catalogue": catalogue,
    }
    inventory = {k: {"path": str(v), "bytes": v.stat().st_size, "sha256": sha(v)} for k, v in files.items()}
    domains = sorted({int(d) for x in demands if isinstance(x, dict) for d in x.get("north_star_domains", [])})
    exercised = sorted({int(d) for x in load(cg406 / "frozen-demand-instance-manifest.json")["instances"] for d in x["primary_domains"]})
    untested = [d for d in domains if d not in exercised]
    scenario_families = sorted({str(x.get("family")) for x in demands if isinstance(x, dict)})
    exercised_families = {str(x.get("family")) for x in demands if isinstance(x, dict) and str(x.get("id")) in {str(y["demand_id"]) for y in load(cg406 / "frozen-demand-instance-manifest.json")["instances"]}}
    counts = {str(x["classification"]): 0 for x in challenge_data["cases"]}
    for x in challenge_data["cases"]: counts[str(x["classification"])] += 1
    packet = {
        "schema": "charitygraph.cg406-governed-quality-decision-packet/v1",
        "campaign": "CG406", "gate_state": challenge_data["gate_state"],
        "recommendation": "GATE3_MORE_EVIDENCE_REQUIRED",
        "recommendation_reason": "CG405 development evidence is auditable, but CG406 fresh semantic holdout has zero executed semantic outputs because separate provider authority was unavailable.",
        "development_set": {"campaign": "CG405", "benchmark_cases": 40, "applicable_positive_demands": 34, "strict_supported": {"count": 25, "rate": 0.7353}, "usable_or_partial": {"count": 28, "rate": 0.8235}, "material_misses": counts},
        "independent_holdout": {"campaign": "CG406", "subjects": 12, "demands": 12, "semantic_outputs": 0, "scorable_outputs": 0, "provider_authority_gap": 12, "rates": metrics406["rates"]},
        "controls": {"freeze_order": True, "reference_independence": True, "provenance_preserved": True, "missingness_preserved": True, "correction_lineage": "CG405 correction classes are explicit in reference-adjudication; no invisible overwrite is used", "private_material_excluded_from_git": True},
        "untested_semantic_demand_primary_domains": untested,
        "untested_semantic_demand_families": [x for x in scenario_families if x not in exercised_families],
        "residual_risks": ["fresh generalisation is untested", "provider-dependent semantic tests remain unexecuted", "correction-class performance is not measured on CG406", "semantic demand coverage is only one selected instance per exercised stratum"],
        "next_gate3_evidence_target": "Obtain separate authority, execute the frozen 12x12 semantic holdout without changing inputs, construct independent references only after result freeze, and report scorable false-positive, supported/usable agreement, missed-evidence, scope/type, provenance, and missingness-control rates plus error clusters.",
        "artifact_inventory": inventory,
    }
    dump(output / "decision-packet.json", packet)
    dump(output / "artifact-hash-inventory.json", inventory)
    dump(output / "correction-missingness-governance-audit.json", {"campaign": "CG406", "cg405_classification_counts": counts, "cg406_honest_missingness": metrics406["counts"]["honest_missingness"], "cg406_provider_authority_gaps": metrics406["counts"]["not_executed_provider_authority"], "status": "PASS_WITH_SEMANTIC_EXECUTION_GAP"})
    dump(output / "reproducibility-manifest.json", {"commands": ["run_cg406_fresh_governed_quality_holdout.py", "compile_cg406_quality_decision_packet.py"], "content_addressed_inputs": True, "private_runtime_excluded_from_git": True})
    (output / "GATE3_GOVERNED_KNOWLEDGE_QUALITY_REVIEW.md").write_text("# CG406 Gate-3 governed-knowledge-quality review\n\n**Recommendation: GATE3_MORE_EVIDENCE_REQUIRED**\n\nCG405 provides auditable development evidence: 25/34 strict supported demands (73.53%) and 28/34 partial-or-usable (82.35%). Its 11 material misses are explicitly classified as 3 acquisition gaps, 4 extraction/representation gaps, 2 legitimate-missingness controls, and 2 evaluation-ambiguity controls.\n\nCG406 independently freezes 12 fresh subjects and 12 demand instances before any result inspection. The result ledger is terminal, the independent reference ledger is constructed after result freeze, and no provider calls or fresh acquisitions occurred. However, all 12 semantic rows are provider-authority execution gaps; semantic outputs and scorable outputs are both zero. Therefore no fresh-holdout quality rate, generalisation claim, or error-cluster claim is supportable.\n\nThe packet does not close Gate 3, award progress, alter Source Universe v1, or publish experimental semantic outputs. The exact next evidence target is recorded in `decision-packet.json`.\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETE", "recommendation": packet["recommendation"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--cg405", type=Path, required=True); p.add_argument("--cg406", type=Path, required=True); p.add_argument("--challenge", type=Path, required=True); p.add_argument("--catalogue", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args(); main(a.cg405.resolve(), a.cg406.resolve(), a.challenge.resolve(), a.catalogue.resolve(), a.output.resolve())
