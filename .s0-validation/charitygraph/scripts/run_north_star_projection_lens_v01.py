"""Private three-subject downstream North-Star projection lens."""
from __future__ import annotations
import argparse, json, hashlib, sqlite3, sys, time
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.north_star_projection import NorthStarLensOutput

DB=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"); ROOT=Path(r"C:\CharityGraph-runtime\north-star-projection-lens-v01")
PROMPT="""Assign each governed observation to zero or more North-Star section IDs (1..20). Return exactly one assignment for every observation_key supplied. Return only JSON with assignments [{observation_key, section_ids, note}]. Do not rewrite propositions, add facts, judge truth, summarize, assign taxonomies, or infer missing content. Empty section_ids is valid when no section naturally fits."""
SCHEMA=NorthStarLensOutput.model_json_schema()
def _strict(node):
 if isinstance(node,dict):
  node.pop("default",None)
  if node.get("type")=="object" and isinstance(node.get("properties"),dict): node["required"]=list(node["properties"])
  for value in node.values(): _strict(value)
 elif isinstance(node,list):
  for value in node: _strict(value)
_strict(SCHEMA)

def packet(subject_id):
 c=sqlite3.connect(DB); rows=c.execute("select o.observation_id,o.scope_id,o.value_json,o.outcome_state,o.observation_time_json,o.evidence_locator_ids_json,o.material_json,s.scope_kind,s.label from knowledge_observations o left join subject_scopes s on s.scope_id=o.scope_id where o.subject_id=? and o.method='model:compact-knowledge-v0.2' order by o.observation_id",(subject_id,)).fetchall(); c.close(); obs=[]
 for i,r in enumerate(rows,1):
  material=json.loads(r[6]); obs.append({"observation_key":f"O{i:03d}","observation_id":r[0],"scope_id":r[1],"value":json.loads(r[2]) if r[2] else None,"scope_kind":"subject" if r[1] is None else r[7],"scope_label":None if r[1] is None else r[8],"outcome_state":r[3],"observation_time":json.loads(r[4]),"qualifications":material.get("qualifications",[]),"evidence_locator_ids":json.loads(r[5]) if r[5] else []})
 return obs

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("subject_id",nargs="+"); args=ap.parse_args(); rows=[]; total=0
 for sid in args.subject_id:
  obs=packet(sid); payload={"observations":[{k:x[k] for k in ("observation_key","value","scope_kind","scope_label","outcome_state","observation_time","qualifications")} for x in obs]}; raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); out=ROOT/sid.replace(":","_"); out.mkdir(parents=True,exist_ok=True); (out/"packet.json").write_bytes(raw); (out/"prompt.txt").write_text(PROMPT,encoding="utf-8"); started=time.perf_counter(); resp=responses_create(model="gpt-5.6-luna",input_text=PROMPT+"\nPACKET:\n"+raw.decode(),text_format={"type":"json_schema","name":"north_star_projection_lens_v01","strict":True,"schema":SCHEMA},max_output_tokens=4000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); (out/"raw-response.json").write_text(json.dumps({"response_id":resp.response_id,"status":resp.status,"output_text":resp.output_text,"usage":resp.usage.__dict__},indent=2),encoding="utf-8"); parsed=NorthStarLensOutput.model_validate(json.loads(resp.output_text)); keys=[x.observation_key for x in parsed.assignments]; expected={x["observation_key"] for x in obs};
  if set(keys)!=expected or len(keys)!=len(set(keys)): raise ValueError("lens must assign every observation key exactly once")
  projection={"subject_id":sid,"coverage_note":"only sampled candidate observations; empty means no sampled observation mapped","sections":{str(i):[x.observation_key for x in parsed.assignments if i in x.section_ids] for i in range(1,21)},"assignments":[x.model_dump(mode="json") for x in parsed.assignments],"observation_ids":{x["observation_key"]:x["observation_id"] for x in obs}}
  (out/"projection.json").write_text(json.dumps(projection,indent=2),encoding="utf-8"); cost=estimate_response_cost("gpt-5.6-luna",resp.usage); total+=cost or 0; rows.append({"subject_id":sid,"observations":len(obs),"assignments":len(parsed.assignments),"zero":sum(not x.section_ids for x in parsed.assignments),"one":sum(len(x.section_ids)==1 for x in parsed.assignments),"multi":sum(len(x.section_ids)>1 for x in parsed.assignments),"populated_sections":[i for i in range(1,21) if any(i in x.section_ids for x in parsed.assignments)],"cost_usd":str(cost),"input_tokens":resp.usage.input_tokens,"output_tokens":resp.usage.output_tokens,"latency_seconds":round(time.perf_counter()-started,3)})
 (ROOT/"report.json").write_text(json.dumps({"prompt_sha256":hashlib.sha256(PROMPT.encode()).hexdigest(),"total_cost_usd":str(total),"subjects":rows},indent=2),encoding="utf-8"); print(json.dumps(rows,indent=2))
if __name__=="__main__": main()
