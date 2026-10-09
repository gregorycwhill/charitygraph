"""Execute CG353 A/B/C on frozen challenge evidence only.

This is deliberately an orchestration boundary: it labels retained text, calls
the existing Responses client, validates schemas, and writes telemetry.  It
does not classify or otherwise interpret evidence in Python.
"""
from __future__ import annotations

import argparse, json
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from charitygraph.compact_knowledge import COMPACT_V02_SCHEMA, CompactKnowledgeOutputV02
from charitygraph.ethos_notability_extraction import (CandidateBundle, OUTPUT_SCHEMA, PROMPT,
    FrozenEthosNotabilityPacket, PacketEvidence, validate_bundle)
from charitygraph.openai_client import estimate_response_cost, responses_create
from charitygraph.unified_semantic_experiment import MODEL, UNIFIED_PROMPT, UNIFIED_PROMPT_VERSION, UNIFIED_SCHEMA, UnifiedSemanticOutput, canonical_hash, enforce_spend

EXPECTED = "120e20160adbfd27a53b526b200e85841850ded612a839dd4381110295300644"
GENERAL_PROMPT = """Extract compact supported knowledge only from the labelled retained evidence below.
Do not browse, use background knowledge, or invent facts.  Every atom needs supporting S/locator evidence.
Keep scope, time and qualifications explicit. Return only schema-valid JSON."""

def strict_schema(schema):
    """Responses requires every object property to be explicitly required."""
    value=json.loads(json.dumps(schema))
    def visit(node):
        if isinstance(node,dict):
            node.pop("default",None)
            if node.get("type")=="object" and isinstance(node.get("properties"),dict): node["required"]=list(node["properties"])
            for child in node.values(): visit(child)
        elif isinstance(node,list):
            for child in node: visit(child)
    visit(value); return value

def evidence_for(packet, root: Path, fallback: Path | None = None):
    """Materialise immutable representations with a deterministic byte-preserving slice."""
    rows=[]
    for n, ev in enumerate(packet["evidence"], 1):
        p=root / ev["representation_locator"]
        if not p.is_file() and fallback is not None:
            p=fallback / ev["representation_locator"]
        if not p.is_file() or sha256(p.read_bytes()).hexdigest()!=ev["representation_sha256"]:
            raise ValueError("missing_or_changed_representation:"+ev["representation_locator"])
        # A fixed 12k-character packet budget is transport shaping, not semantic selection.
        representation=json.loads(p.read_text(encoding="utf-8"))
        # Representations are either decoded text or a retained JSON value;
        # canonical serialisation preserves the latter without interpreting it.
        text=(representation.get("text") if isinstance(representation.get("text"), str) else json.dumps(representation.get("json"), sort_keys=True, ensure_ascii=False, separators=(",",":")))[:6000]
        rows.append((f"S{n:03d}", f"L{n:04d}", ev, text))
    return rows

def compact_input(rows):
    return GENERAL_PROMPT+"\nEVIDENCE:\n"+"\n".join(f"{s} {l} ({e.get('source_role','context')}):\n{t}" for s,l,e,t in rows)[:12000]

def dedicated_packet(packet, rows):
    # The frozen capture binds every record to one subject; the only permitted
    # scope in this workshop is that subject itself (no parent/program transfer).
    evidence=[]
    for _,_,e,t in rows:
        evidence.append(PacketEvidence(evidence_id=e["evidence_fragment_id"], source_record_id=e.get("source_record_id", e["raw_blob_id"]), lineage_id=e["raw_blob_id"], text=t,
            source_role="supporting" if e.get("source_role")=="supporting" else "context", retrieved_at=e.get("retrieved_at"), source_family=e.get("source_family"), source_version=e.get("source_version"), source_locator=e.get("resolved_locator"), source_blob_id=e.get("raw_blob_id"), source_blob_hash=e.get("raw_sha256"), representation_id=e.get("representation_id"), representation_hash=e.get("representation_sha256"), fragment_locator=e.get("fragment_locator"), fragment_hash=e.get("fragment_sha256"), subject_binding_id=packet["subject_id"]))
    return FrozenEthosNotabilityPacket(packet_id=packet["packet_id"], packet_hash=packet["packet_hash"], subject_id=packet["subject_id"], permitted_scope_ids=(packet["subject_id"],), evidence=tuple(evidence))

def call(ledger, prompt, schema, cap):
    # $0.01 is a conservative reservation; actual cost is appended immediately.
    enforce_spend(ledger, "0.01", cap_usd=cap)
    response=responses_create(model=MODEL,input_text=prompt,text_format={"type":"json_schema","name":"cg353_output","strict":True,"schema":schema},max_output_tokens=1200,max_attempts=1,timeout_seconds=120,reasoning={"effort":"none"})
    cost=estimate_response_cost(response.model,response.usage)
    entry={"at":datetime.now(timezone.utc).isoformat(),"model":response.model,"cost_usd":str(cost or 0),"input_tokens":response.usage.input_tokens,"output_tokens":response.usage.output_tokens,"response_id":response.response_id}
    ledger.setdefault("entries",[]).append(entry)
    return response, entry

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--corpus",type=Path,required=True); ap.add_argument("--representations",type=Path,required=True); ap.add_argument("--fallback-representations",type=Path); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--ledger",type=Path,required=True); ap.add_argument("--cap",default="2.00"); ap.add_argument("--case",action="append",dest="cases"); ap.add_argument("--arm",action="append",choices=("A","B","C"),dest="arms"); ap.add_argument("--final-holdout",action="store_true",help="explicitly release the fixed blind controls for the final no-tuning comparison"); args=ap.parse_args()
    corpus=json.loads(args.corpus.read_text(encoding="utf-8")); assert corpus.get("corpus_sha256")==EXPECTED and corpus.get("provider_calls")==0
    ledger=json.loads(args.ledger.read_text()) if args.ledger.exists() else {"experiment_id":"CG-UNIFIED-SEMANTIC-EXTRACTION-353","entries":[]}
    # The final holdout is an all-five, explicit release: no selective blind
    # reading is allowed.  Ordinary workshop runs remain challenge-only.
    challenge={p["case_id"] for p in corpus["packets"] if int(p["case_id"].split("-")[1])<=10}
    blind={p["case_id"] for p in corpus["packets"] if int(p["case_id"].split("-")[1])>10}
    cases=blind if args.final_holdout else challenge
    if args.cases:
        requested=set(args.cases)
        if not requested <= cases: raise ValueError("requested case is outside the permitted frozen split")
        if args.final_holdout and requested != blind: raise ValueError("final holdout must execute all five fixed blind controls")
        cases=requested
    arms=tuple(args.arms or ("A","B","C"))
    schemas={"A":strict_schema(COMPACT_V02_SCHEMA),"B":strict_schema(OUTPUT_SCHEMA),"C":strict_schema(UNIFIED_SCHEMA)}
    report={"experiment_id":ledger["experiment_id"],"model":MODEL,"provider_path":"openai.responses","corpus_sha256":EXPECTED,"unified_prompt_version":UNIFIED_PROMPT_VERSION,"arms":{a:[] for a in arms},"schema_hashes":{k:canonical_hash(v) for k,v in schemas.items()}}
    for case in sorted(cases):
        p15=next(p for p in corpus["packets"] if p["case_id"]==case and p["section"]==15); rows=evidence_for(p15,args.representations,args.fallback_representations)
        packet=dedicated_packet(p15,rows); general=compact_input(rows)
        for arm,prompt,schema in (("A",general,schemas["A"]),("B",PROMPT+"\nPACKET:\n"+packet.model_dump_json(),schemas["B"]),("C",UNIFIED_PROMPT+"\nEVIDENCE:\n"+"\n".join(f"{s} {l} ({e.get('source_role','context')}):\n{t}" for s,l,e,t in rows)[:12000]+"\nETHOS/NOTABILITY PACKET:\n"+packet.model_dump_json(),schemas["C"])):
            if arm not in arms: continue
            response,entry=call(ledger,prompt,schema,args.cap); raw=response.output_text
            valid=False; reasons=[]
            try:
                if arm=="A": CompactKnowledgeOutputV02.model_validate_json(raw); valid=True
                elif arm=="B": v=validate_bundle(packet,raw); valid=v.accepted; reasons=list(v.reasons)
                else: UnifiedSemanticOutput.model_validate_json(raw); valid=True
            except Exception as exc: reasons=["malformed_schema:"+str(exc).splitlines()[0]]
            report["arms"][arm].append({"case_id":case,"packet_hash":p15["packet_hash"],"request_hash":sha256(prompt.encode()).hexdigest(),"response_hash":sha256(raw.encode()).hexdigest(),"raw_response":raw,"valid":valid,"validation_reasons":reasons,"telemetry":entry})
            args.ledger.parent.mkdir(parents=True,exist_ok=True); args.ledger.write_text(json.dumps(ledger,indent=2)+"\n")
            # Persist each completed call before proceeding: a later local or
            # provider failure cannot erase raw evidence of earlier calls.
            args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+"\n")
    report["aggregate"]={a:{"calls":len(r),"valid":sum(x["valid"] for x in r),"input_tokens":sum((x["telemetry"]["input_tokens"] or 0) for x in r),"output_tokens":sum((x["telemetry"]["output_tokens"] or 0) for x in r),"cost_usd":str(sum((Decimal(x["telemetry"]["cost_usd"]) for x in r),Decimal("0")))} for a,r in report["arms"].items()}
    report["report_sha256"]=canonical_hash(report); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__": main()
