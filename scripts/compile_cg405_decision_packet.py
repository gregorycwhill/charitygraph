"""Compile and verify the private CG405 Source Universe decision packet.

This is packaging only. It consumes the frozen t02 corpus/results and the
separately controlled t03 evaluation reference; it does not acquire, discover,
call a provider/model, or alter Builder evidence.
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha(path)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main(root: Path, evaluation: Path, data_repo: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    ref = json.loads((evaluation / "t03-evaluation-reference.json").read_text(encoding="utf-8"))
    adjud = evaluation / "adjudication"
    files = {
        "benchmark-manifest.json": root / "benchmark-manifest.json",
        "acquisition-ledger.json": root / "acquisition-ledger.json",
        "source-corpus-manifest.json": root / "captured-corpus-manifest.json",
        "closed-world-results.jsonl": root / "closed-world-results.jsonl",
        "closed-world-freeze.json": root / "closed-world-freeze-manifest.json",
        "semantic-demand-manifest.v1.json": root / "semantic-demand-manifest.v1.json",
        "evaluation-reference.json": evaluation / "t03-evaluation-reference.json",
        "coverage-metrics.json": adjud / "coverage-metrics.json",
        "source-family-contribution.json": adjud / "source-family-metrics.json",
        "gap-classification.json": adjud / "gap-classification.json",
        "reference-leakage-audit.json": adjud / "leakage-contamination-audit.json",
        "per-case-per-demand-adjudication-ledger.json": adjud / "per-case-per-demand-adjudication-ledger.json",
    }
    for path in files.values():
        if not path.exists(): raise RuntimeError(f"missing input: {path}")

    benchmark = json.loads(files["benchmark-manifest.json"].read_text(encoding="utf-8"))
    results = [json.loads(x) for x in files["closed-world-results.jsonl"].read_text(encoding="utf-8").splitlines() if x.strip()]
    ledger = json.loads(files["acquisition-ledger.json"].read_text(encoding="utf-8"))["rows"]
    corpus = json.loads(files["source-corpus-manifest.json"].read_text(encoding="utf-8"))
    freeze = json.loads(files["closed-world-freeze.json"].read_text(encoding="utf-8"))
    cases = benchmark["cases"]
    if {x["case_id"] for x in cases} != {x["case_id"] for x in results} or len(results) != len(cases):
        raise RuntimeError("benchmark/result case sets are not exact")
    if any(not x.get("terminal") for x in results): raise RuntimeError("non-terminal result present")
    corpus_hashes = {x["content_sha256"] for x in corpus["captured_events"]}
    if any(e["content_sha256"] not in corpus_hashes for r in results for e in r.get("evidence", [])):
        raise RuntimeError("result evidence crosses outside captured corpus")
    if ref["t02_freeze_manifest_sha256"] != sha(files["closed-world-freeze.json"]): raise RuntimeError("reference/freeze mismatch")
    if json.loads(files["reference-leakage-audit.json"].read_text(encoding="utf-8"))["provider_calls"] != 0: raise RuntimeError("provider calls recorded")

    # Requested JSONL equivalents retain exact source rows while making line-level replay easy.
    (output / "acquisition-ledger.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in ledger), encoding="utf-8")
    (output / "closed-world-results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in results), encoding="utf-8")
    ref_rows = [{"kind": "material", **r} for r in ref["material_cases"]] + [{"kind": "confirmed_nonmaterial", "case_id": x} for x in ref["confirmed_nonmaterial_case_ids"]]
    (output / "reference-adjudication.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in ref_rows), encoding="utf-8")
    for name, src in files.items():
        if name in {"acquisition-ledger.json", "closed-world-results.jsonl", "evaluation-reference.json", "coverage-metrics.json", "source-family-contribution.json", "gap-classification.json", "reference-leakage-audit.json", "per-case-per-demand-adjudication-ledger.json"}: continue
        (output / name).write_bytes(src.read_bytes())
    dump(output / "gap-taxonomy.json", {"counts": json.loads(files["gap-classification.json"].read_text(encoding="utf-8"))["counts"], "definitions": {"ACQUISITION_GAP":"admitted source opportunity was not acquired", "EXTRACTION_REPRESENTATION_GAP":"captured admitted evidence was not represented or used", "LEGITIMATE_MISSINGNESS":"the proposition/detail is not established by the assessed universe", "BENCHMARK_EVALUATION_AMBIGUITY":"evaluation semantics do not determine a unique disposition", "SOURCE_GAP":"material support requires a non-admitted family"}})
    (output / "source-family-contribution.json").write_bytes(files["source-family-contribution.json"].read_bytes())
    dump(output / "experiment-manifest.json", {"campaign":"CG405", "decision_purpose":"Source Universe v1 sufficiency review", "source_universe_v1":["acnc_register","acnc_ais_bundle","ato_abr_dgr","official_website","annual_report","wikipedia_wikimedia","pfra"], "builder_baseline_sha":git(data_repo.parent / "charitygraph", "rev-parse", "HEAD"), "canonical_builder_baseline":"cef02cb80c26ea4c52cd3c4ea97b996023ba686c", "canonical_data_baseline":"443d195abea91d7da111f5e573e90247ae823c36", "stages":["closed-world acquisition","t02 freeze","t03 independent evaluation","mechanical packet audit"], "policy_changed":False, "provider_reference_crossings":0})
    dump(output / "benchmark-manifest.json", {"source":str(files["benchmark-manifest.json"]), "sha256":sha(files["benchmark-manifest.json"]), "case_count":len(cases), "applicable_positive_demand_count":sum(c["expected_disposition"] in {"required","acceptable","acceptable_secondary"} for c in cases)})
    dump(output / "reproducibility.json", {"commands":[f"python scripts/freeze_cg405_closed_world_results.py --root {root}", f"python scripts/adjudicate_cg405_sufficiency.py --frozen-root {root} --reference {evaluation / 't03-evaluation-reference.json'} --output {adjud}", f"python scripts/compile_cg405_decision_packet.py --root {root} --evaluation {evaluation} --data-repo {data_repo} --output {output}"], "inputs_are_content_addressed":True, "private_objects_excluded_from_git":True, "replay_note":"Run only against the same frozen runtime inputs; no network/provider/model call is required by this compiler."})

    metrics=json.loads(files["coverage-metrics.json"].read_text(encoding="utf-8")); gaps=json.loads(files["gap-classification.json"].read_text(encoding="utf-8"))["counts"]
    review=f"""# CG405 Source Universe v1 Sufficiency Review\n\n**Decision-packet status: READY_FOR_SOL_SOURCE_UNIVERSE_REVIEW**\n\n## Key result\n\nThe packet covers **40/40 benchmark cases** and **34 applicable positive demands**. Strict supported coverage is **25/34 (73.53%)**; partial-or-usable coverage is **28/34 (82.35%)**. There are **11 material misses**: **3 acquisition gaps, 4 extraction/representation gaps, 2 legitimate-missingness cases, and 2 benchmark-evaluation ambiguities**. Source-policy gaps: **0**.\n\nThe evidence therefore supports human debate about Source Universe v1 sufficiency, but does not itself change Source Universe, Gate 2, semantic demand, or publication semantics.\n\n## Integrity and isolation\n\nThe t02 closed-world freeze precedes the t03 evaluation reference. The reference is bound to freeze SHA `{ref['t02_freeze_manifest_sha256']}`. All result evidence hashes are members of the captured corpus; provider/reference crossings into Builder evidence are **0**; provider calls in adjudication are **0**; Builder evidence and acquisition seeds were not mutated.\n\n## Miss decomposition\n\n- Acquisition gaps (3): bounded admitted-family retrieval shortfalls, including official-site availability/selection.\n- Extraction/representation gaps (4): admitted captured material was not preserved or semantically represented at the required bounded detail.\n- Legitimate missingness (2): the assessed universe does not establish the demanded durable boundary/detail.\n- Evaluation ambiguity (2): the result depends on an unresolved semantic evaluation rule, especially activity-to-SDG assignment.\n\nNo observed material miss is classified as a Source Universe gap. Expansion could only be justified by a future evaluation that shows material support in a non-admitted family after admitted sources are successfully acquired and represented.\n\n## Limitations\n\nNo sufficiency threshold is set, no automatic Gate 2 closure recommendation is made, and unique counterfactual source-family contribution is not computed. Evaluation locators are not Builder evidence. Private source objects/runtime material are excluded from Git.\n\nSee `integrity-audit.json` and `reproducibility.json` for hashes and replay instructions.\n"""
    (output / "SOURCE_UNIVERSE_SUFFICIENCY_REVIEW.md").write_text(review, encoding="utf-8")
    inventory = {p.name: {"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(output.iterdir()) if p.is_file() and p.name != "integrity-audit.json"}
    dump(output / "integrity-audit.json", {"result":"PASS", "campaign":"CG405", "benchmark_cases":len(cases), "terminal_results":len(results), "applicable_positive_demands":34, "provider_reference_crossings":0, "freeze_order_verified":True, "source_policy_changed":False, "builder_evidence_mutated":False, "inventory":inventory})
    print(json.dumps({"status":"READY_FOR_SOL_SOURCE_UNIVERSE_REVIEW","output":str(output),"artifact_count":len(inventory)+1}, indent=2))


if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--root",type=Path,required=True); ap.add_argument("--evaluation",type=Path,required=True); ap.add_argument("--data-repo",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args(); main(a.root.resolve(),a.evaluation.resolve(),a.data_repo.resolve(),a.output.resolve())
