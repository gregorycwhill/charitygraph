"""Run the isolated, fake-only Phase-5 Factory reference control-plane exercise."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from charitygraph.phase5_factory import FactoryPlan, ReferenceFactory
from charitygraph.runtime import SQLiteCatalog

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('--manifest',type=Path,default=Path(r'C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json')); p.add_argument('--runtime-root',type=Path,default=Path(r'C:\CharityGraph-runtime\phase5-factory-reference-v1')); a=p.parse_args(); now=datetime(2026,9,7,tzinfo=timezone.utc)
 plan=FactoryPlan.from_manifest(json.loads(a.manifest.read_text(encoding='utf-8')))
 if len(plan.logical_tasks)!=1331: raise RuntimeError('authoritative Phase-5 task count changed')
 a.runtime_root.mkdir(parents=True,exist_ok=True); catalog=SQLiteCatalog(a.runtime_root/'factory.sqlite3').open(initialize=True); cohort='cohort:'+'5'*32; run='run:'+'5'*32
 catalog.register_cohort({'record_id':cohort,'cohort_code':'P5_REHEARSAL','definition_version':'1','membership_hash':plan.manifest_hash,'budget_cap':{'amount':'10000','currency':'AUD'},'created_at':now}); catalog.register_run({'record_id':run,'cohort_id':cohort,'run_kind':'phase5_factory_reference','status':'planned','configuration_hash':plan.manifest_hash,'created_at':now})
 factory=ReferenceFactory(catalog,plan,cohort_id=cohort,run_id=run); factory.seed(now); completed=factory.run(now); noop=factory.run(now)
 summary={'logical_tasks':len(plan.logical_tasks),'manifest_hash':plan.manifest_hash,'completed_first_run':completed,'completed_terminal_rerun':noop,'network_calls':0,'provider_calls':0,'semantic_knowledge_production':0}
 (a.runtime_root/'reference-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(summary))
if __name__=='__main__': main()
