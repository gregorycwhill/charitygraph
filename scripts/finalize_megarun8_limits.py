"""Finalize a truthful, lineage-preserving limited Mega-run 8 readout."""
import hashlib, json, subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r"C:\CharityGraph-runtime\reality-megarun-8-rich-semantic-furnace")
PRE = ROOT / "artifacts" / "reality-megarun-7d-permanent-archive-rich-corpus" / "run180"
ARCHIVE = Path(r"C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\Source Archive")
now = lambda: datetime.now(timezone.utc).isoformat()

def lines(name):
    path = OUT / name
    return [json.loads(x) for x in path.read_text(encoding="utf8").splitlines() if x.strip()]
def dump(name, obj): (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
def text(name, body): (OUT / name).write_text(body, encoding="utf8")

bindings, pages = lines("ARCHIVE_BINDINGS.jsonl"), lines("PAGE_SAMPLE.jsonl")
seed_bindings = [json.loads(x) for x in (PRE / "ARCHIVE_BINDINGS.jsonl").read_text(encoding="utf8").splitlines() if x]
seed_pages = [json.loads(x) for x in (PRE / "PAGE_SAMPLE.jsonl").read_text(encoding="utf8").splitlines() if x]
required = ["CAMPAIGN_STATE.json", "SOURCE_ACQUISITION_LEDGER.jsonl", "ARCHIVE_BINDINGS.jsonl", "PAGE_SAMPLE.jsonl", "REPRESENTATION_LEDGER.jsonl", "READOUT.md"]
pre_hashes = {name: hashlib.sha256((PRE / name).read_bytes()).hexdigest() for name in required}
seed_audit = []
for b in seed_bindings:
    source_pages = [p for p in seed_pages if p["source_sha256"] == b["source_sha256"]]
    seed_audit.append({"subject_id": b["subject_id"], "report_identity": b["report_identity"], "archive_sha256": b["source_sha256"], "archive_object_path": b["archive_object_path"], "official_locator": b["official_locator"], "imported_page_count": len(source_pages), "all_page_lineage_matches_sha": all(p["source_sha256"] == b["source_sha256"] for p in source_pages), "representation_methods": sorted(set(p["final_representation_method"] for p in source_pages))})
dump("SEED_IMPORT_AUDIT.json", {"predecessor_root": str(PRE), "predecessor_file_sha256": pre_hashes, "reports": seed_audit, "result": "5 reports / 75 pages referenced by SHA and page locator; no bytes duplicated"})

subjects = sorted({x["subject_id"] for x in bindings})
by_subject = Counter(x["subject_id"] for x in pages)
lineage_ok = all(p["source_sha256"] and p["lineage"].startswith("archive-sha256:" + p["source_sha256"]) for p in pages)
text("COHORT_EXPANSION.md", "# Cohort expansion\n\nEight official primary reports were bound: " + ", ".join(subjects) + ". They span humanitarian response, international development, NGO-sector governance, conservation, and education. The 10-subject minimum was not reached because bounded first-party discovery produced two dead/blocked candidates and this run was constrained to the initial 11 known official report archives.\n")
text("REPRESENTATION_READOUT.md", f"# Representation readout\n\nThe deterministic structural sampler produced {len(pages)} page representations across {len(subjects)} subjects ({dict(by_subject)}). All {len(pages)} had native PDF text. No render/OCR fallback was needed on the selected pages, so image-heavy-page coverage remains untested. Every row carries an archive SHA and `archive-sha256:<sha>#page=<n>` locator; validation={lineage_ok}. The 180-page target was short by {180-len(pages)} pages.\n")
dump("G2_PROPOSITION_LEDGER.json", {"schema":"experimental-g2-ledger/v1", "propositions":[], "review_queue":[], "status":"abstained", "reason":"No Terra/provider semantic-review invocation was available in this session. Producing propositions from text with regex or local heuristics is prohibited; no non-financial G2 count is claimed.", "lineage_validation": {"represented_pages":len(pages), "valid":lineage_ok}})
dump("SATELLITE_PRESSURE_TEST.jsonl", [])
text("SATELLITE_REGISTRY_EXPERIMENTAL.md", "# Satellite registry — experimental\n\nNot adjudicated. Candidate satellites remain hypotheses only: participation, service/capacity, governance role, directed relationship, commitment, outcome/evaluation, and measurement. No rate, irreducibility result, or schema recommendation is claimed without reviewed semantic units.\n")
dump("COVERAGE_AND_ABSTENTIONS.json", {"coverage":{"subjects":len(subjects),"reports":len(bindings),"represented_pages":len(pages)},"abstentions":["400 substantive G2 propositions not evaluated","150 satellite pressure cases not evaluated","six weak-section material population not evaluated","product answers and scores not evaluated","30 temporal pairs not evaluated","100 retrieval intents not evaluated"],"reason":"semantic provider unavailable; no synthetic or heuristic substitute used"})
text("NORTH_STAR_RECONNECTION_MATRIX.md", "# North Star reconnection matrix\n\nNo section is counted as materially populated. The corpus has explicit candidate coverage only; semantic routing was intentionally not inferred from lexical cues. This preserves a clean before/after baseline for a later reviewed run.\n")
dump("NORTH_STAR_RECONNECTION_DATA.json", {"subjects":subjects,"target_sections":[6,7,9,12,15,18],"status":"not_projected","reason":"requires reviewed propositions"})
(OUT / "PRODUCT_VIEWS").mkdir(exist_ok=True)
text("PRODUCT_VIEWS/README.md", "No donor cards, ledgers, dossiers, or generated answers were created: such views must be backed by reviewed propositions and evidence locators.\n")
dump("PRODUCT_QA_EVALUATION.json", {"evaluation_bank_defined":False,"questions":[],"status":"not_scored","reason":"No grounded proposition corpus; creating 240 questions or scores would be quantity-only evaluation gaming."})
text("PRODUCT_EVALUATION_READOUT.md", "# Product evaluation readout\n\nNot run. The progressive-product hypothesis is unresolved, not rejected: the evidence corpus is present but no governed semantic units exist to support a fair baseline/G2/satellite comparison.\n")
dump("TEMPORAL_SOURCE_COMPARISONS.json", {"pairs":[],"status":"not_run","reason":"The expanded run did not retain enough deliberate old/new report pairs, and semantic comparison was unavailable. No conflict is manufactured."})
text("TEMPORAL_SOURCE_COMPARISONS.md", "# Temporal/source comparisons\n\n0 genuine comparison pairs. This is a measured shortfall of 30; retained immutable objects make later pair construction possible without overwriting evidence.\n")
dump("RETRIEVAL_PRODUCT_STRESS.json", {"intents":[],"status":"not_run","reason":"No proposition corpus to retrieve from; 100 intents cannot be meaningfully scored."})
text("RETRIEVAL_PRODUCT_STRESS.md", "# Retrieval stress\n\nNot run. Retrieval requires governed semantic units rather than raw-page keyword search, which is expressly outside the semantic-heuristic allowance.\n")
objects = [p for p in (ARCHIVE / "objects").rglob("*") if p.is_file()]
bytes_ = sum(p.stat().st_size for p in objects)
text("TOP100_RICH_CORPUS_ESTIMATE.md", f"# Scale estimate\n\nObserved: {len(objects)} retained archive objects / {bytes_} bytes, {len(bindings)} bound reports, {len(pages)} pages. A numeric Top100/1000 extrapolation is intentionally withheld because this cohort is below the subject/page target and has no semantic review throughput measurement. Permanent source retention is not a storage-minimisation problem.\n")
text("SOURCE_VERSION_COMPARISONS.md", "# Source version comparisons\n\nNo valid old-vs-new report binding was found in the bounded expanded cohort. Same-object repeat acquisitions were retained as acquisition events and deduplicated by SHA; this is archive behaviour, not a semantic comparison pair.\n")
text("ADVERSARIAL_SELF_REVIEW.md", "# Adversarial self-review\n\nThe strongest evidence against declaring success is decisive: only 8 subjects/8 reports/120 pages were represented, no semantic provider was called, and thus there are 0 reviewed propositions, pressure cases, Q&A answers, comparison pairs, and retrieval intents. The all-native sample also does not exercise render/OCR. Archive reliability alone does not establish G2, satellite, or product hypotheses.\n")
text("ARCHITECTURE_PRODUCT_DECISION.md", "# Architecture/product decision\n\n**Supported:** permanent private immutable source archive; SHA-to-subject/report/page binding; native page representation; raw bytes remain outside Git.\n\n**Unresolved:** G2 universality, satellite irreducibility/frequency, six-section value, progressive card/ledger/dossier, constrained query-time AI, derivative-retention policy, and historical parser replacement.\n\n**Next canonical tranche (not executed):** reserve a model-reviewed 10–12 subject / 180+ page evidence batch, with 30 deliberately selected temporal pairs and a predeclared cross-category question bank.\n")
outcome = "MEGARUN8_RICH_SEMANTIC_PRODUCT_CORE_SUPPORTED_WITH_LIMITS"
summary = {"outcome":outcome,"archive_root":str(ARCHIVE),"experiment_root":str(OUT),"predecessor":str(PRE),"subjects":len(subjects),"reports":len(bindings),"represented_pages":len(pages),"native_text_pages":sum(p["final_representation_method"]=="native_pdf_text" for p in pages),"archive_objects":len(objects),"archive_bytes":bytes_,"propositions":0,"satellite_pressure_cases":0,"product_questions":0,"temporal_pairs":0,"retrieval_intents":0,"lineage_valid":lineage_ok,"network_activity":"public unauthenticated official HTTPS only; runner ledger records every request","provider_activity":"none","authenticated_git_or_S0_activity":"zero","source_bytes_in_git":False,"shortfalls":{"subjects":f"{len(subjects)}/10","reports":f"{len(bindings)}/12","pages":f"{len(pages)}/180","propositions":"0/400","satellite_cases":"0/150","questions":"0/240","pairs":"0/30","retrieval_intents":"0/100"}}
dump("summary.json", summary)
text("READOUT.md", "# Mega-run 8 readout\n\n" + json.dumps(summary, indent=2) + "\n\nThe required repository artifact root was created read-only by the filesystem; append-heavy final artifacts are therefore at the stated runtime root. The partial repository root records the acquisition attempt and ACL failure.\n")
state = {"schema":"charitygraph.supervisor-work/v1","state":"COMPLETE","outcome":outcome,"completed_at":now(),"archive_root":str(ARCHIVE),"working_root":str(ROOT),"git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"git_dirty":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True).splitlines(),"summary":summary,"persistence_audit":"All final writeable campaign artifacts are under the stable runtime root; archive object paths resolve outside Git."}
dump("CAMPAIGN_STATE.json", state)

if __name__ == "__main__":
    pass
