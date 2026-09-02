"""Private three-subject Compact v0.2 execution and persistence proof."""
from __future__ import annotations
import argparse, json, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02, COMPACT_V02_SCHEMA
from charitygraph.compact_knowledge_persistence import adapt_compact_v02
from charitygraph.contracts.source import EvidenceLocator
from run_complete_card_sharded_v01 import _packet_for
from run_compact_knowledge_slice_v01 import modest

PROMPT="""Extract evidence-supported Compact Knowledge v0.2 atoms ABOUT THE DECLARED TARGET SUBJECT in the packet. Return only JSON with an atoms array. The subject scope is the declared target only; do not emit standalone facts about unrelated organisations, regulators, investigations or legal instruments. Contextual third parties may appear inside a proposition about the target. Each atom must contain one concise proposition, scope_kind and optional scope_label. Use effective_from/effective_to only for exact supported ISO calendar dates (YYYY-MM-DD); use reporting_period for coarser periods and never manufacture day/month precision. Use explicit_absence only for evidenced absence/none/zero; pending or not-yet-submitted states are supported status propositions. reporting_group means an evidenced formal group of the target; use other_named_scope for named funds, legal vehicles or organisational units that are not target programs/services. Preserve source-native relationship strength and do not upgrade beneficiary to serves, listing to operates, classification to delivery, or business name to program. Populate time only when the evidence establishes the association. Include packet-local evidence locators and qualifications. Do not use North-Star sections, taxonomies, card completeness, opaque IDs or outside knowledge. Sparse output is correct."""
ROOT=Path(r"C:\CharityGraph-runtime\compact-e2e-v02")
DB=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")

def evidence_maps(packet):
    conn=sqlite3.connect(DB); em={}; sm={}
    for s in packet["sources"]:
        sm[s["source_key"]]=s["source_record_id"]
        rows=conn.execute("select evidence_locator_id,locator_json from evidence_locators where source_record_id=?",(s["source_record_id"],)).fetchall()
        for eid,lj in rows:
            try: loc=json.loads(lj).get("locator");
            except Exception: loc=None
            if loc: em[(s["source_key"],loc.replace("[","").replace("]",""))]=eid
    conn.close(); return em,sm

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("abn",nargs="+"); args=ap.parse_args(); total=0; rows=[]
    for abn in args.abn:
        packet=modest(_packet_for(abn)); outdir=ROOT/abn; outdir.mkdir(parents=True,exist_ok=True); packet_bytes=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); (outdir/"packet.json").write_bytes(packet_bytes); (outdir/"prompt.txt").write_text(PROMPT,encoding="utf-8")
        started=time.perf_counter(); raw_path=outdir/"raw-response.json"
        if raw_path.exists():
            payload=json.loads(raw_path.read_text(encoding="utf-8")); usage=type("Usage",(),payload["usage"])(); response=type("Response",(),{"output_text":payload["output_text"],"response_id":payload.get("response_id"),"status":payload.get("status")})()
        else:
            response=responses_create(model="gpt-5.6-luna",input_text=PROMPT+"\nPACKET:\n"+packet_bytes.decode(),text_format={"type":"json_schema","name":"compact_knowledge_v02","strict":True,"schema":COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"}); usage=response.usage; payload={"response_id":response.response_id,"status":response.status,"output_text":response.output_text,"usage":{"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"total_tokens":usage.total_tokens}}; raw_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        parsed=CompactKnowledgeOutputV02.model_validate(json.loads(response.output_text)); em,sm=evidence_maps(packet); cat=__import__('charitygraph.runtime',fromlist=['SQLiteCatalog']).SQLiteCatalog(DB).open(); locmap={}
        for atom in parsed.atoms:
            for ref in atom.evidence:
                key=(ref.source,ref.locator)
                if key not in locmap:
                    eid=f"compact-e2e:{packet['subject']['abn']}:{ref.source}:{ref.locator}"
                    cat.register_evidence_locator(EvidenceLocator(kind="document",source_record_id=sm[ref.source],locator=ref.locator),evidence_locator_id=eid)
                    locmap[key]=eid
        task="modeltask:e2e"+abn; result="modelresult:e2e"+abn
        now=datetime.now(timezone.utc)
        # Replays use the original observation timestamp so deterministic IDs/material remain identical.
        with sqlite3.connect(DB) as check:
            row0=check.execute("select observation_time_json from knowledge_observations where subject_id=? and method='model:compact-knowledge-v0.2' order by created_at limit 1",(packet["subject"]["subject_id"],)).fetchone()
        if row0:
            now=datetime.fromisoformat(json.loads(row0[0])["observed_at"])
        scopes,obs=adapt_compact_v02(parsed,subject_id=packet["subject"]["subject_id"],observed_at=now,model_result_id=result,task_id=task,evidence_locator_map=locmap,source_record_map=sm); [cat.register_scope(s) for s in scopes]; [cat.record_observation(o) for o in obs]; cat.close(); cost=estimate_response_cost("gpt-5.6-luna",usage); total+=cost or 0; rows.append({"abn":abn,"status":response.status,"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"atoms":len(parsed.atoms),"scopes":len(scopes),"observations":len(obs),"cost_usd":str(cost),"latency_seconds":round(time.perf_counter()-started,3)})
    (ROOT/"report.json").write_text(json.dumps({"prompt_sha256":__import__('hashlib').sha256(PROMPT.encode()).hexdigest(),"total_cost_usd":str(total),"subjects":rows},indent=2),encoding="utf-8"); print(json.dumps(rows,indent=2))
if __name__=="__main__": main()
