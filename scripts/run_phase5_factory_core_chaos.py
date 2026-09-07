"""Create isolated deterministic core-chaos scenario work orders (no provider/network calls)."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from charitygraph.phase5_factory_chaos import scenario_ledger

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument('reference_db',type=Path); p.add_argument('output_root',type=Path); a=p.parse_args()
 c=sqlite3.connect(f'file:{a.reference_db.as_posix()}?mode=ro',uri=True); ids=[x[0] for x in c.execute('select physical_attempt_id from physical_attempts order by physical_attempt_id')]
 ledger=scenario_ledger(ids); a.output_root.mkdir(parents=True,exist_ok=True)
 for scenario in ('C1_pre_send','C2_send_ambiguous','C3_receipt_restart','C4_structural','C5_grounding','C6_partial_bundle'):
  selected=[row for row in ledger['rows'] if row['scenario']==scenario]
  (a.output_root/f'{scenario}-work-order.json').write_text(json.dumps({'scenario':scenario,'policy_version':ledger['policy_version'],'physical_attempts':selected,'network_calls':0,'provider_calls':0},indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps(ledger['counts'],sort_keys=True))
if __name__=='__main__': main()
