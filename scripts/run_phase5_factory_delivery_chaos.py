"""Execute full fake transport-level C1--C6 delivery/recovery populations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.phase5_delivery import DELIVERY_CHAOS_SCENARIOS, build_delivery_plan, delivery_chaos_populations
from run_phase5_factory_delivery_reference import run_reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-factory-delivery-v1\chaos"))
    parser.add_argument("--output", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-factory-delivery-v1\delivery-chaos-summary.json"))
    parser.add_argument("--scenarios", nargs="+", choices=DELIVERY_CHAOS_SCENARIOS, default=DELIVERY_CHAOS_SCENARIOS)
    args = parser.parse_args()
    logical = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_delivery_plan(logical)
    populations = delivery_chaos_populations(plan)
    report = {"logical_tasks": len(logical), "provider_request_items": len(plan.request_items), "network_calls": 0, "provider_calls": 0, "semantic_knowledge_production": 0, "scenarios": {}}
    for scenario in args.scenarios:
        items = populations[scenario]
        result = run_reference(args.manifest, args.runtime_root / scenario, scenario=scenario, selected_item_ids={item.request_item_id for item in items})
        report["scenarios"][scenario] = {"selected": len(items), "execution_status": "executed", "automatic_resends": 0, "explicit_reconciliations": len(items) if scenario == "C2_send_ambiguous" else 0, "run_status": result["run_status"], "terminal_noop_unfinished_items": result["terminal_noop_unfinished_items"], "request_item_ids": [item.request_item_id for item in items]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value["selected"] for key, value in report["scenarios"].items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
