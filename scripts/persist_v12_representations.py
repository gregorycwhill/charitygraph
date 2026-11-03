"""Persist V12 readable representations once; semantic runners consume these files."""
from __future__ import annotations
import hashlib,json,concurrent.futures
from pathlib import Path
import sys; sys.path.insert(0,"src")
from charitygraph.document_representation import represent_document
ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12")
def one(item):
 row,a=item; p=Path(a["raw_path"]); raw=p.read_bytes(); rep=represent_document(raw,content_type=a.get("content_type")); return row,a,rep,hashlib.sha256(raw).hexdigest()
def main():
 pre=json.loads((ROOT/'acquisition-preflight.json').read_text(encoding='utf-8')); out=[]; failures=[]; reps=ROOT/'representations'; reps.mkdir(exist_ok=True)
 items=[]
 for row in pre['rows']:
  if 'regulator' in row['target']: continue
  for a in row.get('artifacts',[]):
   if a.get('raw_path'): items.append((row,a))
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  fs={pool.submit(one,x):x for x in items}
  for f,x in fs.items():
   try:
    row,a,rep,sha=f.result(timeout=30)
    if not rep.complete: failures.append({'target':row['target'],'raw_path':a['raw_path'],'reason':rep.gap}); continue
    ident=hashlib.sha256((sha+rep.representation_sha256).encode()).hexdigest(); path=reps/(ident+'.json'); path.write_text(json.dumps({'target':row['target'],'publisher':row['publisher'],'source_relation':row['source_relation'],'material_role':row['material_role'],'original_url':row['requested_url'],'final_url':a.get('url') or row.get('final_url'),'raw_path':a['raw_path'],'raw_sha256':sha,'representation_sha256':rep.representation_sha256,'method':rep.method,'material_type':rep.material_type,'complete':rep.complete,'units':list(rep.units),'text':rep.text},ensure_ascii=False),encoding='utf-8'); out.append({'target':row['target'],'representation_path':str(path),'raw_sha256':sha,'representation_sha256':rep.representation_sha256,'units':len(rep.units),'characters':len(rep.text)})
   except Exception as exc: failures.append({'raw_path':x[1]['raw_path'],'reason':f'{type(exc).__name__}:{exc}'})
 (ROOT/'persisted-representation-manifest.json').write_text(json.dumps({'representations':out,'failures':failures,'provider_calls':0},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'successes':len(out),'failures':len(failures),'provider_calls':0},indent=2))
if __name__=='__main__': main()
