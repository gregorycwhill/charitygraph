"""Execute V12 Compact + batched scope resolution from frozen acquisition preflight."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.document_representation import represent_document
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02,COMPACT_V02_SCHEMA
from charitygraph.scope_resolution_contract import ScopeResolutionOutput,SCOPE_RESOLUTION_SCHEMA
from charitygraph.openai_client import responses_create,estimate_response_cost
ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12")
CP="Extract all evidence-supported Compact Knowledge v0.2 atoms about the declared target. Scope fields are producer hints only. Use exact dates only when supported; use reporting_period for coarse periods. Cite packet-local locators."
RP="Resolve scope independently using only the declared target, proposition and exact evidence excerpts. Do not use producer scope hints. Generic organisation facts/categories are subject; named_program_or_service requires one specifically named instance; other_named_scope requires one named subordinate thing; reporting_group requires formal evidence; otherwise uncertain. Return one indexed decision per atom."
def main():
 persisted=ROOT/"persisted-representation-manifest.json"
 if persisted.exists():
  entries=[]
  for m in json.loads(persisted.read_text(encoding="utf-8"))["representations"]:
   d=json.loads(Path(m["representation_path"]).read_text(encoding="utf-8")); entries.append(({"target":d["target"],"publisher":d["publisher"],"source_relation":d["source_relation"],"material_role":d["material_role"],"requested_url":d.get("original_url")},{"raw_path":d["raw_path"],"raw_sha256":d["raw_sha256"],"representation_sha256":d["representation_sha256"],"content_type":"application/pdf" if d["material_type"]=="pdf" else "text/html","persisted_path":m["representation_path"]}))
 else:
  pre=json.loads((ROOT/"acquisition-preflight.json").read_text(encoding="utf-8")); entries=[]
 if not persisted.exists():
  for row in pre["rows"]:
   for a in row.get("artifacts",[]):
    if a.get("complete") and a.get("raw_path"): entries.append((row,a))
 # material diversity: split each represented body into coherent line chunks, cap 100 packets
 packets=[]
 for row,a in entries:
  if a.get("persisted_path"):
   pd=json.loads(Path(a["persisted_path"]).read_text(encoding="utf-8")); lines=[x for x in pd["text"].splitlines() if x.strip()]; rep=type("Persisted",(),{"representation_sha256":pd["representation_sha256"]})()
  else:
   raw=Path(a["raw_path"]).read_bytes(); rep=represent_document(raw,content_type=a.get("content_type")); lines=[x for x in rep.text.splitlines() if x.strip()]
  step=max(1,min(80,len(lines)//4 or 1))
  for start in range(0,len(lines),step):
   packets.append((row,a,rep,lines[start:start+step],start))
 packets=packets[:100]; summary={"campaign":"broad-compact-diagnostic-v12","source_manifest":"acquisition-preflight.json","packets":[],"atoms":[]}; total=0.0
 for idx,(row,a,rep,lines,start) in enumerate(packets,1):
  locs=[{"source":"S001","locator":f"L{i+1:04d}","text":x[:1200]} for i,x in enumerate(lines)]; packet={"target":{"name":row["target"]},"source":{"publisher":row["publisher"],"relation":row["source_relation"],"material_role":row["material_role"],"original_url":row["requested_url"],"final_url":a.get("url") or row.get("final_url"),"raw_sha256":a["raw_sha256"],"representation_sha256":a["representation_sha256"],"parent_document":a["raw_path"],"chunk_identity":f"lines-{start+1}-{start+len(lines)}"},"evidence":locs}; pb=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(",",":")); psha=hashlib.sha256(pb.encode()).hexdigest(); d=ROOT/f"v12-{idx:03d}"; d.mkdir(exist_ok=True); (d/"packet.json").write_text(pb,encoding="utf-8")
  r=responses_create(model="gpt-5.6-luna",input_text=CP+"\nDECLARED TARGET: "+row["target"]+"\nPACKET:\n"+pb,text_format={"type":"json_schema","name":"compact_knowledge_v02","strict":True,"schema":COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); u=r.usage; c=estimate_response_cost("gpt-5.6-luna",u) or 0; total+=float(c); (d/"compact-raw.json").write_text(json.dumps({"response_id":r.response_id,"status":r.status,"output_text":r.output_text,"usage":u.__dict__},ensure_ascii=False),encoding="utf-8")
  try: parsed=CompactKnowledgeOutputV02.model_validate(json.loads(r.output_text)); valid=True
  except Exception: parsed=None; valid=False
  prow={"target":row["target"],"packet_sha":psha,"raw_sha":a["raw_sha256"],"representation_sha":a["representation_sha256"],"status":r.status,"valid":valid,"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"cost_usd":str(c)}
  if parsed:
   rin=[{"atom_index":i,"proposition":x.proposition,"evidence_items":[{"evidence_index":j,"canonical_ref":f"{e.source}:{e.locator}","exact_excerpt":next((z["text"] for z in locs if z["locator"]==e.locator),"")} for j,e in enumerate(x.evidence)]} for i,x in enumerate(parsed.atoms)]
   rr=responses_create(model="gpt-5.6-luna",input_text=RP+"\nTARGET: "+row["target"]+"\nATOMS:\n"+json.dumps(rin,ensure_ascii=False),text_format={"type":"json_schema","name":"scope_resolution_v1","strict":True,"schema":SCOPE_RESOLUTION_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); ru=rr.usage; rc=estimate_response_cost("gpt-5.6-luna",ru) or 0; total+=float(rc); prow.update({"resolver_status":rr.status,"resolver_input_tokens":ru.input_tokens,"resolver_output_tokens":ru.output_tokens,"resolver_cost_usd":str(rc)})
   try: decs=ScopeResolutionOutput.model_validate(json.loads(rr.output_text)).decisions
   except Exception: decs=()
   for i,x in enumerate(parsed.atoms):
    dec=next((z.model_dump(mode="json") for z in decs if z.atom_index==i),{"status":"invalid"}); dec["canonical_evidence_refs"]=[rin[i]["evidence_items"][j]["canonical_ref"] for j in dec.get("supporting_evidence_indices",[]) if isinstance(j,int) and j<len(rin[i]["evidence_items"])]
    summary["atoms"].append({"task_id":f"v12:{idx}","target":row["target"],"publisher":row["publisher"],"source_relation":row["source_relation"],"material_role":row["material_role"],"original_url":row["requested_url"],"final_url":a.get("url") or row.get("final_url"),"raw_sha":a["raw_sha256"],"representation_sha":a["representation_sha256"],"parent_document":a["raw_path"],"chunk_identity":packet["source"]["chunk_identity"],"packet_sha":psha,"raw_compact_atom":x.model_dump(mode="json"),"producer_scope_hint":{"kind":x.scope_kind,"label":x.scope_label},"resolver_evidence_items":rin[i]["evidence_items"],"semantic_resolver":dec,"persistence_gate":"diagnostic_only"})
  summary["packets"].append(prow)
 (ROOT/"campaign-summary.json").write_text(json.dumps({**summary,"compact_calls":len(summary["packets"]),"resolver_calls":sum(1 for x in summary["packets"] if x.get("resolver_status")),"total_cost_usd":str(round(total,6))},ensure_ascii=False,indent=2),encoding="utf-8"); (ROOT/"aggregate-review.json").write_text(json.dumps({"atoms":summary["atoms"]},ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"compact_calls":len(summary["packets"]),"resolver_calls":sum(1 for x in summary["packets"] if x.get("resolver_status")),"atoms":len(summary["atoms"]),"cost":round(total,6)}))
if __name__=="__main__": main()
