"""Complete the private CLASSIE arm from the frozen v0.5.1 blind view."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from charitygraph.openai_client import estimate_response_cost, responses_create
from scripts.run_sparse_luna_classie_v05 import build_classie_schema, dump, estimated_tokens

RUNTIME = Path(r"C:\CharityGraph-runtime\sparse-luna-classie-v05-20260830T\v051")
BLIND_SHA = "329b497a54215c9b3bfafabfbf290c78a7213f945df02a1e3b4f8653329ab04f"
TAXONOMY = Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json")
CAP = Decimal("0.25")


def taxonomy_ids(concepts: list[dict]) -> set[str]:
    """Read the governed private taxonomy's source-native concept IDs."""
    return {str(c.get("external_concept_id") or c.get("concept_id") or c.get("id")) for c in concepts}


def main() -> int:
    blind_path = RUNTIME / "classie-blind-knowledge-view.json"
    actual_blind = hashlib.sha256(blind_path.read_bytes()).hexdigest()
    if actual_blind != BLIND_SHA:
        raise RuntimeError(f"frozen blind-view SHA mismatch: {actual_blind}")
    blind = json.loads(blind_path.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    taxonomy_sha = hashlib.sha256(TAXONOMY.read_bytes()).hexdigest()
    prompt = ("Infer CharityGraph CLASSIE assignments from this taxonomy-blind knowledge using only the supplied private taxonomy and observations. Return only the strict schema; do not use outside knowledge, ACNC CLASSIE, SDG or CharityGraph Native.\n" + json.dumps({"knowledge": blind, "taxonomy": taxonomy}, ensure_ascii=False, separators=(",", ":")))
    projected = (Decimal(estimated_tokens(prompt)) * Decimal("0.20") + Decimal(12000 * 2) * Decimal("1.20")) / Decimal(1_000_000)
    if projected > CAP:
        raise RuntimeError(f"CLASSIE projected cost exceeds cap: {projected:.6f} > {CAP}")
    start = {"phase": "sparse_classie_v052", "model": "gpt-5.6-luna", "timestamp": datetime.now(timezone.utc).isoformat(), "blind_view_sha256": actual_blind, "taxonomy_sha256": taxonomy_sha, "taxonomy_scheme_id": taxonomy.get("scheme_id"), "taxonomy_version": taxonomy.get("version"), "projected_max_cost_usd": f"{projected:.6f}", "max_attempts": 2, "max_output_tokens": 12000}
    dump(RUNTIME / "classie-v052-execution-start.json", start)
    result = responses_create(model="gpt-5.6-luna", input_text=prompt, text_format={"type": "json_schema", "name": "sparse_classie_v052", "strict": True, "schema": build_classie_schema()}, max_output_tokens=12000, max_attempts=2, timeout_seconds=300, reasoning={"effort": "high"})
    usage = result.usage.__dict__
    actual_cost = estimate_response_cost(result.model, result.usage) or Decimal("0")
    raw_text = result.output_text
    (RUNTIME / "classie-v052-response.json").write_text(json.dumps({"output_text": raw_text, "response_id": result.response_id, "model": result.model, "status": result.status, "usage": usage, "transport_requests": result.transport_requests, "actual_cost_usd": f"{actual_cost:.6f}", "returned_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    parsed = json.loads(raw_text)
    dump(RUNTIME / "classie-v052-raw.json", parsed)
    concept_ids = taxonomy_ids(taxonomy.get("concepts", []))
    unknown = sorted({str(a.get("concept_id")) for a in parsed.get("assignments", [])} - concept_ids)
    valid_refs = set(blind.get("observation_refs", {}))
    unresolved = [r.get("observation_ref") for a in parsed.get("assignments", []) for r in a.get("supporting_observations", []) if r.get("observation_ref") not in valid_refs]
    pairs = [(json.dumps(a.get("target_scope", {}), sort_keys=True), str(a.get("concept_id"))) for a in parsed.get("assignments", [])]
    duplicates = len(pairs) - len(set(pairs))
    forbidden = [a for a in parsed.get("assignments", []) if str(a.get("concept_id", "")).casefold().startswith(("sdg", "native", "acnc"))]
    validation = {"json_schema": True, "unknown_concepts": unknown, "unresolved_observation_refs": unresolved, "duplicate_target_concepts": duplicates, "forbidden_assignment_objects": len(forbidden), "status": "passed" if not unknown and not unresolved and not duplicates and not forbidden else "failed"}
    dump(RUNTIME / "classie-v052-validation.json", validation)
    dump(RUNTIME / "classie-v052-report.json", {"private": True, "blind_view_sha256": actual_blind, "assignment_count": len(parsed.get("assignments", [])), "target_assessments_by_status": {status: sum(1 for x in parsed.get("target_assessments", []) if x.get("status") == status) for status in ("assignments_found", "no_supported_assignment", "insufficient_evidence")}, "validation": validation, "usage": usage, "latency_seconds": None, "actual_cost_usd": f"{actual_cost:.6f}", "transport_requests": result.transport_requests, "acnc_comparison": "ACNC CLASSIE comparison unavailable from frozen source-native records"})
    print(json.dumps({"assignment_count": len(parsed.get("assignments", [])), "validation": validation, "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "actual_cost_usd": f"{actual_cost:.6f}", "transport_requests": result.transport_requests}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
