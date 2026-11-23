"""Build a private, source-safe static preview from previously frozen X2-X3B outputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
TEMP = Path(os.environ["TEMP"])
ROOT = HERE.parents[1]
E5 = TEMP / "charitygraph-e5a-20261117"
E5_MAIN = TEMP / "charitygraph-exp5-preparation-20261117"


def read(p): return json.loads(p.read_text(encoding="utf8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_set(directory, names):
    checks = read(directory / "SHA256SUMS.json")
    for name in names:
        if checks.get(name) != sha(directory / name): raise ValueError("frozen experiment file hash mismatch: " + name)


def build_overlay(x2, x3, review, plan_ais, source_urls):
    if x3["abn"] != "49004875807" or review["abn"] != "82061656577": raise ValueError("charity mismatch")
    plan = {"id":"plan", "name":x3["subject"], "abn":x3["abn"], "programs":[], "sources":source_urls["plan"]}
    finance = x3["financial_answer"]; money = finance["value"]
    if money["basis"] != "reported" or finance["subject_id"] != x2["answers"][0]["charitygraph_id"]: raise ValueError("financial scope mismatch")
    plan["finance"] = {"amount":money["amount"], "currency":money["currency"], "scope":finance["accounting_scope"], "period":"Year ended 30 June 2024", "source":"2024 annual report, summary statement, PDF page 17"}
    ids = {"078ed835-0ad7-ef11-a731-00224893e2ef", "6acdd03b-0ad7-ef11-a731-00224893e2ef"}
    programs = [p for p in plan_ais["Programs"] if p["uuid"] in ids]
    if len(programs) != 2: raise ValueError("source program records missing")
    x2labels = {"X1-P03-01":"Operational status", "X1-P06-01":"Volunteer participation", "X1-P05-01":"Veteran beneficiary focus"}
    for p in programs:
        subject = "provisional:acnc-program:" + p["uuid"]
        item = {"id":subject, "name":p["Name"], "country":", ".join(p["ProgramCountries"]) or "Country not stated", "period":"ACNC AIS 2023–24", "answers":[]}
        for a in x2["answers"]:
            if a["subject_id"] == subject:
                if a["question_id"] not in x2labels or a["status"] != "unknown": raise ValueError("unexpected X2 answer")
                item["answers"].append({"question":x2labels[a["question_id"]], "kind":"Model assessment", "tone":"caution", "value":"Unknown", "note":"Not established from the supplied evidence.", "period":"X2 assessment", "source":"2024 AIS, selected report pages and website excerpts"})
        assessed = [a for a in x3["program_answers"] if a["subject_id"] == subject]
        if len(item["answers"]) != 3 or len(assessed) != 2: raise ValueError("incomplete program answers")
        for a in assessed:
            if a["question_id"] == "X3-P05-01" and a["value"] == "C":
                question, value, note = "Young-children beneficiary focus", "C — explicitly included", "Model assessment of the ACNC-reported beneficiary field; not a count or eligibility rule."
            elif a["question_id"] == "RAH1-Q005" and a["value"] == "direct_service":
                question, value, note = "Activity classification", "Direct service / care delivery", "Provisional activity-type assessment; the direct operator is not established."
            else: raise ValueError("unexpected X3 assessment")
            item["answers"].append({"question":question,"kind":"Model assessment · provisional","tone":"", "value":value,"note":note,"period":"2023–24 reporting period","source":"ACNC AIS program record"})
        plan["programs"].append(item)
    arche = {"id":"arche","name":review["subject"],"abn":review["abn"],"sources":source_urls["arche"],"programs":[]}
    arche_program = {"id":"infocus-provisional","name":review["program"],"country":"Bentley, Western Australia","period":"ACNC AIS 2023–24","answers":[]}
    displays = {"X3B-INF-01":("Medicare-rebated counselling", "Reported in the 2017–18 report"), "X3B-INF-02":("Satellite counselling rooms", "Armadale and Belmont reported"), "X3B-INF-03":("GP referrals", "High referral rate reported"), "X3B-INF-04":("Who directly delivered counselling?", "Insufficiently established")}
    for row in review["comparisons"]:
        key = row["question_id"]
        if key not in displays: raise ValueError("unexpected historical question")
        question, value = displays[key]
        if key == "X3B-INF-04":
            if row["incremental_value_review"] != "insufficient_support_for_exact_operator_claim": raise ValueError("operator review mismatch")
            kind,tone,note = "Review · insufficient evidence", "caution", "The model selected supported, but the report does not establish the direct provider."
        else:
            if row["incremental_value_review"] != "additional_historical_source_claim" or row["enriched"]["value"] != "supported": raise ValueError("historical review mismatch")
            kind,tone,note = "Historical source claim · model assessed", "historical", "First-party report claim; current availability is unknown."
            if key == "X3B-INF-03": note = "The report gives no numeric rate or denominator; current referral patterns are unknown."
        arche_program["answers"].append({"question":question,"kind":kind,"tone":tone,"value":value,"note":note,"period":"2017–18 · historical","source":"Arche Health annual report, PDF page 4"})
    if len(arche_program["answers"]) != 4: raise ValueError("incomplete historical review")
    arche["programs"].append(arche_program)
    return {"schema_version":"x4a-private-overlay-1", "status":"experimental_not_canonical", "charities":[plan,arche]}


def sources():
    decisions = read(E5 / "execution/input-part-decisions.frozen.json")["parts"]
    def url(k):
        result=decisions[k]["source_url"]
        if not result.startswith("https://") or "?" in result: raise ValueError("unsafe source URL")
        return result
    return {"plan":[{"label":"ACNC annual information statement · 2023–24", "url":url("49004875807-A01")}, {"label":"Annual report · 2024, summary financial statement (PDF page 17)","url":url("49004875807-P01")+"#page=17"}], "arche":[{"label":"ACNC annual information statement · 2023–24", "url":url("82061656577-A01")},{"label":"Annual report · 2017–18 (PDF page 4)","url":url("82061656577-P01")+"#page=4"}]}


def cohort():
    matrix = read(E5_MAIN/"main_bundle_plan.v2.frozen.json")["matrix"]
    part_decisions = read(E5/"execution/input-part-decisions.frozen.json")["parts"]
    selected = ["49004875807","65159324697","87000001641","60610666325","74130061317","82061656577","85002535846","33824308256","15190821561","94178965125","73292353593","22402858041"]
    data=[]
    for abn in selected:
        row=next(r for r in matrix if r["abn"] == abn and r["cohort"] == "main")
        identity=read(E5_MAIN/"main_identity_v2"/(abn+".json")); ais=(identity.get("selected_2024_ais") or {}).get("data") or {}
        count=len(ais.get("Programs") or [])
        e5a=(E5/"draft_regulator_foundations"/(abn+".json")).exists()
        decision_counts = {}
        for key, decision in part_decisions.items():
            if key.startswith(abn+"-") and decision["provider_processing"] == "allowed_for_exact_input_part":
                role=decision["source_role"]; decision_counts[role]=decision_counts.get(role,0)+1
        tags = (["program-rich"] if count >= 5 else ["relatively simple"] if count <= 2 else [])
        tags += (["captured source-rich"] if row["annual_report_period"] and row["website_pages"] else ["captured source-poor"] if not row["annual_report_period"] and not row["website_pages"] else [])
        data.append({"name":row["name"],"abn":abn,"stratum":row["stratum"],"source_native_program_count":count,
            "selection_tags":tags,"e5a_exact_decision_part_counts":decision_counts,
            "source_families_captured":["2024 ACNC AIS"] + (["annual report"] if row["annual_report_period"] else []) + (["website"] if row["website_pages"] else []),
            "annual_report_period":row["annual_report_period"],"website_pages_captured":row["website_pages"],"website_status":row["website_status"],
            "source_decision_status":"Only the listed E5A exact parts had recorded decisions; recheck applicability to X4B, and do not assume other captured families are eligible" if e5a else "E5 capture only; exact-part processing decisions must be checked before transmission"})
    return {"schema_version":"x4b-cohort-preparation-1","status":"proposed_not_frozen_or_approved_for_calls", "selection_rule":"Eight existing E5A subjects plus four AIS-only E5 main-cohort cases spanning large and small revenue; intentionally mixed richness, not representative.","source_coverage_caveat":"Captured does not mean complete, current, identity-bound or eligible for a new provider purpose; review exact representations and decisions before use.","questionnaire_status":"awaiting separately reviewed substantive instrument","charities":data}


def main(destination):
    if destination.resolve() == ROOT.resolve() or ROOT.resolve() in destination.resolve().parents: raise ValueError("private output must be outside the repository")
    x2=TEMP/"charitygraph-x2-plan-20261123";x3=TEMP/"charitygraph-x3-20261123";x3b=TEMP/"charitygraph-x3b-20261123"
    verify_set(x2,["answers.json"]);verify_set(x3,["x3-results.json"]);verify_set(x3b,["paired-review.json"])
    old=E5/"execution/49004875807-B-request.json";manifest=read(x2/"manifest.json")
    if sha(old)!=manifest["original_request_sha256"]: raise ValueError("AIS source snapshot mismatch")
    source=read(old);parts=json.loads(source["input"].split("Evidence candidates (JSON object; only IDs appearing as keys are present):\n",1)[1]);ais=parts["A01"]["data"]
    if ais["Abn"]!="49004875807": raise ValueError("AIS identity mismatch")
    overlay=build_overlay(read(x2/"answers.json"),read(x3/"x3-results.json"),read(x3b/"paired-review.json"),ais,sources())
    destination.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(overlay,ensure_ascii=False,indent=2)
    (destination/"preview-data.json").write_text(payload+"\n",encoding="utf8")
    (destination/"data.js").write_text("window.X4A_DATA = "+payload+";\n",encoding="utf8")
    (destination/"x4b-cohort-manifest.json").write_text(json.dumps(cohort(),ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    for name in ("index.html","preview.css","preview.js"):shutil.copyfile(HERE/name,destination/name)
    shutil.copyfile(ROOT.parent/"charitygraph-viewer/styles.css",destination/"viewer-base.css")
    print("Private preview:",destination/"index.html")


if __name__ == "__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: python build_preview.py PRIVATE_OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
