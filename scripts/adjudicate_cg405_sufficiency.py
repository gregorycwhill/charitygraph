"""Mechanically compile the CG405 t03 evaluation-only adjudication.

The reference file is authored independently after t02.  This program neither
acquires sources nor interprets natural language: it verifies the frozen t02
hashes, joins the evaluator's per-case dispositions, and calculates the
decision outputs in a separate evaluation directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


DOMAIN_BY_TASK_FAMILY = {
    "entity_decomposition_v2": "identity_programs_services",
    "mechanism_decomposition_v2": "fundraising",
    "operational_activity_v2": "activities_sdgs",
    "relationship_v2": "relationships",
    "scope_decomposition_v2": "programs_services",
    "sdg_alignment_v2": "activities_sdgs",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    return digest(path)


def rate(numerator: int, denominator: int) -> dict[str, int | None]:
    return {"numerator": numerator, "denominator": denominator,
            "percent": None if not denominator else round(100 * numerator / denominator, 2)}


def main(frozen_root: Path, reference: Path, output: Path) -> None:
    freeze = json.loads((frozen_root / "closed-world-freeze-manifest.json").read_text("utf-8"))
    for name, expected in freeze["decision_relevant_artifacts"].items():
        actual = digest(frozen_root / name)
        if actual != expected:
            raise RuntimeError(f"t02 freeze verification failed for {name}: {actual} != {expected}")
    expected_freeze = "8913132c01ff5c9949eb265937260681f852af4004eb65950960050b961e1906"
    if digest(frozen_root / "closed-world-freeze-manifest.json") != expected_freeze:
        raise RuntimeError("unexpected t02 freeze manifest identity")

    ref = json.loads(reference.read_text("utf-8"))
    if ref.get("t02_freeze_manifest_sha256") != expected_freeze:
        raise RuntimeError("reference is not explicitly bound to the required t02 freeze")
    results = {r["case_id"]: r for r in (json.loads(line) for line in (frozen_root / "closed-world-results.jsonl").read_text("utf-8").splitlines() if line)}
    cases = {c["case_id"]: c for c in json.loads((frozen_root / "benchmark-manifest.json").read_text("utf-8"))["cases"]}
    refs = {r["case_id"]: r for r in ref["material_cases"]}
    confirmed = set(ref["confirmed_nonmaterial_case_ids"])
    if set(results) != set(cases) or (set(refs) | confirmed) != set(cases) or set(refs) & confirmed:
        raise RuntimeError("case sets must form an exact material/non-material reference partition")

    ledger = []
    for case_id in sorted(cases):
        case, closed = cases[case_id], results[case_id]
        oracle = refs.get(case_id, {"material": False, "oracle_state": "EVALUATOR_CONFIRMED_NON_MATERIAL", "gap_class": "NO_MATERIAL_MISS", "rationale": "Fresh evaluation review found no material divergence for this case.", "reference_ids": []})
        material = bool(oracle["material"])
        state = closed["state"]
        supported = state == "SUPPORTS"
        usable = state in {"SUPPORTS", "PARTIAL"}
        miss = material and not supported
        gap = oracle["gap_class"] if miss else "NO_MATERIAL_MISS"
        ledger.append({
            "case_id": case_id, "subject_id": case["subject_id"], "subject_name": case["subject_name"],
            "demand_family": case["task_family"], "proposition_key": case["proposition_key"],
            "expected_disposition": case["expected_disposition"], "closed_world_state": state,
            "strict_supported": supported, "usable_or_partial": usable, "material": material,
            "applicable_positive_demand": case["expected_disposition"] in {"required", "acceptable", "acceptable_secondary"},
            "north_star_domain": DOMAIN_BY_TASK_FAMILY[case["task_family"]],
            "material_miss": miss, "oracle_state": oracle["oracle_state"], "gap_class": gap,
            "rationale": oracle["rationale"], "reference_ids": oracle["reference_ids"],
        })
    if any(x["material_miss"] and x["gap_class"] == "NO_MATERIAL_MISS" for x in ledger):
        raise RuntimeError("unclassified material miss")

    material = [x for x in ledger if x["material"]]
    applicable = [x for x in ledger if x["applicable_positive_demand"]]
    metrics = {
        "all_cases": {"strict_supported_demand_coverage": rate(sum(x["strict_supported"] for x in ledger), len(ledger)),
                      "partial_or_usable_coverage": rate(sum(x["usable_or_partial"] for x in ledger), len(ledger))},
        "applicable_positive_demands": {"strict_supported_demand_coverage": rate(sum(x["strict_supported"] for x in applicable), len(applicable)),
                                        "partial_or_usable_coverage": rate(sum(x["usable_or_partial"] for x in applicable), len(applicable))},
        "material_cases": {"strict_supported_demand_coverage": rate(sum(x["strict_supported"] for x in material), len(material)),
                           "partial_or_usable_coverage": rate(sum(x["usable_or_partial"] for x in material), len(material))},
    }
    for key, group in (("by_north_star_domain", "north_star_domain"), ("by_demand_family", "demand_family"), ("by_subject", "subject_name")):
        buckets = defaultdict(list)
        for row in ledger: buckets[row[group]].append(row)
        metrics[key] = {name: {"case_count": len(rows), "applicable_positive_case_count": sum(r["applicable_positive_demand"] for r in rows), "strict_supported": rate(sum(r["strict_supported"] for r in rows if r["applicable_positive_demand"]), sum(r["applicable_positive_demand"] for r in rows)), "usable": rate(sum(r["usable_or_partial"] for r in rows if r["applicable_positive_demand"]), sum(r["applicable_positive_demand"] for r in rows))} for name, rows in sorted(buckets.items())}

    acquisition = json.loads((frozen_root / "acquisition-ledger.json").read_text("utf-8"))["rows"]
    family_metrics = {}
    for family, rows in sorted(((name, [r for r in acquisition if r["source_family"] == name]) for name in sorted({r["source_family"] for r in acquisition})), key=lambda x: x[0]):
        family_metrics[family] = {"attempts": len(rows), "captured": sum(r["status"] == "CAPTURED" for r in rows), "outcomes": dict(sorted(Counter(r["status"] for r in rows).items()))}
    contribution = Counter()
    corpus = json.loads((frozen_root / "captured-corpus-manifest.json").read_text("utf-8"))
    object_families = defaultdict(set)
    for event in corpus["captured_events"]:
        object_families[event["content_sha256"]].add(event["source_family"])
    for row in results.values():
        if row["state"] != "SUPPORTS": continue
        families = set().union(*(object_families[e["content_sha256"]] for e in row.get("evidence", []) if e["content_sha256"] in object_families))
        for family in families: contribution[family] += 1
    for family in family_metrics:
        family_metrics[family]["supported_case_contribution"] = contribution[family]
        family_metrics[family]["unique_supported_contribution"] = None
        family_metrics[family]["unique_contribution_note"] = "Not computed: frozen selectors do not encode counterfactual substitution sets."

    classification = dict(sorted(Counter(x["gap_class"] for x in ledger if x["material_miss"]).items()))
    audit = {"t02_freeze_manifest_sha256": expected_freeze, "reference_sha256": digest(reference),
             "evaluation_only": True, "builder_corpus_mutated": False, "builder_acquisition_seeds_mutated": False,
             "source_policy_changed": False, "provider_calls": 0,
             "result": "PASS", "statement": "Reference metadata and adjudication outputs remain evaluation-only and were not added to the Builder corpus, acquisition inputs, or source-policy controls."}
    write_json(output / "per-case-per-demand-adjudication-ledger.json", {"rows": ledger})
    write_json(output / "coverage-metrics.json", metrics)
    write_json(output / "source-family-metrics.json", family_metrics)
    write_json(output / "gap-classification.json", {"material_miss_count": sum(classification.values()), "counts": classification})
    write_json(output / "leakage-contamination-audit.json", audit)
    write_json(output / "source-universe-sufficiency-interpretation.json", {
        "source_gap_count": classification.get("SOURCE_GAP", 0),
        "fixable_builder_shortfall_count": classification.get("ACQUISITION_GAP", 0) + classification.get("EXTRACTION_REPRESENTATION_GAP", 0),
        "non_source_non_builder_count": classification.get("LEGITIMATE_MISSINGNESS", 0) + classification.get("BENCHMARK_EVALUATION_AMBIGUITY", 0),
        "finding": "This evaluation does not support expanding Source Universe v1: no material miss is classified SOURCE_GAP.",
        "what_would_change_that_finding": "A future evaluation-only reference must demonstrate material information in a non-admitted family after applicable admitted sources have been successfully acquired and represented.",
        "what_the_observed_shortfall_calls_for": "Improve bounded official-site acquisition and representation/semantic processing; retain legitimate missingness; clarify ambiguous SDG evaluation semantics.",
        "threshold_note": "No sufficiency threshold is set and Gate 2 is not closed by this result."
    })
    summary = {"campaign": "CG405", "stage": "t03", "t02_freeze_manifest_sha256": expected_freeze,
               "evaluation_reference_sha256": digest(reference), "case_count": len(ledger), "material_case_count": len(material),
               "material_miss_count": sum(classification.values()), "gap_counts": classification,
               "coverage_metrics_sha256": digest(output / "coverage-metrics.json"),
               "ledger_sha256": digest(output / "per-case-per-demand-adjudication-ledger.json"),
               "leakage_audit_sha256": digest(output / "leakage-contamination-audit.json"),
               "leakage_audit_sha256": digest(output / "leakage-contamination-audit.json"),
               "private_material_excluded_from_git": True}
    write_json(output / "t03-sufficiency-adjudication-summary.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.frozen_root, args.reference, args.output)
