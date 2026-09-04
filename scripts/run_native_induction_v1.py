"""Private, bounded Section 19 Native-induction Semantic Lab runner."""
from __future__ import annotations
import hashlib, json, os, time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from charitygraph.openai_client import responses_create, estimate_response_cost, ApiUsage

ROOT = Path(r"C:\CharityGraph-runtime\native-induction-v1")
REVIEW = Path(r"C:\tmp\charitygraph-lab-review\native-induction-v1-review")
MAX_OUTPUT = 6000
MODEL = "gpt-5.6-luna"

SOURCES = [
    (Path(r"C:\CharityGraph-runtime\worldvision-luna-knowledge-v02-20260830T103756Z\parsed-output.json"), "World Vision Australia", "world-vision-whole-card"),
    (Path(r"C:\CharityGraph-runtime\sparse-whole-card-calibration-v01-20260830T043558Z\gpt-5.6-luna-returned-output.json"), "Australian Communities Foundation", "acf-whole-card"),
    (Path(r"C:\CharityGraph-runtime\whole-card-calibration-v01-20260830T024044Z\returned-output.json"), "The Fred Hollows Foundation", "fred-whole-card"),
    (Path(r"C:\CharityGraph-runtime\sparse-luna-classie-v05-20260830T\whole-card-parsed.json"), "Tweed Regional Gallery Foundation Limited", "tweed-whole-card"),
    (Path(r"C:\CharityGraph-runtime\modest-website-luna-classie-v061-20260831T\whole-card-parsed.json"), "Local Buying Foundation (WA)", "local-buying-whole-card"),
]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_observations() -> list[dict[str, Any]]:
    rows=[]
    for path, subject, provenance in SOURCES:
        raw=path.read_bytes(); doc=json.loads(raw.decode("utf-8"));
        for i, obs in enumerate(doc.get("observations", []), 1):
            # Existing outputs do not expose a durable ID; derive a stable local identity
            # from immutable artefact hash and ordinal without semantic interpretation.
            oid=obs.get("observation_id") or f"nativeobs:{sha(raw + str(i).encode())[:48]}"
            scope=obs.get("scope") or {}
            temporal=obs.get("temporal_scope") or {}
            rows.append({"observation_id":oid,"subject":subject,"source_case":provenance,
                "section_id":obs.get("section_id"),"scope":scope,"proposition":obs.get("proposition"),
                "epistemic_status":obs.get("epistemic_status"),"temporal_scope":temporal,
                "evidence":obs.get("evidence") or [],"qualifications":obs.get("qualifications") or []})
    return rows

def schema_a() -> dict[str, Any]:
    return {"type":"object","additionalProperties":False,"required":["concepts"],"properties":{"concepts":{"type":"array","items":{"type":"object","additionalProperties":False,"required":["concept_id","preferred_label","definition","inclusion_boundary","exclusion_boundary","supporting_observation_ids","organisations","parent_concept_candidate","confidence_statement"],"properties":{"concept_id":{"type":"string"},"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"supporting_observation_ids":{"type":"array","items":{"type":"string"}},"organisations":{"type":"array","items":{"type":"string"}},"parent_concept_candidate":{"type":["string","null"]},"confidence_statement":{"type":"string"}}}}}}

def schema_b() -> dict[str, Any]:
    item={"type":"object","additionalProperties":False,"required":["observation_id","concept_ids","support_rationale","missing_concept_suggestion","ambiguity_note"],"properties":{"observation_id":{"type":"string"},"concept_ids":{"type":"array","items":{"type":"string"}},"support_rationale":{"type":"string"},"missing_concept_suggestion":{"type":["string","null"]},"ambiguity_note":{"type":["string","null"]}}}
    return {"type":"object","additionalProperties":False,"required":["attachments"],"properties":{"attachments":{"type":"array","items":item}}}

PROMPT_A="""You are performing private CharityGraph Section 19 Native induction. Use ONLY the supplied taxonomy-blind governed observations. Propose a compact set of provisional CharityGraph-native concepts only when the same underlying semantic object recurs across observations. Do not reproduce or infer ACNC, CLASSIE, SDG, or any external taxonomy; do not use outside knowledge. Preserve distinctions between activity/output/outcome/impact, operator/deliverer/funder/sponsor/partner/auspice/network, fundraising/expenditure, purpose/activity, ethos/conduct, and commitment/implementation. Concepts may cross North-Star sections. Do not force every observation into a concept and do not infer quality, worth or impact. Return JSON matching the supplied schema."""
PROMPT_B="""You are performing the blind attachment stage of private CharityGraph Section 19 Native induction. Use ONLY the provisional concepts and held-out taxonomy-blind observations supplied. Do not modify concepts, use external taxonomies or outside knowledge. Attach zero, one or multiple concepts only when substantively supported by the observation; permit no suitable concept; identify missing-concept suggestions and apparent overlap. Return JSON matching the supplied schema."""

def call(prompt: str, payload: Any, schema: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    text=prompt+"\nINPUT:\n"+json.dumps(payload,ensure_ascii=False,separators=(",",":"))
    started=time.perf_counter()
    response=responses_create(model=MODEL,input_text=text,text_format={"type":"json_schema","name":"native_induction","strict":True,"schema":schema},max_output_tokens=MAX_OUTPUT,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"})
    meta={"response_id":response.response_id,"status":response.status,"input_tokens":response.usage.input_tokens,"output_tokens":response.usage.output_tokens,"total_tokens":response.usage.total_tokens,"cost_usd":str(estimate_response_cost(MODEL,response.usage) or 0),"latency_seconds":round(time.perf_counter()-started,3),"transport_requests":response.transport_requests}
    (ROOT/f"response-{len(list(ROOT.glob('response-*.json')))+1:02d}.json").write_text(json.dumps({"metadata":meta,"output_text":response.output_text},ensure_ascii=False,indent=2),encoding="utf-8")
    try: return json.loads(response.output_text),meta
    except json.JSONDecodeError: return None,meta|{"validation":"invalid_json"}

def main() -> None:
    ROOT.mkdir(parents=True,exist_ok=True); REVIEW.mkdir(parents=True,exist_ok=True)
    rows=load_observations(); by_org=defaultdict(list)
    for r in rows: by_org[r["subject"]].append(r)
    induction=[]; holdout=[]
    for org in sorted(by_org):
        ordered=sorted(by_org[org], key=lambda r:r["observation_id"])
        holdout += ordered[::5]; induction += ordered[1:][::5] if False else [r for j,r in enumerate(ordered) if j%5!=0]
    preflight={"organisations":sorted(by_org),"eligible_observations":len(rows),"induction_observations":len(induction),"holdout_observations":len(holdout),"sections":dict(Counter(str(r["section_id"]) for r in rows)),"scope_kinds":dict(Counter((r["scope"] or {}).get("kind","unknown") for r in rows)),"observations_per_organisation":{k:len(v) for k,v in sorted(by_org.items())},"partition_rule":"per organisation, stable observation-id order; every fifth observation held out for Stage B"}
    (ROOT/"preflight.json").write_text(json.dumps(preflight,ensure_ascii=False,indent=2),encoding="utf-8")
    projection=lambda rs:[{"observation_id":r["observation_id"],"subject":r["subject"],"section_id":r["section_id"],"scope":r["scope"],"proposition":r["proposition"],"epistemic_status":r["epistemic_status"],"temporal_scope":r["temporal_scope"],"evidence":r["evidence"],"qualifications":r["qualifications"]} for r in rs]
    a,ma=call(PROMPT_A,{"observations":projection(induction)},schema_a());
    if a is None: raise SystemExit("Stage A invalid JSON")
    concepts=a.get("concepts",[]); valid_ids={r["observation_id"] for r in induction}; concepts=[c for c in concepts if all(x in valid_ids for x in c.get("supporting_observation_ids",[]))]
    b,mb=call(PROMPT_B,{"concepts":concepts,"held_out_observations":projection(holdout)},schema_b());
    if b is None: raise SystemExit("Stage B invalid JSON")
    hold_ids={r["observation_id"] for r in holdout}; concept_ids={c.get("concept_id") for c in concepts}; attaches=[x for x in b.get("attachments",[]) if x.get("observation_id") in hold_ids and all(cid in concept_ids for cid in x.get("concept_ids",[]))]
    (ROOT/"analysis.json").write_text(json.dumps({"preflight":preflight,"stage_a_metadata":ma,"stage_b_metadata":mb,"concepts":concepts,"attachments":attaches},ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"experiment_id":"native-induction-v1","corpus_organisations":preflight["organisations"],"eligible_observations":len(rows),"induction_observations":len(induction),"holdout_observations":len(holdout),"provider_calls":2,"complete_calls":sum(x.get("status")=="completed" for x in (ma,mb)),"incomplete_calls":sum(x.get("status")!="completed" for x in (ma,mb)),"input_tokens":sum(int(x.get("input_tokens") or 0) for x in (ma,mb)),"output_tokens":sum(int(x.get("output_tokens") or 0) for x in (ma,mb)),"cost_usd":str(sum((float(x.get("cost_usd") or 0) for x in (ma,mb)))) ,"concept_count":len(concepts),"concepts_supported_2plus_orgs":sum(len(set(c.get("organisations",[])))>=2 for c in concepts),"concepts_supported_3plus_orgs":sum(len(set(c.get("organisations",[])))>=3 for c in concepts),"stage_b_tested":len(attaches),"stage_b_zero":sum(not x.get("concept_ids") for x in attaches),"stage_b_one":sum(len(x.get("concept_ids",[]))==1 for x in attaches),"stage_b_multi":sum(len(x.get("concept_ids",[]))>1 for x in attaches),"missing_concept_suggestions":sum(bool(x.get("missing_concept_suggestion")) for x in attaches),"provider_config":{"model":MODEL,"reasoning":"none","max_output_tokens":MAX_OUTPUT,"retries":0},"production_native_persistence":False}
    (ROOT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    # Public-safe review sample: concepts only, no raw provider traffic or source documents.
    sample=concepts[:]; REVIEW.joinpath("review-sample.json").write_text(json.dumps({"experiment_id":"native-induction-v1","concepts":sample,"attachments":attaches[:30]},ensure_ascii=False,indent=2),encoding="utf-8")
    REVIEW.joinpath("aggregate-diagnostics.json").write_text(json.dumps(summary|{"fanout_by_organisation":preflight["observations_per_organisation"]},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
