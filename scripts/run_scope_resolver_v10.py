"""Independent Luna scope-resolution replay over V10 atoms."""
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
import sys
sys.path.insert(0,"src")
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.scope_resolution_contract import ScopeResolutionOutput,SCOPE_RESOLUTION_SCHEMA

ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v10")
PROMPT="""Resolve scope independently for each numbered atom. Do not use producer scope hints. Use only the declared target and exact evidence excerpts. Generic organisation facts/categories are subject. A named_program_or_service requires one specifically named instance. other_named_scope is a specifically named subordinate network, portfolio, fund, legal vehicle or organisational unit. reporting_group requires formal consolidation evidence. Use uncertain when target relevance is clear but scope is not defensible. Do not invent or normalize names. Return one decision per atom with exact evidence refs."""
def main():
    agg=json.loads((ROOT/'aggregate-review.json').read_text(encoding='utf-8')); groups={}
    for a in agg['atoms']: groups.setdefault(a['producer_task_id'],[]).append(a)
    out=[]; total=0.0
    for key,items in groups.items():
        packet=[{'index':i,'proposition':a['raw_compact_atom']['proposition'],'evidence':a['raw_compact_atom']['evidence']} for i,a in enumerate(items)]
        b=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); started=time.perf_counter()
        resp=responses_create(model='gpt-5.6-luna',input_text=PROMPT+'\nTARGET: '+items[0]['target']+'\nATOMS:\n'+b.decode(),text_format={'type':'json_schema','name':'scope_resolution_v1','strict':True,'schema':SCOPE_RESOLUTION_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'none'})
        usage=resp.usage; cost=estimate_response_cost('gpt-5.6-luna',usage) or 0; total+=float(cost)
        parsed=ScopeResolutionOutput.model_validate(json.loads(resp.output_text)); out.append({'producer_task_id':key,'target':items[0]['target'],'status':resp.status,'decisions': [d.model_dump(mode='json') for d in parsed.decisions], 'input_tokens':usage.input_tokens,'output_tokens':usage.output_tokens,'cost_usd':str(cost),'latency_seconds':round(time.perf_counter()-started,3)})
    (ROOT/'scope-resolution-v10.json').write_text(json.dumps({'prompt_sha256':hashlib.sha256(PROMPT.encode()).hexdigest(),'calls':len(out),'total_cost_usd':str(total),'results':out},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'calls':len(out),'total_cost_usd':str(total)},indent=2))
if __name__=='__main__': main()
