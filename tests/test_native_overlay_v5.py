import json, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('v5',Path(__file__).parents[1]/'scripts'/'run_v5_overlay_lifecycle.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
def test_schema_zero_and_facets():
    s=mod.schema(); ov=s['properties']['reviews']['items']['properties']['overlays']['items']; assert 'relationship_role' not in ov['properties']['facet']['enum']
def test_whole_org_split():
    rows=json.loads(Path(r'C:\CharityGraph-runtime\native-induction-v4r-faceted-disposition-repair\stage-a-dispositions.json').read_text(encoding='utf-8')); c={}
    for r in rows: c[r['subject']]=c.get(r['subject'],0)+len(r.get('objects',[]))
    o=sorted(c,key=lambda n:(-c[n],n)); assert set(o[:3]).isdisjoint(o[3:]); assert sum(c[n] for n in o[:3])==240; assert sum(c[n] for n in o[3:])==49
