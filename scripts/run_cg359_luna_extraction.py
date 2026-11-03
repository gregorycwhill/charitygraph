"""Run the frozen CG359 Luna semantic extraction over all 15 cases."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create
from charitygraph.unified_semantic_experiment import MODEL, UNIFIED_PROMPT, UNIFIED_SCHEMA, UnifiedSemanticOutput
from charitygraph.unified_semantic_experiment import canonical_hash, enforce_spend
from charitygraph.stage_manifest import StageManifestError, verify_chain

COHORT = "fa77ab9141ddc5621713c9f487294cadb59fdcdf6d001fc5b4deb2d1e050e5ad"

def strict_schema(value):
    value = json.loads(json.dumps(value))
    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["required"] = list(node["properties"])
            for child in node.values(): visit(child)
        elif isinstance(node, list):
            for child in node: visit(child)
    visit(value); return value

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--representations", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cap", default="2.00")
    ap.add_argument("--stage-manifest", type=Path, action="append", required=True,
                    help="ordered cohort, corpus, packet, request-set manifests; required before any provider call")
    a = ap.parse_args()
    corpus = json.loads(a.corpus.read_text(encoding="utf-8"))
    if corpus.get("cohort_sha256") != COHORT: raise SystemExit("frozen cohort identity mismatch")
    try:
        chain = verify_chain(a.stage_manifest)
    except (OSError, ValueError, StageManifestError) as error:
        raise SystemExit("stage-manifest preflight failed before provider execution: " + str(error))
    request_set = chain[-1]["bindings"]
    if request_set["cohort_sha256"] != COHORT or request_set["authorised_corpus_sha256"] != corpus.get("corpus_sha256"):
        raise SystemExit("stage-manifest preflight failed: corpus/cohort identity mismatch")
    ledger = json.loads(a.ledger.read_text(encoding="utf-8")) if a.ledger.exists() else {"entries": []}
    schema = strict_schema(UNIFIED_SCHEMA)
    prompt = UNIFIED_PROMPT + "\nThe packets below are the complete frozen admissible evidence universe. Do not browse. Return structured CharityGraph JSON only. For §15 and §17, cite exact evidence IDs and abstain when unsupported."
    report = {"experiment_id":"CG-ETHOS-NOTABILITY-BOUNDED-CORPUS-EXPERIMENT-359","model":MODEL,"provider_path":"openai.responses","cohort_sha256":COHORT,"source_corpus_sha256":corpus.get("corpus_sha256"),"prompt_sha256":sha256(prompt.encode()).hexdigest(),"schema_sha256":canonical_hash(schema),"network_allowed":False,"cases":[]}
    for case in sorted({p["case_id"] for p in corpus["packets"]}):
        packets = [p for p in corpus["packets"] if p["case_id"] == case]
        row = {"case_id":case,"subject_id":packets[0]["subject_id"],"packet_hashes":{str(p["section"]):p["packet_hash"] for p in packets}}
        evidence=[]; seen=set()
        for p in packets:
            for e in p.get("evidence",[]):
                h=e["representation_sha256"]
                if h in seen: continue
                seen.add(h)
                path=a.representations / (h + ".json")
                if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=h:
                    row.update({"failure_class":"retained_representation_missing_or_changed","failure":h,"provider_called":False}); break
                value=json.loads(path.read_text(encoding="utf-8"))
                body=value.get("text") if isinstance(value,dict) else None
                if not isinstance(body,str): body=json.dumps(value.get("json",value) if isinstance(value,dict) else value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
                evidence.append({"evidence_id":"S%03d"%(len(evidence)+1),"representation_sha256":h,"source_family":e.get("source_family"),"source_role":e.get("source_role"),"resolved_locator":e.get("resolved_locator"),"section_bindings":[p["section"]],"content":body})
            if row.get("failure_class"): break
        if row.get("failure_class"):
            report["cases"].append(row); continue
        request=prompt+"\nCASE "+case+"\n"+json.dumps({"packets":[{"section":p["section"],"coverage_state":p.get("coverage_state"),"evidence_ids":[e["evidence_id"] for e in evidence]} for p in packets],"evidence":evidence},ensure_ascii=False,sort_keys=True)
        row["request_hash"]=sha256(request.encode()).hexdigest()
        enforce_spend(ledger,"0.10",cap_usd=a.cap)
        try:
            response=responses_create(model=MODEL,input_text=request,text_format={"type":"json_schema","name":"cg359_charitygraph_semantic_output","strict":True,"schema":schema},max_output_tokens=2400,max_attempts=1,timeout_seconds=180,reasoning={"effort":"none"})
            valid=True; reasons=[]
            try: UnifiedSemanticOutput.model_validate_json(response.output_text)
            except Exception as e: valid=False; reasons=["malformed_schema:"+str(e).splitlines()[0]]
            cost=estimate_response_cost(response.model,response.usage)
            telemetry={"at":datetime.now(timezone.utc).isoformat(),"model":response.model,"response_id":response.response_id,"input_tokens":response.usage.input_tokens,"output_tokens":response.usage.output_tokens,"cost_usd":str(cost or 0)}
            ledger.setdefault("entries",[]).append(telemetry)
            row.update({"provider_called":True,"response_hash":sha256(response.output_text.encode()).hexdigest(),"raw_response":response.output_text,"valid":valid,"validation_reasons":reasons,"telemetry":telemetry})
        except OpenAIRequestError as e:
            row.update({"provider_called":True,"failure_class":"provider_failure","failure":str(e),"telemetry":{"response_id":None,"input_tokens":0,"output_tokens":0,"cost_usd":"0"}})
        a.ledger.parent.mkdir(parents=True,exist_ok=True); a.ledger.write_text(json.dumps(ledger,indent=2)+"\n",encoding="utf-8")
        report["cases"].append(row); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report["aggregate"]={"cases":len(report["cases"]),"provider_calls":sum(bool(x.get("provider_called")) for x in report["cases"]),"valid":sum(bool(x.get("valid")) for x in report["cases"]),"input_tokens":sum(x.get("telemetry",{}).get("input_tokens",0) or 0 for x in report["cases"]),"output_tokens":sum(x.get("telemetry",{}).get("output_tokens",0) or 0 for x in report["cases"]),"cost_usd":str(sum((Decimal(str(x.get("telemetry",{}).get("cost_usd","0"))) for x in report["cases"]),Decimal("0")))}
    report["report_sha256"]=canonical_hash(report); a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

if __name__ == "__main__": main()
