"""Run the bounded World Vision -> UN SDG mapping experiment (private)."""
from __future__ import annotations

import hashlib
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


KNOWLEDGE_RUN = Path(r"C:\CharityGraph-runtime\worldvision-luna-knowledge-v02-20260830T103756Z")
SDG_RUN = Path(r"C:\CharityGraph-runtime\governed-un-sdg-v1-20260830T")
EXPECTED_SOURCE_PACKET_SHA = "5aacb9371f28a4c0766cf190013d8af50ab7b7037ee1bd6dd9243e90d5294ed0"
EXPECTED_SDG_PACKET_SHA = "12727486510de7e5e082135ac7e9fd6ea9c68d9df258bc4a36374b95775b1795"
MODEL = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 16_000
MAX_ATTEMPTS = 2
SPEND_CAP_USD = Decimal("0.25")
TARGETS = (
    ("subject", "World Vision Australia"),
    ("named_program_or_service", "Child and Community Sponsorship"),
    ("named_program_or_service", "Australian First Nations Program"),
    ("named_program_or_service", "Climate Action and Resilience"),
    ("named_program_or_service", "Water Access, Sanitation, and Hygiene"),
    ("named_program_or_service", "Humanitarian and Emergency Affairs"),
    ("named_program_or_service", "Health and Nutrition"),
    ("named_program_or_service", "Agriculture and Food Security"),
    ("named_program_or_service", "Education and Child Protection"),
    ("named_program_or_service", "Economic Empowerment"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_knowledge_view(parsed_path: Path = KNOWLEDGE_RUN / "parsed-output.json") -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw = json.loads(parsed_path.read_text(encoding="utf-8"))
    observations: list[dict[str, Any]] = []
    refs: dict[str, dict[str, Any]] = {}
    excluded = 0
    for item in raw.get("observations", []):
        if item.get("section_id") == 19 or item.get("scope", {}).get("label") == "Martu Leadership Program":
            excluded += 1
            continue
        ref = f"O{len(observations) + 1:03d}"
        copied = dict(item)
        copied["observation_ref"] = ref
        observations.append(copied)
        refs[ref] = copied
    if excluded != 3:
        raise ValueError("expected exactly the two section-19 observations plus the historical Martu observation to be excluded")
    view = {
        "view_version": "worldvision-knowledge-taxonomy-blind-v0.3",
        "source_packet_sha256": (KNOWLEDGE_RUN / "packet.sha256").read_text(encoding="ascii").strip(),
        "knowledge_output_sha256": _sha(parsed_path),
        "subject": {"name": "World Vision Australia", "abn": "28004778081"},
        "observations": observations,
    }
    if view["source_packet_sha256"] != EXPECTED_SOURCE_PACKET_SHA:
        raise ValueError("World Vision knowledge output does not trace to the expected source packet")
    return view, refs


def validate_mapping(value: dict[str, Any], *, observation_refs: dict[str, dict[str, Any]], taxonomy: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    target_failures: list[str] = []
    expected_targets = set(TARGETS)
    assessments = value.get("target_assessments")
    if not isinstance(assessments, list) or len(assessments) != len(TARGETS):
        target_failures.append("target_assessments must contain exactly ten entries")
    seen_targets: set[tuple[str, str]] = set()
    if isinstance(assessments, list):
        for row in assessments:
            scope = row.get("target_scope", {}) if isinstance(row, dict) else {}
            key = (scope.get("kind"), scope.get("label"))
            seen_targets.add(key)
            if key not in expected_targets:
                target_failures.append(f"unexpected target scope: {key}")
            if row.get("status") not in {"assignments_found", "no_supported_assignment", "insufficient_evidence"}:
                target_failures.append(f"invalid target status: {key}")
    if seen_targets != expected_targets:
        target_failures.append("target scopes are not exactly the governed ten")
    concepts = {
        identifier
        for row in taxonomy.get("concepts", [])
        for identifier in (row.get("concept_id"), row.get("authority_native_id"))
        if identifier
    }
    assignments = value.get("assignments")
    if not isinstance(assignments, list):
        failures.append("assignments must be an array")
        assignments = []
    seen_assignment_keys: set[tuple[tuple[str, str], str]] = set()
    for index, row in enumerate(assignments):
        scope = row.get("target_scope", {})
        scope_key = (scope.get("kind"), scope.get("label"))
        goal = row.get("goal_id")
        key = (scope_key, goal)
        if key in seen_assignment_keys:
            failures.append(f"duplicate target/Goal assignment at index {index}")
        seen_assignment_keys.add(key)
        if scope_key not in expected_targets:
            failures.append(f"assignment target is outside governed ten: {scope_key}")
        if row.get("scheme") != "un-sdg" or row.get("scheme_version") != "1":
            failures.append(f"assignment has incorrect scheme/version at index {index}")
        if goal not in concepts:
            failures.append(f"assignment has unknown or non-goal ID at index {index}")
        refs = row.get("supporting_observations") or []
        if not any(ref.get("role") == "supporting" for ref in refs if isinstance(ref, dict)):
            failures.append(f"assignment has no supporting observation at index {index}")
        for ref in refs:
            observation_ref = ref.get("observation_ref") if isinstance(ref, dict) else None
            if observation_ref not in observation_refs:
                failures.append(f"assignment has unresolved observation {observation_ref!r} at index {index}")
        if isinstance(goal, str) and ("target" in goal.lower() or "indicator" in goal.lower()):
            failures.append(f"target/indicator identifier returned at index {index}")
    return {
        "json_valid": True,
        "exact_target_assessments": not target_failures and len(assessments or []) == 10,
        "target_failures": target_failures,
        "assignment_count": len(assignments),
        "distinct_goals_used": len({row.get("goal_id") for row in assignments}),
        "failures": failures,
    }


def run(output_root: Path | None = None) -> dict[str, Any]:
    knowledge_view, observation_refs = build_knowledge_view()
    knowledge_bytes = (json.dumps(knowledge_view, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    knowledge_sha = hashlib.sha256(knowledge_bytes).hexdigest()
    sdg_path = SDG_RUN / "un-sdg-definition-packet.json"
    sdg_bytes = sdg_path.read_bytes()
    sdg_sha = hashlib.sha256(sdg_bytes).hexdigest()
    if sdg_sha != EXPECTED_SDG_PACKET_SHA:
        raise ValueError("governed UN SDG inference packet hash mismatch")
    taxonomy = json.loads(sdg_bytes.decode("utf-8"))
    prompt = (Path(__file__).with_name("worldvision_sdg_v03_prompt.txt").read_text(encoding="utf-8").replace("\r\n", "\n"))
    schema = json.loads(Path(__file__).with_name("worldvision_sdg_v03_schema.json").read_text(encoding="utf-8"))
    prompt_bytes = prompt.encode("utf-8")
    schema_bytes = (json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    prompt_sha = hashlib.sha256(prompt_bytes).hexdigest()
    schema_sha = hashlib.sha256(schema_bytes).hexdigest()
    input_text = prompt.format(taxonomy=json.dumps(taxonomy, ensure_ascii=False, sort_keys=True, separators=(",", ":")), knowledge_view=knowledge_bytes.decode("utf-8"))
    estimated_input_tokens = (len(input_text.encode("utf-8")) + 3) // 4
    projected = ((Decimal(estimated_input_tokens) * Decimal("0.20")) + (Decimal(MAX_OUTPUT_TOKENS) * Decimal("1.20"))) * MAX_ATTEMPTS / Decimal(1_000_000)
    if projected > SPEND_CAP_USD:
        raise RuntimeError(f"retry-inclusive projected exposure {projected} exceeds USD {SPEND_CAP_USD}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = output_root or Path(r"C:\CharityGraph-runtime") / f"worldvision-luna-sdg-v03-{stamp}"
    root.mkdir(parents=False, exist_ok=False)
    (root / "taxonomy-blind-knowledge-view.json").write_bytes(knowledge_bytes)
    (root / "taxonomy-blind-knowledge-view.sha256").write_text(knowledge_sha + "\n", encoding="ascii")
    (root / "governed-un-sdg-inference-packet.json").write_bytes(sdg_bytes)
    (root / "governed-un-sdg-inference-packet.sha256").write_text(sdg_sha + "\n", encoding="ascii")
    (root / "prompt.txt").write_bytes(prompt_bytes)
    (root / "prompt.sha256").write_text(prompt_sha + "\n", encoding="ascii")
    (root / "strict-schema.json").write_bytes(schema_bytes)
    (root / "strict-schema.sha256").write_text(schema_sha + "\n", encoding="ascii")
    started = time.perf_counter()
    telemetry: dict[str, Any] = {"model": MODEL, "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": 300, "max_transport_attempts": MAX_ATTEMPTS, "estimated_input_tokens": estimated_input_tokens, "projected_exposure_usd": str(projected.quantize(Decimal("0.000001")))}
    parsed: dict[str, Any] | None = None
    try:
        response = responses_create(model=MODEL, input_text=input_text, text_format={"type": "json_schema", "name": "worldvision_sdg_mapping_v03", "strict": True, "schema": schema}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=MAX_ATTEMPTS, timeout_seconds=300, reasoning={"effort": "high"})
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
    diagnostics = validate_mapping(parsed, observation_refs=observation_refs, taxonomy=taxonomy) if parsed is not None else {"json_valid": False, "failures": ["no parseable response"]}
    (root / "validation-diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lineage: list[dict[str, Any]] = []
    if parsed is not None:
        for assignment in parsed.get("assignments", []):
            for ref in assignment.get("supporting_observations", []):
                observation = observation_refs.get(ref.get("observation_ref"), {})
                lineage.append({"target_scope": assignment.get("target_scope"), "goal_id": assignment.get("goal_id"), "observation_ref": ref.get("observation_ref"), "role": ref.get("role"), "evidence": observation.get("evidence", [])})
    (root / "resolved-assignment-observation-source-lineage.json").write_text(json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assignments = (parsed or {}).get("assignments", [])
    by_target: dict[str, list[str]] = {}; by_goal: dict[str, int] = {}
    for row in assignments:
        target = row.get("target_scope", {}).get("label", "")
        by_target.setdefault(target, []).append(row.get("goal_id", ""))
        by_goal[row.get("goal_id", "")] = by_goal.get(row.get("goal_id", ""), 0) + 1
    (root / "assignments-by-target.json").write_text(json.dumps(by_target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "assignments-by-goal.json").write_text(json.dumps(by_goal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    telemetry.update({"latency_seconds": round(time.perf_counter() - started, 3), "actual_input_tokens": (telemetry.get("usage") or {}).get("input_tokens"), "output_tokens": (telemetry.get("usage") or {}).get("output_tokens"), "knowledge_view_sha256": knowledge_sha, "sdg_packet_sha256": sdg_sha, "source_packet_sha256": knowledge_view["source_packet_sha256"], "validation": diagnostics, "provider_calls": 1 if telemetry.get("response_id") else 0, "source_acquisition": 0})
    (root / "experiment-report.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"root": str(root), "knowledge_view_sha256": knowledge_sha, "sdg_packet_sha256": sdg_sha, "source_packet_sha256": knowledge_view["source_packet_sha256"], "provider_calls": telemetry["provider_calls"], "validation_failures": diagnostics.get("failures", [])}, indent=2))
    return telemetry


if __name__ == "__main__":
    run()
