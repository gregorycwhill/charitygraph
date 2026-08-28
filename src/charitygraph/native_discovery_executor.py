"""Small production executor for one evidence-bound native discovery task.

The executor deliberately accepts evidence content from the private runtime and
keeps all response/input bodies outside the repository.  It owns only the
generic task/run/cost/slot lifecycle; acquisition and source policy remain
caller's responsibilities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import (DISCOVERY_OUTPUT_SCHEMA_V2, ModelResult, ModelTask, ProgramServiceDiscoveryOutput, ProgramServiceDiscoveryOutputV2, discovery_schema, discovery_schema_v2)
from .contracts.ids import deterministic_id
from .openai_client import ApiResult, estimate_response_cost, responses_create
from .runtime import SQLiteCatalog


PROMPT_TEMPLATE_ID = "program_service_discovery"
PROMPT_TEMPLATE_VERSION = "v1"
PROVIDER_ID = "openai"
MODEL_SNAPSHOT = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 8000


DISCOVERY_PROMPT = """Identify program-, service-, project-, campaign- or other program/service-like subjects actually supported by the supplied evidence.\n\nA program or service is an identifiable delivered offering or operating subject; a proper or trademarked name is not required, and a stable descriptive service may qualify. Navigation headings, themes, portfolios, capability labels, topic areas, partnerships and organisational practices do not qualify merely because they appear as headings. Distinguish projects and campaigns from durable programs/services. A pilot may be a project or service depending on what the evidence establishes. Do not infer effectiveness, outcome achievement, causal impact or ROI. First-party evidence supports claims about what the organisation says it operates; it does not automatically prove outcomes. Every proposal must cite one or more supplied evidence IDs and preserve uncertainty.\n\nReturn only the strict JSON object matching the supplied schema.\n\nSUBJECT: {subject_id}\n\nEVIDENCE:\n{evidence}"""

DISCOVERY_PROMPT_V2 = """Identify program-, service-, project-, campaign- or other program/service-like subjects supported by the supplied evidence. Current availability is not subject identity: report operational status separately as current, closing_or_winding_down, historical, or unknown. A program or service is an identifiable delivered offering or operating subject; headings, themes, portfolios, capabilities, topics, partnerships and organisational practices do not qualify merely because they appear as headings. Distinguish projects and campaigns from programs/services. Do not infer outcomes, impact or ROI. Every proposal must cite supplied evidence IDs and preserve uncertainty. Return only the strict JSON object matching the supplied schema.\n\nSUBJECT: {subject_id}\n\nEVIDENCE:\n{evidence}"""
PROMPT_TEMPLATE_VERSION_V2 = "v2"


@dataclass(frozen=True)
class NativeDiscoveryExecution:
    run_id: str
    task_id: str
    task_run_id: str
    reservation_id: str
    slot_key: str
    provider_response_id: str | None
    model_result_id: str | None
    output: ProgramServiceDiscoveryOutput | ProgramServiceDiscoveryOutputV2 | None
    proposals: tuple[dict[str, Any], ...]
    projected_candidates: tuple[dict[str, Any], ...]
    actual_usd: Decimal | None
    actual_aud: Decimal | None
    input_tokens: int | None
    output_tokens: int | None
    transport_requests: int
    status: str
    validation_errors: tuple[str, ...] = ()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_prompt(task: ModelTask, evidence_content: Mapping[str, str], *, v2: bool = False) -> str:
    """Render the versioned frozen prompt with evidence in task order only."""
    chunks = []
    for item in task.evidence_inputs:
        if item.evidence_id not in evidence_content:
            raise ValueError(f"missing private evidence content for {item.evidence_id}")
        chunks.append(f"[{item.evidence_id}]\n{evidence_content[item.evidence_id]}")
    prompt = DISCOVERY_PROMPT_V2 if v2 else DISCOVERY_PROMPT
    return prompt.format(subject_id=task.subject_id, evidence="\n\n".join(chunks))


def _parse_discovery_output(
    task: ModelTask, output_text: str,
) -> tuple[ProgramServiceDiscoveryOutput | ProgramServiceDiscoveryOutputV2, tuple[str, ...]]:
    """Validate a response with the output model selected by the task version."""
    task_v2 = task.task_schema.schema_id == "urn:charitygraph:builder:schema:program-service-discovery-task:2.0"
    output_v2 = task.output_schema.schema_id == DISCOVERY_OUTPUT_SCHEMA_V2.schema_id
    if task_v2 != output_v2:
        raise ValueError("v2 discovery requires matching task and output schema identities")
    output_type = ProgramServiceDiscoveryOutputV2 if task_v2 else ProgramServiceDiscoveryOutput
    try:
        return output_type.model_validate_json(output_text), ()
    except Exception as exc:
        return output_type(proposals=()), (str(exc)[:500],)

def execute_native_discovery(
    catalog: SQLiteCatalog,
    *,
    task: ModelTask,
    evidence_content: Mapping[str, str],
    cohort_id: str,
    run_id: str,
    reservation_id: str,
    authorization_scope_hash: str,
    reservation_aud: Decimal,
    pricing_snapshot_id: str,
    fx_snapshot_id: str,
    fx_usd_aud: Decimal,
    measurement_id: str = "production",
    owner: str = "native-discovery-worker",
    runtime_root: str | Path,
    request_fn: Callable[..., ApiResult] = responses_create,
    now: datetime | None = None,
) -> NativeDiscoveryExecution:
    """Execute exactly one logical provider call for a registered task.

    A transport retry remains inside ``request_fn``.  No semantic retry is
    performed after a paid response, even when strict validation fails.
    """
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    catalog.register_task(task, run_id=run_id, now=now)
    catalog.transition_run(run_id, "running", now=now)
    catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(reservation_aud), "currency": "AUD"}, "model_task_ids": (task.record_id,)}, now=now)
    slot = catalog.claim_authorized_call(authorization_scope_hash=authorization_scope_hash, subject_id=task.subject_id, task_family="program_service_discovery", material_hash=task.cache_key or "", measurement_id=measurement_id, owner=owner, now=now, lease_expires_at=now + timedelta(hours=1))
    catalog.claim_task(task.record_id, owner=owner, lease_expires_at=now + timedelta(hours=1), now=now)
    task_run_id = deterministic_id("taskrun:", {"task_id": task.record_id, "run_id": run_id, "attempt": 1})
    attempt = catalog.begin_task_attempt(task.record_id, owner=owner, task_run_id=task_run_id, now=now, reservation_id=reservation_id)
    task_v2 = task.task_schema.schema_id == "urn:charitygraph:builder:schema:program-service-discovery-task:2.0"
    output_v2 = task.output_schema.schema_id == DISCOVERY_OUTPUT_SCHEMA_V2.schema_id
    if task_v2 != output_v2:
        raise ValueError("v2 discovery requires matching task and output schema identities")
    prompt = build_prompt(task, evidence_content, v2=task_v2)
    runtime = Path(runtime_root).resolve()
    input_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    io_dir = runtime / "input-output"
    io_dir.mkdir(parents=True, exist_ok=True)
    input_path = io_dir / f"{task_run_id.replace(':', '_')}.input.txt"
    input_path.write_text(prompt, encoding="utf-8")
    input_artifact_id = "canary-input-" + input_hash
    catalog.index_artifact(artifact_id=input_artifact_id, content_hash=input_hash, schema_id=task.task_schema.schema_id, schema_version=task.task_schema.schema_version, storage_path=str(input_path), availability="available", created_at=now, indexed_at=now)
    response: ApiResult | None = None
    raw_response_path: Path | None = None
    transmitted = False
    try:
        schema = (discovery_schema_v2 if task_v2 else discovery_schema)(tuple(item.evidence_id for item in task.evidence_inputs))
        catalog.mark_authorized_call_transmitted(slot["slot_key"], now=now)
        transmitted = True
        response = request_fn(model=task.model_snapshot, input_text=prompt, text_format={"type": "json_schema", "name": "program_service_discovery", "schema": schema}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=2)
        raw_response_path = io_dir / f"{task_run_id.replace(':', '_')}.response.json"
        raw_response_path.write_text(response.output_text, encoding="utf-8")
        response_hash = hashlib.sha256(response.output_text.encode("utf-8")).hexdigest()
        response_artifact_id = "canary-response-" + response_hash
        catalog.index_artifact(artifact_id=response_artifact_id, content_hash=response_hash, schema_id=task.output_schema.schema_id, schema_version=task.output_schema.schema_version, storage_path=str(raw_response_path), availability="available", created_at=now, indexed_at=now)
        actual_usd = estimate_response_cost(response.model, response.usage)
        actual_aud = None if actual_usd is None else (actual_usd * fx_usd_aud).quantize(Decimal("0.000001"))
        usage = {"input_tokens": response.usage.input_tokens or 0, "output_tokens": response.usage.output_tokens or 0, "cached_input_tokens": 0, "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0, "other_billable_units": []}
        cost = {"cohort_id": cohort_id, "run_id": run_id, "task_run_id": task_run_id, "reservation_id": reservation_id, "pricing_snapshot_id": pricing_snapshot_id, "fx_snapshot_id": fx_snapshot_id, "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd or Decimal("0")), "currency": "USD"}, "aud_cost": {"amount": str(actual_aud or Decimal("0")), "currency": "AUD"}, "usage": usage, "recorded_at": now}
        catalog.record_cost_entry(cost, entry_key=f"actual:{task_run_id}")
        parsed_output, parse_errors = _parse_discovery_output(task, response.output_text)
        errors: list[str] = list(parse_errors)
        output: ProgramServiceDiscoveryOutput | ProgramServiceDiscoveryOutputV2 | None = parsed_output
        result_id = deterministic_id("modelresult:", {"task_run_id": task_run_id, "response_id": response.response_id, "output_hash": hashlib.sha256(response.output_text.encode()).hexdigest()})
        if errors:
            validation_status = "invalid"
        else:
            validation_status = "valid"
        result = ModelResult(record_id=result_id, created_at=now, producer={"kind": "code", "producer_id": "native-discovery-executor", "version": "1"}, model_task_id=task.record_id, task_run_id=task_run_id, output_schema=task.output_schema, output=output, validation_status=validation_status, validation_errors=tuple(errors), raw_response_ref=str(raw_response_path), completed_at=now, provider_id=response.model and task.provider_id or task.provider_id, model_snapshot=response.model)
        catalog.register_model_result(result)
        if errors:
            catalog.finish_failed_attempt(task_run_id, owner=owner, completed_at=now, retryable=False, error_class="output_validation", error_message_redacted="strict discovery output validation failed", result_artifact_id=response_artifact_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=pricing_snapshot_id, fx_snapshot_id=fx_snapshot_id)
            catalog.complete_authorized_call(slot["slot_key"], now=now, result_ref=result_id, terminal_failure=True)
            status = "failed_terminal"
            projected: tuple[dict[str, Any], ...] = ()
        else:
            projected = tuple(catalog.project_program_candidates(result_id, now=now))
            catalog.finish_successful_attempt(task_run_id, owner=owner, completed_at=now, result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=pricing_snapshot_id, fx_snapshot_id=fx_snapshot_id)
            catalog.complete_authorized_call(slot["slot_key"], now=now, result_ref=result_id)
            status = "succeeded"
        position = catalog.reservation_position(reservation_id)
        unused = max(Decimal("0"), position["reserved"] - min(position["actual"], position["reserved"]) - position["released"])
        if unused > 0:
            catalog.release_cost(reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:{reservation_id}")
        catalog.transition_run(run_id, "succeeded" if status == "succeeded" else "failed", now=now)
        return NativeDiscoveryExecution(run_id, task.record_id, task_run_id, reservation_id, slot["slot_key"], response.response_id, result_id, output if not errors else None, tuple(p.model_dump(mode="python") for p in output.proposals) if not errors else (), projected, actual_usd, actual_aud, response.usage.input_tokens, response.usage.output_tokens, response.transport_requests, status, tuple(errors))
    except Exception:
        # Once the send boundary is crossed, every failure is terminal and
        # the authorization is never resettable.
        if transmitted:
            try:
                catalog.abandon_authorized_call(slot["slot_key"], now=now, provider_transmitted=True, reason="post-send failure")
            except Exception:
                pass
            try:
                catalog.finish_failed_attempt(task_run_id, owner=owner, completed_at=now, retryable=False, error_class="post_send_failure", error_message_redacted="provider response processing failed")
            except Exception:
                pass
            try:
                position = catalog.reservation_position(reservation_id)
                unused = max(Decimal("0"), position["reserved"] - min(position["actual"], position["reserved"]) - position["released"])
                if unused > 0:
                    catalog.release_cost(reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:{reservation_id}")
                catalog.transition_run(run_id, "failed", now=now)
            except Exception:
                pass
        else:
            catalog.abandon_authorized_call(slot["slot_key"], now=now, provider_transmitted=False, reason="pre-transmission failure")
            catalog.finish_failed_attempt(task_run_id, owner=owner, completed_at=now, retryable=False, error_class="provider_request", error_message_redacted="provider request failed")
            position = catalog.reservation_position(reservation_id)
            unused = max(Decimal("0"), position["reserved"] - min(position["actual"], position["reserved"]) - position["released"])
            if unused > 0:
                catalog.release_cost(reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:{reservation_id}")
            catalog.transition_run(run_id, "failed", now=now)
        raise
