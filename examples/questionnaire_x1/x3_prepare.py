"""Prepare private X3 source context and the visually checked financial result."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from charitygraph.questionnaire_x1 import SourcePack, Questionnaire, answer, prepare, write_json

TEMP = Path(os.environ["TEMP"])
X2 = TEMP / "charitygraph-x2-plan-20261123"
OUT = TEMP / "charitygraph-x3-20261123"
REPORT = TEMP / "charitygraph-exp5-preparation-20261117/main_reports/49004875807-representation.json"
PRIOR_REQUEST = TEMP / "charitygraph-e5a-20261117/execution/49004875807-B-request.json"
HERE = Path(__file__).resolve().parent


def load(p):
    return json.loads(p.read_text(encoding="utf8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "ledger.json").exists():
        raise RuntimeError("X3 attempt exists; preserve frozen evidence and results")
    pack_data = load(X2 / "source-pack.json")
    prior = load(PRIOR_REQUEST)
    parts = json.loads(prior["input"].split("Evidence candidates (JSON object; only IDs appearing as keys are present):\n", 1)[1])
    a01 = next(x for x in pack_data["source_representations"] if x["representation_id"] == "A01")
    assert digest(canonical(parts["A01"])) == a01["representation_sha256"]
    programs = parts["A01"]["data"]["Programs"]
    for p in pack_data["programs"]:
        source_uuid = p["program_id"].rsplit(":", 1)[1]
        matches = [i for i, record in enumerate(programs) if record["uuid"] == source_uuid]
        assert len(matches) == 1 and programs[matches[0]]["AisUuid"] == parts["A01"]["uuid"]
        p["source_context"] = [{"representation_id": "A01", "locator": f"/data/Programs/{matches[0]}"}]
    pack_data["pack_id"] = "x3-" + pack_data["pack_id"]
    page = load(REPORT)["pages"][16]
    assert page["page"] == 17 and page["page_state"] == "native_text_sufficient"
    # The transcription is privately supplied after visual review. No semantic
    # extraction, source text or real financial result is hard-coded in Git.
    transcription = load(OUT / "finance-transcription.json")
    report_ref = str(REPORT) + "#/pages/16"
    pack_data["source_representations"].append({"representation_id": "financial-statement-page-17", "source_family": "annual_report_page", "snapshot_id": "plan-australia-2024-report", "representation_sha256": digest(canonical(page)), "reference": report_ref, "reporting_period": "2023-07-01/2024-06-30", "state": "available", "provenance": "retained E5 mechanical representation; PDF page 17, printed page 34; visually verified for private analytical review"})
    pack = SourcePack.model_validate(pack_data)
    qdata = load(HERE / "questionnaire-v0.1.json"); qdata["questionnaire_id"] = "x3-financial-source-native"; qdata["version"] = "1.0.0"
    qdata["questions"] = [q for q in qdata["questions"] if q["question_id"] == "X1-P13-01"]
    q = Questionnaire.model_validate(qdata)
    response = {"question_id": "X1-P13-01", "subject_id": pack.charitygraph_id,
        "questionnaire_id": q.questionnaire_id, "questionnaire_version": q.version,
        "source_snapshot_id": pack.snapshot_id, "status": "answered", "method": "source_native",
        "value": transcription["value"], "source_references": [report_ref]}
    if transcription["value"]["source_reference"] != report_ref:
        raise ValueError("transcription must cite the retained statement page")
    result = answer(pack, q, [response])
    for key in ("source_label", "accounting_scope", "source_statement", "source_locator", "source_unit", "validation", "nscoa"):
        result["answers"][0][key] = transcription[key]
    write_json(OUT / "source-pack.json", pack.model_dump()); write_json(OUT / "finance-questionnaire.json", qdata)
    write_json(OUT / "finance-answer.json", result)
    print("two source-bound program locators; private visual statement result validated")


if __name__ == "__main__":
    build()
