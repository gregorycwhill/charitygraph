"""Private Terra review of the five frozen Luna CLASSIE candidates."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from charitygraph.openai_client import estimate_response_cost, responses_create
from scripts.run_sparse_luna_classie_v05 import dump, estimated_tokens

RUNTIME = Path(r"C:\CharityGraph-runtime\sparse-luna-classie-v05-20260830T\v051")
BLIND_SHA = "329b497a54215c9b3bfafabfbf290c78a7213f945df02a1e3b4f8653329ab04f"
TAXONOMY = Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json")


def review_schema() -> dict:
    obs = {"type": "object", "additionalProperties": False,
           "properties": {"observation_ref": {"type": "string", "pattern": "^O[0-9]{3,}$"}, "role": {"type": "string", "enum": ["supporting", "corroborating", "context"]}}, "required": ["observation_ref", "role"]}
    review = {"type": "object", "additionalProperties": False,
              "properties": {"candidate_index": {"type": "integer", "minimum": 0, "maximum": 4}, "decision": {"type": "string", "enum": ["accept", "narrow_qualify", "reject"]}, "supporting_observations": {"type": "array", "items": obs}, "rationale": {"type": "string"}}, "required": ["candidate_index", "decision", "supporting_observations", "rationale"]}
    omission = {"type": "object", "additionalProperties": False,
                "properties": {"status": {"type": "string", "enum": ["no_strong_omission", "strong_omission_found"]}, "supporting_observations": {"type": "array", "items": obs}, "rationale": {"type": "string"}}, "required": ["status", "supporting_observations", "rationale"]}
    return {"type": "object", "additionalProperties": False, "properties": {"candidate_reviews": {"type": "array", "minItems": 5, "maxItems": 5, "items": review}, "omission_check": omission}, "required": ["candidate_reviews", "omission_check"]}


def taxonomy_ids(concepts: list[dict]) -> set[str]:
    return {str(c.get("external_concept_id") or c.get("concept_id") or c.get("id")) for c in concepts}


def main() -> int:
    blind_path = RUNTIME / "classie-blind-knowledge-view.json"
    if hashlib.sha256(blind_path.read_bytes()).hexdigest() != BLIND_SHA:
        raise RuntimeError("frozen blind-view SHA mismatch")
    blind = json.loads(blind_path.read_text(encoding="utf-8"))
    wrapper = json.loads((RUNTIME / "classie-v052-response.json").read_text(encoding="utf-8"))
    candidates = json.loads(wrapper["output_text"]).get("assignments", [])
    if len(candidates) != 5:
        raise RuntimeError(f"expected five frozen Luna candidates, found {len(candidates)}")
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8")); all_ids = taxonomy_ids(taxonomy.get("concepts", [])); candidate_ids = {str(c.get("concept_id")) for c in candidates}
    if not candidate_ids <= all_ids:
        raise RuntimeError("frozen Luna candidate concept is absent from permitted taxonomy")
    relevant_obs = sorted({str(r.get("observation_ref")) for c in candidates for r in c.get("supporting_observations", [])})
    knowledge = {"subject": blind.get("subject"), "observations": [blind.get("observation_refs", {}).get(ref) | {"observation_ref": ref} for ref in relevant_obs if blind.get("observation_refs", {}).get(ref)]}
    taxonomy_subset = [c for c in taxonomy.get("concepts", []) if str(c.get("external_concept_id") or c.get("concept_id") or c.get("id")) in candidate_ids]
    packet = {"candidate_assignments": candidates, "relevant_knowledge": knowledge, "taxonomy": {"scheme_id": taxonomy.get("scheme_id"), "version": taxonomy.get("version"), "concepts": taxonomy_subset}}
    dump(RUNTIME / "terra-v053-review-packet.json", packet)
    prompt = ("Review the five supplied CharityGraph CLASSIE candidates; do not remap from scratch. For each, return accept, narrow_qualify, or reject with supporting observation references and a private rationale. Then perform only a bounded omission check for any strongly supported assignment Luna materially missed. Use only supplied taxonomy-blind observations and taxonomy entries; no outside knowledge, raw source documents, ACNC CLASSIE, SDG or CharityGraph Native.\n" + json.dumps(packet, ensure_ascii=False, separators=(",", ":")))
    projected = (Decimal(estimated_tokens(prompt)) * Decimal("2.00") + Decimal(8000 * 2) * Decimal("12.00")) / Decimal(1_000_000)
    start = {"phase": "sparse_terra_classie_v053", "model": "gpt-5.6-terra", "timestamp": datetime.now(timezone.utc).isoformat(), "blind_view_sha256": BLIND_SHA, "taxonomy_sha256": hashlib.sha256(TAXONOMY.read_bytes()).hexdigest(), "candidate_count": 5, "projected_max_cost_usd": f"{projected:.6f}", "max_attempts": 2, "max_output_tokens": 8000}
    dump(RUNTIME / "terra-v053-execution-start.json", start)
    started = datetime.now(timezone.utc)
    result = responses_create(model="gpt-5.6-terra", input_text=prompt, text_format={"type": "json_schema", "name": "sparse_terra_classie_review_v053", "strict": True, "schema": review_schema()}, max_output_tokens=8000, max_attempts=2, timeout_seconds=300, reasoning={"effort": "high"})
    returned = datetime.now(timezone.utc)
    usage = result.usage.__dict__; actual = estimate_response_cost(result.model, result.usage) or Decimal("0")
    (RUNTIME / "terra-v053-response.json").write_text(json.dumps({"output_text": result.output_text, "response_id": result.response_id, "model": result.model, "status": result.status, "usage": usage, "transport_requests": result.transport_requests, "actual_cost_usd": f"{actual:.6f}", "latency_seconds": (returned - started).total_seconds(), "returned_at": returned.isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    parsed = json.loads(result.output_text); dump(RUNTIME / "terra-v053-raw.json", parsed)
    valid_refs = set(blind.get("observation_refs", {})); reviews = parsed.get("candidate_reviews", []); indices = [r.get("candidate_index") for r in reviews]
    errors = []
    if len(reviews) != 5 or sorted(indices) != [0, 1, 2, 3, 4]: errors.append("candidate review coverage/index invalid")
    for review in reviews:
        if any(ref.get("observation_ref") not in valid_refs for ref in review.get("supporting_observations", [])): errors.append("review observation reference unresolved")
    omission = parsed.get("omission_check", {}); errors.extend([] if all(r.get("observation_ref") in valid_refs for r in omission.get("supporting_observations", [])) else ["omission observation reference unresolved"])
    validation = {"json_schema": True, "candidate_count": len(reviews), "candidate_indices": indices, "errors": errors, "status": "passed" if not errors else "failed"}
    dump(RUNTIME / "terra-v053-validation.json", validation)
    counts = {d: sum(1 for r in reviews if r.get("decision") == d) for d in ("accept", "narrow_qualify", "reject")}
    report = {"private": True, "candidate_count": len(reviews), **counts, "strongly_supported_omission_count": int(omission.get("status") == "strong_omission_found"), "validation": validation, "usage": usage, "latency_seconds": (returned - started).total_seconds(), "actual_cost_usd": f"{actual:.6f}", "transport_requests": result.transport_requests, "blind_view_sha256": BLIND_SHA}
    dump(RUNTIME / "terra-v053-report.json", report)
    print(json.dumps({"candidate_count": len(reviews), **counts, "strongly_supported_omission_count": report["strongly_supported_omission_count"], "validation": validation, "usage": usage, "latency_seconds": report["latency_seconds"], "actual_cost_usd": report["actual_cost_usd"]}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
