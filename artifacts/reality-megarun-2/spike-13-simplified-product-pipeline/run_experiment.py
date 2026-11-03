"""Disposable Spike 13 A/B replay; no canonical or provider interaction."""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent
TOKEN = "REALITY_SPIKE_13_SIMPLIFIED_PIPELINE_DISCOVERED"

# These are only retained Spike-12 evidence summaries.  No source acquisition or
# natural-language inference occurs here; predicate/section are explicit fixtures.
EVIDENCE = [
    ("RC-1", "Australian Red Cross", "two operating divisions", "organisation", "2024-25", "structure", "organisation", None),
    ("RC-2", "Australian Red Cross", "member-run services", "service", "2024-25", "service_description", "capacity", None),
    ("RC-3", "Australian Red Cross", "branches", "site/footprint", "2024-25", "footprint", "capacity", None),
    ("RC-4", "Australian Red Cross", "volunteers and employees", "organisation", "2024-25", "workforce", "capacity", "capacity:workforce"),
    ("RC-5", "Australian Red Cross", "reported reach metrics", "reported metric", "2024-25", "reported_reach", "outcomes", "capacity:reach"),
    ("RC-6", "Australian Red Cross", "ACFID Code commitment and stated values", "organisation", "2024-25", "commitment", "ethos", "ethos:commitment"),
    ("RC-7", "Australian Red Cross", "external audit / separately audited programmes", "organisation/programme", "2024-25", "audit_statement", "governance", None),
    ("WV-1", "World Vision Australia", "named directors and committee responsibilities", "organisation", "2025", "governance_structure", "governance", None),
    ("WV-2", "World Vision Australia", "international-board relationship", "organisation relationship", "2025", "relationship", "relationships", None),
    ("WV-3", "World Vision Australia", "account certification and auditor", "organisation", "2025", "audit_statement", "governance", None),
    ("WV-4", "World Vision Australia", "faith-related director statement", "speaker/director", "2025", "faith_statement", "ethos", "ethos:speaker_scoped"),
    ("SUN-1", "Sunrise Foundation", "historical structured regulator bundles", "organisation", "historical", "regulator_bundle", "classification", None),
]
SUBJECTS = ["Australian Red Cross", "World Vision Australia", "MSF", "Bush Heritage", "Sunrise Foundation"]
COVERAGE = {
    "Australian Red Cross": "examined_with_candidates", "World Vision Australia": "examined_with_candidates",
    "MSF": "no_compatible_retained_evidence", "Bush Heritage": "no_compatible_retained_evidence",
    "Sunrise Foundation": "not_processed",
}

def proposition(row):
    ident, subject, claim, scope, period, predicate, section, semantic = row
    return {"proposition_id": f"P-{ident}", "subject_ref": subject, "predicate": predicate,
            "value": {"kind": "attributed_text", "data": claim},
            "scope": {"level": scope, "ref": None, "text": scope},
            "valid_time": {"start": period, "end": period, "precision": "period"},
            "assertion_mode": "reported", "status": "candidate", "evidence_refs": [ident],
            "source_role": "regulator_record" if ident == "SUN-1" else "first_party_report",
            "domain_semantics": semantic, "route": section}

def route(props):
    """The complete deterministic product router: route is explicit fixture metadata."""
    result = defaultdict(list)
    for p in props:
        if p["status"] == "candidate": result[p["route"]].append(p["proposition_id"])
    return dict(result)

def answer(question, subject, props):
    matched = [p for p in props if p["subject_ref"] == subject]
    if not matched:
        state = COVERAGE[subject]
        return {"question": question, "subject": subject, "answer": f"I cannot answer from this ledger: coverage is {state}.", "citations": [], "bounded": True}
    if "ethos" in question.lower():
        matched = [p for p in matched if p["route"] == "ethos"]
        if "organisation-wide" in question.lower():
            matched = [p for p in matched if p["scope"]["level"] == "organisation"]
    elif "govern" in question.lower() or "audit" in question.lower():
        matched = [p for p in matched if p["route"] == "governance"]
    elif "capacity" in question.lower() or "service" in question.lower():
        matched = [p for p in matched if p["route"] == "capacity"]
    if "current" in question.lower():
        matched = [p for p in matched if p["valid_time"]["start"] != "historical"]
    if not matched:
        return {"question": question, "subject": subject, "answer": "The ledger has no candidate in that requested domain.", "citations": [], "bounded": True}
    # Terra simulation is constrained to quoted fixture values, scope/time and IDs.
    phrases = [f"{p['value']['data']} ({p['scope']['level']}; {p['valid_time']['start']})" for p in matched]
    return {"question": question, "subject": subject, "answer": "; ".join(phrases) + ".", "citations": [p["evidence_refs"][0] for p in matched], "bounded": True}

def main():
    start = time.perf_counter(); props = [proposition(r) for r in EVIDENCE]; sections = route(props)
    ledger = {"experiment": "Spike 13 challenger", "envelope": "Spike 12 G2", "propositions": props,
              "coverage": [{"subject_ref": s, "projection_domain": "all", "state": COVERAGE[s], "evidence_boundary_refs": []} for s in SUBJECTS],
              "relations": [
                  {"type": "scope_split", "members": ["P-RC-7"], "outcome": "organisation/programme audit remains reviewable"},
                  {"type": "speaker_scope", "members": ["P-WV-4"], "outcome": "not organisation-wide ethos"},
                  {"type": "time_bound", "members": ["P-SUN-1"], "outcome": "not current"},
                  {"type": "duplicate", "members": ["P-RC-6"], "outcome": "one proposition; repeated support permitted"},
              ]}
    questions = [
        ("What capacity evidence is retained?", "Australian Red Cross"),
        ("What governance or audit evidence is retained?", "World Vision Australia"),
        ("What ethos evidence is organisation-wide?", "World Vision Australia"),
        ("What can you say about the charity?", "MSF"),
        ("What can you say about the charity?", "Bush Heritage"),
        ("What is current?", "Sunrise Foundation"),
    ]
    answers = [answer(q, s, props) for q, s in questions]
    elapsed = round((time.perf_counter() - start) * 1000, 3)
    challenger = {"stages": 5, "translations_adapters": 2, "record_types": 4,
                  "semantic_retained": "12/12 attributed claims; scope/time on 12/12; capacity/ethos qualifier on 4/4 requiring it",
                  "semantic_loss": "no new extraction or promotion; values remain candidates", "useful_sections": len(sections),
                  "missingness_fidelity": "5/5 explicit coverage states; MSF/Bush Heritage are not fabricated",
                  "provenance_fidelity": "12/12 evidence IDs and source roles retained", "conflicts_corrections": "4 reviewable relations; no fabricated substantive conflict",
                  "human_review_units": 16, "glue_loc": 154, "runtime_ms": elapsed,
                  "readability": "one progressive card section per deterministic route plus evidence IDs", "ai_query": "6/6 bounded; all supported answers cite evidence or abstain"}
    legacy = {"stages": 10, "translations_adapters": "8-9", "record_types": "6+", "semantic_retained": "governed replay; no better evidence coverage for absent reports",
              "semantic_loss": "none measured in prior replay", "useful_sections": "historically 6-12 depending subject", "missingness_fidelity": "explicit coverage",
              "provenance_fidelity": "retained through typed graph", "conflicts_corrections": "separate governance/correction machinery", "human_review_units": 16,
              "glue_loc": "~100 bridge + historical compiler/runtime", "runtime_ms": "not comparable: historical artifacts replayed", "readability": "20-section compiled surface", "ai_query": "requires a ledger/read model"}
    result = {"token": TOKEN, "spec_identifier": "CG-REALITY-SPIKE-13-SIMPLIFIED-PRODUCT-PIPELINE-TERRA-164", "model": "terra",
              "inputs": {"spike_11": "read", "spike_12": "read", "spike_9_10": "absent; not reconstructed", "spike_8": "read as legacy benchmark"},
              "subjects": SUBJECTS, "legacy": legacy, "challenger": challenger,
              "compiler_runtime_test": {"finding": "migration_residue_for_product_projection", "basis": "Spike 8 demonstrated section/missingness parity through a straight-line envelope; this replay retains review/relations but does not invoke a compiler.", "not_residue": "evidence attribution, scope/time, coverage, review status and correction relations"},
              "mutations": {"s0": False, "github": False, "canonical": False, "authorisation": False, "provider_subsystem": False}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "challenger_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (OUT / "terra_query_simulation.json").write_text(json.dumps({"model": "terra", "mode": "constrained-ledger simulation", "answers": answers}, indent=2), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    card = ["# Progressive card (challenger)", "", "Candidate claims only; each claim is attributable and opens to the ledger."]
    for subject in SUBJECTS:
        card += [f"\n## {subject}", f"Coverage: `{COVERAGE[subject]}`"]
        for p in [x for x in props if x["subject_ref"] == subject]: card.append(f"- {p['route']}: {p['value']['data']} — [{p['evidence_refs'][0]}] ({p['valid_time']['start']}, {p['scope']['level']}; candidate)")
    (OUT / "progressive_card.md").write_text("\n".join(card) + "\n", encoding="utf-8")
    assert len(props) == 12 and all(p["evidence_refs"] and p["scope"] and p["valid_time"] for p in props)
    assert all(a["bounded"] for a in answers) and all(answers[i]["citations"] == [] for i in (2, 3, 4, 5))

if __name__ == "__main__": main()
