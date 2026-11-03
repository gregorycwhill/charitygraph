"""Disposable, provider-free 20-subject batch scale probe.

Consumes retained regulator-return representations and three explicitly bounded
report controls.  It writes experimental artifacts only; no observation is
promoted and no natural-language semantic inference is attempted.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT.parent / "charitygraph-data" / "releases" / "rc4-2026-08-14" / "source-records"
OUT = ROOT / "artifacts" / "reality-megarun-3-twenty-charity-dryrun"
PRIOR_ABNS = {
    "24646643156", "32590616129", "45127505739", "49079016738", "74052124375",
    "50169561394", "28004778081", "78053639115", "75442934320", "87684571829",
    "32942723464", "82136720784", "30091040649", "11566496319",
}
RICH_CONTROLS = [
    ("50169561394", "Australian Red Cross Society", 117),
    ("28004778081", "World Vision Australia", 46),
    ("78053639115", "Bush Heritage Australia", 59),
]


def ais_paths():
    return sorted(p for p in RECORDS.iterdir() if p.is_file() and p.name.startswith("src%3Aacnc-ais-detail%3A"))


def abn_from_path(path: Path) -> str:
    return path.name.split("%3A")[2]


def add(props, subject, abn, source_id, predicate, content, pointer, scope, qualifier=None):
    props.append({"id": f"G2-20-{len(props)+1:04d}", "subject": subject, "subject_id": abn,
        "predicate": predicate, "content": str(content), "scope": scope,
        "valid_time": "AIS StatementYear", "source_role": "regulator_lodged_structured_return",
        "source_record_id": source_id, "locator": pointer,
        "epistemic": "reported_source_native_structured_field", "state": "candidate",
        "qualifier": qualifier or {}, "route": None, "novel": True})


def route(predicate: str) -> str:
    if predicate in {"reported_purpose_description", "reported_program"}:
        return "section_3_purpose_programs"
    if predicate.startswith("reported_total_") or predicate == "reported_surplus_deficit":
        return "section_12_finance_resource_flow"
    if predicate in {"reported_fte_staff", "reported_unpaid_volunteers"}:
        return "section_6_workforce"
    if predicate == "reported_related_party_transaction_status":
        return "section_18_governance_controls"
    return "section_1_identity"


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    selected = [p for p in ais_paths() if abn_from_path(p) not in PRIOR_ABNS][:17]
    if len(selected) != 17:
        raise RuntimeError(f"expected >=17 new retained AIS records, found {len(selected)}")
    chunks, props, abstentions, outcomes, failures = [], [], [], [], []
    for abn, subject, pages in RICH_CONTROLS:
        for slot in range(1, 4):
            chunks.append({"chunk_id": f"{abn}-report-control-{slot}", "subject": subject, "abn": abn,
                "representation": "retained report diagnostic/bounded recovery", "locator": f"report control range; sampled slot {slot}",
                "state": "coverage_only_representation_unavailable_for_novel_extraction", "report_pages": pages})
        abstentions.append({"subject": subject, "domain": "report_proposition_extraction", "state": "not_established_from_retained_representation", "reason": "retained report control has no newly readable source-native representation; prior evidence is not replayed"})
        outcomes.append({"subject": subject, "subject_id": abn, "cohort": "prior_rich_report_control", "terminal_state": "coverage_card_abstention", "report_representation": "bounded/unavailable for novel extraction", "chunks": 3, "propositions": 0, "review_units": 1, "novel": False})
        failures.append({"subject": subject, "taxonomy": "report_native_representation_unavailable", "local": True, "action": "coverage/card terminal; continue batch"})
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
    for path in selected:
        record = json.loads(path.read_text(encoding="utf-8"))
        data, abn, source_id = record["source_payload"]["data"], abn_from_path(path), record["source_record_id"]
        subject = data.get("LegalName") or f"Australian charity (ABN {abn})"
        before = len(props)
        for i, (label, keys) in enumerate(fields, 1):
            present = [k for k in keys if data.get(k) not in (None, "", [], {})]
            chunks.append({"chunk_id": f"{abn}-{i:02d}", "subject": subject, "abn": abn, "label": label,
                "source_record_id": source_id, "locator": "$.source_payload.data." + ",$.source_payload.data.".join(present),
                "representation": "retained ACNC AIS structured return", "state": "inspected_structured" if present else "abstained_empty_structured", "field_count": len(present)})
        add(props, subject, abn, source_id, "legal_name", subject, "$.source_payload.data.LegalName", "organisation identity")
        add(props, subject, abn, source_id, "reported_charity_size", data.get("CharitySize"), "$.source_payload.data.CharitySize", "organisation; AIS size category")
        add(props, subject, abn, source_id, "reported_operating_status", data.get("ActivityOperating"), "$.source_payload.data.ActivityOperating", "organisation; AIS return")
        if data.get("ActivityPersuitPurposesDescription"):
            add(props, subject, abn, source_id, "reported_purpose_description", data["ActivityPersuitPurposesDescription"], "$.source_payload.data.ActivityPersuitPurposesDescription", "organisation self-description", {"not": "independently evaluated outcome"})
        for i, program in enumerate(data.get("Programs") or []):
            add(props, subject, abn, source_id, "reported_program", program.get("Name"), f"$.source_payload.data.Programs[{i}].Name", "named program", {"classification": program.get("ProgramClassification"), "location_count": len(program.get("ProgramLocations") or [])})
        for field, predicate in [("RevenueTotal", "reported_total_revenue"), ("ExpenseTotal", "reported_total_expense"), ("TotalAssets", "reported_total_assets"), ("TotalLiabilities", "reported_total_liabilities"), ("NetSurplusDeficit", "reported_surplus_deficit"), ("HrFteStaff", "reported_fte_staff"), ("HrUnpainVolunteers", "reported_unpaid_volunteers")]:
            if data.get(field) is not None: add(props, subject, abn, source_id, predicate, data[field], f"$.source_payload.data.{field}", "AIS reporting-period field")
        if data.get("FinRelatedPartyTransactions"):
            add(props, subject, abn, source_id, "reported_related_party_transaction_status", data["FinRelatedPartyTransactions"], "$.source_payload.data.FinRelatedPartyTransactions", "AIS disclosure status", {"not": "propriety finding"})
        for domain in ("relationship_graph", "outcome_measurement", "service_capacity", "financial_statement_context"):
            abstentions.append({"subject": subject, "domain": domain, "state": "not_established_from_retained_representation", "reason": "AIS structured return does not establish this rich domain"})
        outcomes.append({"subject": subject, "subject_id": abn, "cohort": "new_retained_AIS", "terminal_state": "ledger_coverage_card", "report_representation": "no retained report selected; AIS structured return available", "chunks": 10, "propositions": len(props)-before, "review_units": (len(props)-before)+4, "novel": True})
    for p in props: p["route"] = route(p["predicate"])
    cards = []
    for outcome in outcomes:
        ps = [p for p in props if p["subject_id"] == outcome["subject_id"]]
        cards.append({"subject": outcome["subject"], "terminal_state": outcome["terminal_state"], "evidence_state": outcome["report_representation"], "candidate_count": len(ps), "progressive_routes": dict(Counter(p["route"] for p in ps)), "review_unit": "candidate plus exact JSON pointer" if ps else "coverage abstention"})
    route_counts, failure_counts = Counter(p["route"] for p in props), Counter(f["taxonomy"] for f in failures)
    summary = {"schema": "charitygraph.reality-megarun3.twenty-charity-dryrun/v1", "run_id": "CG-MEGARUN3-172-TWENTY-CHARITY-BATCH-DRYRUN-TERRA", "status": "complete_experimental_no_canonical_mutation", "subjects": outcomes, "subject_count": len(outcomes), "terminal_subjects": len(outcomes), "pages_or_chunks_inspected": len(chunks), "substantive_chunks_per_AIS_subject": 10, "proposition_count": len(props), "coverage_abstentions": len(abstentions), "review_units": sum(o["review_units"] for o in outcomes), "section_coverage": dict(route_counts), "failure_taxonomy": dict(failure_counts), "maturity_distribution": {"ledger_coverage_card": 17, "coverage_card_abstention": 3}, "automatable_share": {"mechanically_renderable_subjects": 17, "of_20": 0.85, "note": "structured AIS-to-candidate construction; review/promotion remains governed"}, "bespoke_exceptions": [], "artifact_volume": {"ledgers": 4, "cards": len(cards), "chunk_records": len(chunks)}, "batch_bottlenecks": ["retained report representation is sparse/unreadable for controls", "rich relationship, measurement, capacity and statement-table semantics remain coverage gaps/satellites", "candidate review units scale with proposition yield rather than subject count"], "top_100_workload_model": {"sample_subjects": 20, "terminal_rate": 1.0, "AIS_like_mix_projection": {"subjects": 85, "chunks": 850, "candidate_propositions": round(len(props)/17*85), "coverage_abstentions": 340}, "report_control_mix_projection": {"subjects": 15, "coverage_review_units": 15, "representation_recovery_required_before_novel_report_claims": True}, "cost_shape": "provider-free retained structured routing costs no model spend; human/governed review is approximately candidate propositions plus coverage units; uncalled providers excluded"}, "provider_network_s0_github_activity": "none", "canonical_mutations": False}
    state = {"session_key": "cg-megarun3-172-twenty-charity-batch-dryrun-v1", "state": "COMPLETE", "counts": {"subjects": len(outcomes), "chunks": len(chunks), "propositions": len(props), "terminal": len(outcomes)}, "restart": "Disposable artifacts only; retained raw source bytes were not copied."}
    for name, body in [("PAGE_CHUNK_LEDGER.json", chunks), ("G2_PROPOSITION_LEDGER.json", props), ("COVERAGE_ABSTENTION_LEDGER.json", abstentions), ("PROGRESSIVE_CARDS.json", cards), ("FAILURE_TAXONOMY.json", failures), ("SUMMARY.json", summary), ("CAMPAIGN_STATE.json", state)]:
        (OUT / name).write_text(json.dumps(body, indent=2), encoding="utf-8")
    (OUT / "READOUT.md").write_text(f"# Twenty-charity provider-free dry run\n\nAll {len(outcomes)} subjects reached an explicit terminal ledger/coverage/card state. Seventeen newly propositionised AIS subjects yielded {len(props)} unpromoted source-native candidates from {len(chunks)} inspected chunks; three prior rich report controls closed as coverage/card abstentions because their retained report representation was unavailable for novel extraction. No provider, acquisition, S0, GitHub, or canonical mutation occurred.\n", encoding="utf-8")
    print(json.dumps({"subjects": len(outcomes), "chunks": len(chunks), "propositions": len(props), "terminal": len(outcomes), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    run()
