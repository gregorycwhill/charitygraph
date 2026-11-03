"""Freeze CG358's final centrally retained source universe and shared packets.

This is a mechanical assembly/verification program.  It never fetches,
discovers, interprets prose, or calls a semantic provider.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def canon(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_path(root: Path, item: dict) -> Path:
    name = item["raw_sha256"]
    direct = root / "raw" / name
    return direct if direct.is_file() else root / "raw" / f"{name}.json"


def retain(root: Path, item: dict, out: Path) -> dict:
    """Copy exact hash-addressed bytes into the successor central store."""
    raw = raw_path(root, item)
    rep = root / item["representation_locator"]
    if not raw.is_file() or not rep.is_file():
        raise RuntimeError(f"missing retained object for {item['case_id']}")
    if hashlib.sha256(raw.read_bytes()).hexdigest() != item["raw_sha256"]:
        raise RuntimeError(f"raw hash mismatch for {item['case_id']}")
    if hashlib.sha256(rep.read_bytes()).hexdigest() != item["representation_sha256"]:
        raise RuntimeError(f"representation hash mismatch for {item['case_id']}")
    raw_out = out / "raw" / item["raw_sha256"]
    rep_out = out / "representations" / f"{item['representation_sha256']}.json"
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    rep_out.parent.mkdir(parents=True, exist_ok=True)
    if not raw_out.exists():
        shutil.copyfile(raw, raw_out)
    if not rep_out.exists():
        shutil.copyfile(rep, rep_out)
    result = dict(item)
    result["representation_locator"] = f"representations/{item['representation_sha256']}.json"
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cg357", type=Path, required=True)
    p.add_argument("--repair", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    cohort = load(a.cg357 / "cohort.json")
    regulatory = load(a.cg357 / "regulatory" / "source-attempt-manifest.json")
    rich = load(a.cg357 / "rich" / "source-attempt-manifest.json")
    repair = load(a.repair / "source-attempt-manifest.json")
    old_frozen = load(a.cg357 / "frozen" / "frozen-corpus.json")
    if cohort["cohort_sha256"] != "fa77ab9141ddc5621713c9f487294cadb59fdcdf6d001fc5b4deb2d1e050e5ad":
        raise RuntimeError("unexpected cohort")
    if not repair.get("repairable_transport_failures_exhausted"):
        raise RuntimeError("repair sweep is not exhausted")
    a.out.mkdir(parents=True, exist_ok=True)
    stores = ((a.cg357 / "regulatory", regulatory), (a.cg357 / "rich", rich), (a.repair, repair))
    retained, failures = [], []
    for root, manifest in stores:
        for item in manifest["attempts"]:
            if item["status"] == "captured":
                retained.append(retain(root, item, a.out))
            else:
                failures.append(dict(item))
    by_case = {case["case_id"]: [] for case in cohort["cases"]}
    for item in retained:
        by_case[item["case_id"]].append(item)
    packets, coverage, attempt_totals_by_case = [], [], {}
    for case in cohort["cases"]:
        evidence = sorted(by_case[case["case_id"]], key=lambda x: (x["source_family"], x["raw_sha256"]))
        families = sorted({item["source_family"] for item in evidence})
        attempts_for_case = [x for x in regulatory["attempts"] + rich["attempts"] + repair["attempts"] if x["case_id"] == case["case_id"]]
        attempt_totals_by_case[case["case_id"]] = {family: {"captured": sum(x["status"] == "captured" and x["source_family"] == family for x in attempts_for_case), "failed": sum(x["status"] != "captured" and x["source_family"] == family for x in attempts_for_case)} for family in sorted({x["source_family"] for x in attempts_for_case})}
        coverage.append({"case_id": case["case_id"], "arm": case["arm"], "captured_source_count": len(evidence),
                         "source_families": families, "rich_non_acnc": any(x["source_family"] != "acnc_regulatory" for x in evidence)})
        for section in (15, 17):
            material = {"case_id": case["case_id"], "subject_id": case["subject_id"], "section": section,
                        "selection_version": "central-retained-source-selection-v3", "evidence": evidence}
            packets.append({**material, "packet_id": "packet:" + sha(material), "packet_hash": sha(material),
                            "coverage_state": "rich_retained_sources" if material["evidence"] else "coverage_gap"})
    manifest = {
        "contract": "cg358-final-retained-universe-v1", "corpus_id": "empirical-ethos-notability-rich-v3-final",
        "version": "3.0.0", "cohort_sha256": cohort["cohort_sha256"],
        "predecessor": {"corpus_id": old_frozen["corpus_id"], "version": old_frozen["version"], "corpus_sha256": old_frozen["corpus_sha256"]},
        "source_attempt_manifests": {"regulatory_v1": regulatory["manifest_sha256"], "rich_v2": rich["manifest_sha256"], "official_repair_v3": repair["manifest_sha256"]},
        "retained_objects": retained, "failed_attempts": failures, "coverage_by_case": coverage, "source_attempt_totals_by_case": attempt_totals_by_case,
        "source_family_totals": {family: {"captured": sum(x["status"] == "captured" and x.get("source_family") == family for x in regulatory["attempts"] + rich["attempts"] + repair["attempts"]), "failed": sum(x["status"] != "captured" and x.get("source_family") == family for x in regulatory["attempts"] + rich["attempts"] + repair["attempts"])} for family in sorted({x["source_family"] for x in regulatory["attempts"] + rich["attempts"] + repair["attempts"]})},
        "packets": packets, "provider_calls": 0, "authenticated_github_mutations": 0,
        "network_owner": "central_acquisition_only", "candidate_outputs_present": False,
    }
    manifest["retained_universe_sha256"] = sha({k: v for k, v in manifest.items() if k != "retained_universe_sha256"})
    (a.out / "retained-universe.json").write_bytes(canon(manifest))
    print(json.dumps({"retained_universe_sha256": manifest["retained_universe_sha256"], "retained": len(retained), "failures": len(failures), "packets": len(packets), "totals": manifest["source_family_totals"]}, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
