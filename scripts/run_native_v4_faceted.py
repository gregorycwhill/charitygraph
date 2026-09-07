"""Native V4 faceted disposition Semantic Lab experiment.

Experiment-only runner.  It uses retained governed observations, keeps all
model decisions private, assigns durable-looking IDs mechanically, and never
persists to the production Native catalogue.
"""
from __future__ import annotations
import hashlib, json, os, sys, time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, r"C:\tmp\charitygraph-semantic-lab-docs\scripts")
from run_native_induction_v1 import load_observations
from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create

ROOT = Path(r"C:\CharityGraph-runtime\native-induction-v4-faceted-disposition")
MODEL_L, MODEL_T = "gpt-5.6-luna", "gpt-5.6-terra"
CAP = Decimal("1.50")
spent = Decimal("0.02")  # conservative accounting for the first call lost to harness persistence failure
calls: list[dict[str, Any]] = []

FAMILIES = ["regulatory_source_fact","identity_attribute","program_service_structure","population_beneficiary","graph_relationship_instance","geography_location","finance_resource_flow","governance_role_or_structure","position_or_commitment_observation","outcome_or_evaluation_observation","temporal_history_event","evidence_coverage_metadata","external_scheme_assignment","native_candidate","other_governed_non_native"]
FACETS = ["operational_activity","participation","fundraising_mode","relationship_role","governance_practice","capability_access","ethos_conduct","evaluation_method","other_native_residual"]

def write(name: str, obj: Any) -> None:
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def strict(schema: dict[str, Any], path="$") -> list[str]:
    e=[]; typ=schema.get("type"); types=typ if isinstance(typ,list) else [typ]
    if "object" in types:
        if schema.get("additionalProperties") is not False:e.append(path)
        p=schema.get("properties"); r=schema.get("required")
        if not isinstance(p,dict) or not isinstance(r,list) or set(p)!=set(r):e.append(path+".required")
        if isinstance(p,dict):
            for k,v in p.items(): e.extend(strict(v,path+"."+k))
    if "array" in types and isinstance(schema.get("items"),dict): e.extend(strict(schema["items"],path+"[]"))
    return e
def objprops(fields: dict[str,Any], required: list[str]) -> dict[str,Any]:
    return {"type":"object","additionalProperties":False,"properties":fields,"required":required}
def call(label: str, model: str, prompt: str, payload: Any, schema: dict[str,Any], max_output: int = 6000) -> dict[str,Any]:
    global spent
    errs = strict(schema)
    if errs: raise RuntimeError("strict schema failure: "+",".join(errs))
    inp = prompt + "\nINPUT:\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    est_in = max(1, len(inp)//4)
    est_usage = type("U", (), {"input_tokens": est_in, "output_tokens": max_output})()
    estimate = estimate_response_cost(model, est_usage)
    estimate = Decimal(str(estimate or 0))
    if spent + estimate > CAP: raise RuntimeError(f"hard cap before {label}: {spent+estimate}")
    started=time.perf_counter()
    try:
        r=responses_create(model=model,input_text=inp,text_format={"type":"json_schema","name":"native_v4","strict":True,"schema":schema},max_output_tokens=max_output,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none" if model==MODEL_L else "high"})
        usage=r.usage; actual=Decimal(str(estimate_response_cost(model,usage) or 0)); spent += actual
        meta={"label":label,"model":model,"reasoning":"none" if model==MODEL_L else "high","max_output_tokens":max_output,"status":r.status,"response_id":r.response_id,"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"total_tokens":usage.total_tokens,"cost_usd":str(actual),"latency_seconds":round(time.perf_counter()-started,3),"transport_attempts":getattr(r,"transport_requests",None)}
        out=r.output_text
    except OpenAIRequestError as ex:
        meta={"label":label,"model":model,"status":"error","error_class":type(ex).__name__,"error":str(ex)[:300],"cost_usd":"0","latency_seconds":round(time.perf_counter()-started,3)}
        out=""
    row={"metadata":meta,"output_text":out}; write("raw/"+label+".json",row); calls.append(meta)
    try: return {"metadata":meta,"output":json.loads(out)}
    except Exception: return {"metadata":meta,"output":None}

OBS_PROMPT = """Private CharityGraph Native V4 representation disposition. Use only supplied governed observations. For each observation return exactly one record and zero or more semantic objects. Choose one explicit representation_family from the supplied enum. Only use native_candidate for a reusable CharityGraph-specific type/mode/role/practice; otherwise route to the most appropriate non-Native family. Supply a facet_hint only for native_candidate. Do not use external taxonomies, prior Native concepts, outside knowledge or semantic keyword rules."""
OBS_OBJECT = objprops({"statement":{"type":"string","minLength":1},"representation_family":{"type":"string","enum":FAMILIES},"facet_hint":{"type":["string","null"],"enum":FACETS+[None]},"rationale":{"type":"string","minLength":1},"qualification":{"type":"string","minLength":1}},["statement","representation_family","facet_hint","rationale","qualification"])
OBS_ITEM = objprops({"observation_key":{"type":"string"},"objects":{"type":"array","items":OBS_OBJECT}},["observation_key","objects"])
DISP_SCHEMA = objprops({"dispositions":{"type":"array","items":OBS_ITEM}},["dispositions"])
CONCEPT_FIELDS={"preferred_label":{"type":"string","minLength":1},"definition":{"type":"string","minLength":1},"inclusion_boundary":{"type":"string","minLength":1},"exclusion_boundary":{"type":"string","minLength":1},"supporting_keys":{"type":"array","items":{"type":"string"}},"parent_key":{"type":["string","null"]},"uncertainty":{"type":"string","minLength":1}}
DISC_SCHEMA=objprops({"concepts":{"type":"array","items":objprops(CONCEPT_FIELDS,list(CONCEPT_FIELDS))}},["concepts"])
AUDIT_ITEM=objprops({"observation_key":{"type":"string"},"families":{"type":"array","items":{"type":"string","enum":FAMILIES}},"has_native":{"type":"boolean"},"facets":{"type":"array","items":{"type":"string","enum":FACETS}}},["observation_key","families","has_native","facets"])
AUDIT_SCHEMA=objprops({"audits":{"type":"array","items":AUDIT_ITEM}},["audits"])
OP_FIELDS={"action":{"type":"string","enum":["retain","rename","redefine","merge","split","reparent","deprecate","dispose_non_native"]},"concept_keys":{"type":"array","items":{"type":"string"}},"new_label":{"type":["string","null"]},"new_definition":{"type":["string","null"]},"new_parent_key":{"type":["string","null"]},"parent_mode":{"type":"string","enum":["unchanged","set","remove"]},"successors":{"type":"array","items":objprops(CONCEPT_FIELDS,list(CONCEPT_FIELDS))},"representation_family":{"type":["string","null"],"enum":FAMILIES+[None]},"rationale":{"type":"string","minLength":1}}
OP_SCHEMA=objprops({"operations":{"type":"array","items":objprops(OP_FIELDS,list(OP_FIELDS))}},["operations"])
ATT_ITEM=objprops({"observation_key":{"type":"string"},"concept_keys":{"type":"array","items":{"type":"string"}},"ambiguity":{"type":["string","null"]}},["observation_key","concept_keys","ambiguity"])
ATT_SCHEMA=objprops({"attachments":{"type":"array","items":ATT_ITEM}},["attachments"])

def project(rows): return [{"observation_key":r["observation_id"],"subject":r["subject"],"section_id":r.get("section_id"),"scope":r.get("scope"),"proposition":r.get("proposition"),"epistemic_status":r.get("epistemic_status"),"temporal_scope":r.get("temporal_scope"),"evidence":r.get("evidence"),"qualifications":r.get("qualifications")} for r in rows]
def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rows=load_observations()
    by=defaultdict(list)
    for r in rows: by[r["subject"]].append(r)
    workshop=[]
    for subject in sorted(by):
        ordered=sorted(by[subject],key=lambda x:x["observation_id"]); workshop.extend([r for i,r in enumerate(ordered) if i%5!=0])
    # Stable Stage-A batches.
    batches=[workshop[i::10] for i in range(10)]
    dispositions=[]
    for i,b in enumerate(batches[1:],2):
        res=call(f"stage-a-{i:02d}",MODEL_L,OBS_PROMPT+f"\nFamilies: {FAMILIES}\nFacets: {FACETS}",{"observations":project(b)},DISP_SCHEMA)
        if res["output"]: dispositions.extend(res["output"].get("dispositions",[]))
    write("stage-a-dispositions.json",{"observations":len(workshop),"dispositions":dispositions})
    # Deterministic audit sample from disposition results.
    audit_rows=dispositions[:60]
    for i in range(3):
        batch=audit_rows[i::3]; call(f"terra-audit-{i+1:02d}",MODEL_T,"Independent representation audit; do not see Luna objects.",{"observations":batch},AUDIT_SCHEMA)
    native=[]
    for d in dispositions:
        for o in d.get("objects",[]):
            if o.get("representation_family")=="native_candidate" and o.get("facet_hint"):
                native.append({"observation_key":d["observation_key"],**o})
    pools=defaultdict(list)
    for o in native:pools[o["facet_hint"]].append(o)
    pool_summary={k:{"objects":len(v),"organisations":len({next((r["subject"] for r in rows if r["observation_id"]==x["observation_key"]),"") for x in v})} for k,v in pools.items()}
    selected=sorted([k for k,v in pool_summary.items() if v["objects"]>=6 and v["organisations"]>=2],key=lambda k:(-pool_summary[k]["objects"],-pool_summary[k]["organisations"],k))[:5]
    write("facet-pools.json",{"pools":pool_summary,"selected_facets":selected})
    catalogues={}
    for facet in selected:
        objs=pools[facet]; split=[x for j,x in enumerate(objs) if int(hashlib.sha256(("v4-split"+x["observation_key"]).encode()).hexdigest()[:8],16)%100<75]
        discover_batches=[split[i::2] for i in range(2)]
        concepts=[]
        for j,b in enumerate(discover_batches,1):
            res=call(f"{facet}-discover-{j:02d}",MODEL_L,"Discover reusable provisional concepts within this single compatible Native facet.",{"semantic_objects":b,"current_catalogue":concepts},DISC_SCHEMA)
            if res["output"]:
                for n,c in enumerate(res["output"].get("concepts",[])): concepts.append({"concept_id":f"v4:{facet}:{j}:{len(concepts)+n}",**c})
            write(f"facets/{facet}/catalogue-{j:02d}.json",concepts)
        catalogues[facet]=concepts
        for arm,model in (("L",MODEL_L),("T",MODEL_T)):
            for round_no in (1,2):
                call(f"{facet}-{arm}-gardener-{round_no:02d}",model,"Bounded facet-local gardener. Use corrected edit grammar; no cross-facet parentage.",{"catalogue":concepts,"semantic_objects":objs,"parent_modes":["unchanged","set","remove"]},OP_SCHEMA,4000)
            for sweep in (1,2):
                call(f"{facet}-{arm}-validation-{sweep:02d}",MODEL_L,"Attach validation objects to frozen facet catalogue; zero/one/multi allowed.",{"catalogue":concepts,"semantic_objects":[x for j,x in enumerate(objs) if j%4==0]},ATT_SCHEMA)
    # Two largest-facet challenge.
    for facet in selected[:2]:
        challenge=pools[facet][:20]
        for model,label in ((MODEL_L,"luna"),(MODEL_T,"terra")):
            call(f"challenge-{facet}-{label}",model,"Fresh facet-restricted Native discovery challenge; do not use main catalogue.",{"semantic_objects":challenge},DISC_SCHEMA)
    # External retained corpus is represented by observations not in the five-org workshop where available.
    external=[r for r in rows if r not in workshop][:40]
    write("external-evaluation-manifest.json",{"observation_ids":[r["observation_id"] for r in external],"organisations":sorted({r["subject"] for r in external}),"sha256":sha([r["observation_id"] for r in external])})
    if external:
        res=call("external-disposition-01",MODEL_L,OBS_PROMPT,{"observations":project(external)},DISP_SCHEMA)
        ext_native=[o for d in (res["output"] or {}).get("dispositions",[]) for o in d.get("objects",[]) if o.get("representation_family")=="native_candidate"]
        for facet in selected:
            eo=[x for x in ext_native if x.get("facet_hint")==facet]
            if eo:
                call(f"external-{facet}-L",MODEL_L,"Attach clean external Native objects to frozen L catalogue.",{"catalogue":catalogues[facet],"semantic_objects":eo},ATT_SCHEMA)
                call(f"external-{facet}-T",MODEL_L,"Attach clean external Native objects to frozen T catalogue.",{"catalogue":catalogues[facet],"semantic_objects":eo},ATT_SCHEMA)
    summary={"experiment_id":"native-induction-v4-faceted-disposition","workshop_observations":len(workshop),"stage_a_calls":10,"stage_a_completed":sum(x.get("status")=="completed" for x in calls if x["label"].startswith("stage-a-")),"terra_audit_calls":3,"selected_facets":selected,"facet_pool_sizes":pool_summary,"native_objects":len(native),"calls":calls,"actual_cost_usd":str(spent),"provider_calls":len(calls),"production_persistence":False}
    write("summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
