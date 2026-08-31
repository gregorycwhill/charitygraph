"""Execute the three pre-authorised Red Cross direct-service section tasks.

This runner is intentionally bounded to the task identities in the private
section preflight.  It performs no source acquisition and keeps packets,
responses and projections in the private runtime tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.contracts import ScopeRecord, project_observation, wire_to_domain
from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput
from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create, responses_retrieve
from charitygraph.runtime import SQLiteCatalog
from charitygraph.strict_schema import strictify_schema, validate_strict_schema
from charitygraph.direct_service_planning import SECTIONS, section_prompt, wire_schema_sha


SUBJECT_ID = "subject:d10dfad31cb04c5fb27ada0a81f36b69"
CORPUS_ID = "corpus:a7dd2f638bb5be4960b006ec9ce05927a51fd41e076e4ea32605a035fab29dbf"
MODEL = "gpt-5.6-luna"
OWNER = "direct-service-phase3-section-worker"
PRICING_ID = "pricing:bfd141c5764a2927647406c12b1072f46bb8364e7c5f31f17b1be5261c3a6653"
FX_ID = "fx:725b0aab965ecb9aaa34a7d14b32339b746f53fb525ee0445098d39795040744"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _locators(catalog: SQLiteCatalog, packet: dict[str, Any], now: datetime) -> tuple[set[str], list[dict[str, Any]], dict[str, str]]:
    ids: set[str] = set()
    locator_sources: dict[str, str] = {}
    source_meta: list[dict[str, Any]] = packet["sources"]
    for index, source in enumerate(source_meta, 1):
        locator = f"[S{index:03d}:L0001]"
        catalog.register_evidence_locator({"kind": "document", "source_record_id": source["source_record_id"], "locator": locator}, evidence_locator_id=locator, now=now)
        ids.add(locator)
        locator_sources[locator] = source["source_record_id"]
    return ids, source_meta, locator_sources


def _register_scopes(catalog: SQLiteCatalog, packet: dict[str, Any], now: datetime) -> set[str]:
    result: set[str] = set()
    for item in packet["scopes"]:
        scope = ScopeRecord(record_id=item["scope_id"], created_at=now, producer={"kind": "code", "producer_id": "direct-service-section-runner", "version": "1"}, subject_id=SUBJECT_ID, scope_kind=item["scope_kind"], label=item["label"])
        if catalog.get_scope(scope.record_id) is None:
            catalog.register_scope(scope)
        result.add(scope.record_id)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("section", choices=tuple(SECTIONS))
    parser.add_argument("--catalogue", default=r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
    parser.add_argument("--packet", default=r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\packet.json")
    parser.add_argument("--preflight", default=r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\section-task-preflight.json")
    parser.add_argument("--runtime-root", default=r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1\sections")
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
    task_spec = next(row for row in preflight["tasks"] if row["section_number"] == args.section)
    packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if sha(packet_bytes) != task_spec["packet_sha"]:
        raise RuntimeError("frozen packet SHA changed")
    prompt = section_prompt(packet, args.section)
    if sha(prompt.encode()) != task_spec["prompt_sha"]:
        raise RuntimeError("frozen section prompt SHA changed")
    schema = strictify_schema(DirectServiceWireOutput.model_json_schema())
    validate_strict_schema(schema)
    if wire_schema_sha() != task_spec["wire_schema_sha"]:
        raise RuntimeError("provider wire schema SHA changed")
    now = datetime.now(timezone.utc)
    runtime = Path(args.runtime_root) / f"section-{args.section}"
    catalog = SQLiteCatalog(args.catalogue).open()
    try:
        catalog.migrate()
        allowed_scopes = _register_scopes(catalog, packet, now)
        evidence_locators, source_meta, locator_sources = _locators(catalog, packet, now)
        cohort_id = "cohort:" + sha(("DIRECT-SERVICE-PHASE3" + SUBJECT_ID).encode())[:64]
        run_id = task_spec["run_id"]
        task_id = task_spec["task_id"]
        task_run_id = task_spec["task_run_id"]
        if catalog.get_cohort(cohort_id) is None:
            catalog.register_cohort({"record_id": cohort_id, "cohort_code": "DIRECT-SERVICE-PHASE3", "definition_version": "direct-service-v1", "membership_hash": sha(SUBJECT_ID.encode()), "budget_cap": {"amount": "0.50", "currency": "AUD"}, "created_at": now})
        if catalog.get_run(run_id) is None:
            catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "direct_service_section", "status": "planned", "configuration_hash": sha((task_spec["packet_sha"] + task_spec["prompt_sha"]).encode()), "created_at": now})
        if catalog.get_task(task_id) is None:
            catalog.register_task({"record_id": task_id, "run_id": run_id, "subject_id": SUBJECT_ID, "scope_id": None, "cohort_id": cohort_id, "task_type": "direct_service_semantics", "task_schema": {"schema_id": "urn:charitygraph:builder:schema:direct-service-task:1.0"}, "output_schema": {"schema_id": "urn:charitygraph:builder:schema:direct-service-semantic-output:1.0", "schema_version": "1.0"}, "cache_key": task_spec["cache_key"], "provider_id": "openai", "model_snapshot": MODEL, "created_at": now}, run_id=run_id, now=now)
        estimated_aud = (Decimal(task_spec["estimated_max_usd"]) * Decimal("1.52")).quantize(Decimal("0.000001"))
        reservation_id = "reservation:" + sha((run_id + task_id).encode())[:64]
        if catalog.get_reservation(reservation_id) is None:
            catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(estimated_aud), "currency": "AUD"}, "model_task_ids": (task_id,)}, now=now)
        preflight = {"section": args.section, "task_id": task_id, "run_id": run_id, "task_run_id": task_run_id, "packet_sha256": task_spec["packet_sha"], "prompt_sha256": task_spec["prompt_sha"], "wire_schema_sha256": task_spec["wire_schema_sha"], "model": MODEL, "reasoning_effort": "high", "max_output_tokens": 24000, "max_attempts": 1, "estimated_max_usd": task_spec["estimated_max_usd"], "estimated_max_aud": str(estimated_aud), "provider_calls": 0}
        _write(runtime / "preflight.json", preflight)
        catalog.transition_run(run_id, "running", now=now)
        catalog.claim_task(task_id, owner=OWNER, lease_expires_at=now + timedelta(hours=2), now=now)
        catalog.begin_task_attempt(task_id, owner=OWNER, task_run_id=task_run_id, now=now, reservation_id=reservation_id)
        slot = catalog.claim_authorized_call(authorization_scope_hash=sha((CORPUS_ID + task_spec["packet_sha"] + task_id).encode()), subject_id=SUBJECT_ID, task_family="direct_service_semantics", material_hash=task_spec["packet_sha"], measurement_id="production", owner=OWNER, now=now, lease_expires_at=now + timedelta(hours=2))
        catalog.mark_authorized_call_transmitted(slot["slot_key"], now=now)
        try:
            response = responses_create(model=MODEL, input_text=prompt, text_format={"type": "json_schema", "name": "direct_service_semantic_output", "strict": True, "schema": schema}, max_output_tokens=24000, max_attempts=1, timeout_seconds=300, reasoning={"effort": "high"})
        except OpenAIRequestError as exc:
            detail = {"error_class": type(exc).__name__, "error_message": str(exc)[:512], "attempts_made": exc.attempts_made, "status_code": exc.status_code, "diagnostic": exc.diagnostic.as_dict() if exc.diagnostic else {}}
            _write(runtime / "provider-error.json", detail)
            catalog.complete_authorized_call(slot["slot_key"], now=now, terminal_failure=True)
            catalog.finish_failed_attempt(task_run_id, owner=OWNER, completed_at=now, retryable=False, error_class="ambiguous_transport" if exc.status_code is None else "provider_request", error_message_redacted="provider acceptance cannot be ruled out" if exc.status_code is None else "provider request failed")
            catalog.transition_run(run_id, "failed", now=now)
            _write(runtime / "run-report.json", preflight | {"provider_calls": 1, "transport_requests": exc.attempts_made, "validation_status": "provider_error", "provider_error": detail})
            return 0
        response_payload = {"response_id": response.response_id, "model": response.model, "status": response.status, "output_text": response.output_text, "usage": response.usage.__dict__, "transport_requests": response.transport_requests}
        _write(runtime / "response.json", response_payload)
        errors: list[str] = []
        output = None
        try:
            if response.status == "incomplete":
                raise ValueError("response status is incomplete")
            wire = DirectServiceWireOutput.model_validate_json(response.output_text)
            if wire.section != SECTIONS[args.section][0]:
                raise ValueError(f"response section {wire.section!r} does not match {SECTIONS[args.section][0]!r}")
            output = wire_to_domain(wire, allowed_scope_ids=allowed_scopes, evidence_locators=evidence_locators)
        except Exception as exc:
            errors.append(str(exc)[:500])
        actual_usd = estimate_response_cost(response.model, response.usage) or Decimal("0")
        actual_aud = (actual_usd * Decimal("1.52")).quantize(Decimal("0.000001"))
        usage = {"input_tokens": response.usage.input_tokens or 0, "output_tokens": response.usage.output_tokens or 0, "cached_input_tokens": 0, "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0, "other_billable_units": []}
        result_id = "modelresult:" + sha((task_run_id + str(response.response_id) + sha(response.output_text.encode())).encode())[:64]
        catalog.record_cost_entry({"cohort_id": cohort_id, "run_id": run_id, "task_run_id": task_run_id, "reservation_id": reservation_id, "pricing_snapshot_id": PRICING_ID, "fx_snapshot_id": FX_ID, "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd), "currency": "USD"}, "aud_cost": {"amount": str(actual_aud), "currency": "AUD"}, "usage": usage, "recorded_at": now}, entry_key=f"actual:{task_run_id}")
        if output is not None and not errors:
            for index, proposition in enumerate(output.propositions):
                cited = tuple(dict.fromkeys(locator_sources[ref.locator] for ref in proposition.evidence))
                catalog.record_observation(project_observation(proposition, record_id=f"observation:{sha((result_id + str(index)).encode())[:64]}", subject_id=SUBJECT_ID, scope_id=proposition.scope_id, source_record_ids=cited, created_at=now, producer={"kind": "model", "producer_id": MODEL, "version": "direct-service-v1"}))
        if output is None or errors:
            catalog.complete_authorized_call(slot["slot_key"], now=now, result_ref=result_id, terminal_failure=True)
            catalog.finish_failed_attempt(task_run_id, owner=OWNER, completed_at=now, retryable=False, error_class="output_validation", error_message_redacted="direct-service output validation failed", result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_ID, fx_snapshot_id=FX_ID)
            run_status = "failed"
        else:
            catalog.complete_authorized_call(slot["slot_key"], now=now, result_ref=result_id)
            catalog.finish_successful_attempt(task_run_id, owner=OWNER, completed_at=now, result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_ID, fx_snapshot_id=FX_ID)
            run_status = "succeeded"
        catalog.transition_run(run_id, run_status, now=now)
        if actual_aud < estimated_aud:
            catalog.release_cost(reservation_id, {"amount": str(estimated_aud - actual_aud), "currency": "AUD"}, now=now, entry_key=f"release:{task_run_id}")
        reasoning_tokens = None
        if response.response_id:
            try:
                reasoning_tokens = responses_retrieve(response.response_id, timeout_seconds=60).reasoning_tokens
            except Exception:
                pass
        _write(runtime / "projection.json", {"validation_status": "valid" if not errors else "invalid", "validation_errors": errors, "output": output.model_dump(mode="json") if output else None, "response_id": response.response_id, "task_id": task_id, "run_id": run_id, "usage": usage, "reasoning_tokens": reasoning_tokens, "actual_usd": str(actual_usd), "actual_aud": str(actual_aud), "packet_sha256": task_spec["packet_sha"], "prompt_sha256": task_spec["prompt_sha"]})
        _write(runtime / "run-report.json", preflight | {"provider_calls": 1, "response_id": response.response_id, "response_status": response.status, "transport_requests": response.transport_requests, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "reasoning_tokens": reasoning_tokens, "actual_usd": str(actual_usd), "actual_aud": str(actual_aud), "validation_status": "valid" if not errors else "invalid", "validation_errors": errors, "proposition_count": len(output.propositions) if output else 0, "relationship_count": len(output.relationships) if output else 0, "source_meta": source_meta})
        return 0
    finally:
        catalog.close()


if __name__ == "__main__":
    raise SystemExit(main())
