"""Create private, non-authorized section-task identities and cost projections."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from charitygraph.direct_service_planning import plan_section_tasks

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--packet", type=Path, default=Path(r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\packet.json")); ap.add_argument("--output", type=Path, default=Path(r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\section-task-preflight.json")); args = ap.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8")); report = plan_section_tasks(packet); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(report, indent=2, sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
