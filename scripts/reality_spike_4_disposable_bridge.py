"""Reality Spike 4 disposable bridge.

NOT a production pipeline.  It composes retained Spike 3 packets with the
historical vNext governed contracts/projection compiler, without acquisition,
provider calls, or promotion into any canonical store.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT.parent / "bitemporal-governed-knowledge-v1" / "src"
sys.path.insert(0, str(HISTORICAL))
from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.knowledge import ExternalIdentifier, Observation, ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import (CardEvidence, CoverageInput, IntegratedGraph,
    NORTH_STAR_PROJECTION_VNEXT, compile_matrix, project_subject)

PACKETS = ROOT / "artifacts" / "reality-spike-3-acnc-substance"
OUT = ROOT / "artifacts" / "reality-spike-4-governed-projection"
NOW = datetime.now(timezone.utc)

SECTIONS = {1:"Identity / regulatory",2:"Purpose / cause",3:"Programs / services",4:"Activities / SDGs",5:"Geography / beneficiaries",6:"Participation",7:"Direct service / capacity",8:"Fundraising",9:"Governance / leadership",10:"People / workforce",11:"Scale / capability",12:"Relationships",13:"Finances",14:"Funding / dependencies",15:"Ethos / values",16:"Conduct / adverse",17:"Notable history",18:"Evaluation / outcomes",19:"Classification / search / AI discovery",20:"Evidence / coverage / freshness / corrections"}

def h(v: object) -> str: return hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()
def ident(prefix: str, value: object) -> str: return prefix + h(value)
def dump(p: Path, v: object): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v, indent=2, default=str)+"\n", encoding="utf-8")
def obs(abn, n, predicate, value, source, sections):
    subject=ident("subject:",abn); scope=ident("scope:",abn); oid=ident("observation:",[abn,n,predicate])
    return Observation(record_id=oid, created_at=NOW, producer=ProducerRef(kind="code",producer_id="reality-spike-4-disposable-bridge",version="1"), about_subject_ids=(subject,), subject_id=subject, scope_id=scope, predicate=predicate, value=value, evidence_locator_ids=(ident("evidence:",abn),), source_record_ids=(ident("srcrec:",abn),), observation_time=ObservationTime(observed_at=NOW, reporting_period="ACNC latest submitted AIS / retained profile"), method="EXPERIMENTAL_SOURCE_NATIVE_TRANSLATION", lifecycle_status="accepted"), CardEvidence(observation_id=oid, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=tuple(sections), projection_contract_id="north-star-v0.2", note=f"EXPERIMENTAL_PRODUCT_OWNER_PROMOTION; retained Spike 3 ACNC field: {source}")
def make(abn: str):
    p=json.loads((PACKETS/abn/"packet.json").read_text(encoding="utf-8")); profile=(p["acnc_profile"].get("data") or {}); ais=p.get("ais_source_native_nonempty_fields") or {}; name=p["name"]
    subject=ident("subject:",abn); source_hash=h(p); src=ident("srcrec:",abn); scope=ident("scope:",abn)
    ref=ArtifactRef(artifact_id=src,content_hash=source_hash,schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0",schema_version="1.0"))
    subjects=(SubjectRecord(record_id=ident("subjectrecord:",abn),created_at=NOW,producer=ProducerRef(kind="code",producer_id="reality-spike-4-disposable-bridge",version="1"),about_subject_ids=(subject,),subject_id=subject,subject_kind="organisation",lifecycle_status="active",display_name=name,external_identifiers=(ExternalIdentifier(scheme="ABN",value=abn,issuing_authority="ACNC",source_record_ids=(src,)),),identity_authority_refs=(ref,),identity_policy_id="EXPERIMENTAL_SPIKE4_ACNC_JOIN_ONLY"),)
    scopes=(ScopeRecord(record_id=scope,created_at=NOW,producer=ProducerRef(kind="code",producer_id="reality-spike-4-disposable-bridge",version="1"),about_subject_ids=(subject,),subject_id=subject,scope_kind="organisation",label=name),)
    pairs=[]; n=1
    # Exact source-native field mapping; no prose interpretation or model call.
    mappings=[("Name",profile.get("Name"),"ACNC profile Name",[1]),("Status",profile.get("Status"),"ACNC profile Status",[1]),("Activity",ais.get("ActivityPersuitPurposesDescription") or profile.get("SummaryOfActivities"),"ACNC AIS/profile activity",[2,4]),("Charity size",ais.get("CharitySize") or profile.get("CharitySize"),"ACNC charity size",[11]),("Employees",{k:ais[k] for k in ais if k in {"HrFullTimeEmployees","HrPartTimeEmployees","HrCasualEmployees","HrUnpainVolunteers"}},"ACNC AIS workforce fields",[10,11]),("Financials",{k:ais[k] for k in ais if k in {"RevenueTotal","ExpenseTotal","NetSurplusDeficit","TotalAssets","TotalLiabilities","NetAssetsLiabilities"}},"ACNC AIS finance fields",[13]),("Funding",{k:profile[k] for k in profile if k.startswith("TotalGrossIncome")},"ACNC profile income fields",[14]),("Established",profile.get("DateEstablished"),"ACNC profile DateEstablished",[17]),("Evidence packet",{"retrieved_at":p["retrieved_at"],"filings":len(p.get("filings",[])),"model_calls":0},"Spike 3 packet / filing representations",[20])]
    for label,value,source,sects in mappings:
        if value not in (None,"",{},[]): pairs.append(obs(abn,n,label,value,source,sects)); n+=1
    for prog in profile.get("Programs") or []:
        pairs.append(obs(abn,n,"ACNC listed program",prog,"ACNC profile Programs",[3,5])); n+=1
    if profile.get("Beneficiaries"): pairs.append(obs(abn,n,"ACNC listed beneficiaries",[x.get("Name") for x in profile["Beneficiaries"]],"ACNC profile Beneficiaries",[5])); n+=1
    observations,evidence=zip(*pairs)
    explicit=[]
    assigned={s for e in evidence for s in e.section_ids}
    for sid in range(1,21):
        if sid not in assigned: explicit.append(CoverageInput(subject_id=subject,section_id=sid,projection_contract_id="north-star-v0.2",state="NOT_PROCESSED",basis="no_domain_result",note="No compatible retained Spike 3 source-native field or report semantic extraction."))
    graph=IntegratedGraph(subjects=subjects,scopes=scopes,observations=observations,evidence=evidence,coverage_inputs=tuple(explicit))
    return p, graph, project_subject(graph,subject,projection_contract=NORTH_STAR_PROJECTION_VNEXT)
def render(packet, projection):
    lookup={x.record_id:x for x in []}; lines=[f"# {packet['name']}","","**EXPERIMENTAL — NON-PRODUCTION.** Governed-contract bridge over retained Spike 3 evidence; all promoted observations are `EXPERIMENTAL_PRODUCT_OWNER_PROMOTION`.","",f"ACNC profile: {packet['identity']['acnc_profile_url']}","", "## North Star v0.2 projection"]
    for s in projection['sections']:
        lines += [f"\n### {s['section_id']}. {s['title']}", f"Status: `{s['missingness']}` ({s.get('basis')})"]
        if s['observation_ids']: lines.append("Evidence-backed governed observation IDs: " + ", ".join(s['observation_ids']))
        else: lines.append("No compatible observation was projected; this is explicit missingness, not a negative claim.")
    lines += ["\n## Trust compact",f"Retained packet timestamp: {packet['retrieved_at']}. Source family: ACNC profile/latest AIS plus {len(packet.get('filings',[]))} selected filing representations. Provider calls: 0. Report prose was not semantically extracted in this bridge."]
    return "\n".join(lines)+"\n"
def main():
    OUT.mkdir(parents=True,exist_ok=True); allgraphs=[]; projections=[]
    for abn in ("37646526132","74068758654","47613674461"):
        packet,graph,projection=make(abn); allgraphs.append(graph); projections.append((packet,projection)); folder=OUT/abn; dump(folder/"governed_projection.json",projection); (folder/"card.md").write_text(render(packet,projection),encoding="utf-8")
        dump(folder/"experimental_governed_records.json",{"source_record":{"record_id":ident("srcrec:",abn),"payload_hash":h(packet)},"evidence_fragment":{"record_id":ident("evidence:",abn),"source_record_id":ident("srcrec:",abn)},"promotion_decision":"EXPERIMENTAL_PRODUCT_OWNER_PROMOTION","graph":graph.model_dump(mode="json")})
    # compiler requires one graph: concatenate the independently valid graphs.
    merged=IntegratedGraph(subjects=tuple(x for g in allgraphs for x in g.subjects),scopes=tuple(x for g in allgraphs for x in g.scopes),observations=tuple(x for g in allgraphs for x in g.observations),evidence=tuple(x for g in allgraphs for x in g.evidence),coverage_inputs=tuple(x for g in allgraphs for x in g.coverage_inputs))
    matrix=compile_matrix(merged,projection_contract=NORTH_STAR_PROJECTION_VNEXT); dump(OUT/"cohort_matrix.json",matrix)
    lines=["# Reality Spike 4 cohort comparison","","Experimental non-production governed-contract projection. `GOVERNED_PRESENT` is unavailable because retained input was deliberately promoted only under `EXPERIMENTAL_PRODUCT_OWNER_PROMOTION`. `EXPERIMENTAL_REVIEW` means source evidence reached a section; `NOT_PROCESSED` is explicit missingness.",""]
    for row in matrix: lines.append(f"- {row['section_id']}. {row['title']}: " + "; ".join(f"{c['subject_name']}={c['status']} ({c['observation_count']})" for c in row['cells']))
    (OUT/"COHORT_COMPARISON.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
if __name__ == '__main__': main()
