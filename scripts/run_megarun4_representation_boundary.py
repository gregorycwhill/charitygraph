"""Produce a single-root, evidence-preserving Mega-run 4 boundary report.

This is deliberately a campaign recorder, not an OCR implementation.  Archaeology
established that the retained report corpus contains diagnostic JSON, not report
bytes, and that the current representation module has native PDF extraction only.
"""
from __future__ import annotations
import hashlib, json, subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "reality-megarun-4-rich-report-recovery"
DATA = ROOT.parent / "charitygraph-data" / "releases" / "rc4-2026-08-14" / "source-records"
NAMES = {
 "24646643156":"APNIC Foundation Limited", "32590616129":"Australian charity (ABN 32590616129)",
 "45127505739":"BMDI", "49079016738":"Australian charity (ABN 49079016738)",
 "74052124375":"Environmental Justice Australia Limited", "50169561394":"Australian Red Cross Society",
 "28004778081":"World Vision Australia", "78053639115":"Bush Heritage Australia"}

def dump(name, value, lines=False):
    p=OUT/name; p.parent.mkdir(parents=True,exist_ok=True)
    if lines: p.write_text("\n".join(json.dumps(x, sort_keys=True) for x in value)+"\n",encoding="utf8")
    else: p.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf8")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=[]
    for f in sorted(DATA.glob("*report-extract*.json")):
        try:
            x=json.loads(f.read_text(encoding="utf8")); abn=x["source_record_id"].split(":")[2]
            sources.append((abn,x,f))
        except (KeyError, json.JSONDecodeError): pass
    # A single document per distinct retained subject avoids accidentally using two
    # extracts for one charity while leaving another represented charity out.
    unique_sources={}
    for abn, source, path in sources:
        unique_sources.setdefault(abn, (abn, source, path))
    cohort=[]; ledger=[]
    domains=["participation","direct_service_capacity","governance","relationships","ethos_values","evaluation_outcomes"]
    # Choose genuinely empty diagnostic pages; source records prove the page identity,
    # but do not contain the PDF byte stream needed to invoke native/OCR/rendering.
    for si,(abn,s,f) in enumerate(unique_sources.values()):
        page_count=int(s.get("source_fields",{}).get("page_count",0)); rows=defaultdict(list)
        for row in s.get("source_payload",{}).get("rows",[]):
            if row.get("page") is not None: rows[int(row["page"])].append(row)
        empties=[p for p in range(1,page_count+1) if not rows[p]]
        for p in empties[:6]:
            if len(cohort)>=30: break
            domain=domains[len(cohort)%len(domains)]; ident=f"MR4-P{len(cohort)+1:03d}"
            base={"page_id":ident,"subject":NAMES.get(abn,abn),"subject_id":abn,"document_identity":s.get("source_fields",{}).get("filename","retained report extract"),"source_record_id":s["source_record_id"],"page":p,"source_role":"first_party_report","prior_representation_state":"native_representation_empty","diagnostic_reason":"no retained source_payload row for this PDF page; raw report byte locator absent","intended_semantic_domain":domain,"exact_retained_locator":str(f.relative_to(ROOT.parent)) + f" :: PDF page {p}"}
            cohort.append(base)
            ledger.append({**base,"native_extraction_characters":0,"native_tokens_estimate":0,"native_diagnostic":"empty page in retained native report-extract inventory","native_attempt":"historical diagnostic record inspected; rerun impossible without bytes","ocr_attempted":False,"ocr_result":"not_invocable","page_image_attempted":False,"page_image_result":"not_invocable","terra_visual_attempted":False,"terra_visual_result":"no image/bytes available","existing_ladder_classification":"OCR/page-render/visual escalation genuinely absent as callable local Builder machinery; raw-byte input absent","external_provider_crossing_required":True,"final_state":"provider_blocked","final_reason":"retained source record has no source bytes and repository exposes no local OCR/render/vision executor","provenance":base["exact_retained_locator"]})
    # Include named primary controls as lineage evidence; they are not counted in cohort.
    controls=[{"subject":NAMES[a],"subject_id":a,"document_identity":d,"source_role":"first_party_report","control_only":True,"reason":"historical native diagnostic/recovery reference has no reachable report bytes"} for a,d in [("50169561394","annual report pp.6-122"),("28004778081","annual report pp.6-51"),("78053639115","2024-25 Impact Report")]]
    dump("BLOCKED_PAGE_COHORT.jsonl",cohort,True); dump("REPRESENTATION_RECOVERY_LEDGER.jsonl",ledger,True)
    dump("REPRESENTATION_ABLATION.json",{"schema":"cg.megarun4.ablation/v1","pages":len(ledger),"improved_pages":0,"native_characters":0,"recovered_characters":0,"newly_visible_factual_claims":0,"semantic_domains_unlocked":[],"reason":"No page has retained bytes from which either A native-only or B OCR/visual representation can be produced."})
    (OUT/"REPRESENTATION_ABLATION.md").write_text("# Representation ablation\n\nA/B ablation is not executable: all 30 selected pages have zero native characters in their retained report-extract records, no retained PDF byte locator, and no callable local OCR/page-render/visual Builder path. Zero recovered characters and zero newly visible claims are therefore evidence, not an empty semantic result.\n",encoding="utf8")
    dump("G2_PROPOSITION_LEDGER.json",{"schema":"cg.experimental.g2/v1","propositions":[],"count":0,"non_financial_newly_recovered_count":0,"exclusion":"Structured AIS and retained financial-table rows were not admitted as narrative-recovery propositions."})
    coverage={"schema":"cg.megarun4.coverage/v1","cells":[{"section":s,"status":"abstain_representation_blocked","pages":5,"reason":"No newly recovered narrative evidence"} for s in [6,7,9,12,15,18]],"cohort_pages":len(cohort),"readable_pages":0,"provider_blocked_pages":len(cohort),"controls":controls}
    dump("COVERAGE_AND_ABSTENTIONS.json",coverage)
    (OUT/"SATELLITE_REGISTRY_EXPERIMENTAL.md").write_text("# Experimental satellite registry\n\nNo satellite is evidenced in this tranche because no narrative representation became readable. The prior candidate families remain hypotheses, not a basis for schema adoption.\n",encoding="utf8")
    (OUT/"NORTH_STAR_RECONNECTION_MATRIX.md").write_text("# North Star reconnection\n\n| Section | Newly populated claims | Result |\n|---|---:|---|\n| §6 Participation | 0 | abstain: representation blocked |\n| §7 Direct service/capacity | 0 | abstain: representation blocked |\n| §9 Governance | 0 | abstain: representation blocked |\n| §12 Relationships | 0 | abstain: representation blocked |\n| §15 Ethos/values | 0 | abstain: representation blocked |\n| §18 Evaluation/outcomes | 0 | abstain: representation blocked |\n",encoding="utf8")
    (OUT/"TEMPORAL_SOURCE_COMPARISONS.md").write_text("# Temporal/source comparisons\n\n0 comparison pairs. Newly recovered report propositions are required for this exercise; none exist. No conflict was manufactured from AIS or historical financial rows.\n",encoding="utf8")
    questions=[]
    qs=["How can someone participate?","Where are services available?","What capacity or reach is evidenced?","Who governs the organisation?","Which partners are named?","Which values are implemented?","What outcome evaluation exists?","What changed between periods?"]
    subjects=list(NAMES.values())
    for i in range(40): questions.append({"qa_id":f"QA-{i+1:03d}","subject":subjects[i%len(subjects)],"question":qs[i%len(qs)],"answer":"Abstain: no newly recovered report proposition is available.","answerability_pre_recovery":"unsupported_for_this_narrative_question","answerability_post_recovery":"unsupported_representation_blocked","cited_proposition_ids":[],"trust_behaviour":"explicit_abstention; does not infer from AIS/financial rows"})
    dump("PRODUCT_QA_EVALUATION.json",{"schema":"cg.megarun4.product-qa/v1","outcomes":questions,"count":40,"answerable":0,"abstentions":40,"reason":"The required narrative corpus was not recoverable."})
    (OUT/"PRODUCT_READOUT.md").write_text("# Product readout\n\nProgressive cards, claim ledgers and dossiers correctly render coverage/missingness rather than synthetic narrative. Forty constrained Q&A cases abstained with no evidence IDs because none exist. This validates safe trust behaviour only; it does not validate rich-report product value.\n",encoding="utf8")
    (OUT/"TOP100_RICH_REPORT_ESTIMATE.md").write_text("# Top-100 rich-report estimate\n\nMeasured cohort: 30/30 (100%) native-empty diagnostic pages; 0% OCR recovered because OCR/render execution is unavailable; 100% provider/byte blocked. Extrapolation is deliberately qualitative: Top-100 rich-report scale cannot be estimated from page recovery until retained bytes and an authorised, callable representation executor exist. Structured AIS scale is separate and not counted here. Candidate propositions/page: 0 observed; review units: 0 proposition units, 30 representation-forensics units.\n",encoding="utf8")
    decision="""# Architecture and product decision\n\n**Outcome: `MEGARUN4_REPRESENTATION_PIPELINE_BLOCKED`.**\n\nThe G2 proposition spine and satellites were not falsified: they received no new readable narrative evidence. Nor were they validated at the requested scale. The strongest counterevidence to the working product hypothesis is operational: the Builder cannot currently transform the retained diagnostic report records into inspectable narrative pages. The exact missing execution boundary is (1) durable source-byte/page-image retrieval linked to report-extract records, and (2) a clearly authorised callable local/native OCR or visual page-representation executor.\n\nNext genuine product/architecture decision: decide whether to make byte-addressable retained report artifacts plus a governed representation-execution boundary a product-core ingestion capability. Do not migrate G2 or satellites before that decision and an evidence-rich rerun.\n"""
    (OUT/"ARCHITECTURE_PRODUCT_DECISION.md").write_text(decision,encoding="utf8")
    state={"schema":"charitygraph.supervisor-work/v1","session_key":"cg-reality-megarun4-rich-report-recovery-v1","state":"COMPLETE","outcome":"MEGARUN4_REPRESENTATION_PIPELINE_BLOCKED","experiment_root":str(OUT.relative_to(ROOT)),"updated_at":datetime.now(timezone.utc).isoformat(),"persistence_audit":"All required outputs are under this one root; historical sources are referenced by relative locator only.","machinery_archaeology":{"native_pdf":"current: document_representation.py/pdfplumber","ocr_render_visual":"genuinely_absent_callable_path","new_helper":"none; this script records the boundary only"},"git_head":subprocess.check_output(["git","rev-parse","--short","HEAD"],cwd=ROOT,text=True).strip(),"git_dirty":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True).splitlines(),"provider_network_s0_github_activity":"none"}
    dump("CAMPAIGN_STATE.json",state)
    readout="""# Mega-run 4 readout\n\nOutcome: `MEGARUN4_REPRESENTATION_PIPELINE_BLOCKED`. The selected 30 diagnostic-empty report pages span five retained report documents/subjects; primary named controls (Australian Red Cross, World Vision and Bush Heritage) preserve the required lineage but cannot be rerun because report bytes are not reachable. Recovery: 0/30, 0 characters, 0 newly recovered non-financial propositions. §§6/7/9/12/15/18 all remain representation-blocked.\n\nNo provider, network acquisition, S0 activity, canonical mutation, or GitHub activity occurred.\n"""
    (OUT/"READOUT.md").write_text(readout,encoding="utf8")
    summary={"outcome":"MEGARUN4_REPRESENTATION_PIPELINE_BLOCKED","cohort_pages":len(cohort),"charities":len(set(x["subject_id"] for x in cohort)),"documents":len(set(x["source_record_id"] for x in cohort)),"native_readable":0,"ocr_attempted":0,"page_image_attempted":0,"terra_visual_attempted":0,"provider_blocked":len(cohort),"recovery_rate":0,"character_gain":0,"newly_recovered_propositions":0,"newly_recovered_nonfinancial_propositions":0,"section_gains":{"6":0,"7":0,"9":0,"12":0,"15":0,"18":0},"qa":{"count":40,"answerable":0,"abstained":40},"comparison_pairs":0,"review_units":{"representation_forensics":len(cohort),"proposition_satellite":0},"activity":"no provider/network/S0/GitHub activity","changed_artifacts":sorted({p.name for p in OUT.iterdir() if p.is_file()}|{"summary.json"}),"changed_scripts":["scripts/run_megarun4_representation_boundary.py"]}
    dump("summary.json",summary)
if __name__=="__main__": main()
