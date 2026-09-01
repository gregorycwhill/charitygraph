"""Execute one explicitly authorised frozen Section 16 pressure-case task.

This runner is deliberately limited to the three substantive Life Without
Barriers bundles created by :mod:`charitygraph.section16_preflight`.  It does
not acquire material, retry transport, select evidence, or publish/project
model output.  Raw responses remain private runtime artefacts; only complete
strictly valid typed output is registered as a private model result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.contracts import ModelResult, SchemaRef
from charitygraph.contracts.conduct_compliance import ConductComplianceWireOutput, wire_to_domain
from charitygraph.contracts.ids import deterministic_id
from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create
from charitygraph.runtime import SQLiteCatalog
from charitygraph.section16_preflight import (
    MODEL,
    OUTPUT_CEILING,
    REASONING,
    SUBJECT_ID,
    build_pressure_case_bundles,
    bundle_evidence_map,
    bundle_prompt,
    plan_pressure_case,
    wire_schema,
)


ALLOWED_BUNDLES = {
    "2020_compliance_action",
    "2023_enforceable_undertaking",
    "2025_compliance_action",
}
OWNER = "section16-pressure-case-v2-worker"
COHORT_ID = "cohort:7bd7b247c5e70fcdaa5bde1921d16ff01ba83b97dd8a5d8b2f4e4affb7502b2a"
COHORT_CREATED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)
PRICING_SNAPSHOT_ID = "pricing:bfd141c5764a2927647406c12b1072f46bb8364e7c5f31f17b1be5261c3a6653"
FX_SNAPSHOT_ID = "fx:725b0aab965ecb9aaa34a7d14b32339b746f53fb525ee0445098d39795040744"
FX_USD_AUD = Decimal("1.52")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _task_report(report: dict[str, Any], bundle_name: str) -> dict[str, Any]:
    return next(item for item in report["bundles"] if item["bundle_name"] == bundle_name)


def _register_evidence(catalog: SQLiteCatalog, bundle: dict[str, Any], now: datetime) -> dict[str, str]:
    """Bind packet keys to globally unique runtime locator IDs.

    ``[S001:L0001]`` is canonical only within a frozen packet.  The original
    packet locator remains in each locator record; the stable catalogue ID also
    includes the bundle and source identity so two frozen packets cannot collide.
    """
    runtime_map: dict[str, str] = {}
    for representation in bundle["representations"]:
        source_record_id = representation["source_record_id"]
        if catalog.get_source_record(source_record_id) is None:
            raise RuntimeError(f"frozen bundle references unavailable source record: {source_record_id}")
        for line in representation["lines"]:
            locator = line["canonical_locator"]
            runtime_locator_id = "locator:" + _sha(
                json.dumps(
                    {"bundle_sha256": bundle["bundle_sha256"], "source_record_id": source_record_id, "packet_locator": locator},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            catalog.register_evidence_locator(
                {"kind": "document", "source_record_id": source_record_id, "locator": locator},
                evidence_locator_id=runtime_locator_id,
                now=now,
            )
            runtime_map[line["evidence_key"]] = runtime_locator_id
    return runtime_map


def _register_lifecycle(catalog: SQLiteCatalog, task: dict[str, Any], now: datetime) -> tuple[str, Decimal]:
    if catalog.get_cohort(COHORT_ID) is None:
        catalog.register_cohort(
            {
                "record_id": COHORT_ID,
                "cohort_code": "SECTION16-LWB-V2",
                "definition_version": "section16-pressure-case-v2",
                "membership_hash": _sha(SUBJECT_ID.encode()),
                "budget_cap": {"amount": "0.25", "currency": "AUD"},
                "created_at": COHORT_CREATED_AT,
            }
        )
    if catalog.get_run(task["run_id"]) is not None or catalog.get_task(task["task_id"]) is not None:
        raise RuntimeError("preflighted task or run already exists; refusing a second execution")
    catalog.register_run(
        {
            "record_id": task["run_id"],
            "cohort_id": COHORT_ID,
            "run_kind": "section16_pressure_case",
            "status": "planned",
            "configuration_hash": _sha((task["bundle_sha256"] + task["prompt_sha256"] + task["wire_schema_sha256"]).encode()),
            "created_at": now,
        }
    )
    catalog.register_task(
        {
            "record_id": task["task_id"],
            "run_id": task["run_id"],
            "subject_id": SUBJECT_ID,
            "scope_id": None,
            "cohort_id": COHORT_ID,
            "task_type": "semantic_interpretation",
            "task_schema": {"schema_id": "urn:charitygraph:builder:schema:conduct-compliance-task:1.0"},
            "cache_key": task["cache_key"],
            "provider_id": "openai",
            "model_snapshot": MODEL,
            "created_at": now,
        },
        run_id=task["run_id"],
        now=now,
    )
    reserved_aud = (Decimal(task["projected_usd"][str(OUTPUT_CEILING)]) * FX_USD_AUD).quantize(Decimal("0.000001"))
    reservation_id = deterministic_id("reservation:", {"run_id": task["run_id"], "task_id": task["task_id"]})
    catalog.reserve_cost(
        {
            "record_id": reservation_id,
            "cohort_id": COHORT_ID,
            "run_id": task["run_id"],
            "reserved_aud": {"amount": str(reserved_aud), "currency": "AUD"},
            "model_task_ids": (task["task_id"],),
        },
        now=now,
    )
    return reservation_id, reserved_aud


def _release_unused(catalog: SQLiteCatalog, reservation_id: str, now: datetime) -> None:
    position = catalog.reservation_position(reservation_id)
    unused = max(Decimal("0"), position["reserved"] - min(position["actual"], position["reserved"]) - position["released"])
    if unused:
        catalog.release_cost(reservation_id, {"amount": str(unused), "currency": "AUD"}, now=now, entry_key=f"release:{reservation_id}")


def execute(bundle_name: str, *, packet_path: Path, store_root: Path, preflight_path: Path, catalogue_path: Path, authorization_path: Path, runtime_root: Path) -> dict[str, Any]:
    if bundle_name not in ALLOWED_BUNDLES:
        raise ValueError("only the three explicitly authorised substantive bundles may be executed")
    regenerated = plan_pressure_case(packet_path, store_root)
    report = json.loads(preflight_path.read_text(encoding="utf-8"))
    task = _task_report(report, bundle_name)
    fresh = _task_report(regenerated, bundle_name)
    identity_fields = ("bundle_sha256", "prompt_sha256", "wire_schema_sha256", "evidence_map_sha256", "task_id", "run_id", "task_run_id", "cache_key")
    if any(task[field] != fresh[field] for field in identity_fields):
        raise RuntimeError("preflighted task identity differs from regenerated frozen bundle")
    bundle = next(item for item in build_pressure_case_bundles(packet_path, store_root) if item["bundle_name"] == bundle_name)
    if bundle["bundle_sha256"] != task["bundle_sha256"]:
        raise RuntimeError("frozen bundle SHA mismatch")
    prompt = bundle_prompt(bundle)
    if _sha(prompt.encode()) != task["prompt_sha256"]:
        raise RuntimeError("frozen prompt SHA mismatch")
    schema = wire_schema()
    if _sha(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) != task["wire_schema_sha256"]:
        raise RuntimeError("strict schema SHA mismatch")

    now = datetime.now(timezone.utc)
    output_dir = runtime_root / bundle_name
    catalog = SQLiteCatalog(catalogue_path, authorization_path=authorization_path).open()
    transmitted = False
    reservation_id: str | None = None
    slot_key: str | None = None
    try:
        runtime_evidence_map = _register_evidence(catalog, bundle, now)
        evidence_map = bundle_evidence_map(bundle)
        if set(evidence_map) != set(runtime_evidence_map):
            raise RuntimeError("registered evidence keys do not exactly equal the frozen evidence map")
        reservation_id, reserved_aud = _register_lifecycle(catalog, task, now)
        auth_scope = _sha(json.dumps({"authorization": "active-chat-2026-09-01", "task_id": task["task_id"], "bundle_sha256": task["bundle_sha256"]}, sort_keys=True).encode())
        catalog.authorize_semantic_measurement(
            authorization_scope_hash=auth_scope,
            subject_id=SUBJECT_ID,
            task_family="section16_conduct_compliance",
            material_hash=task["bundle_sha256"],
            measurement_id="production",
            authorized_by="product_owner_active_chat_2026-09-01",
            now=now,
        )
        slot = catalog.claim_authorized_call(
            authorization_scope_hash=auth_scope,
            subject_id=SUBJECT_ID,
            task_family="section16_conduct_compliance",
            material_hash=task["bundle_sha256"],
            measurement_id="production",
            owner=OWNER,
            now=now,
            lease_expires_at=now + timedelta(hours=2),
        )
        slot_key = slot["slot_key"]
        catalog.transition_run(task["run_id"], "running", now=now)
        if not catalog.claim_task(task["task_id"], owner=OWNER, lease_expires_at=now + timedelta(hours=2), now=now):
            raise RuntimeError("could not claim preflighted task")
        catalog.begin_task_attempt(task["task_id"], owner=OWNER, task_run_id=task["task_run_id"], now=now, reservation_id=reservation_id)
        start = {
            "bundle_name": bundle_name,
            "bundle_sha256": task["bundle_sha256"],
            "task_id": task["task_id"],
            "run_id": task["run_id"],
            "task_run_id": task["task_run_id"],
            "prompt_sha256": task["prompt_sha256"],
            "wire_schema_sha256": task["wire_schema_sha256"],
            "evidence_map_sha256": task["evidence_map_sha256"],
            "model": MODEL,
            "reasoning_effort": REASONING,
            "max_output_tokens": OUTPUT_CEILING,
            "max_attempts": 1,
            "projected_max_usd": task["projected_usd"][str(OUTPUT_CEILING)],
            "reserved_aud": str(reserved_aud),
            "source_acquisition": 0,
        }
        _write(output_dir / "execution-start.json", start)
        catalog.mark_authorized_call_transmitted(slot_key, now=now)
        transmitted = True
        try:
            response = responses_create(
                model=MODEL,
                input_text=prompt,
                text_format={"type": "json_schema", "name": "conduct_compliance_section16", "strict": True, "schema": schema},
                max_output_tokens=OUTPUT_CEILING,
                max_attempts=1,
                timeout_seconds=300,
                reasoning={"effort": REASONING},
            )
        except OpenAIRequestError as exc:
            detail = {"error_class": type(exc).__name__, "error_message": str(exc)[:512], "attempts_made": exc.attempts_made, "status_code": exc.status_code}
            _write(output_dir / "provider-error.json", detail)
            catalog.complete_authorized_call(slot_key, now=now, terminal_failure=True)
            catalog.finish_failed_attempt(task["task_run_id"], owner=OWNER, completed_at=now, retryable=False, error_class="ambiguous_transport" if exc.status_code is None else "provider_request", error_message_redacted="provider request failed", usage=None, pricing_snapshot_id=PRICING_SNAPSHOT_ID, fx_snapshot_id=FX_SNAPSHOT_ID)
            catalog.transition_run(task["run_id"], "failed", now=now)
            _release_unused(catalog, reservation_id, now)
            result = start | {"provider_calls": 1, "transport_requests": exc.attempts_made, "status": "provider_error", "provider_error": detail}
            _write(output_dir / "run-report.json", result)
            return result

        raw_payload = {"response_id": response.response_id, "model": response.model, "status": response.status, "output_text": response.output_text, "usage": response.usage.__dict__, "transport_requests": response.transport_requests}
        raw_path = output_dir / "raw-response.json"
        _write(raw_path, raw_payload)
        raw_hash = _sha(raw_path.read_bytes())
        raw_artifact_id = "model-response:" + raw_hash
        catalog.index_artifact(artifact_id=raw_artifact_id, content_hash=raw_hash, schema_id="urn:charitygraph:builder:schema:conduct-compliance-wire:1.0", schema_version="1.0", storage_path=str(raw_path), availability="available", created_at=now, indexed_at=now)
        actual_usd = estimate_response_cost(response.model, response.usage) or Decimal("0")
        actual_aud = (actual_usd * FX_USD_AUD).quantize(Decimal("0.000001"))
        usage = {"input_tokens": response.usage.input_tokens or 0, "cached_input_tokens": 0, "output_tokens": response.usage.output_tokens or 0, "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0, "other_billable_units": []}
        catalog.record_cost_entry(
            {"cohort_id": COHORT_ID, "run_id": task["run_id"], "task_run_id": task["task_run_id"], "reservation_id": reservation_id, "pricing_snapshot_id": PRICING_SNAPSHOT_ID, "fx_snapshot_id": FX_SNAPSHOT_ID, "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd), "currency": "USD"}, "aud_cost": {"amount": str(actual_aud), "currency": "AUD"}, "usage": usage, "recorded_at": now},
            entry_key=f"actual:{task['task_run_id']}",
        )
        errors: list[str] = []
        output = None
        try:
            if response.status != "completed":
                raise ValueError(f"provider response status is {response.status!r}")
            wire = ConductComplianceWireOutput.model_validate_json(response.output_text)
            output = wire_to_domain(wire, allowed_scope_ids={SUBJECT_ID}, evidence_key_map=runtime_evidence_map, observed_at=now)
        except Exception as exc:
            errors.append(str(exc)[:512])
        response_hash = _sha(response.output_text.encode())
        result_id = deterministic_id("modelresult:", {"task_run_id": task["task_run_id"], "response_id": response.response_id, "output_hash": response_hash})
        if errors:
            catalog.complete_authorized_call(slot_key, now=now, result_ref=raw_artifact_id, terminal_failure=True)
            catalog.finish_failed_attempt(task["task_run_id"], owner=OWNER, completed_at=now, retryable=False, error_class="output_validation", error_message_redacted="strict Section 16 output validation failed", result_artifact_id=raw_artifact_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_SNAPSHOT_ID, fx_snapshot_id=FX_SNAPSHOT_ID)
            catalog.transition_run(task["run_id"], "failed", now=now)
            status = "invalid"
        else:
            result = ModelResult(
                record_id=result_id,
                created_at=now,
                producer={"kind": "code", "producer_id": "section16-pressure-case-v2-runner", "version": "1"},
                model_task_id=task["task_id"],
                task_run_id=task["task_run_id"],
                output_schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:conduct-compliance-semantic-output:1.0", schema_version="1.0"),
                output=output,
                validation_status="valid",
                raw_response_ref=raw_artifact_id,
                completed_at=now,
                provider_id="openai",
                model_snapshot=response.model,
            )
            catalog.register_model_result(result)
            catalog.complete_authorized_call(slot_key, now=now, result_ref=result_id)
            catalog.finish_successful_attempt(task["task_run_id"], owner=OWNER, completed_at=now, result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_SNAPSHOT_ID, fx_snapshot_id=FX_SNAPSHOT_ID)
            catalog.transition_run(task["run_id"], "succeeded", now=now)
            status = "valid"
        _release_unused(catalog, reservation_id, now)
        result_report = start | {"provider_calls": 1, "response_id": response.response_id, "response_status": response.status, "transport_requests": response.transport_requests, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "actual_usd": str(actual_usd), "actual_aud": str(actual_aud), "validation_status": status, "validation_errors": errors, "proposition_count": len(output.propositions) if output else 0, "result_id": result_id if not errors else None, "raw_response_artifact_id": raw_artifact_id, "source_acquisition": 0}
        _write(output_dir / "run-report.json", result_report)
        return result_report
    except Exception:
        if slot_key is not None:
            try:
                catalog.abandon_authorized_call(slot_key, now=now, provider_transmitted=transmitted, reason="runner_post_send_failure" if transmitted else "runner_pre_send_failure")
            except Exception:
                pass
        if reservation_id is not None:
            try:
                _release_unused(catalog, reservation_id, now)
            except Exception:
                pass
        raise
    finally:
        catalog.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", choices=tuple(sorted(ALLOWED_BUNDLES)))
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\bundles-v2\executions-v2"))
    parser.add_argument("--packet", type=Path, default=Path(r"C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\packet.json"))
    parser.add_argument("--store-root", type=Path, default=Path(r"C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901"))
    parser.add_argument("--preflight", type=Path, default=Path(r"C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\bundles-v2\section16-provider-preflight.json"))
    parser.add_argument("--catalogue", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--authorization", type=Path, default=Path(r"C:\CharityGraph-runtime\state\semantic-measurement-authorizations.sqlite3"))
    args = parser.parse_args()
    print(json.dumps(execute(args.bundle, packet_path=args.packet, store_root=args.store_root, preflight_path=args.preflight, catalogue_path=args.catalogue, authorization_path=args.authorization, runtime_root=args.runtime_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
