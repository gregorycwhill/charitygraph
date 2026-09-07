import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('v5r',Path(__file__).parents[1]/'scripts'/'run_v5r_overlay_quality.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_quality_schema_has_task_specific_dispositions():
 s=m.quality_schema(); item=s['properties']['reviews']['items']; assert set(item['properties']['disposition']['enum'])=={'accept','reframe','move_facet','reject_native'}
def test_core_facets_exclude_relationship_role(): assert 'relationship_role' not in m.CORE
