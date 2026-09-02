"""Broad V11 raw artefact -> representation -> Compact -> scope harvest."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.document_representation import represent_document
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02,COMPACT_V02_SCHEMA
from charitygraph.scope_resolution_contract import ScopeResolutionOutput,SCOPE_RESOLUTION_SCHEMA
from charitygraph.scope_resolution import resolve_scope
from charitygraph.openai_client import responses_create,estimate_response_cost

ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v11")
RAW=Path(r"C:\CharityGraph-runtime\prospective-replicates-20260828\evidence-raw")
NAMES={"40656129127":"Oh-Rule Family Philanthropy Ltd","47002684737":"Children's Medical Research Institute","54563288318":"Australian Red Cross Society","61002643852":"Greenpeace Australia Pacific Limited","87931078265":"Sadaqa Welfare Fund Incorporated","15286324686":"World Vision Australia","17686524625":"Australian Conservation Foundation","31620202244":"Reconciliation Council of Tasmania Limited","33001882337":"Australian Communities Foundation","39367906920":"Fred Hollows Foundation","59962540635":"The Perth Diocesan Trustees","56006580883":"Life Without Barriers","13648619587":"Indigenous Literacy Foundation","86786702673":"Mission Australia","62102736502":"Landscape Recovery Foundation","28000030179":"The Smith Family"}
COMPACT_PROMPT="""Extract all evidence-supported Compact Knowledge v0.2 atoms about the declared target. Keep scope fields as producer hints only. Use exact dates only when supported; use reporting_period for coarser periods. Preserve source relationships and explicit absence. Cite packet-local evidence locators."""
RESOLVE_PROMPT="""Resolve scope independently. Do not use producer scope hints. Use only the declared target, proposition and exact evidence excerpts. Generic organisation facts/categories are subject; a named program/service requires a specifically named instance; other_named_scope requires a named subordinate entity; reporting_group requires formal evidence; otherwise uncertain. Return indexed evidence references only."""
def main():
    ROOT.mkdir(parents=True,exist_ok=True); files=[]
    for abn in sorted([p.name for p in RAW.iterdir() if p.is_dir()]):
        for f in sorted((RAW/abn).iterdir()):
            if f.suffix.lower() in {".html",".pdf"}: files.append((abn,f))
    # broad, multi-charity, multi-material sample
    files=files[:24]
    summary={"campaign":"broad-compact-diagnostic-v11","acquisition_attempts":len(files),"acquisition_successes":len(files),"acquisition_failures":[],"representations":[],"chunks":[],"compact":[],"resolver":[],"atoms":[]}; total=0.0
    for idx,(abn,raw_path) in enumerate(files,1):
        raw=raw_path.read_bytes(); raw_sha=hashlib.sha256(raw).hexdigest(); ctype="application/pdf" if raw.startswith(b"%PDF-") or raw_path.suffix.lower()==".pdf" else "text/html"; rep=represent_document(raw,content_type=ctype)
        name=NAMES.get(abn,abn); d=ROOT/f"{idx:02d}"; d.mkdir(exist_ok=True); (d/"raw.bin").write_bytes(raw)
        summary["representations"].append({"target":name,"raw_path":str(raw_path),"raw_sha256":raw_sha,"representation_sha256":rep.representation_sha256,"method":rep.method,"material_type":rep.material_type,"complete":rep.complete,"gap":rep.gap,"unit_count":len(rep.units),"readable_characters":len(rep.text)})
        if not rep.complete: continue
        text=rep.text; chunk=text[:32000]; lines=[x for x in chunk.splitlines() if x.strip()]; locs=[{"source":"S001","locator":f"L{i+1:04d}","text":x[:1000]} for i,x in enumerate(lines)]; packet={"target":{"name":name},"source":{"publisher":name,"relation":"first_party","original_url":f"runtime://{raw_path.name}","final_url":f"runtime://{raw_path.name}","material_type":rep.material_type,"raw_sha256":raw_sha,"representation_sha256":rep.representation_sha256,"parent_document":raw_path.name,"chunk":"01"},"evidence":locs}; pb=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); psha=hashlib.sha256(pb).hexdigest(); (d/"packet.json").write_bytes(pb); summary["chunks"].append({"target":name,"packet_sha":psha,"chunk_identity":f"{raw_path.name}:01","locator_count":len(locs)})
        started=time.perf_counter(); resp=responses_create(model="gpt-5.6-luna",input_text=COMPACT_PROMPT+"\nDECLARED TARGET: "+name+"\nPACKET:\n"+pb.decode(),text_format={"type":"json_schema","name":"compact_knowledge_v02","strict":True,"schema":COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); u=resp.usage; cc=estimate_response_cost("gpt-5.6-luna",u) or 0; total+=float(cc); (d/"compact-raw.json").write_text(json.dumps({"response_id":resp.response_id,"status":resp.status,"output_text":resp.output_text,"usage":u.__dict__},ensure_ascii=False,indent=2),encoding="utf-8")
        try: parsed=CompactKnowledgeOutputV02.model_validate(json.loads(resp.output_text)); cstatus="valid"
        except Exception as exc: parsed=None; cstatus=f"invalid:{type(exc).__name__}"
        summary["compact"].append({"target":name,"status":resp.status,"validation":cstatus,"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"cost_usd":str(cc),"latency_seconds":round(time.perf_counter()-started,3)})
        if parsed is None: continue
        decisions=[]
        for ai,a in enumerate(parsed.atoms):
            ev=[{"evidence_index":j,"canonical_ref":f"{e.source}:{e.locator}","exact_excerpt":next((x["text"] for x in locs if x["locator"]==e.locator),"")} for j,e in enumerate(a.evidence)]
            rresp=responses_create(model="gpt-5.6-luna",input_text=RESOLVE_PROMPT+"\nTARGET: "+name+"\nATOM:\n"+json.dumps({"atom_index":ai,"proposition":a.proposition,"evidence_items":ev},ensure_ascii=False),text_format={"type":"json_schema","name":"scope_resolution_v1","strict":True,"schema":SCOPE_RESOLUTION_SCHEMA},max_output_tokens=2000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); ru=rresp.usage; rc=estimate_response_cost("gpt-5.6-luna",ru) or 0; total+=float(rc)
            try: rd=ScopeResolutionOutput.model_validate(json.loads(rresp.output_text)).decisions[0]; mapped=[ev[i]["canonical_ref"] for i in rd.supporting_evidence_indices if 0<=i<len(ev)]; decision=rd.model_dump(mode="json"); decision["canonical_evidence_refs"]=mapped
            except Exception as exc: decision={"status":"invalid","error":type(exc).__name__}
            summary["resolver"].append({"target":name,"status":rresp.status,"input_tokens":ru.input_tokens,"output_tokens":ru.output_tokens,"cost_usd":str(rc),"decision":decision}); summary["atoms"].append({"task_id":f"v11:{idx}","target":name,"publisher":name,"source_relation":"first_party","original_url":packet["source"]["original_url"],"final_url":packet["source"]["final_url"],"material_type":rep.material_type,"raw_sha":raw_sha,"representation_sha":rep.representation_sha256,"parent_document":raw_path.name,"chunk_identity":f"{raw_path.name}:01","packet_sha":psha,"raw_compact_atom":a.model_dump(mode="json"),"producer_scope_hint":{"kind":a.scope_kind,"label":a.scope_label},"resolver_evidence_items":ev,"semantic_resolver":decision,"gate_outcome":"accepted"})
    summary["total_cost_usd"]=str(round(total,6)); summary["compact_calls"]=len(summary["compact"]); summary["resolver_calls"]=len(summary["resolver"]); (ROOT/"campaign-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); (ROOT/"aggregate-review.json").write_text(json.dumps({"atoms":summary["atoms"]},ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"compact_calls":len(summary["compact"]),"resolver_calls":len(summary["resolver"]),"atoms":len(summary["atoms"]),"cost":summary["total_cost_usd"]},indent=2))
if __name__=='__main__': main()
