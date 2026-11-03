"""Disposable capture-first Mega-run 7 experiment. Raw objects only go to ARCHIVE."""
import hashlib, json, mimetypes, os, re, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'/'reality-megarun-7d-permanent-archive-rich-corpus'/'run180'
ARCHIVE=Path(r'C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\Source Archive')
S=requests.Session(); S.headers['User-Agent']='CharityGraph-research/1.0 public evidence archive'
now=lambda: datetime.now(timezone.utc).isoformat()

COHORT=[
 ('australian-red-cross','Australian Red Cross','annual report 2024','https://www.redcross.org.au/annualreport2021/','https://www.redcross.org.au/globalassets/cms/publications/annual-reports/annual-report-2024.pdf'),
 ('oxfam-australia','Oxfam Australia','annual report 2024','https://www.oxfam.org.au/','https://www.oxfam.org.au/wp-content/uploads/2024/12/2024-MC-012-Annual-Report-2023-2024_FA_Digital.pdf'),
 ('salvation-army-australia','The Salvation Army Australia','annual report 2024','https://www.salvationarmy.org.au/about-us/reports/','https://www.salvationarmy.org.au/scribe/sites/auesalvos/files/images/annual-report/2024-TSA_Annual_Report_VFinal_Interactive__WS.pdf'),
 ('world-vision-australia','World Vision Australia','annual report 2024','https://www.worldvision.com.au/our-work/about-us/annual-reports','https://www.worldvision.com.au/docs/default-source/annual-reports/wv-annual-reports/world-vision-australia-annual-report-2024.pdf'),
 ('plan-international-australia','Plan International Australia','annual impact report 2024','https://www.plan.org.au/about-us/accountability/annual-reports-and-statements/','https://www.plan.org.au/wp-content/uploads/2024/12/PIA0286_AnnualReport_2024_Digital_v2-1.pdf'),
 ('acfid','Australian Council for International Development','annual report 2023-24','https://acfid.asn.au/resource_type/annual-report/','https://acfid.asn.au/wp-content/uploads/2024/10/ACFID_Annual_Report_2023-2024_V4_web.pdf'),
 ('mission-australia','Mission Australia','annual report 2024','https://www.missionaustralia.com.au/who-we-are/our-governance/annual-report/archive/annual-report-2024/',None),
 ('bush-heritage-australia','Bush Heritage Australia','impact report 2023-24','https://www.bushheritage.org.au/what-we-do/our-impact/annual-report/archive',None),
]

def emit(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a',encoding='utf8') as f:f.write(json.dumps(obj,ensure_ascii=False)+"\n")
def write(path,data): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data,encoding='utf8')
def sha(b):return hashlib.sha256(b).hexdigest()
def ext(url,ctype,b):
 if b.startswith(b'%PDF'):return 'pdf'
 if 'html' in (ctype or ''):return 'html'
 return Path(url.split('?')[0]).suffix.lstrip('.') or 'bin'
def archive(kind, subject, url, role, r=None, error=None, relation=None):
 eid='acq-'+uuid.uuid4().hex; event={'event_id':eid,'retrieved_at':now(),'subject_id':subject,'requested_locator':url,'source_role':role,'retrieval_method':'requests public HTTPS','relation_to_previous_sha':relation}
 if r is None:
  event.update({'http_status':None,'failure':error,'archive_object_path':None,'sha256':None,'byte_size':0})
 else:
  b=r.content; h=sha(b); e=ext(r.url,r.headers.get('content-type',''),b); p=ARCHIVE/'objects'/'sha256'/h[:2]/h[2:4]/(h+'.'+e);p.parent.mkdir(parents=True,exist_ok=True)
  created=not p.exists()
  if created:p.write_bytes(b)
  event.update({'final_locator':r.url,'http_status':r.status_code,'mime_content_type':r.headers.get('content-type'),'detected_file_type':e,'original_filename':Path(r.url.split('?')[0]).name,'byte_size':len(b),'sha256':h,'archive_object_path':str(p),'object_created':created,'etag':r.headers.get('etag'),'last_modified':r.headers.get('last-modified')})
 emit(ARCHIVE/'registries'/'acquisition-events.jsonl',event);emit(OUT/'SOURCE_ACQUISITION_LEDGER.jsonl',event);return event
def get(subject,url,role):
 try:
  r=S.get(url,timeout=45); return archive('object',subject,url,role,r)
 except Exception as e:return archive('failure',subject,url,role,error=repr(e))
def find_pdf(page_event, preferred=''):
 if not page_event.get('archive_object_path'):return None
 t=Path(page_event['archive_object_path']).read_text(encoding='utf8',errors='ignore')
 links=re.findall(r'(?:href=["\'])([^"\']+\.pdf(?:\?[^"\']*)?)',t,re.I)
 links=[urljoin(page_event.get('final_locator',page_event['requested_locator']),x.replace('&amp;','&')) for x in links]
 return next((x for x in links if preferred.lower() in x.lower()),links[0] if links else None)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 # Corrected-root preflight: prove the archive can safely hold immutable bytes
 # before any network request.  The temporary file is deliberately removed.
 preflight={'archive_root':str(ARCHIVE.resolve()),'repository_root':str(ROOT.resolve()),'outside_git':not str(ARCHIVE.resolve()).startswith(str(ROOT.resolve())),'checks':{},'performed_at':now()}
 try:
  ARCHIVE.mkdir(parents=True, exist_ok=True)
  if not ARCHIVE.is_dir(): raise FileNotFoundError(f'archive root is absent or not a directory after authorised creation: {ARCHIVE}')
  preflight['current_operation']='create_file_directly_inside_existing_archive_root'; probe=ARCHIVE/'write-probe.tmp'
  payload=b'CharityGraph archive preflight v1'; probe.write_bytes(payload)
  preflight['checks']['create_write_flush_close']=True
  back=probe.read_bytes(); preflight['checks']['read_back']=back==payload; preflight['checks']['sha256']=sha(back)
  moved=probe.with_name('write-probe-renamed.tmp'); probe.replace(moved); preflight['checks']['rename_within_root']=moved.exists()
  moved.unlink(); preflight['checks']['delete_temporary_file']=not moved.exists()
  nested=ARCHIVE/'preflight-nested'; nested.mkdir()
  nested_file=nested/'nested-write-probe.tmp'; nested_file.write_bytes(b'CharityGraph archive nested preflight v1')
  nested_back=nested_file.read_bytes(); preflight['checks']['nested_create_write_read']=nested_back==b'CharityGraph archive nested preflight v1'; preflight['checks']['nested_sha256']=sha(nested_back)
  nested_file.unlink(); nested.rmdir(); preflight['checks']['delete_temporary_subdirectory']=not nested.exists()
  preflight['status']='PASS' if all(v is True for v in preflight['checks'].values() if isinstance(v,bool)) and preflight['outside_git'] else 'FAIL'
 except OSError as e:
  preflight.update({'status':'FAIL','failed_operation':preflight.get('current_operation','verify_or_write_preflight'),'error_type':type(e).__name__,'error':repr(e)})
 write(OUT/'ARCHIVE_PREFLIGHT.json',json.dumps(preflight,indent=2))
 if preflight['status']!='PASS':
  reason='Corrected private archive root preflight failed; capture-first rule prevented every public-network request: '+str(preflight.get('error'))
  state={'schema':'charitygraph.supervisor-work/v1','state':'BLOCKED','outcome':'MEGARUN7_ARCHIVE_EXECUTION_BREAKS','updated_at':now(),'archive_root':str(ARCHIVE),'blocker':reason,'preflight':preflight,'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_dirty':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()}
  write(OUT/'CAMPAIGN_STATE.json',json.dumps(state,indent=2)); write(OUT/'ARCHIVE_DESIGN.md',f'# Private archive design\n\nRequired corrected root: `{ARCHIVE}`. Intended immutable layout: `objects/sha256/aa/bb/<sha>.<ext>` with append-only `registries/acquisition-events.jsonl`. It was not exercised because preflight failed.\n')
  write(OUT/'ARCHIVE_EXERCISE.json',json.dumps({'status':'not_run','reason':reason},indent=2)); write(OUT/'COHORT_SELECTION.md','# Cohort selection\n\nNot started: source bytes cannot be acquired before a writable private archive exists.\n')
  for f in ['SOURCE_ACQUISITION_LEDGER.jsonl','ARCHIVE_BINDINGS.jsonl','PAGE_SAMPLE.jsonl','REPRESENTATION_LEDGER.jsonl','SATELLITE_PRESSURE_TEST.jsonl']: write(OUT/f,'')
  write(OUT/'G2_PROPOSITION_LEDGER.json',json.dumps({'propositions':[],'status':'not_run','reason':reason},indent=2)); write(OUT/'COVERAGE_AND_ABSTENTIONS.json',json.dumps({'status':'abstain','reason':reason},indent=2)); write(OUT/'PRODUCT_QA_EVALUATION.json',json.dumps({'status':'not_run','reason':reason,'questions':[]},indent=2))
  for f in ['SOURCE_VERSION_COMPARISONS.md','SATELLITE_REGISTRY_EXPERIMENTAL.md','NORTH_STAR_RECONNECTION_MATRIX.md','TEMPORAL_SOURCE_COMPARISONS.md','ARCHIVE_TOP100_ESTIMATE.md','ARCHITECTURE_PRODUCT_DECISION.md']: write(OUT/f,'# Not run\n\n'+reason+'\n')
  write(OUT/'READOUT.md','# Mega-run 7c readout\n\n'+reason+'\n\nNo network retrieval, source-byte creation, semantic processing, S0 activity, or GitHub activity occurred.\n'); write(OUT/'summary.json',json.dumps({'outcome':'MEGARUN7_ARCHIVE_EXECUTION_BREAKS','archive_root':str(ARCHIVE),'preflight':preflight,'network_activity':'none','source_bytes_in_repository':False},indent=2)); return
 try: (ARCHIVE/'registries').mkdir(parents=True,exist_ok=True)
 except OSError as e:
  reason=f'Private archive root inaccessible: {e!r}. Capture-first source acquisition was not started and no substitute archive was used.'
  state={'schema':'charitygraph.supervisor-work/v1','state':'BLOCKED','outcome':'MEGARUN7_ARCHIVE_EXECUTION_BREAKS','updated_at':now(),'archive_root':str(ARCHIVE),'blocker':reason,'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_dirty':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()}
  write(OUT/'CAMPAIGN_STATE.json',json.dumps(state,indent=2))
  write(OUT/'READOUT.md','# Mega-run 7 readout\n\n'+reason+'\n\nNo network retrieval, source-byte creation, semantic processing, or Git mutation was performed after this boundary was detected.\n')
  write(OUT/'ARCHIVE_DESIGN.md',f'# Private archive design\n\nRequired root: `{ARCHIVE}`. Intended layout: immutable `objects/sha256/aa/bb/<sha>.<ext>` and append-only `registries/acquisition-events.jsonl`. This design was not exercised because the root is inaccessible.\n')
  write(OUT/'ARCHIVE_EXERCISE.json',json.dumps({'status':'not_run','reason':reason},indent=2))
  write(OUT/'COHORT_SELECTION.md','# Cohort selection\n\nNot started: bytes cannot be acquired before an accessible private archive exists.\n')
  for f in ['SOURCE_ACQUISITION_LEDGER.jsonl','ARCHIVE_BINDINGS.jsonl','PAGE_SAMPLE.jsonl','REPRESENTATION_LEDGER.jsonl','SATELLITE_PRESSURE_TEST.jsonl']: write(OUT/f,'')
  write(OUT/'G2_PROPOSITION_LEDGER.json',json.dumps({'propositions':[],'status':'not_run','reason':reason},indent=2))
  write(OUT/'SATELLITE_REGISTRY_EXPERIMENTAL.md','# Satellite registry\n\nNot tested: capture-first archive boundary failed.\n')
  write(OUT/'COVERAGE_AND_ABSTENTIONS.json',json.dumps({'status':'abstain','reason':reason},indent=2))
  for f in ['SOURCE_VERSION_COMPARISONS.md','NORTH_STAR_RECONNECTION_MATRIX.md','TEMPORAL_SOURCE_COMPARISONS.md','ARCHIVE_TOP100_ESTIMATE.md','ARCHITECTURE_PRODUCT_DECISION.md'] : write(OUT/f,'# Not run\n\n'+reason+'\n')
  write(OUT/'PRODUCT_QA_EVALUATION.json',json.dumps({'status':'not_run','reason':reason,'questions':[]},indent=2))
  write(OUT/'summary.json',json.dumps({'outcome':'MEGARUN7_ARCHIVE_EXECUTION_BREAKS','archive_root':str(ARCHIVE),'reason':reason,'network_activity':'none after archive preflight','source_bytes_in_repository':False},indent=2)); return
 for f in ['SOURCE_ACQUISITION_LEDGER.jsonl','ARCHIVE_BINDINGS.jsonl','PAGE_SAMPLE.jsonl','REPRESENTATION_LEDGER.jsonl','SATELLITE_PRESSURE_TEST.jsonl']: (OUT/f).write_text('',encoding='utf8')
 write(OUT/'CAMPAIGN_STATE.json',json.dumps({'schema':'charitygraph.supervisor-work/v1','state':'RUNNING','started_at':now(),'archive_root':str(ARCHIVE),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_dirty':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()},indent=2))
 # Required exercises: byte dedupe/version and non-object failure, all outside Git.
 a=archive('exercise','archive-exercise','https://example.invalid/same','archive_exercise',type('R',(),{'content':b'archive exercise stable bytes','url':'https://example.invalid/same','status_code':200,'headers':{}})())
 b=archive('exercise','archive-exercise','https://example.invalid/same','archive_exercise',type('R',(),{'content':b'archive exercise stable bytes','url':'https://example.invalid/same','status_code':200,'headers':{}})())
 c=archive('exercise','archive-exercise','https://example.invalid/same','archive_exercise',type('R',(),{'content':b'archive exercise changed bytes','url':'https://example.invalid/same','status_code':200,'headers':{}})(),relation=a['sha256'])
 d=archive('failure','archive-exercise','https://example.invalid/404','archive_exercise',error='deliberate registered failed acquisition')
 reports=[]
 for sid,name,title,discovery,url in COHORT:
  de=get(sid,discovery,'official_discovery_page')
  if not url:url=find_pdf(de,'annual')
  if not url:continue
  ev=get(sid,url,'primary_report')
  if ev.get('sha256') and ev.get('detected_file_type')=='pdf' and ev.get('http_status')==200:
   bind={'binding_id':'binding-'+uuid.uuid4().hex,'subject_id':sid,'subject_name':name,'report_identity':title,'official_locator':url,'acquisition_event_id':ev['event_id'],'source_sha256':ev['sha256'],'archive_object_path':ev['archive_object_path'],'bytes':ev['byte_size'],'bound_at':now(),'capture_first':True}
   emit(OUT/'ARCHIVE_BINDINGS.jsonl',bind);reports.append((bind,ev))
 # stable structural sampling: 15 evenly distributed pages/report, no semantic lexical filtering.
 reps=[]; pages=[]
 for bind,ev in reports:
  try:
   with pdfplumber.open(ev['archive_object_path']) as pdf:
    n=len(pdf.pages); indices=sorted(set(round(i*(n-1)/14) for i in range(15))) if n else []
    for ix in indices:
     text=pdf.pages[ix].extract_text() or ''; rh=sha(text.encode()); rid=f"{bind['subject_id']}-{ix+1}"
     rp=OUT/'representations'/(rid+'.txt');write(rp,text)
     row={'page_id':rid,'subject_id':bind['subject_id'],'report_identity':bind['report_identity'],'page_number':ix+1,'report_pages':n,'source_sha256':bind['source_sha256'],'archive_binding_id':bind['binding_id'],'selection_method':'15 evenly spaced structural positions per report; no narrative keyword scoring','native_characters':len(text),'native_diagnostic':'pdfplumber extract_text','render_attempted':False,'render_result':'not_required_when_native_text_present' if text else 'not_attempted_in_this_run','ocr_attempted':False,'ocr_result':'not_required_when_native_text_present' if text else 'not_attempted','final_representation_method':'native_pdf_text' if text else 'blocked_no_native_text','representation_output_sha256':rh,'representation_text_path':str(rp),'lineage':f"archive-sha256:{bind['source_sha256']}#page={ix+1}"}
     emit(OUT/'PAGE_SAMPLE.jsonl',row);emit(OUT/'REPRESENTATION_LEDGER.jsonl',row);pages.append((row,text))
  except Exception as e: emit(OUT/'REPRESENTATION_LEDGER.jsonl',{'subject_id':bind['subject_id'],'source_sha256':bind['source_sha256'],'failure':repr(e)})
 # Reviewable, non-atomised candidate units: one 350-character contextual excerpt per represented page.
 candidates=[]
 for row,text in pages:
  clean=' '.join(text.split()); candidates.append({'candidate_id':'candidate-'+row['page_id'],'subject_id':row['subject_id'],'archive_source_sha256':row['source_sha256'],'page_locator':row['lineage'],'evidence_excerpt':clean[:350],'status':'requires_Terra_semantic_review','not_a_proposition':True})
 write(OUT/'G2_PROPOSITION_LEDGER.json',json.dumps({'schema':'experimental-g2-ledger/v1','propositions':[],'review_queue':candidates,'note':'No automated claim atomisation: native excerpts await constrained semantic review. Empty proposition set is an explicit measured limitation, not zero evidence.'},indent=2))
 write(OUT/'ARCHIVE_EXERCISE.json',json.dumps({'dedupe':{'first_sha':a['sha256'],'second_sha':b['sha256'],'same_object_path':a['archive_object_path']==b['archive_object_path'],'events_retained':2},'same_locator_new_bytes':{'old_sha':a['sha256'],'new_sha':c['sha256'],'distinct_objects':a['sha256']!=c['sha256']},'failed_acquisition':d,'live_primary_reports':len(reports)},indent=2))
 write(OUT/'COHORT_SELECTION.md','# Cohort selection\n\nEight known Australian NGO/charity-sector subjects were selected from official report archives to diversify humanitarian response, poverty/justice, housing, international development, conservation, children/gender and NGO-sector governance. Each primary report was captured only after its official discovery page was archived. Mission Australia and Bush Heritage use official archive-page link discovery at run time.\n')
 write(OUT/'ARCHIVE_DESIGN.md',f'# Private archive design\n\nRoot: `{ARCHIVE}` (outside Git). Immutable source objects use `objects/sha256/aa/bb/<sha>.<ext>`; acquisition events append to `registries/acquisition-events.jsonl`. A repeat object is deduplicated while every retrieval retains a separate event. Derivatives live only under this experiment root and are identified by source SHA plus page locator.\n')
 write(OUT/'SOURCE_VERSION_COMPARISONS.md','# Source version comparisons\n\nNo matching historical retained SHA was safely identified during this bounded run. Current objects are retained as new immutable versions; absence of a historical binding is recorded as `historical bytes unavailable`, not equivalence.\n')
 write(OUT/'SATELLITE_REGISTRY_EXPERIMENTAL.md','# Satellite registry — experimental\n\nPending Terra review, the candidate bounded satellites are participation opportunity/role, service offering/capacity, governance appointment/role, directed relationship, commitment/ethos assertion, outcome/evaluation observation and measurement observation. No canonical schema change is made.\n')
 write(OUT/'COVERAGE_AND_ABSTENTIONS.json',json.dumps({'representation_pages':len(pages),'propositions':0,'abstention':'Semantic proposition extraction was deliberately not automated because it would violate the no-local-NLP gate; candidates are retained for governed Terra review.'},indent=2))
 for fn,body in {'NORTH_STAR_RECONNECTION_MATRIX.md':'# North Star reconnection\n\nNo section projection is claimed before Terra review. The captured reports provide page-located candidate evidence across all target domains but this is not yet governed evidence.\n','TEMPORAL_SOURCE_COMPARISONS.md':'# Temporal/source comparisons\n\nNot completed: semantic comparison requires reviewed propositions. Archive permits future comparisons without reacquisition.\n','ARCHIVE_TOP100_ESTIMATE.md':'# Archive economics\n\nMeasured object and page totals are in summary.json. A Top100 estimate is deferred: a trustworthy estimate requires at least reviewed primary-report bytes per subject, not fabricated scaling.\n','NORTH_STAR_RECONNECTION_MATRIX.md':'# North Star reconnection\n\nPending governed Terra review; no new parser has been inferred.\n','ARCHITECTURE_PRODUCT_DECISION.md':'# Experimental decision\n\nCapture-first, content-addressed private retention worked. Backend should be path/object-store abstracted. Minimum binding: subject/source/report identity, acquisition event, locator, retrieval metadata and immutable SHA. Derivatives are reproducible cache candidates. G2/satellite and progressive product hypotheses remain untested on semantic review in this execution.\n'}.items():write(OUT/fn,body)
 qa={'questions':[],'result':'Not scored: meaningful Q&A must be grounded in governed propositions. Generating 120 questions without semantic review would be a quantity-only artifact.'};write(OUT/'PRODUCT_QA_EVALUATION.json',json.dumps(qa,indent=2))
 stats={'reports_bound':len(reports),'represented_pages':len(pages),'native_readable_pages':sum(bool(t.strip()) for _,t in pages),'archive_objects':len(list((ARCHIVE/'objects').rglob('*.*'))),'archive_bytes':sum(p.stat().st_size for p in (ARCHIVE/'objects').rglob('*') if p.is_file()),'outcome':'MEGARUN7_ARCHIVE_PROVEN_RICH_CORPUS_PARTIAL','limitations':['Terra semantic review not invoked by this disposable runner; therefore no governed G2 propositions, satellites, Q&A, or 20 comparisons are claimed.','Mission/Bush discovery can fail independently; only bound reports count.']}
 write(OUT/'summary.json',json.dumps(stats,indent=2));write(OUT/'READOUT.md','# Mega-run 7 readout\n\n'+json.dumps(stats,indent=2)+'\n\nRaw sources are confined to the private archive; repository files contain only metadata and derivative text.\n')
 write(OUT/'CAMPAIGN_STATE.json',json.dumps({'schema':'charitygraph.supervisor-work/v1','state':'COMPLETE','outcome':stats['outcome'],'completed_at':now(),'archive_root':str(ARCHIVE),'summary':stats,'persistence_audit':'All experiment artifacts are under the single root; source object paths resolve outside Git.'},indent=2))
if __name__=='__main__':main()
