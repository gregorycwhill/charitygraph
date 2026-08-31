"""Deterministic planning for independently governed direct-service sections."""
from __future__ import annotations
import hashlib, json
from decimal import Decimal
from typing import Any
from .contracts.direct_service_wire import DirectServiceWireOutput
from .contracts.ids import deterministic_id
from .strict_schema import strictify_schema, validate_strict_schema

SECTIONS = {
    "6": ("participation", ("participation_opportunity", "participation_measure")),
    "11": ("capability_access_availability", ("service_offer", "eligibility", "access_pathway", "current_availability", "capacity_measure")),
    "13": ("scheme_accreditation", ("scheme_membership", "accreditation")),
}

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def section_prompt(packet: dict[str, Any], section: str) -> str:
    name, types = SECTIONS[section]
    scopes = "\n".join(f"{s['scope_id']} | {s['scope_kind']} | {s['label']}" for s in packet["scopes"])
    evidence = "\n\n".join(packet["evidence"])
    return (f"You are performing a bounded CharityGraph Phase 3 direct-service semantics task.\n"
            f"This task is ONLY for section {section} ({name}). Emit only: {', '.join(types)}.\n"
            "Return only the strict JSON object matching the supplied schema. Use ONLY supplied evidence. "
            f"The target subject is {packet['subject_id']}. Emit sparse propositions only where evidence supports them.\n"
            "Use exact task-visible scope IDs; never invent IDs or bind by fuzzy labels. Keep opportunity, "
            "measure, service, availability, capacity, eligibility, access, membership and accreditation distinct. "
            "Relationships are directed, role-specific and non-propagating; emit only relationships relevant to this section.\n\n"
            f"TASK-VISIBLE SCOPES:\n{scopes}\n\nPACKET EVIDENCE:\n{evidence}\n")

def wire_schema_sha() -> str:
    schema = strictify_schema(DirectServiceWireOutput.model_json_schema()); validate_strict_schema(schema)
    return _sha(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode())

def plan_section_tasks(packet: dict[str, Any], *, ceilings=(8000, 12000, 16000, 24000), model="gpt-5.6-luna", reasoning_effort="high") -> dict[str, Any]:
    packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    packet_sha, schema_sha = _sha(packet_bytes), wire_schema_sha(); tasks = []
    for section, (name, types) in SECTIONS.items():
        prompt = section_prompt(packet, section); prompt_sha = _sha(prompt.encode()); input_tokens = (len(prompt.encode()) + 3) // 4
        comparisons = []
        for ceiling in ceilings:
            usd = (Decimal(input_tokens) * Decimal("0.20") / Decimal(1_000_000) + Decimal(ceiling) * Decimal("1.20") / Decimal(1_000_000)).quantize(Decimal("0.000001"))
            comparisons.append({"max_output_tokens": ceiling, "estimated_input_tokens": input_tokens, "estimated_max_usd": str(usd)})
        cache_key = _sha(json.dumps({"section": section, "packet_sha": packet_sha, "prompt_sha": prompt_sha, "schema_sha": schema_sha, "model": model, "reasoning": reasoning_effort}, sort_keys=True, separators=(",", ":")).encode())
        task_id = deterministic_id("modeltask:", {"kind": "direct_service_section", "section": section, "cache_key": cache_key})
        run_id = deterministic_id("run:", {"kind": "direct_service_section", "section": section, "task": task_id})
        task_run_id = deterministic_id("taskrun:", {"kind": "direct_service_section", "section": section, "task": task_id, "run": run_id, "attempt": 1})
        selected = comparisons[-1]
        tasks.append({"section_number": section, "expected_section": name, "allowed_proposition_types": types, "task_id": task_id, "run_id": run_id, "task_run_id": task_run_id, "cache_key": cache_key, "packet_sha": packet_sha, "prompt_sha": prompt_sha, "wire_schema_sha": schema_sha, "model": model, "reasoning_effort": reasoning_effort, "proposed_output_ceiling": selected["max_output_tokens"], "physical_max_attempts": 1, "authorization_state": "not_authorized", "ceiling_comparison": comparisons, "estimated_input_tokens": selected["estimated_input_tokens"], "estimated_max_usd": selected["estimated_max_usd"]})
    total = sum((Decimal(t["estimated_max_usd"]) for t in tasks), Decimal("0"))
    return {"kind": "direct_service_section_preflight", "packet_sha": packet_sha, "wire_schema_sha": schema_sha, "model": model, "reasoning_effort": reasoning_effort, "tasks": tasks, "three_task_projected_maximum_usd": str(total.quantize(Decimal("0.000001"))), "three_task_projected_maximum_aud": str((total * Decimal("1.52")).quantize(Decimal("0.000001"))), "provider_calls": 0, "authorization_state": "not_authorized"}

__all__ = ["SECTIONS", "section_prompt", "wire_schema_sha", "plan_section_tasks"]
