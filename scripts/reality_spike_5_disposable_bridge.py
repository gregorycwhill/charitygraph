"""Reality Spike 5 disposable eight-charity replay.

Experimental read-only composition of retained Spike 3 packets, retained Phase 5
frozen representations, and one retained ranked AIS row.  It deliberately does
not acquire, parse PDFs, call a provider, or write any canonical/S0 store.
"""
from __future__ import annotations

import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE5 = ROOT.parent / "phase5-execution-packet" / "work" / "product-value-baseline-2026-09-14"
HISTORICAL = ROOT.parent / "bitemporal-governed-knowledge-v1" / "src"
sys.path.insert(0, str(HISTORICAL))
from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.knowledge import ExternalIdentifier, Observation, ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import CardEvidence, CoverageInput, IntegratedGraph, NORTH_STAR_PROJECTION_VNEXT, compile_matrix, project_subject

OUT = ROOT / "artifacts" / "reality-spike-5-eight-charity-anatomy"
SPIKE3 = ROOT / "artifacts" / "reality-spike-3-acnc-substance"
RANKING = ROOT.parent / "charitygraph-data" / "rankings" / "acnc-2024-ais-donation-ranking-top10000.json"
NOW = datetime.now(timezone.utc)
SUBJECTS = {
 "28004778081":"World Vision Australia", "28000030179":"The Smith Family",
 "74068758654":"Medecins Sans Frontieres Australia Limited", "37646526132":"Sunrise Foundation Limited",
 "50169561394":"Australian Red Cross Society", "47613674461":"Noongar Boodja Trust",
 "78053639115":"Bush Heritage Australia", "61002643852":"Greenpeace Australia Pacific Limited"}
SECTIONS={1:"Identity / regulatory",2:"Purpose / cause",3:"Programs / services",4:"Activities / SDGs",5:"Geography / beneficiaries",6:"Participation",7:"Direct service / capacity",8:"Fundraising",9:"Governance / leadership",10:"People / workforce",11:"Scale / capability",12:"Relationships",13:"Finances",14:"Funding / dependencies",15:"Ethos / values",16:"Conduct / adverse",17:"Notable history",18:"Evaluation / outcomes",19:"Classification / search / AI discovery",20:"Evidence / coverage / freshness / corrections"}

def h(x): return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()
def ident(p,x): return p+h(x)
def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,default=str)+"\n",encoding="utf-8")
def nonempty(x): return x not in (None,"",{},[])

def retained_input(abn):
    """Return source-native data and declared source families; no content acquisition."""
    p=SPIKE3/abn/"packet.json"
    if p.exists():
        raw=json.loads(p.read_text(encoding="utf-8")); profile=raw.get("acnc_profile",{}).get("data") or {}; ais=raw.get("ais_source_native_nonempty_fields") or {}
        return {"name":raw["name"],"profile":profile,"ais":ais,"kind":"spike3_packet","packet":raw,
                "families":{"ACNC register/profile":"available historical machine-readable","AIS detail":"available historical machine-readable","annual/financial reports":"available historical represented filing(s)","official website":"not retained","Wikipedia/Wikimedia":"not retained","DGR/ABR":"not retained","PFRA":"not applicable","specialist/historical":"available Spike 3 packet"}}
    fp=PHASE5/"source-only"/"representations"/abn/"acnc-entity-record.txt"
    if fp.exists():
        raw=json.loads(fp.read_text(encoding="utf-8")); ais=raw.get("data",raw); report=(PHASE5/"source-only"/"representations"/abn/"annual-financial-report-excerpt.txt")
        return {"name":ais.get("LegalName",SUBJECTS[abn]),"profile":ais,"ais":ais,"kind":"phase5_frozen_ais","packet":raw,
                "families":{"ACNC register/profile":"available historical machine-readable","AIS detail":"available historical machine-readable","annual/financial reports":("available historical text representation" if report.exists() else "not retained"),"official website":"not retained","Wikipedia/Wikimedia":"not retained","DGR/ABR":"not retained","PFRA":"not applicable","specialist/historical":"available Phase 5 human-adjudicated experiment records"}}
    ranked=json.loads(RANKING.read_text(encoding="utf-8")); row=next(x for x in ranked["records"] if x["abn"]==abn)
    return {"name":row["charity_name"],"profile":row,"ais":row,"kind":"ranked_ais_row","packet":row,
            "families":{"ACNC register/profile":"not retained","AIS detail":"available historical machine-readable (ranked row)","annual/financial reports":"not retained","official website":"not retained","Wikipedia/Wikimedia":"not retained","DGR/ABR":"not retained","PFRA":"not applicable","specialist/historical":"available Data frozen ranking snapshot"}}

def historical_items(abn):
    f=PHASE5/"adjudicated-context"/"governed-items.json"
    if not f.exists(): return []
    data=json.loads(f.read_text(encoding="utf-8"))
    return [x for x in data.get("proposition_items",[]) if abn in x.get("retention_decision_id","") and x.get("item_kind")=="proposition" and x.get("adjudication_disposition") in {"ACCEPT","ACCEPT_MINOR_CORRECTION"}]

def pair(abn,n,predicate,value,source,sections,method="EXPERIMENTAL_SOURCE_NATIVE_TRANSLATION"):
    subject=ident("subject:",abn); oid=ident("observation:",[abn,n,predicate]); src=ident("srcrec:",abn)
    ob=Observation(record_id=oid,created_at=NOW,producer=ProducerRef(kind="code",producer_id="reality-spike-5-disposable-bridge",version="1"),about_subject_ids=(subject,),subject_id=subject,scope_id=ident("scope:",abn),predicate=predicate,value=value,evidence_locator_ids=(ident("evidence:",abn),),source_record_ids=(src,),observation_time=ObservationTime(observed_at=NOW,reporting_period="retained historical source representation"),method=method,lifecycle_status="accepted")
    return ob,CardEvidence(observation_id=oid,disposition="REUSABLE_EXPERIMENTAL_INPUT",section_ids=tuple(sections),projection_contract_id="north-star-v0.2",note="EXPERIMENTAL_PRODUCT_OWNER_PROMOTION; retained source material")

def make(abn):
    inp=retained_input(abn); profile,ais=inp["profile"],inp["ais"]; name=inp["name"]; subject=ident("subject:",abn); src=ident("srcrec:",abn)
    ref=ArtifactRef(artifact_id=src,content_hash=h(inp["packet"]),schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0",schema_version="1.0"))
    subjects=(SubjectRecord(record_id=ident("subjectrecord:",abn),created_at=NOW,producer=ProducerRef(kind="code",producer_id="reality-spike-5-disposable-bridge",version="1"),about_subject_ids=(subject,),subject_id=subject,subject_kind="organisation",lifecycle_status="active",display_name=name,external_identifiers=(ExternalIdentifier(scheme="ABN",value=abn,issuing_authority="ACNC",source_record_ids=(src,)),),identity_authority_refs=(ref,),identity_policy_id="EXPERIMENTAL_SPIKE5_RETAINED_JOIN_ONLY"),)
    scopes=(ScopeRecord(record_id=ident("scope:",abn),created_at=NOW,producer=ProducerRef(kind="code",producer_id="reality-spike-5-disposable-bridge",version="1"),about_subject_ids=(subject,),subject_id=subject,scope_kind="organisation",label=name),)
    mappings=[("Name",profile.get("Name") or profile.get("LegalName") or profile.get("charity_name"),[1]),("Status",profile.get("Status") or profile.get("registration_status"),[1]),("Activity",ais.get("ActivityPersuitPurposesDescription") or profile.get("SummaryOfActivities") or profile.get("conducted_activities"),[2,4]),("Charity size",ais.get("CharitySize") or profile.get("CharitySize") or profile.get("charity_size"),[11]),("Employees",{k:ais[k] for k in ais if k in {"HrFullTimeEmployees","HrPartTimeEmployees","HrCasualEmployees","HrUnpainVolunteers","HrFteStaff"}},[10,11]),("Financials",{k:ais[k] for k in ais if k in {"RevenueTotal","ExpenseTotal","NetSurplusDeficit","TotalAssets","TotalLiabilities","NetAssetsLiabilities"}},[13]),("Funding",{k:ais[k] for k in ais if k.startswith("Income")},[14]),("Established",profile.get("DateEstablished"),[17]),("Fundraising",profile.get("fundraising_online") or ais.get("RegulatorFundRaising"),[8]),("Evidence packet",{"kind":inp["kind"],"provider_calls":0},[20])]
    pairs=[]; n=1; origin={}
    for label,value,sects in mappings:
        if nonempty(value): pairs.append(pair(abn,n,label,value,inp["kind"],sects)); origin[pairs[-1][0].record_id]="positive_structured"; n+=1
    for prog in profile.get("Programs") or []:
        pairs.append(pair(abn,n,"ACNC listed program",prog,inp["kind"],[3,5])); origin[pairs[-1][0].record_id]="positive_structured"; n+=1
    ben=profile.get("Beneficiaries")
    if ben: pairs.append(pair(abn,n,"ACNC listed beneficiaries",ben,inp["kind"],[5])); origin[pairs[-1][0].record_id]="positive_structured"; n+=1
    for item in historical_items(abn):
        rep=item.get("governed_representation") or {}; sids=rep.get("north_star_section_ids") or ([rep["north_star_section_id"]] if rep.get("north_star_section_id") else [])
        sids=[int(x) for x in sids if str(x).isdigit()]
        if sids:
            pairs.append(pair(abn,n,item.get("governed_proposition_type","historical proposition"),rep,"Phase 5 human-adjudicated historical record",sids,"EXPERIMENTAL_HISTORICAL_SEMANTIC_REPLAY")); origin[pairs[-1][0].record_id]="positive_historical_replay"; n+=1
    observations,evidence=zip(*pairs)
    assigned={s for e in evidence for s in e.section_ids}; coverage=tuple(CoverageInput(subject_id=subject,section_id=s,projection_contract_id="north-star-v0.2",state="NOT_PROCESSED",basis="no_domain_result",note="No retained compatible structured field or accepted historical replay observation.") for s in range(1,21) if s not in assigned)
    graph=IntegratedGraph(subjects=subjects,scopes=scopes,observations=observations,evidence=evidence,coverage_inputs=coverage)
    return inp,graph,project_subject(graph,subject,projection_contract=NORTH_STAR_PROJECTION_VNEXT),origin

def render(inp,projection,origin):
    lines=[f"# {inp['name']}","","**EXPERIMENTAL — NON-PRODUCTION.** Read-only retained-material replay; no canonical/S0 mutation or provider call.","", "## 20-section projection"]
    for s in projection["sections"]:
        kinds=sorted({origin.get(x) for x in s.get("observation_ids",[]) if origin.get(x)})
        lines += [f"\n### {s['section_id']}. {s['title']}",f"State: `{s['missingness']}`; anatomy: `{','.join(kinds) if kinds else 'honest_missingness'}`"]
        lines += ["Governed observations: "+", ".join(s["observation_ids"]) if s["observation_ids"] else "No compatible observation projected; this is processing missingness, not a claim of absence."]
    lines += ["\n## Source inventory",*[f"- {k}: {v}" for k,v in inp["families"].items()]]
    return "\n".join(lines)+"\n"

def inventory(inp):
    """Mechanical inventory of retained-family status; it makes no content claim."""
    out={}
    for family,status in inp["families"].items():
        out[family]={"retention_status":("not_applicable" if status=="not applicable" else "available" if status.startswith("available") else "not_retained"),"freshness":"historical" if status.startswith("available") else "unknown","machine_readable":("machine-readable" in status or "AIS row" in status),"semantic_observations_present":(family=="specialist/historical" and "Phase 5" in status),"projection_consumable_today":(family in {"ACNC register/profile","AIS detail","specialist/historical"} and status.startswith("available")),"note":status}
    return out

def main():
    allgraphs=[]; results=[]
    for abn in SUBJECTS:
        inp,g,proj,origin=make(abn); allgraphs.append(g); results.append((abn,inp,g,proj,origin)); folder=OUT/abn
        dump(folder/"governed_projection.json",proj); dump(folder/"experimental_governed_records.json",{"input_kind":inp["kind"],"source_families":inp["families"],"promotion_decision":"EXPERIMENTAL_PRODUCT_OWNER_PROMOTION","graph":g.model_dump(mode="json"),"observation_anatomy":origin}); (folder/"card.md").write_text(render(inp,proj,origin),encoding="utf-8")
    merged=IntegratedGraph(subjects=tuple(x for g in allgraphs for x in g.subjects),scopes=tuple(x for g in allgraphs for x in g.scopes),observations=tuple(x for g in allgraphs for x in g.observations),evidence=tuple(x for g in allgraphs for x in g.evidence),coverage_inputs=tuple(x for g in allgraphs for x in g.coverage_inputs))
    matrix=compile_matrix(merged,projection_contract=NORTH_STAR_PROJECTION_VNEXT); dump(OUT/"cohort_matrix.json",matrix)
    summary={"token":"REALITY_SPIKE_5_EIGHT_CHARITY_ANATOMY_DISCOVERED","provider_calls":0,"subjects":[{"abn":a,"name":i["name"],"input_kind":i["kind"],"source_families":i["families"],"governed_observations":len(g.observations),"missingness":sum(1 for x in p["sections"] if not x["observation_ids"]),"sections_positive":[x["section_id"] for x in p["sections"] if x["observation_ids"]]} for a,i,g,p,o in results],"source_inventory":{a:inventory(i) for a,i,g,p,o in results},"matrix":matrix,"builder_machinery":{"retained_spike4_bridge":"reusable_historical","retained_phase5_governed_records":"reusable_historical","current_acquisition_parser":"current_not_invoked","current_vnext_20_section_compiler":"genuinely_absent","historical_integrated_card_compiler":"reusable_historical"}}
    dump(OUT/"summary.json",summary)
if __name__=="__main__": main()
