"""CG360 bounded canary runner.

The runner is intentionally boring: selection and packet traversal are
deterministic, provider calls are one read-unit at a time, and consolidation
only combines already validated structured atoms.  It never re-reads source
text during consolidation.
"""
from __future__ import annotations

import argparse, json, time
from hashlib import sha256
from pathlib import Path
from typing import Any

from charitygraph.openai_client import OpenAIRequestError, responses_create
from charitygraph.semantic_packetisation import estimate_tokens
from charitygraph.unified_semantic_experiment import MODEL, UNIFIED_PROMPT, UNIFIED_SCHEMA, UnifiedSemanticOutput, canonical_hash

COHORT = "fa77ab9141ddc5621713c9f487294cadb59fdcdf6d001fc5b4deb2d1e050e5ad"

def strict_schema(value: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(value))
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["required"] = list(node["properties"])
            for child in node.values(): visit(child)
        elif isinstance(node, list):
            for child in node: visit(child)
    visit(value)
    return value

def select_canary(packetisation: dict[str, Any]) -> list[str]:
    """Select exactly three largest cases by deterministic preflight size."""
    sizes: dict[str, int] = {}
    for unit in packetisation.get("read_units", []):
        case = unit["payload"]["packet"]["case_id"]
        sizes[case] = sizes.get(case, 0) + estimate_tokens(unit["payload"])
    return [case for case, _ in sorted(sizes.items(), key=lambda row: (-row[1], row[0]))[:3]]

def merge_outputs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mechanically concatenate validated arrays; no evidence text is read."""
    atoms, ethos, history = [], [], []
    for row in rows:
        output = row["output"]
        atoms.extend(output["general"]["atoms"])
        ethos.extend(output["ethos_notability"].get("ethos_candidates", []))
        history.extend(output["ethos_notability"].get("history_candidates", []))
    result = {"general": {"atoms": atoms}, "ethos_notability": {
        "outcome": "candidates" if ethos or history else "abstain",
        "ethos_candidates": ethos, "history_candidates": history,
        "reason": None if ethos or history else "No supported candidates in validated read units.",
    }}
    UnifiedSemanticOutput.model_validate(result)
    return result

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packetisation", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--max-output-tokens", type=int, default=1600)
    ap.add_argument("--attempts", type=int, default=3)
    args = ap.parse_args()
    packet = json.loads(args.packetisation.read_text(encoding="utf-8"))
    if packet.get("cohort_sha256") != COHORT: raise SystemExit("cohort identity mismatch")
    cases = select_canary(packet)
    units = [u for u in packet["read_units"] if u["payload"]["packet"]["case_id"] in cases]
    schema = strict_schema(UNIFIED_SCHEMA)
    prompt = UNIFIED_PROMPT + "\nRead unit is complete for this call. Do not browse. Return JSON only."
    ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger.exists() else {"requests": []}
    completed: dict[str, dict[str, Any]] = {r["unit_id"]: r for r in ledger["requests"] if r.get("status") == "valid"}
    for unit in units:
        uid = unit["unit_id"]
        if uid in completed: continue
        request = prompt + "\n" + json.dumps(unit["payload"], ensure_ascii=False, sort_keys=True)
        row = {"unit_id": uid, "request_sha256": sha256(request.encode()).hexdigest(), "attempts": []}
        for attempt in range(1, args.attempts + 1):
            try:
                response = responses_create(model=MODEL, input_text=request,
                    text_format={"type":"json_schema","name":"cg360_unit","strict":True,"schema":schema},
                    max_output_tokens=args.max_output_tokens, max_attempts=1, timeout_seconds=180,
                    reasoning={"effort":"none"})
                output = json.loads(response.output_text)
                UnifiedSemanticOutput.model_validate(output)
                row.update({"status":"valid", "output":output, "output_sha256":sha256(response.output_text.encode()).hexdigest(),
                            "response_id":response.response_id, "model":response.model,
                            "usage":response.usage.__dict__, "attempts":row["attempts"] + [{"attempt":attempt,"status":"valid"}]})
                break
            except (OpenAIRequestError, ValueError, json.JSONDecodeError) as error:
                diag = getattr(error, "diagnostic", None)
                row["attempts"].append({"attempt":attempt,"status":"failed","error":str(error),"diagnostic":None if diag is None else diag.as_dict()})
                if attempt < args.attempts: time.sleep(min(2 ** (attempt - 1), 8))
        if row.get("status") != "valid": row["status"] = "failed"
        ledger["requests"].append(row); args.ledger.parent.mkdir(parents=True, exist_ok=True)
        args.ledger.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        completed[uid] = row
    result = {"format":"charitygraph.cg360.canary.v1", "cohort_sha256":COHORT, "cases":cases,
              "unit_count":len(units), "valid_units":sum(r.get("status")=="valid" for r in completed.values()),
              "failed_units":sum(r.get("status")=="failed" for r in completed.values()), "prompt_sha256":sha256(prompt.encode()).hexdigest(),
              "schema_sha256":canonical_hash(schema), "outputs":[]}
    for case in cases:
        rows = [r for r in completed.values() if any(u["unit_id"] == r["unit_id"] and u["payload"]["packet"]["case_id"] == case for u in units)]
        if any(r.get("status") != "valid" for r in rows): continue
        consolidated = merge_outputs(rows)
        result["outputs"].append({"case_id":case,"output":consolidated,"output_sha256":canonical_hash(consolidated),"unit_ids":sorted(r["unit_id"] for r in rows)})
    result["report_sha256"] = canonical_hash(result)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("cases","unit_count","valid_units","failed_units","report_sha256")}, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
