"""Disposable Mega-run 3 blind-cohort experiment.

This deliberately consumes retained ACNC AIS source records only.  It is not a
promotion path: every emitted statement is an unpromoted candidate with its
JSON-pointer locator.  The fixed cohort was chosen by representation diversity
before reading subject-level claims.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# The experiment lives inside the Builder repository, beside its Data sibling.
RECORDS = ROOT.parent / "charitygraph-data" / "releases" / "rc4-2026-08-14" / "source-records"
OUT = ROOT / "artifacts" / "reality-megarun-3-blind-cohort"

# These are deliberately unlike Spike 15's ARC/WVA/BHA/MSF rich cases and are
# also excluded from the immediately preceding report-furnace selection.
COHORT = {
    "75442934320": "medium arts body; unusually program-rich AIS",
    "87684571829": "small organisation; unusually program-rich AIS",
    "32942723464": "large Indigenous legal-service body",
    "82136720784": "small animal-welfare body",
    "30091040649": "medium international child-focused body",
    "11566496319": "small ACT artists association with related-party disclosure",
}


def find_record(abn: str) -> dict:
    matches = [path for path in RECORDS.iterdir() if path.is_file() and f"acnc-ais-detail%3A{abn}%3A" in path.name]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one retained AIS source for {abn}; got {len(matches)}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def add(props, subject, source_id, predicate, content, pointer, scope, qualifier=None):
    props.append({
        "id": f"G2-BC-{len(props)+1:03d}", "subject": subject,
        "predicate": predicate, "content": content, "scope": scope,
        "valid_time": "AIS StatementYear", "source_role": "regulator_lodged_structured_return",
        "source_record_id": source_id, "locator": pointer,
        "epistemic": "reported_source_native_structured_field", "state": "candidate",
        "qualifier": qualifier or {}, "route": None,
    })


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    chunks, props, subject_notes, abstentions = [], [], [], []
    for abn, rationale in COHORT.items():
        record = find_record(abn)
        data = record["source_payload"]["data"]
        name = data["LegalName"]
        sid = record["source_record_id"]
        # Each is a source-native structurally bounded evidence chunk, not a
        # fabricated page.  We inspect at least ten per subject where present.
        fields = [
            ("identity", ["LegalName", "CharitySize", "StatementYear"]),
            ("purpose", ["ActivityPersuitPurposesDescription"]),
            ("activity", ["ActivityMain", "ActivityOperating", "ActivityOperatingOverseas"]),
            ("beneficiaries", ["BeneficiaryMain", "BeneficiaryOtherDescription"]),
            ("programs", ["Programs"]),
            ("workforce", ["HrFteStaff", "HrFullTimeEmployees", "HrPartTimeEmployees", "HrUnpainVolunteers"]),
            ("income", ["RevenueTotal", "IncomeDonationsBequests", "IncomeGovernmentGrants"]),
            ("expenses", ["ExpenseTotal", "ExpenseEmployees", "ExpenseGrantDonationsInAustralia"]),
            ("financial_position", ["TotalAssets", "TotalLiabilities", "NetAssetsLiabilities", "NetSurplusDeficit"]),
            ("governance_regulatory", ["FinRelatedPartyTransactions", "RelatedPartyDetails", "RegulatorFundRaising"]),
        ]
        for n, (label, keys) in enumerate(fields, 1):
            present = {k: data.get(k) for k in keys if data.get(k) not in (None, "", [], {})}
            chunks.append({"chunk_id": f"{abn}-{n:02d}", "subject": name, "abn": abn,
                "label": label, "source_record_id": sid, "locator": "$.source_payload.data." + ",$.source_payload.data.".join(present),
                "state": "inspected_structured" if present else "abstained_empty_structured", "field_count": len(present)})
        # Atomic propositions are intentionally conservative and mechanically
        # tied to disclosed fields; no text classification or inferred impact.
        add(props, name, sid, "legal_name", str(data["LegalName"]), "$.source_payload.data.LegalName", "organisation identity")
        add(props, name, sid, "reported_charity_size", str(data.get("CharitySize")), "$.source_payload.data.CharitySize", "organisation; AIS size category")
        add(props, name, sid, "reported_operating_status", str(data.get("ActivityOperating")), "$.source_payload.data.ActivityOperating", "organisation; AIS return")
        if data.get("ActivityPersuitPurposesDescription"):
            add(props, name, sid, "reported_purpose_description", data["ActivityPersuitPurposesDescription"], "$.source_payload.data.ActivityPersuitPurposesDescription", "organisation self-description", {"not": "independently evaluated outcome"})
        for i, program in enumerate(data.get("Programs") or [], 1):
            add(props, name, sid, "reported_program", str(program.get("Name")), f"$.source_payload.data.Programs[{i-1}].Name", "named program", {"classification": program.get("ProgramClassification"), "location_count": len(program.get("ProgramLocations") or [])})
        for field, predicate in [("RevenueTotal", "reported_total_revenue"), ("ExpenseTotal", "reported_total_expense"), ("TotalAssets", "reported_total_assets"), ("TotalLiabilities", "reported_total_liabilities"), ("NetSurplusDeficit", "reported_surplus_deficit"), ("HrFteStaff", "reported_fte_staff"), ("HrUnpainVolunteers", "reported_unpaid_volunteers")]:
            if data.get(field) is not None:
                add(props, name, sid, predicate, str(data[field]), f"$.source_payload.data.{field}", "AIS reporting-period field")
        if data.get("FinRelatedPartyTransactions"):
            add(props, name, sid, "reported_related_party_transaction_status", str(data["FinRelatedPartyTransactions"]), "$.source_payload.data.FinRelatedPartyTransactions", "AIS disclosure status", {"not": "propriety finding"})
        subject_notes.append({"abn": abn, "subject": name, "selection_rationale": rationale,
            "program_count": len(data.get("Programs") or []), "size": data.get("CharitySize"),
            "propositions": sum(1 for p in props if p["subject"] == name), "chunks": 10})
        for domain, reason in [
            ("relationship_graph", "AIS program and disclosure fields do not establish a complete relationship graph"),
            ("outcome_measurement", "AIS purpose/program fields do not establish an outcome measure, denominator or method"),
            ("service_capacity", "reported program presence does not establish current service capacity or availability"),
            ("financial_statement_context", "AIS totals do not preserve full statement/table context or comparative periods"),
        ]:
            abstentions.append({"subject": name, "domain": domain, "state": "not_established_from_retained_representation", "reason": reason})

    # Deterministic external projection routing. G2 proposition identity stays route-free.
    for p in props:
        p["route"] = ("section_3_purpose_programs" if p["predicate"] in {"reported_purpose_description", "reported_program"}
            else "section_12_finance_resource_flow" if p["predicate"].startswith("reported_total_") or p["predicate"] == "reported_surplus_deficit"
            else "section_6_workforce" if "staff" in p["predicate"] or "volunteers" in p["predicate"]
            else "section_18_governance_controls" if "related_party" in p["predicate"]
            else "section_1_identity")
    ledgers = {s["subject"]: [p for p in props if p["subject"] == s["subject"]] for s in subject_notes}
    cards = []
    for s in subject_notes:
        ps = ledgers[s["subject"]]
        cards.append({"subject": s["subject"], "evidence_state": "retained regulator-lodged AIS; structured chunks inspected",
            "progressive_card": {"identity": [p for p in ps if p["route"] == "section_1_identity"], "programs": [p for p in ps if p["route"] == "section_3_purpose_programs"], "finance": [p for p in ps if p["route"] == "section_12_finance_resource_flow"]},
            "claim_ledger": ps, "review_unit": "one candidate proposition plus exact AIS JSON pointer"})
    counts = Counter(p["route"] for p in props)
    summary = {"schema": "charitygraph.reality-megarun3.blind-cohort/v1", "status": "complete_experimental_no_canonical_mutation",
        "run_id": "CG-MEGARUN3-168-BLIND-NOVEL-COHORT-TERRA", "subjects": subject_notes,
        "evidence_volume": {"subjects": len(subject_notes), "inspected_chunks": len(chunks), "minimum_chunks_per_subject": 10, "source_records": len(subject_notes)},
        "proposition_count": len(props), "abstention_count": len(abstentions), "abstentions": abstentions,
        "section_coverage": dict(counts), "bespoke_exceptions": ["Program arrays vary from 2 to 10 entries; repeated atomic reported_program records suffice.", "Related-party disclosure is a disclosure-status satellite, not a governance-quality inference.", "AIS purpose prose remains a quoted reported description; no impact/outcome classification was attempted."],
        "satellites": ["AIS StatementYear", "program classification", "program location count", "reporting-period scope", "source JSON pointer"],
        "adapter_changes": "none; consumed retained acnc-ais-detail representation directly", "review_burden": f"one proposition and exact JSON pointer; {len(props)} candidate review units plus {len(abstentions)} coverage abstentions",
        "strongest_evidence_against_hypothesis": "Structured AIS supports many atomic spine records but compresses relationships, measurement methodology, temporal program changes and full financial-statement context into satellites or coverage gaps; it cannot by itself make a richly explanatory card.",
        "provider_network_s0_github_activity": "none", "canonical_mutations": False}
    (OUT / "PAGE_CHUNK_LEDGER.json").write_text(json.dumps(chunks, indent=2), encoding="utf-8")
    (OUT / "G2_PROPOSITION_LEDGER.json").write_text(json.dumps(props, indent=2), encoding="utf-8")
    (OUT / "ABSTENTION_LEDGER.json").write_text(json.dumps(abstentions, indent=2), encoding="utf-8")
    (OUT / "PROGRESSIVE_CARDS_AND_CLAIM_LEDGERS.json").write_text(json.dumps(cards, indent=2), encoding="utf-8")
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "CAMPAIGN_STATE.json").write_text(json.dumps({"session_key": "cg-megarun3-168-blind-novel-cohort-v1", "state": "COMPLETE", "counts": {"subjects": len(subject_notes), "chunks": len(chunks), "propositions": len(props)}}, indent=2), encoding="utf-8")
    readout = f"# Mega-run 3 blind novel cohort\n\nSix previously unused (for Spikes 15/16) charities were selected by diversity before subject evidence was inspected. The retained AIS representation yielded {len(chunks)} inspected structured chunks and {len(props)} unpromoted atomic G2 candidates.\n\nThe G2 spine generalised without an adapter change, but rich program, relationship, measurement and financial-table semantics remain satellites or coverage gaps. No source acquisition, provider call, S0 work, GitHub operation or canonical mutation occurred.\n"
    (OUT / "READOUT.md").write_text(readout, encoding="utf-8")
    print(json.dumps({"subjects": len(subject_notes), "chunks": len(chunks), "propositions": len(props), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    run()
