"""Reality Spike 8: disposable read-only architecture inversion experiment.

Inputs are the already-generated Spike 5 governed experimental records.  This
does not acquire, parse, infer from prose, call a model/provider, or mutate S0
or canonical state.  It deliberately exposes the minimum envelope needed to
replay the retained experiment, and a thinner query-time view of that envelope.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "artifacts" / "reality-spike-5-eight-charity-anatomy"
OUT = ROOT / "artifacts" / "reality-spike-8-architecture-inversion"
SUBJECTS = {
    "28004778081": "World Vision Australia", "37646526132": "Sunrise Foundation Limited",
    "50169561394": "Australian Red Cross Society", "47613674461": "Noongar Boodja Trust",
    "28000030179": "The Smith Family",
}
SECTIONS = {1:"Identity / regulatory",2:"Purpose / cause",3:"Programs / services",4:"Activities / SDGs",5:"Geography / beneficiaries",6:"Participation",7:"Direct service / capacity",8:"Fundraising",9:"Governance / leadership",10:"People / workforce",11:"Scale / capability",12:"Relationships",13:"Finances",14:"Funding / dependencies",15:"Ethos / values",16:"Conduct / adverse",17:"Notable history",18:"Evaluation / outcomes",19:"Classification / search / AI discovery",20:"Evidence / coverage / freshness / corrections"}
QUERY_SECTIONS = (1, 2, 3, 5, 11, 13, 14)

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

def load(abn): return json.loads((IN / abn / "experimental_governed_records.json").read_text(encoding="utf-8"))

def envelope(data):
    """One portable, intentionally lossy record shape. No new semantic routing."""
    graph = data["graph"]
    assigns = {x["observation_id"]: x["section_ids"] for x in graph["evidence"]}
    anatomy = data.get("observation_anatomy", {})
    out = []
    for ob in graph["observations"]:
        origin = anatomy.get(ob["record_id"], "unknown")
        status = "governed" if origin == "positive_historical_replay" else "structured_fact"
        out.append({
            "id": ob["record_id"], "subject": ob["subject_id"], "scope": ob.get("scope_id"),
            "proposition_type": ob["predicate"], "target_sections": assigns.get(ob["record_id"], []),
            "value": ob.get("value"), "evidence_locator": ob.get("evidence_locator_ids", []),
            "source_locator": ob.get("source_record_ids", []),
            "source_authority": "regulator_structured" if origin == "positive_structured" else "historical_governed_replay",
            "attribution": "retained historical source representation",
            "time": ob.get("observation_time"), "epistemic_status": status,
            "missingness": None, "coverage": None,
            # Kept solely to make dropped semantics auditable in this spike.
            "dropped_from_canonical": {"outcome_state": ob.get("outcome_state"), "qualifications": ob.get("qualifications"), "supersedes": ob.get("supersedes_observation_id")},
        })
    covered = {s for item in out for s in item["target_sections"]}
    coverage = [{"section_id": s, "state": "POPULATED" if s in covered else "NOT_PROCESSED",
                 "basis": "computed_from_envelope_presence" if s in covered else "no_retained_compatible_proposition"}
                for s in SECTIONS]
    return out, coverage

def projection(items, coverage):
    return {"sections": [{"section_id": s, "title": SECTIONS[s],
              "proposition_ids": [x["id"] for x in items if s in x["target_sections"]],
              "missingness": next(x["state"] for x in coverage if x["section_id"] == s)} for s in SECTIONS]}

def render_b(name, items, coverage):
    lines = [f"# B — {name}: straight-line progressive card", "", "> EXPERIMENTAL, NON-PRODUCTION. Retained historical material only.", ""]
    for s in SECTIONS:
        selected = [x for x in items if s in x["target_sections"]]
        if selected:
            badges = ", ".join(sorted({x["source_authority"] for x in selected}))
            lines.append(f"- §{s} {SECTIONS[s]} — {len(selected)} proposition(s); `{badges}`; evidence ledger available.")
    absent = [str(x["section_id"]) for x in coverage if x["state"] != "POPULATED"]
    lines += ["", f"Coverage: {20-len(absent)}/20 populated. Not processed: {', '.join(absent) or 'none'}. This is not an absence claim."]
    return "\n".join(lines) + "\n"

def render_c(name, items, coverage):
    selected = [x for x in items if set(x["target_sections"]) & set(QUERY_SECTIONS)]
    lines = [f"# C — {name}: query-time orientation response", "", "**Asked:** What is this organisation, what does it do, who does it serve, and what scale/funding information is retained?", "", "Response assembled at render time from retained propositions:"]
    for x in selected[:12]:
        value = json.dumps(x["value"], ensure_ascii=False) if isinstance(x["value"], (dict, list)) else str(x["value"])
        lines.append(f"- `{x['proposition_type']}`: {value[:360]}  ")
        lines.append(f"  _{x['source_authority']} · {x['epistemic_status']} · locator {', '.join(x['evidence_locator'])}_")
    missing = [SECTIONS[x["section_id"]] for x in coverage if x["state"] != "POPULATED"]
    lines += ["", "Not answered from this query view: " + "; ".join(missing) + ". These are unprocessed/unsupported here, not negative findings."]
    return "\n".join(lines) + "\n"

def render_ledger(name, items):
    lines = [f"# B — {name}: evidence ledger", "", "|Proposition|Sections|Authority / status|Locator|", "|---|---|---|---|"]
    for x in items:
        value = json.dumps(x["value"], ensure_ascii=False) if isinstance(x["value"], (dict, list)) else str(x["value"])
        lines.append(f"|{x['proposition_type']}: {value[:140]}|{', '.join(map(str, x['target_sections']))}|{x['source_authority']} / {x['epistemic_status']}|{', '.join(x['evidence_locator'])}|")
    return "\n".join(lines) + "\n"

def main():
    rows = []
    for abn, name in SUBJECTS.items():
        data = load(abn); items, coverage = envelope(data); a = json.loads((IN / abn / "governed_projection.json").read_text(encoding="utf-8"))
        b = projection(items, coverage)
        apos = {x["section_id"] for x in a["sections"] if x.get("observation_ids")}
        bpos = {x["section_id"] for x in b["sections"] if x.get("proposition_ids")}
        folder = OUT / abn
        dump(folder / "A_actual_projection.json", a); dump(folder / "B_envelope.json", {"propositions": items, "coverage": coverage}); dump(folder / "B_projection.json", b)
        (folder / "B_card.md").parent.mkdir(parents=True, exist_ok=True)
        (folder / "B_card.md").write_text(render_b(name, items, coverage), encoding="utf-8")
        (folder / "B_ledger.md").write_text(render_ledger(name, items), encoding="utf-8")
        (folder / "C_query_time.md").write_text(render_c(name, items, coverage), encoding="utf-8")
        # The actual compiler adds object validation and explicit coverage records; B derives coverage.
        rows.append({"abn": abn, "name": name, "a_positive_sections": sorted(apos), "b_positive_sections": sorted(bpos),
                     "a_b_section_parity": apos == bpos, "a_b_missingness_parity": (set(SECTIONS)-apos) == (set(SECTIONS)-bpos),
                     "propositions": len(items), "c_query_propositions": len([x for x in items if set(x["target_sections"]) & set(QUERY_SECTIONS)]),
                     "source_authorities": sorted({x["source_authority"] for x in items})})
    summary = {"token": "REALITY_SPIKE_8_ARCHITECTURE_INVERSION_DISCOVERED", "provider_calls": 0, "network_acquisition": 0,
               "subjects": rows, "all_a_b_parity": all(x["a_b_section_parity"] and x["a_b_missingness_parity"] for x in rows),
               "paths": {"A": "retained source representations → historical typed records → experimental promotion → integrated 20-section compiler → surface",
                         "B": "retained experimental records → one normalized envelope → deterministic existing assignment replay → progressive card + ledger",
                         "C": "retained envelope → query section selection → attributed response"}}
    dump(OUT / "summary.json", summary)
if __name__ == "__main__": main()
