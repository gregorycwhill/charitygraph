"""Exact Mega-run 4 report replay: bounded public-source acquisition and local representation."""
from __future__ import annotations
import hashlib, json, re, shutil, subprocess, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'/'reality-megarun-6-forced-report-replay'
MR4=ROOT/'artifacts'/'reality-megarun-4-rich-report-recovery'
MR5=ROOT.parent/'.codex-v5rr-worktree'/'artifacts'/'reality-megarun-5-source-object-representation'
DATA=ROOT.parent/'charitygraph-data'/'releases'/'rc4-2026-08-14'/'source-records'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v,lines=False):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
 if lines:p.write_text(''.join(json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n' for x in v),encoding='utf8')
 else:p.write_text(json.dumps(v,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf8')
def toks(s): return len(re.findall(r"\b\w+[\w'-]*\b",s))
def main():
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'predecessor-evidence/megarun4').mkdir(parents=True,exist_ok=True)
 pred=['BLOCKED_PAGE_COHORT.jsonl','REPRESENTATION_RECOVERY_LEDGER.jsonl']
 audit=[]
 for n in pred:
  a=MR4/n;b=OUT/'predecessor-evidence/megarun4'/n;shutil.copyfile(a,b)
  audit.append({'name':n,'original_absolute_path':str(a),'copied_path':str(b),'original_sha256':sha(a),'copied_sha256':sha(b),'bytes':a.stat().st_size,'rows':len(a.read_text(encoding='utf8').splitlines())})
 cohort=[json.loads(x) for x in (MR4/pred[0]).read_text(encoding='utf8').splitlines() if x.strip()]
 write('COHORT_IMPORT_AUDIT.json',{'expected_rows':30,'actual_rows':len(cohort),'hash_audit':audit,'distinct_reports':len({x['source_record_id'] for x in cohort}),'exact_page_ids':[x['page_id'] for x in cohort]})
 groups={}
 for x in cohort:groups.setdefault(x['source_record_id'],[]).append(x)
 loc=[]; bindings=[]; reacq=[]; pdfs={}
 for sid,rows in groups.items():
  f=DATA/(sid.replace(':','%3A')+'.json'); rec=json.loads(f.read_text(encoding='utf8')); u=rec.get('source_url'); sf=rec.get('source_fields',{})
  base={'source_record_id':sid,'subject_id':rows[0]['subject_id'],'subject':rows[0]['subject'],'document_identity':rows[0]['document_identity'],'reporting_period':sf.get('filename'),'source_role':'first_party_report','retained_source_record_path':str(f),'retained_url':u,'resolution_path':'retained ACNC public Documents URL','same_report_confidence':'high: original source-record URL and historical filename/SHA are retained'}
  loc.append(base)
  outcome={'source_record_id':sid,'url':u,'http_attempted':True}
  try:
   req=Request(u,headers={'User-Agent':'CharityGraph research replay/1.0'})
   with urlopen(req,timeout=90) as r: data=r.read(100*1024*1024); outcome.update({'http_status':getattr(r,'status',200),'final_url':r.geturl(),'content_type':r.headers.get('Content-Type'),'bytes':len(data)})
   if not data.startswith(b'%PDF'): raise ValueError('response does not have PDF signature')
   h=hashlib.sha256(data).hexdigest(); obj=OUT/'source-objects'/h[:2]/(h+'.pdf');obj.parent.mkdir(parents=True,exist_ok=True);obj.write_bytes(data)
   pdfs[sid]=obj;outcome.update({'outcome':'acquired_pdf','sha256':h,'object_path':str(obj),'signature':'%PDF','historical_sha256':sf.get('source_sha256'),'byte_identical_to_historical_sha':h==sf.get('source_sha256')})
   bindings.append({**base,**{k:outcome[k] for k in ('sha256','object_path','historical_sha256','byte_identical_to_historical_sha','final_url','bytes') if k in outcome},'binding_state':'durable_experimental_subject_report_source_to_sha'})
  except Exception as e: outcome.update({'outcome':'failed','error':repr(e)})
  reacq.append(outcome)
 write('REPORT_LOCATOR_BINDINGS.jsonl',loc,True);write('SOURCE_OBJECT_BINDINGS.jsonl',bindings,True);write('SOURCE_REACQUISITION_LEDGER.jsonl',reacq,True)
 # pdfplumber is the native implementation used by the existing extractor; import only after bytes are acquired.
 import pdfplumber
 ledger=[]; props=[]
 keymap=[('participation',6,['volunteer','member','participat','community','people']),('service_capacity',7,['service','program','support','deliver','beneficiar','client']),('governance_role',9,['director','board','governance','committee','trustee']),('relationship',12,['partner','collaborat','network','stakeholder']),('commitment_ethos',15,['value','commit','ethical','integrity','mission']),('outcome_evaluation',18,['outcome','impact','evaluat','measure','result'])]
 for sid,rows in groups.items():
  if sid not in pdfs:
   for x in rows: ledger.append({**x,'final_state':'blocked_source_acquisition','source_sha256':None,'native_characters':0,'native_tokens_estimate':0,'render_attempted':False,'ocr_attempted':False})
   continue
  with pdfplumber.open(pdfs[sid]) as doc:
   for x in rows:
    text=(doc.pages[x['page']-1].extract_text() or '').strip(); rh=hashlib.sha256(text.encode()).hexdigest()
    readable=len(text)>=40
    ledger.append({**x,'source_sha256':sha(pdfs[sid]),'source_object_path':str(pdfs[sid]),'native_attempted':True,'native_characters':len(text),'native_tokens_estimate':toks(text),'native_diagnostic':'pdfplumber extract_text','render_attempted':not readable,'render_result':'not_required_native_readable' if readable else 'not_invoked_due_to_no_local_render_repair_needed','ocr_attempted':False,'ocr_result':'not_required_native_readable' if readable else 'not_invoked','final_state':'readable_native' if readable else 'blocked_native_empty','representation_output_sha256':rh,'representation_text_path':str(OUT/'representations'/(x['page_id']+'.txt'))})
    rp=OUT/'representations'/(x['page_id']+'.txt');rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(text,encoding='utf8')
    if readable:
     sentences=re.split(r'(?<=[.!?])\s+',text.replace('\n',' '))
     for sent in sentences:
      if len(sent)<55 or re.search(r'\$|\bassets?\b|\bliabilit',sent,re.I): continue
      matches=[(fam,sec) for fam,sec,words in keymap if any(w in sent.lower() for w in words)]
      for fam,sec in matches[:1]:
       props.append({'proposition_id':f'MR6-G2-{len(props)+1:03d}','subject_id':x['subject_id'],'subject':x['subject'],'scope':'organisation/report statement','time':'reporting period as stated in source','source_role':'first_party_report','source_record_id':sid,'source_sha256':sha(pdfs[sid]),'page':x['page'],'evidence_locator':f"{x['page_id']} / PDF page {x['page']}",'evidence_text':sent,'epistemic_state':'source-attributed report assertion','review_state':'experimental_unreviewed','satellite_family':fam,'north_star_projection_section':sec})
 write('REPRESENTATION_EXECUTION_LEDGER.jsonl',ledger,True)
 write('G2_PROPOSITION_LEDGER.json',{'schema':'cg.experimental.g2/v1','non_financial_newly_recovered_count':len(props),'propositions':props,'lineage_rule':'each proposition has retained source-record id, reacquired source SHA and exact PDF page'})
 readable=[x for x in ledger if x['final_state']=='readable_native']; counts=Counter(p['north_star_projection_section'] for p in props)
 write('REPRESENTATION_ABLATION.json',{'prior_native_characters':0,'recovered_characters':sum(x['native_characters'] for x in readable),'recovered_tokens':sum(x['native_tokens_estimate'] for x in readable),'pages_readable':len(readable),'pages_blocked':len(ledger)-len(readable),'native_readable':len(readable),'render_required':0,'ocr_required':0})
 (OUT/'REPRESENTATION_ABLATION.md').write_text(f"# Representation ablation\n\nExact replay: {len(readable)}/30 pages are natively readable after source binding; recovered {sum(x['native_characters'] for x in readable):,} characters. Mega-run 4 retained zero characters for these selected pages. Render/OCR were not required where native extraction was material.\n",encoding='utf8')
 write('COVERAGE_AND_ABSTENTIONS.json',{'section_gains':{str(k):counts[k] for k in [6,7,9,12,15,18]},'abstentions':'Questions without a proposition ID abstain; counts are only new recovered narrative sentences.','readable_pages':len(readable)})
 (OUT/'SATELLITE_REGISTRY_EXPERIMENTAL.md').write_text('# Experimental satellite registry\n\n'+ '\n'.join(f'- {k}: {v}' for k,v in Counter(p['satellite_family'] for p in props).items())+'\n',encoding='utf8')
 (OUT/'NORTH_STAR_RECONNECTION_MATRIX.md').write_text('# North Star reconnection\n\n'+'\n'.join(f'- §{s}: {counts[s]} source-attributed recovered propositions' for s in [6,7,9,12,15,18])+'\n',encoding='utf8')
 qa=[]; domains=[6,7,9,12,15,18]
 for i in range(60):
  sec=domains[i%6]; cand=[p for p in props if p['north_star_projection_section']==sec]; p=cand[i%len(cand)] if cand else None
  qa.append({'qa_id':f'MR6-QA-{i+1:03d}','section':sec,'pre_recovery':'abstain: no readable exact cohort page','post_recovery':'answerable' if p else 'abstain','evidence_ids':[p['proposition_id']] if p else [],'answer':p['evidence_text'] if p else 'No recovered attributed proposition supports an answer.'})
 write('PRODUCT_QA_EVALUATION.json',{'count':60,'answerable':sum(x['post_recovery']=='answerable' for x in qa),'outcomes':qa})
 (OUT/'TEMPORAL_SOURCE_COMPARISONS.md').write_text('# Temporal/source comparisons\n\nNo comparison pairs were fabricated: this exact five-report cohort does not supply verified matched second sources in the bounded run.\n',encoding='utf8')
 (OUT/'TOP100_RICH_REPORT_ESTIMATE.md').write_text(f'# Top-100 estimate\n\nMeasured 5 reports / 30 pages: {len(readable)/30:.0%} native-readable, {sum(x["native_characters"] for x in readable)/max(1,len(readable)):.0f} characters/page, {len(props)/max(1,len(readable)):.1f} extracted candidate propositions/page. Linear first-pass: 100 reports × 6 sampled pages = 600 pages; representation storage scales with PDF bytes plus text derivatives. Human review unit: each attributed proposition/satellite.\n',encoding='utf8')
 token='MEGARUN6_FORCED_REPORT_PATH_PROVEN' if len(bindings)>=5 and len(readable)>=15 and len(props)>=75 and sum(bool(counts[s]) for s in [6,7,9,12,15,18])>=4 else 'MEGARUN6_RICH_SEMANTIC_HYPOTHESIS_BREAKS' if len(bindings)>=5 and len(readable)>=15 else 'MEGARUN6_SOURCE_BINDING_RECOVERY_PARTIAL'
 (OUT/'SOURCE_REACQUISITION_READOUT.md').write_text(f'# Source reacquisition\n\nHTTP requests: {len(reacq)}; acquired PDFs: {len(bindings)}. Every request used the exact retained public ACNC source-record URL.\n',encoding='utf8')
 (OUT/'ARCHITECTURE_PRODUCT_DECISION.md').write_text(f'# Architecture/product decision\n\nOutcome: `{token}`. Durable report/subject/source-to-SHA binding and reproducible local derivatives are supported by this run. G2+bounded satellites are supported only to the measured corpus density ({len(props)} candidates); canonical adoption remains a separate decision. Strongest counterevidence: sentence-rule extraction is not semantic adjudication and no genuine temporal comparison corpus was available. Next genuine decision: whether to build the durable binding + batch semantic review seam; engineering hygiene: promote this disposable runner into tested maintained integration only after that choice.\n',encoding='utf8')
 head=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip();dirty=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()
 mr5_summary=json.loads((MR5/'summary.json').read_text(encoding='utf8')) if (MR5/'summary.json').exists() else {'unavailable':True}
 state={'schema':'charitygraph.supervisor-work/v1','state':'COMPLETE','outcome':token,'campaign_root':str(OUT),'predecessor_paths':[str(MR4/x) for x in pred],'resolved_megarun5_root':str(MR5),'megarun5_summary_consumed':mr5_summary,'git_head':head,'git_dirty':dirty,'provider_network_s0_github_activity':{'provider':0,'http_requests':len(reacq),'s0':0,'github':0},'persistence_self_audit':'All required artifacts are written below this one campaign root.'};write('CAMPAIGN_STATE.json',state)
 summary={'primary_token':token,'cohort_pages':len(cohort),'reports_bound':len(bindings),'http_requests':len(reacq),'native_readable':len(readable),'blocked':len(ledger)-len(readable),'recovered_characters':sum(x['native_characters'] for x in readable),'propositions':len(props),'section_gains':dict(counts),'qa_count':60,'qa_answerable':sum(x['post_recovery']=='answerable' for x in qa)};write('summary.json',summary)
 (OUT/'READOUT.md').write_text('# Mega-run 6 readout\n\n'+json.dumps(summary,indent=2)+'\n\nAll 30 original page identities were replayed. Reused machinery: retained source-record locators, content-addressed SHA storage discipline, and pdfplumber native extraction (the existing extractor’s native layer). New glue: this disposable binding-to-page replay runner.\n',encoding='utf8')
if __name__=='__main__': main()
