"""Freeze a successor retained-source corpus after central acquisition only."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--regulatory", type=Path, required=True)
    p.add_argument("--rich", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    cohort = json.loads(a.cohort.read_text(encoding="utf-8"))
    old = json.loads((a.regulatory / "source-attempt-manifest.json").read_text(encoding="utf-8"))
    rich = json.loads((a.rich / "source-attempt-manifest.json").read_text(encoding="utf-8"))
    if sha(cohort) != old["cohort_sha256"] or sha(cohort) != rich["cohort_sha256"]:
        raise SystemExit("cohort identity mismatch: successor cannot be frozen")
    sources_by_case = {case["case_id"]: [] for case in cohort["cases"]}
    for item in old["attempts"] + rich["attempts"]:
        if item["status"] == "captured":
            sources_by_case[item["case_id"]].append(item)
    packets = []
    coverage = []
    for case in cohort["cases"]:
        sources = sources_by_case[case["case_id"]]
        families = sorted({x["source_family"] for x in sources})
        rich_sources = [x for x in sources if x["source_family"] != "acnc_regulatory"]
        coverage.append({"case_id": case["case_id"], "arm": case["arm"], "captured_source_count": len(sources),
                         "source_families": families, "rich_non_acnc": bool(rich_sources)})
        for section in (15, 17):
            material = {"case_id": case["case_id"], "subject_id": case["subject_id"], "section": section,
                        "selection_version": "central-retained-source-selection-v2", "evidence": sources}
            packets.append({**material, "packet_id": "packet:" + sha(material), "packet_hash": sha(material),
                            "coverage_state": "rich_retained_sources" if rich_sources else ("regulatory_only" if sources else "coverage_gap")})
    family_counts = {family: sum(family in row["source_families"] for row in coverage)
                     for family in sorted({f for row in coverage for f in row["source_families"]})}
    corpus = {"corpus_id": "empirical-ethos-notability-rich-v2", "version": "2.0.0",
              "frozen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "cohort_sha256": sha(cohort),
              "predecessor": {"corpus_id": old["corpus_id"], "version": old["version"], "manifest_sha256": old["manifest_sha256"]},
              "source_attempt_manifests": {"regulatory_v1": old["manifest_sha256"], "rich_v2": rich["manifest_sha256"]},
              "packet_selection_versions": {"15": "central-retained-source-selection-v2", "17": "central-retained-source-selection-v2"},
              "coverage_by_case": coverage, "source_family_case_coverage": family_counts, "packets": packets,
              "provider_calls": 0, "candidate_outputs_present": False}
    corpus["corpus_sha256"] = sha(corpus)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "frozen-corpus.json").write_bytes(canon(corpus))
    print(json.dumps({"corpus_sha256": corpus["corpus_sha256"], "packets": len(packets), "family_case_coverage": family_counts,
                      "rich_challenge_cases": sum(x["rich_non_acnc"] and x["arm"] == "challenge" for x in coverage),
                      "rich_blind_cases": sum(x["rich_non_acnc"] and x["arm"] == "blind" for x in coverage)}, indent=2))


if __name__ == "__main__":
    main()
