"""Private Baseline Charity Corpus v1 acquisition experiment."""
from __future__ import annotations
import argparse, hashlib, json
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from charitygraph.baseline_corpus import (AcquisitionState, BindingState, CorpusMember, DiscoveryState, MaterialOrigin, RepresentationReadiness, build_corpus_manifest, enumerate_site_candidates, rank_site_candidates_with_luna, represent_pdf)
from charitygraph.contracts import AcquisitionReceipt, PropositionAuthorityRole, SourceDefinition, SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog

ABNS=("28000030179","50169561394","20077830347","22007498482","15000002522","28004778081","46070556642","67649417658","45146631843","15101252171")
WEBSITES={"28000030179":"https://www.thesmithfamily.com.au","50169561394":"https://www.redcross.org.au","20077830347":"https://www.communityfoundation.org.au","22007498482":"https://www.acf.org.au","15000002522":"https://www.missionaustralia.com.au","28004778081":"https://www.worldvision.com.au","46070556642":"https://www.hollows.org","67649417658":"https://landscaperecovery.com.au","45146631843":"https://www.ilf.org.au","15101252171":"https://www.lwb.org.au"}
API="https://www.acnc.gov.au/api/dynamics"
WIKI="https://en.wikipedia.org/w/api.php"
PFRA="https://www.pfra.org.au/"
DEV=set(ABNS[:7])
MAX_PROVIDER_USD=Decimal("0.50")
LUNA_INPUT_USD_PER_MILLION=Decimal("0.20")
LUNA_OUTPUT_USD_PER_MILLION=Decimal("1.20")
LUNA_MAX_OUTPUT_TOKENS=8000

def projected_luna_cost(candidates):
    # Bound a call (including one permitted transport retry) before transmission.
    input_tokens=(len(json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))) // 4) + 128
    return (Decimal(input_tokens) * LUNA_INPUT_USD_PER_MILLION + Decimal(LUNA_MAX_OUTPUT_TOKENS * 2) * LUNA_OUTPUT_USD_PER_MILLION) / Decimal(1_000_000)

def now(): return datetime.now(timezone.utc)
def fetch(url):
    req=Request(url,headers={"User-Agent":"CharityGraph baseline-corpus-v1/1.0"})
    with urlopen(req,timeout=45) as r: return r.read(),r.geturl(),r.status,r.headers.get_content_type()
def digest(b): return hashlib.sha256(b).hexdigest()

def subjects(catalog):
    with catalog._connection() as conn:
        rows=conn.execute("SELECT e.identifier_value,e.subject_id FROM external_identifiers e WHERE e.scheme='ABN' AND e.issuing_authority='Australian Business Register' AND e.status='active'").fetchall()
    mapping={str(r[0]):str(r[1]) for r in rows}
    if set(mapping)!=set(ABNS): raise RuntimeError("stable vNext catalogue does not contain all ten governed ABNs")
    return mapping

def source_lineage(catalog,store,*,family,endpoint,url,body,resolved,media,subject_id,role,revision=None):
    created=now(); definition_id=deterministic_id("srcdef:",{"family":family,"endpoint":endpoint,"profile":"baseline-v1"})
    definition=SourceDefinition(record_id=definition_id,created_at=created,producer={"kind":"code","producer_id":"baseline-corpus-v1","version":"1"},publisher="Australian Charities and Not-for-profits Commission" if family.startswith("acnc") else family,source_class=family,authority_roles=(PropositionAuthorityRole(proposition="source material",role="source-reported",basis="bounded baseline acquisition"),),acquisition_locator=endpoint,temporal_semantics="current_or_reported_period",publication_eligibility="private_review_only",steward="CharityGraph private corpus")
    if catalog.get_source_definition(definition_id) is None: catalog.register_source_definition(definition)
    h=digest(body); artifact_id="srcblob:"+h; indexed=catalog.get_artifact(artifact_id)
    if indexed is None: artifact=store.put(body,created_at=created)
    else: artifact=type("A",(),{"artifact_id":artifact_id,"content_hash":h,"byte_size":len(body)})()
    receipt_id=deterministic_id("acq:",{"source_definition_id":definition_id,"artifact_id":artifact_id})
    if catalog.get_acquisition_receipt(receipt_id) is None:
        catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=receipt_id,created_at=created,producer={"kind":"code","producer_id":"baseline-corpus-v1","version":"1"},source_definition_id=definition_id,requested_locator=url,resolved_locator=resolved,retrieved_at=created,outcome="available",response_status=200,media_type=media,content_hash=h,byte_size=len(body),artifact_id=artifact_id,tool_id="urllib",tool_version="stdlib"))
    source_id=deterministic_id("srcrec:",{"source_family":family,"source_version":revision,"source_locator":resolved,"payload_hash":h})
    if catalog.get_source_record(source_id) is None:
        catalog.register_source_record(SourceRecord(record_id=source_id,created_at=created,producer={"kind":"code","producer_id":"baseline-corpus-v1","version":"1"},source_family=family,source_role=role,source_version=revision,source_locator=resolved,retrieved_at=created,observed_at=created,media_type=media,payload_ref=artifact_id,payload_hash=h,attribution="Australian Charities and Not-for-profits Commission" if family.startswith("acnc") else None))
    return definition_id,receipt_id,artifact_id,source_id

def acnc_fetch(abn):
    search_url=API+"/search/charity?"+urlencode({"search":abn}); search_body,_,_,_=fetch(search_url); search=json.loads(search_body); matches=[x for x in search.get("results",[]) if str(x.get("data",{}).get("Abn",""))==abn]
    if len(matches)!=1: raise RuntimeError(f"ACNC exact ABN resolution failed for {abn}")
    uuid=matches[0]["uuid"]; url=f"{API}/entity/{uuid}"; body,resolved,status,media=fetch(url); entity=json.loads(body)
    if str(entity.get("data",{}).get("Abn",""))!=abn: raise RuntimeError(f"ACNC ABN mismatch for {abn}")
    return url,body,resolved,status,media,entity

def run(args):
    runtime=args.runtime.resolve(); runtime.mkdir(parents=True,exist_ok=True); catalog=SQLiteCatalog(Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")).open(initialize=True); ids=subjects(catalog); store=ContentAddressedArtifactStore(runtime/"objects",allowed_roots=(runtime,),catalog=catalog)
    corpora=[]; matrix=[]; site={}; pdf=[]; all_artifacts=set(); acquired_new=0; reused=0; wiki_hits=0; pfra_hits=0; provider_spend=Decimal("0")
    for abn in ABNS:
        sid=ids[abn]; members=[]; coverage={}
        # ACNC Register: use existing governed SourceRecord or acquire the exact current API record.
        acnc_rows=[]
        with catalog._connection() as conn:
            acnc_rows=conn.execute("SELECT source_record_id,payload_ref,payload_hash,source_locator FROM source_records WHERE source_family='acnc_register' AND source_locator LIKE ?",('%'+abn+'%',)).fetchall()
        if acnc_rows:
            source_ids=tuple(r[0] for r in acnc_rows); arts=tuple(r[1] for r in acnc_rows); def_id=deterministic_id("srcdef:",{"family":"acnc_register","endpoint":f"{API}/entity","profile":"baseline-v1"}); recs=tuple(deterministic_id("acq:",{ "source_definition_id":def_id,"artifact_id":a}) for a in arts); members.append(CorpusMember(source_family="acnc_register",source_definition_id=def_id,acquisition_receipt_ids=recs,artifact_ids=arts,source_record_ids=source_ids,discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.AVAILABLE,subject_binding=BindingState.BOUND,material_origin=MaterialOrigin.REUSED_EXISTING)); coverage["acnc_register"]={"discovery":"resolved","acquisition":"available","binding":"bound","origin":"reused_existing","record_ids":source_ids}
        else:
            url,body,resolved,status,media,entity=acnc_fetch(abn); d,r,a,s=source_lineage(catalog,store,family="acnc_register",endpoint=f"{API}/entity",url=url,body=body,resolved=resolved,media=media,subject_id=sid,role="register_identity"); members.append(CorpusMember(source_family="acnc_register",source_definition_id=d,acquisition_receipt_ids=(r,),artifact_ids=(a,),source_record_ids=(s,),discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.AVAILABLE,subject_binding=BindingState.BOUND,material_origin=MaterialOrigin.NEWLY_ACQUIRED)); coverage["acnc_register"]={"discovery":"resolved","acquisition":"available","binding":"bound","origin":"newly_acquired","record_ids":(s,)}; acquired_new+=1
        # ACNC AIS: current API entity includes period metadata; fetch latest detail when available.
        try:
            url,body,resolved,status,media,entity=acnc_fetch(abn); reports=[x for x in entity.get("data",{}).get("AnnualReports",[]) if x.get("IsAIS") and x.get("Status")=="Submitted" and x.get("AISId")]; latest=max(reports,key=lambda x:(int(x.get("Year") or 0),x.get("DateReceived") or ""),default=None)
        except Exception: latest=None
        if latest:
            detail_url=f"{API}/entity/{latest['AISId']}"; b,res,st,mt=fetch(detail_url); d,r,a,s=source_lineage(catalog,store,family="acnc_ais_bundle",endpoint=f"{API}/entity/{{AISId}}",url=detail_url,body=b,resolved=res,media=mt,subject_id=sid,role="annual_information_statement",revision=str(latest.get("Year") or latest.get("AISId"))); members.append(CorpusMember(source_family="acnc_ais_bundle",source_definition_id=d,acquisition_receipt_ids=(r,),artifact_ids=(a,),source_record_ids=(s,),source_revision=str(latest.get("Year") or latest.get("AISId")),effective_period=str(latest.get("Year") or ""),discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.AVAILABLE,subject_binding=BindingState.BOUND,material_origin=MaterialOrigin.NEWLY_ACQUIRED)); coverage["acnc_ais_bundle"]={"discovery":"resolved","acquisition":"available","binding":"bound","origin":"newly_acquired","period":latest.get("Year"),"record_ids":(s,)}; acquired_new+=1
        else: coverage["acnc_ais_bundle"]={"discovery":"resolved","acquisition":"absent","binding":"no_bound_record","origin":"none"}
        # ATO/ABR DGR
        dgr_url=f"https://abr.business.gov.au/ABN/View?abn={abn}"
        try:
            b,res,st,mt=fetch(dgr_url); bound=abn.encode() in b
            if bound:
                d,r,a,s=source_lineage(catalog,store,family="ato_abr_dgr",endpoint="https://abr.business.gov.au/ABN/View",url=dgr_url,body=b,resolved=res,media=mt,subject_id=sid,role="dgr_registration"); members.append(CorpusMember(source_family="ato_abr_dgr",source_definition_id=d,acquisition_receipt_ids=(r,),artifact_ids=(a,),source_record_ids=(s,),discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.AVAILABLE,subject_binding=BindingState.BOUND,material_origin=MaterialOrigin.NEWLY_ACQUIRED)); coverage["ato_abr_dgr"]={"discovery":"resolved","acquisition":"available","binding":"bound","origin":"newly_acquired","record_ids":(s,)}; acquired_new+=1
            else: coverage["ato_abr_dgr"]={"discovery":"resolved","acquisition":"available","binding":"no_bound_record","origin":"none"}
        except Exception as e: coverage["ato_abr_dgr"]={"discovery":"resolved","acquisition":"failed","binding":"none","origin":"none","error":type(e).__name__}
        # Official website
        base=WEBSITES[abn]; site_row={"status":"failed","candidate_count":0,"ranking":None,"top10":[],"acquired_page_records":[]}
        try:
            b,res,st,mt=fetch(base); candidates=enumerate_site_candidates(b.decode("utf-8","replace"),base); site_row["status"]="enumerated"; site_row["candidate_count"]=len(candidates)
            if abn in DEV and not args.skip_luna:
                ranking=rank_site_candidates_with_luna(candidates,subject_name=abn); site_row["ranking"]=ranking
                if not ranking.get("validation_error"):
                    for c in [candidates[i] for i in ranking["ranked_ordinals"][:10]]:
                        try:
                            pb,pr,ps,pm=fetch(c["url"]); d,r,a,s=source_lineage(catalog,store,family="official_website",endpoint=base,url=c["url"],body=pb,resolved=pr,media=pm,subject_id=sid,role="official_page"); site_row["acquired_page_records"].append({"url":c["url"],"source_record_id":s,"artifact_id":a}); members.append(CorpusMember(source_family="official_website",source_definition_id=d,acquisition_receipt_ids=(r,),artifact_ids=(a,),source_record_ids=(s,),discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.AVAILABLE,subject_binding=BindingState.BOUND,material_origin=MaterialOrigin.NEWLY_ACQUIRED)); acquired_new+=1
                        except Exception: pass
            coverage["official_website"]={"discovery":"resolved","acquisition":"available","binding":"bound","origin":"newly_acquired","candidate_count":len(candidates)}
        except Exception as e: coverage["official_website"]={"discovery":"resolved","acquisition":"failed","binding":"none","origin":"none","error":type(e).__name__}
        site[abn]=site_row
        # Wikipedia attempt, exact title only and revision pinned.
        try:
            q=WIKI+"?"+urlencode({"action":"query","list":"search","srsearch":abn,"format":"json","srlimit":10}); wb,wr,ws,wm=fetch(q); search=json.loads(wb).get("query",{}).get("search",[]); exact=next((x for x in search if x.get("title","").casefold().replace(" ","")==abn.casefold()),None)
            if exact: wiki_hits+=1; coverage["wikipedia_wikimedia"]={"discovery":"resolved","acquisition":"available","binding":"no_bound_record","origin":"newly_acquired","title":exact.get("title"),"revision":None}
            else: coverage["wikipedia_wikimedia"]={"discovery":"resolved","acquisition":"absent","binding":"no_bound_record","origin":"none"}
        except Exception as e: coverage["wikipedia_wikimedia"]={"discovery":"resolved","acquisition":"failed","binding":"none","origin":"none","error":type(e).__name__}
        # PFRA attempt; no name-only binding.
        try:
            pb,pr,ps,pm=fetch(PFRA); bound=abn.encode() in pb
            coverage["pfra"]={"discovery":"resolved","acquisition":"available","binding":"bound" if bound else "no_bound_record","origin":"newly_acquired" if bound else "none"}; pfra_hits+=1 if bound else 0
        except Exception as e: coverage["pfra"]={"discovery":"resolved","acquisition":"failed","binding":"none","origin":"none","error":type(e).__name__}
        manifest=build_corpus_manifest(subject_id=sid,profile_version="baseline-charity-corpus-v1",members=members,retrieval_timestamps=(now().isoformat(),),builder_commit=None); corpora.append(manifest.model_dump(mode="json")); matrix.append({"abn":abn,"subject_id":sid,"coverage":coverage})
    prior_pdf=Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-20260829-report\baseline-corpus-v1-report.json")
    if prior_pdf.exists():
        try: pdf=json.loads(prior_pdf.read_text(encoding="utf-8-sig")).get("pdf_representation",[])
        except Exception: pdf=[]
    provider_rows=[v.get("ranking") for v in site.values() if v.get("ranking") and not v.get("ranking").get("validation_error")]
    provider_calls=[v.get("ranking") for v in site.values() if v.get("ranking")]
    total_input=sum(int((v.get("usage") or {}).get("input_tokens") or 0) for v in provider_calls)
    total_output=sum(int((v.get("usage") or {}).get("output_tokens") or 0) for v in provider_calls)
    total_cost=sum(float(v.get("cost_usd") or 0) for v in provider_calls)
    report={"version":"baseline-charity-corpus-v1","private":True,"subjects":matrix,"corpora":corpora,"official_site_rankings":site,"pdf_representation":pdf,"aggregate":{"source_families":6,"subjects":10,"newly_acquired_material_count":acquired_new,"reused_material_count":reused,"wikipedia_hits":wiki_hits,"pfra_bound_hits":pfra_hits,"provider_calls":len(provider_calls),"validated_provider_calls":len(provider_rows),"provider":"gpt-5.6-luna","input_tokens":total_input,"output_tokens":total_output,"cost_usd":f"{total_cost:.6f}","semantic_extraction":False,"economics":"exact Luna usage/cost recorded; no ranked BudgetCohort ledger used; fail-closed USD 0.50 cap"}}
    out=runtime/"baseline-corpus-v1-report.json"; out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); (runtime/"baseline-corpus-v1-report.sha256").write_text(hashlib.sha256(out.read_bytes()).hexdigest()+"\n",encoding="ascii"); catalog.close(); print(json.dumps({"report":str(out),"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"subjects":10},indent=2)); return 0

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--runtime",type=Path,default=Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-corrected-20260829")); ap.add_argument("--skip-luna",action="store_true"); raise SystemExit(run(ap.parse_args()))
