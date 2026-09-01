"""Execute one modest, card-blind compact-knowledge shard per subject."""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, "src")
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.compact_knowledge import CompactKnowledgeOutput, STRICT_SCHEMA
from run_complete_card_sharded_v01 import _packet_for, _public_packet

MODEL = "gpt-5.6-luna"
PROMPT = """Extract all evidence-supported CharityGraph knowledge atoms from this packet.\nReturn only JSON with an atoms array. Each atom is one concise proposition with scope, temporal semantics, epistemic status, and packet-local evidence. Do not use North-Star section IDs, taxonomies, card completeness, opaque IDs, or outside knowledge. Sparse output is correct; do not manufacture coverage."""
ROOT = Path(r"C:\CharityGraph-runtime\compact-knowledge-v01")

def modest(packet):
    source = packet["sources"][0]
    lines = source["content"].splitlines()
    kept=[]; size=0
    for line in lines:
        if kept and size + len(line) + 1 > 60000: break
        kept.append(line); size += len(line)+1
    return _public_packet(dict(packet, sources=[dict(source, content="\n".join(kept))]))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("abn", nargs="+"); ap.add_argument("--execute", action="store_true"); ap.add_argument("--root",type=Path,default=ROOT); args=ap.parse_args()
    rows=[]; projected=Decimal("0")
    for abn in args.abn:
        packet=modest(_packet_for(abn)); raw=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); est=(len(raw)+len(PROMPT.encode())+3)//4; maxout=7000; p=(Decimal(est)*Decimal(".20")+Decimal(maxout)*Decimal("1.20"))/Decimal(1_000_000); projected+=p
        row={"abn":abn,"packet_sha256":hashlib.sha256(raw).hexdigest(),"input_tokens_estimate":est,"projected_usd":str(p.quantize(Decimal(".000001")))}
        if args.execute:
            out=args.root/abn; out.mkdir(parents=True,exist_ok=True); (out/"packet.json").write_bytes(raw); (out/"prompt.txt").write_text(PROMPT,encoding="utf-8")
            started=time.perf_counter()
            try:
                response=responses_create(model=MODEL,input_text=PROMPT+"\nPACKET:\n"+raw.decode(),text_format={"type":"json_schema","name":"compact_knowledge_v01","strict":True,"schema":STRICT_SCHEMA},max_output_tokens=maxout,max_attempts=1,timeout_seconds=300,reasoning={"effort":"high"})
                payload={"response_id": response.response_id, "model": response.model, "status": response.status, "output_text": response.output_text, "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "total_tokens": response.usage.total_tokens}}
                (out/"raw-response.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
                valid=CompactKnowledgeOutput.model_validate(json.loads(response.output_text))
                row.update({"provider_calls":1,"input_tokens":response.usage.input_tokens,"output_tokens":response.usage.output_tokens,"cost_usd":str(estimate_response_cost(MODEL, response.usage)),"valid":True,"atoms":len(valid.atoms)})
            except Exception as exc:
                (out/"error.json").write_text(json.dumps({"error_class":type(exc).__name__,"error":str(exc)},indent=2),encoding="utf-8"); row.update({"provider_calls":1 if (out/"raw-response.json").exists() else 0,"valid":False,"error_class":type(exc).__name__})
            row["latency_seconds"]=round(time.perf_counter()-started,3)
        rows.append(row)
    result={"prompt_sha256":hashlib.sha256(PROMPT.encode()).hexdigest(),"projected_total_usd":str(projected.quantize(Decimal(".000001"))),"subjects":rows}; args.root.mkdir(parents=True,exist_ok=True); (args.root/"run-report.json").write_text(json.dumps(result,indent=2),encoding="utf-8"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
