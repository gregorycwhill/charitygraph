"""Run the private Terra review of the World Vision Luna SDG candidates."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from charitygraph.openai_client import estimate_response_cost, responses_create  # noqa: E402

KNOWLEDGE_RUN = Path(r"C:\CharityGraph-runtime\worldvision-luna-sdg-v03-20260830T115500Z")
SDG_RUN = Path(r"C:\CharityGraph-runtime\governed-un-sdg-v1-20260830T")
EXPECTED_LUNA_VIEW_SHA = "d3b643b965cf26d9ca06ff3b01759753b204e6d90124846bda3614791e844dea"
EXPECTED_SDG_PACKET_SHA = "12727486510de7e5e082135ac7e9fd6ea9c68d9df258bc4a36374b95775b1795"
EXPECTED_SOURCE_PACKET_SHA = "5aacb9371f28a4c0766cf190013d8af50ab7b7037ee1bd6dd9243e90d5294ed0"
MODEL = "gpt-5.6-terra"
MAX_OUTPUT_TOKENS = 16_000
MAX_ATTEMPTS = 2
SPEND_CAP_USD = Decimal("1.00")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_v03_runner():
    path = Path(__file__).with_name("run_worldvision_luna_sdg_v03.py")
    spec = importlib.util.spec_from_file_location("worldvision_sdg_v03_dependency", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_normalized_inputs() -> tuple[dict[str, Any], bytes, bytes, dict[str, Any]]:
    v03 = _load_v03_runner()
    view_path = KNOWLEDGE_RUN / "taxonomy-blind-knowledge-view.json"
    view_bytes = view_path.read_bytes()
    if _sha(view_path) != EXPECTED_LUNA_VIEW_SHA:
        raise ValueError("v0.3 knowledge-view hash mismatch")
    view = json.loads(view_bytes.decode("utf-8"))
    if view.get("source_packet_sha256") != EXPECTED_SOURCE_PACKET_SHA:
        raise ValueError("v0.3 source-packet lineage hash mismatch")
    luna = json.loads((Path(r"C:\CharityGraph-runtime\worldvision-luna-sdg-v03-20260830T115500Z") / "parsed-response.json").read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    for item in luna.get("assignments", []):
        candidate = dict(item)
        candidate["candidate_ref"] = f"C{len(candidates) + 1:03d}"
        candidate["registry_scheme"] = "un-sdg"
        candidate["registry_scheme_version"] = "1"
        candidates.append(candidate)
    if len(candidates) != 21:
        raise ValueError(f"expected 21 Luna candidates, found {len(candidates)}")
    normalized = {"packet_version": "worldvision-terra-sdg-review-v0.4", "candidate_count": len(candidates), "candidates": candidates}
    candidate_bytes = (json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    sdg_path = SDG_RUN / "un-sdg-definition-packet.json"
    sdg_bytes = sdg_path.read_bytes()
    if _sha(sdg_path) != EXPECTED_SDG_PACKET_SHA:
        raise ValueError("governed SDG packet hash mismatch")
    taxonomy = json.loads(sdg_bytes.decode("utf-8"))
    # Keep the dependency explicit in the runner without invoking its provider path.
    _, refs = v03.build_knowledge_view()
    return normalized, view_bytes, sdg_bytes, {"taxonomy": taxonomy, "candidates_bytes": candidate_bytes, "observation_refs": refs}


def validate_review(value: dict[str, Any], *, candidate_refs: set[str], observation_refs: dict[str, dict[str, Any]], taxonomy: dict[str, Any], existing_pairs: set[tuple[tuple[str, str], str]]) -> dict[str, Any]:
    failures: list[str] = []
    reviews = value.get("candidate_reviews")
    if not isinstance(reviews, list) or len(reviews) != 21:
        failures.append("candidate_reviews must contain exactly 21 entries")
        reviews = reviews if isinstance(reviews, list) else []
    seen: set[str] = set()
    for index, row in enumerate(reviews):
        ref = row.get("candidate_ref") if isinstance(row, dict) else None
        if ref not in candidate_refs:
            failures.append(f"unknown candidate_ref at index {index}: {ref!r}")
        elif ref in seen:
            failures.append(f"duplicate candidate_ref at index {index}: {ref}")
        seen.add(ref)
        if row.get("verdict") not in {"accept", "narrow_qualify", "reject"}:
            failures.append(f"invalid verdict at index {index}")
        for cited in row.get("supporting_observations", []) or []:
            if cited.get("observation_ref") not in observation_refs:
                failures.append(f"unresolved observation at review index {index}")
    if seen != candidate_refs:
        failures.append("candidate references are not exactly C001-C021")
    goal_ids = {identifier for concept in taxonomy.get("concepts", []) for identifier in (concept.get("concept_id"), concept.get("authority_native_id")) if identifier}
    target_labels = {label for _, label in _TARGETS}
    omission_pairs: set[tuple[tuple[str, str], str]] = set()
    omissions = value.get("strongly_supported_omissions")
    if not isinstance(omissions, list):
        failures.append("strongly_supported_omissions must be an array")
        omissions = []
    for index, row in enumerate(omissions):
        scope = row.get("target_scope", {})
        scope_key = (scope.get("kind"), scope.get("label"))
        goal = row.get("goal_id")
        pair = (scope_key, goal)
        if scope_key[1] not in target_labels:
            failures.append(f"omission target outside governed ten at index {index}")
        if goal not in goal_ids:
            failures.append(f"omission has unknown Goal at index {index}")
        if pair in omission_pairs:
            failures.append(f"duplicate omission target/Goal at index {index}")
        if pair in existing_pairs:
            failures.append(f"omission duplicates existing Luna candidate at index {index}")
        omission_pairs.add(pair)
        for cited in row.get("supporting_observations", []) or []:
            if cited.get("observation_ref") not in observation_refs:
                failures.append(f"unresolved omission observation at index {index}")
    forbidden = ("CLASSIE", "ACNC Registration", "CharityGraph Native")
    encoded = json.dumps(value, ensure_ascii=False)
    for token in forbidden:
        if token in encoded:
            failures.append(f"forbidden taxonomy output token: {token}")
    return {"json_valid": True, "candidate_count": len(reviews), "candidate_refs_exact": seen == candidate_refs, "omission_count": len(omissions), "failures": failures}


_TARGETS = (
    ("subject", "World Vision Australia"), ("named_program_or_service", "Child and Community Sponsorship"),
    ("named_program_or_service", "Australian First Nations Program"), ("named_program_or_service", "Climate Action and Resilience"),
    ("named_program_or_service", "Water Access, Sanitation, and Hygiene"), ("named_program_or_service", "Humanitarian and Emergency Affairs"),
    ("named_program_or_service", "Health and Nutrition"), ("named_program_or_service", "Agriculture and Food Security"),
    ("named_program_or_service", "Education and Child Protection"), ("named_program_or_service", "Economic Empowerment"),
)


def run(output_root: Path | None = None) -> dict[str, Any]:
    normalized, view_bytes, sdg_bytes, extras = build_normalized_inputs()
    taxonomy = extras["taxonomy"]
    candidates = normalized["candidates"]
    candidate_bytes = extras["candidates_bytes"]
    prompt = Path(__file__).with_name("worldvision_terra_sdg_v04_prompt.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    schema = json.loads(Path(__file__).with_name("worldvision_terra_sdg_v04_schema.json").read_text(encoding="utf-8"))
    prompt_bytes = prompt.encode("utf-8")
    schema_bytes = (json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    prompt_sha, schema_sha = hashlib.sha256(prompt_bytes).hexdigest(), hashlib.sha256(schema_bytes).hexdigest()
    input_text = prompt.format(taxonomy=sdg_bytes.decode("utf-8"), knowledge_view=view_bytes.decode("utf-8"), candidates=candidate_bytes.decode("utf-8"))
    estimated = (len(input_text.encode("utf-8")) + 3) // 4
    projected = ((Decimal(estimated) * Decimal("2.00")) + Decimal(MAX_OUTPUT_TOKENS) * Decimal("12.00")) * MAX_ATTEMPTS / Decimal(1_000_000)
    if projected > SPEND_CAP_USD:
        raise RuntimeError(f"retry-inclusive Terra exposure {projected} exceeds USD {SPEND_CAP_USD}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = output_root or Path(r"C:\CharityGraph-runtime") / f"worldvision-terra-sdg-review-v04-{stamp}"
    root.mkdir(parents=False, exist_ok=False)
    (root / "normalized-luna-candidates.json").write_bytes(candidate_bytes)
    (root / "normalized-luna-candidates.sha256").write_text(hashlib.sha256(candidate_bytes).hexdigest() + "\n", encoding="ascii")
    (root / "knowledge-view.json").write_bytes(view_bytes)
    (root / "knowledge-view.sha256").write_text(EXPECTED_LUNA_VIEW_SHA + "\n", encoding="ascii")
    (root / "sdg-packet.json").write_bytes(sdg_bytes)
    (root / "sdg-packet.sha256").write_text(EXPECTED_SDG_PACKET_SHA + "\n", encoding="ascii")
    (root / "prompt.txt").write_bytes(prompt_bytes); (root / "prompt.sha256").write_text(prompt_sha + "\n", encoding="ascii")
    (root / "strict-schema.json").write_bytes(schema_bytes); (root / "strict-schema.sha256").write_text(schema_sha + "\n", encoding="ascii")
    existing_pairs = {((c.get("target_scope", {}).get("kind"), c.get("target_scope", {}).get("label")), c.get("goal_id")) for c in candidates}
    telemetry: dict[str, Any] = {"model": MODEL, "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": 300, "max_transport_attempts": MAX_ATTEMPTS, "estimated_input_tokens": estimated, "projected_exposure_usd": str(projected.quantize(Decimal("0.000001")))}
    started = time.perf_counter(); parsed: dict[str, Any] | None = None
    try:
        response = responses_create(model=MODEL, input_text=input_text, text_format={"type": "json_schema", "name": "worldvision_terra_sdg_review_v04", "strict": True, "schema": schema}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=MAX_ATTEMPTS, timeout_seconds=300, reasoning={"effort": "high"})
        telemetry.update({"response_id": response.response_id, "status": response.status, "transport_attempts": response.transport_requests, "usage": response.usage.__dict__, "cost_usd": str(estimate_response_cost(MODEL, response.usage) or 0), "output_text": response.output_text})
        (root / "raw-response.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            parsed = json.loads(response.output_text)
            (root / "parsed-response.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            telemetry.update({"json_valid": False, "parse_error": type(exc).__name__, "parse_error_detail": str(exc)[:240]})
    except Exception as exc:
        telemetry.update({"provider_error": type(exc).__name__, "provider_error_detail": str(exc)[:240], "transport_attempts": getattr(exc, "attempts_made", 0), "cost_usd": "0"})
        (root / "raw-response.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    diagnostics = validate_review(parsed, candidate_refs={f"C{i:03d}" for i in range(1, 22)}, observation_refs=extras["observation_refs"], taxonomy=taxonomy, existing_pairs=existing_pairs) if parsed is not None else {"json_valid": False, "failures": ["no parseable response"]}
    (root / "validation-diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reviews = (parsed or {}).get("candidate_reviews", [])
    verdicts = {"accept": 0, "narrow_qualify": 0, "reject": 0}; by_target: dict[str, dict[str, int]] = {}; by_goal: dict[str, dict[str, int]] = {}; cited: set[str] = set()
    candidate_by_ref = {c["candidate_ref"]: c for c in candidates}
    for review in reviews:
        verdict = review.get("verdict"); verdicts[verdict] = verdicts.get(verdict, 0) + 1
        candidate = candidate_by_ref.get(review.get("candidate_ref"), {}); target = candidate.get("target_scope", {}).get("label", "unknown"); goal = candidate.get("goal_id", "unknown")
        by_target.setdefault(target, {}).setdefault(verdict, 0); by_target[target][verdict] += 1
        by_goal.setdefault(goal, {}).setdefault(verdict, 0); by_goal[goal][verdict] += 1
        cited.update(x.get("observation_ref") for x in review.get("supporting_observations", []) if x.get("observation_ref"))
    report = {"candidate_count": len(candidates), "verdict_counts": verdicts, "strongly_supported_omission_count": len((parsed or {}).get("strongly_supported_omissions", [])), "verdict_by_target": by_target, "verdict_by_goal": by_goal, "cited_observation_count": len(cited), "validation": diagnostics, "estimated_input_tokens": estimated, "projected_exposure_usd": str(projected.quantize(Decimal("0.000001"))), "knowledge_view_sha256": EXPECTED_LUNA_VIEW_SHA, "sdg_packet_sha256": EXPECTED_SDG_PACKET_SHA, "source_packet_sha256": EXPECTED_SOURCE_PACKET_SHA, "latency_seconds": round(time.perf_counter() - started, 3), "actual_input_tokens": (telemetry.get("usage") or {}).get("input_tokens"), "output_tokens": (telemetry.get("usage") or {}).get("output_tokens"), "cost_usd": telemetry.get("cost_usd", "0"), "transport_attempts": telemetry.get("transport_attempts", 0), "provider_calls": 1 if telemetry.get("response_id") else 0, "source_acquisition": 0}
    (root / "structural-review-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"root": str(root), **{k: report[k] for k in ("candidate_count", "verdict_counts", "strongly_supported_omission_count", "cited_observation_count", "actual_input_tokens", "output_tokens", "latency_seconds", "cost_usd", "provider_calls")}, "validation_failures": diagnostics.get("failures", [])}, indent=2))
    return report


if __name__ == "__main__":
    run()
