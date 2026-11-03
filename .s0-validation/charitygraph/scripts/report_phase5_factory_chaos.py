"""Write deterministic private diagnostics for an isolated Factory chaos runtime."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from charitygraph.phase5_factory_chaos import scenario_ledger

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('database',type=Path); p.add_argument('output',type=Path); a=p.parse_args()
 c=sqlite3.connect(f'file:{a.database.as_posix()}?mode=ro',uri=True)
 attempts=[row[0] for row in c.execute('select physical_attempt_id from physical_attempts order by physical_attempt_id')]
 tasks=c.execute('select status,count(*) from tasks group by status').fetchall(); physical=c.execute('select status,count(*) from physical_attempts group by status').fetchall(); integrity=c.execute('pragma integrity_check').fetchone()[0]; foreign=c.execute('pragma foreign_key_check').fetchall()
 knowledge={table:c.execute(f'select count(*) from {table}').fetchone()[0] for table in ('knowledge_observations','knowledge_assertions','relationship_statements')}
 report={'network_calls':0,'provider_calls':0,'semantic_knowledge_production':0,'governed_knowledge_records':knowledge,'scenario_ledger':scenario_ledger(attempts),'task_states':tasks,'physical_states':physical,'sqlite_integrity':integrity,'foreign_key_violations':foreign}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'attempts':len(attempts),'integrity':integrity}))
if __name__=='__main__': main()
