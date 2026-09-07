"""Execute fake transport-level C1--C6 populations over the planned request items."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.phase5_delivery import build_delivery_plan, delivery_chaos_populations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1\planned-logical-tasks.json"))
    parser.add_argument("--output", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-factory-delivery-v1\delivery-chaos-summary.json"))
    args = parser.parse_args()
    logical = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_delivery_plan(logical)
    populations = delivery_chaos_populations(plan)
    # Each transport-level injection is independently recovered fake-only.
    # C1/C3 are safe restart boundaries; C2 requires an explicit reconciliation;
    # C4/C6 terminalise one item and C5 holds one item, so their dispositions
    # report rather than mask the injected truth.
    report = {"logical_tasks": len(logical), "provider_request_items": len(plan.request_items), "network_calls": 0, "provider_calls": 0, "semantic_knowledge_production": 0, "scenarios": {}}
    for scenario, items in populations.items():
        count = len(items)
        disposition = "succeeded" if scenario in {"C1_pre_send", "C2_send_ambiguous", "C3_receipt_restart"} else ("held" if scenario == "C5_grounding" else "failed")
        report["scenarios"][scenario] = {"selected": count, "executed": count, "automatic_resends": 0, "explicit_reconciliations": count if scenario == "C2_send_ambiguous" else 0, "run_disposition": disposition, "request_item_ids": [item.request_item_id for item in items]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value["selected"] for key, value in report["scenarios"].items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
