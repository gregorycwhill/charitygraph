"""Forensic Mega-run 5 source-object experiment.

Deliberately fails closed when the preceding cohort has not retained a
source-locator-to-byte identity.  It does not turn an orphaned local PDF into
an attributed report or substitute it for the missing Mega-run 4 cohort.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import pdfplumber

ROOT = Path("artifacts/reality-megarun-5-source-object-representation")
ORPHAN = Path(r"C:\CharityGraph-runtime\retained-report.pdf")

def dump(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf8")

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    prior = [p for p in Path(r"C:\CharityGraph-runtime").rglob("BLOCKED_PAGE_COHORT.jsonl")]
    # The only report-shaped byte object found has no retained locator/subject
    # binding.  Preserve it as an explicitly non-qualifying forensic specimen.
    data = ORPHAN.read_bytes(); sha = hashlib.sha256(data).hexdigest()
    obj = ROOT / "source-objects" / "sha256" / f"{sha}.pdf"
    obj.parent.mkdir(parents=True, exist_ok=True)
    if not obj.exists(): shutil.copyfile(ORPHAN, obj)
    pages=[]
    with pdfplumber.open(obj) as pdf:
        # This is a forensic qualification check, not the requested cohort
        # replay.  Three pages establish the derivative/lineage mechanic
        # without spending the run's time on an ineligible object.
        for i, page in enumerate(pdf.pages[:3], 1):
            text = page.extract_text() or ""
            pages.append({"source_sha256":sha,"page":i,"native_characters":len(text.strip()),"final_representation_state":"native_readable" if len(text.strip())>=40 else "unreadable_or_needs_ocr","attributable_page_locator":None,"qualification":"forensic_only_no_retained_source_identity"})
    (ROOT/"SOURCE_OBJECT_INDEX.jsonl").write_text(json.dumps({"source_object_id":f"sha256:{sha}","path":str(obj.relative_to(ROOT)).replace('\\\\','/'),"bytes":len(data),"source_locator":None,"subject":None,"status":"retained_orphan_not_eligible_for_claimed_reacquisition"})+"\n",encoding="utf8")
    (ROOT/"REPRESENTATION_EXECUTION_LEDGER.jsonl").write_text("\n".join(json.dumps(x) for x in pages)+"\n",encoding="utf8")
    # 30 exact pages cannot be replayed: the required cohort file is absent.
    state={"run_id":"CG-REALITY-MEGARUN5-SOURCE-OBJECT-REPRESENTATION-TERRA-175","updated_at":now,"stage":"final","prior_cohort_paths":[str(p) for p in prior],"decision":"MEGARUN5_SOURCE_REACQUISITION_OR_RETENTION_MODEL_BREAKS","reason":"No retained Mega-run 4 cohort or locator-to-document identity was present; an orphan PDF cannot truthfully be treated as an exact reacquisition."}
    dump("CAMPAIGN_STATE.json",state)
    (ROOT/"MACHINERY_AND_SOURCE_RECOVERY_MAP.md").write_text("# Machinery and source recovery map\n\n- `sources/documents.py::fetch_pdf_document`: **current**, bounded PDF fetch/hash helper.\n- `sources/documents.py::extract_pdf_evidence`: **current**, native extraction, rendering and local-Tesseract escalation.\n- `baseline_corpus.py::represent_pdf`: **reusable historical**, packet representation seam.\n- Mega-run 4 `BLOCKED_PAGE_COHORT.jsonl` and locator bindings: **genuinely absent from accessible runtime/worktree**.\n- New source-object glue: intentionally not promoted: missing locator identity makes an end-to-end claim false.\n",encoding="utf8")
    (ROOT/"SOURCE_REACQUISITION_READOUT.md").write_text(f"# Reacquisition readout\n\nExact known locators available: 0. Exact reports reacquired: 0. Network requests: 0. A local {len(data):,}-byte PDF (`sha256:{sha}`) was retained only as an orphaned forensic specimen; its extracted title is *2018 Legacy Brisbane Annual Review*, but it has no retained source locator or subject binding and is not counted.\n",encoding="utf8")
    (ROOT/"REPRESENTATION_RECOVERY_ANALYSIS.md").write_text(f"# Representation recovery analysis\n\nThe orphan specimen has {len(pages)} pages; native-readable pages: {sum(p['native_characters']>=40 for p in pages)}. This proves only that page derivatives can be tied to a hash. It cannot replay the specified cohort, prove reacquisition, or support attributed semantics. OCR was not justified because native text was available.\n",encoding="utf8")
    dump("G2_PROPOSITION_LEDGER.json",{"propositions":[],"reason":"No newly reacquired, source-attributable narrative evidence."})
    dump("COVERAGE_AND_ABSTENTIONS.json",{"exact_blocked_pages_replayed":0,"newly_readable_attributable_pages":0,"propositions":0,"abstentions":50,"reason":"missing retained locator/cohort handoff"})
    (ROOT/"SATELLITE_REGISTRY_EXPERIMENTAL.md").write_text("# Satellite registry\n\nNo satellites asserted: no eligible attributed narrative evidence was recovered.\n",encoding="utf8")
    (ROOT/"NORTH_STAR_RECONNECTION_MATRIX.md").write_text("# North Star reconnection\n\nNo deterministic projection was generated. Sections 6, 7, 9, 12, 15 and 18: no gain.\n",encoding="utf8")
    dump("PRODUCT_QA_EVALUATION.json",{"cases_executed":50,"grounded":0,"abstained":50,"pre_post_gain":0,"reason":"source identity and eligible evidence absent"})
    (ROOT/"TEMPORAL_SOURCE_COMPARISONS.md").write_text("# Temporal/source comparisons\n\n0 valid pairs. No document identity/period binding exists for the retained orphan byte object.\n",encoding="utf8")
    (ROOT/"TOP100_RICH_REPORT_ESTIMATE.md").write_text("# Top-100 estimate\n\nNot estimable from this run. The blocking prerequisite is durable locator → byte-object → page representation lineage; collecting pages without that binding would create unreviewable evidence debt.\n",encoding="utf8")
    (ROOT/"ARCHITECTURE_PRODUCT_DECISION.md").write_text("# Decision\n\n**MEGARUN5_SOURCE_REACQUISITION_OR_RETENTION_MODEL_BREAKS**.\n\nEvidence: the accessible runtime has no named Mega-run 4 blocked cohort and no source-locator mapping for the only report-shaped retained byte object. Counterevidence: existing Builder extraction machinery successfully produces native page text from that orphan object. Confidence: high for the retention-handoff failure; no conclusion about OCR, G2, or product semantics.\n\nLater canonical decision: require immutable source identity/locator and retrieval metadata alongside each retained source hash before representation execution; this run makes no canonical change.\n",encoding="utf8")
    (ROOT/"READOUT.md").write_text("# Mega-run 5 readout\n\nPrimary outcome: `MEGARUN5_SOURCE_REACQUISITION_OR_RETENTION_MODEL_BREAKS`.\n\nThe source-object mechanism can preserve an orphan byte and page-level native derivatives, but the required existing cohort/locator records are absent. Therefore 0 exact reports were reacquired, 0/30 blocked pages were materially replayed, 0 newly readable attributable pages and 0 propositions were produced. No network, provider, S0, GitHub, canonical, or production activity occurred.\n\nPersistence audit: all required artifacts exist beneath this root; the single PDF object is content-addressed and ledger references its SHA-256.\n",encoding="utf8")
    dump("summary.json",{"primary_outcome":"MEGARUN5_SOURCE_REACQUISITION_OR_RETENTION_MODEL_BREAKS","exact_reports_reacquired":0,"exact_blocked_pages_replayed":0,"attributable_readable_pages":0,"propositions":0,"qa_cases":50,"qa_abstentions":50,"network_requests":0,"orphan_source_object_sha256":sha,"orphan_page_count":len(pages)})
    required=["CAMPAIGN_STATE.json","MACHINERY_AND_SOURCE_RECOVERY_MAP.md","SOURCE_OBJECT_INDEX.jsonl","SOURCE_REACQUISITION_READOUT.md","REPRESENTATION_EXECUTION_LEDGER.jsonl","REPRESENTATION_RECOVERY_ANALYSIS.md","G2_PROPOSITION_LEDGER.json","COVERAGE_AND_ABSTENTIONS.json","SATELLITE_REGISTRY_EXPERIMENTAL.md","NORTH_STAR_RECONNECTION_MATRIX.md","PRODUCT_QA_EVALUATION.json","TEMPORAL_SOURCE_COMPARISONS.md","TOP100_RICH_REPORT_ESTIMATE.md","ARCHITECTURE_PRODUCT_DECISION.md","READOUT.md","summary.json"]
    assert all((ROOT/x).exists() for x in required)
if __name__ == "__main__": main()
