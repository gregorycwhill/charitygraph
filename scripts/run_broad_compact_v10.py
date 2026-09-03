"""Private V10 representation + scope-resolution harvest over frozen packets."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02, COMPACT_V02_SCHEMA
from charitygraph.scope_resolution import resolve_scope

RUNTIME=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v10")
PROMPT=(Path("scripts/run_compact_e2e_v02.py").read_text(encoding="utf-8").split('PROMPT="""',1)[1].split('"""',1)[0])

def packets():
    roots=[Path(rf"C:\CharityGraph-runtime\broad-compact-diagnostic-v{x}") for x in (7,8,9)]
    out=[]; seen=set()
    for root in roots:
        for p in sorted(root.glob("*/packet.json")):
            try: data=json.loads(p.read_text(encoding="utf-8"))
            except Exception: continue
            subject=(data.get("target_subject") or data.get("subject") or {}).get("name")
            if subject and subject not in seen:
                seen.add(subject); out.append((subject,p,data))
    return out[:12]

def main():
    RUNTIME.mkdir(parents=True,exist_ok=True); rows=[]; atoms=[]; total=0.0
    for i,(subject,path,packet) in enumerate(packets(),1):
        b=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode(); sha=hashlib.sha256(b).hexdigest()
        d=RUNTIME/f"{i:02d}"; d.mkdir(exist_ok=True); (d/"packet.json").write_bytes(b); (d/"prompt.txt").write_text(PROMPT,encoding="utf-8")
        started=time.perf_counter(); req= response= None
        response=responses_create(model="gpt-5.6-luna",input_text=PROMPT+"\nPACKET:\n"+b.decode(),text_format={"type":"json_schema","name":"compact_knowledge_v02","strict":True,"schema":COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"})
        u=response.usage; cost=estimate_response_cost("gpt-5.6-luna",u) or 0.0; total+=float(cost)
        raw={"response_id":response.response_id,"status":response.status,"output_text":response.output_text,"usage":{"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"total_tokens":u.total_tokens}}
        (d/"raw-response.json").write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
        parsed=CompactKnowledgeOutputV02.model_validate(json.loads(response.output_text)); scope_changes=0
        for n,a in enumerate(parsed.atoms):
            res=resolve_scope(producer_scope_kind=a.scope_kind,producer_scope_label=a.scope_label,evidence_refs=tuple(f"{e.source}:{e.locator}" for e in a.evidence))
            if res.resolved_scope_kind != a.scope_kind: scope_changes+=1
            atoms.append({"producer_task_id":f"v10:{i}","target":subject,"source_publisher":None,"source_relation":"first_party","original_url":None,"final_url":None,"material_type":"public_prose","raw_artefact_sha":None,"representation_sha":sha,"parent_document_id":path.name,"chunk_identity":f"v10:{i}","packet_sha":sha,"raw_compact_atom":a.model_dump(mode="json"),"producer_scope_hint":{"kind":a.scope_kind,"label":a.scope_label},"resolved_scope":{"kind":res.resolved_scope_kind,"label":res.resolved_scope_label,"status":res.scope_status,"evidence_refs":list(res.evidence_refs)}})
        rows.append({"subject":subject,"packet":str(path),"packet_sha":sha,"status":response.status,"atoms":len(parsed.atoms),"scope_changes":scope_changes,"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"reasoning_tokens":getattr(u,"reasoning_tokens",0),"cost_usd":str(cost),"latency_seconds":round(time.perf_counter()-started,3)})
    (RUNTIME/"campaign-summary.json").write_text(json.dumps({"campaign":"broad-compact-diagnostic-v10","provider_calls":len(rows),"total_cost_usd":str(total),"subjects":rows},indent=2),encoding="utf-8")
    (RUNTIME/"aggregate-review.json").write_text(json.dumps({"atoms":atoms},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rows,indent=2))
if __name__=="__main__": main()
