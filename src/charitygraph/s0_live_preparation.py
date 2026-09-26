"""Explicit, idempotent S0 live preparation for a future fresh attempt."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .s0_live import canonical_locator_provider_factory
from .s0_pricing import load_supervisor_capture
from .scale_s0 import ScalePreflightError, locator_search_request_body_sha256, packet_task_key
from .runtime.catalog import S0_LIVE_SEND_ATTESTER, S0_LIVE_SEND_OBSERVED_VALUE, S0_LIVE_SEND_SETTING_NAME
from .s0_acquisition_bridge import bundle_packets
import hashlib
import json


@dataclass(frozen=True)
class HumanA3Input:
    attested_by: str
    observed_at: datetime
    setting_name: str
    observed_value: str
    provider_account_project: str
    execution_authority: str
    structured_authority: Mapping[str, Any] | None = None
    structured_authority_hash: str | None = None


def persist_explicit_a3(catalog: Any, *, attempt: Any, attestation: HumanA3Input, now: datetime) -> dict[str, Any]:
    if now.tzinfo is None or attestation.observed_at.tzinfo is None:
        raise ScalePreflightError("A3 timestamps must be timezone-aware")
    observed = attestation.observed_at.astimezone(timezone.utc)
    current = now.astimezone(timezone.utc)
    if observed > current or current - observed > timedelta(minutes=60):
        raise ScalePreflightError("A3 observation is missing, future-dated, or stale")
    if (attestation.attested_by != S0_LIVE_SEND_ATTESTER or attestation.setting_name != S0_LIVE_SEND_SETTING_NAME
            or attestation.observed_value != S0_LIVE_SEND_OBSERVED_VALUE or not attestation.provider_account_project
            or not attestation.execution_authority):
        raise ScalePreflightError("A3 fields do not match the canonical S0 authority")
    window = {
        "window_id": "window:s0:" + attempt.attempt_id,
        "execution_attempt_id": attempt.attempt_id,
        "mandate_id": attempt.mandate_id,
        "slice_id": attempt.slice_id,
        "run_id": attempt.run_id,
        "attested_by": attestation.attested_by,
        "setting_name": attestation.setting_name,
        "observed_value": attestation.observed_value,
        "provider_account_project": attestation.provider_account_project,
        "execution_authority": attestation.execution_authority,
        "observed_at": observed,
        "valid_until": observed + timedelta(minutes=60),
    }
    if attestation.structured_authority is not None or attestation.structured_authority_hash is not None:
        from .s0_structured_authority import structured_authority_from_material
        authority = structured_authority_from_material(attestation.structured_authority or {})
        if authority.hash != attestation.structured_authority_hash or authority.hash != attestation.execution_authority:
            raise ScalePreflightError("A3 structured authority hash does not match the live authority")
        if (authority.attempt_id != attempt.attempt_id or authority.run_id != attempt.run_id
                or authority.provider_project != attestation.provider_account_project):
            raise ScalePreflightError("A3 structured authority is bound to another attempt, run, or project")
        window.update({"structured_authority": authority.material(), "structured_authority_hash": authority.hash})
    return catalog.register_scale_s0_attestation_window(window)


def checkpoint_structured_locator_preprovider(*, catalog: Any, attempt: Any, authority: Any,
                                               frozen_subjects: Iterable[Any], now: datetime) -> dict[str, Any]:
    """Compile and persist maximal safe state before A3, reservations or send.

    The returned checkpoint is intentionally not a request lifecycle.  A later
    fresh A3 must still pass through normal just-in-time reservation preparation.
    """
    from .s0_structured_authority import compile_locator_authority, validate_live_bindings
    compiled = compile_locator_authority(authority, tuple(frozen_subjects))
    validate_live_bindings(authority, attempt_id=attempt.attempt_id, run_id=attempt.run_id,
                           builder_commit_sha=attempt.builder_commit_sha, data_merge_sha=attempt.data_commit_sha,
                           provider_project=authority.provider_project)
    checkpoint = {
        "checkpoint_id": "checkpoint:s0-locator:" + compiled.authority.hash,
        "execution_attempt_id": attempt.attempt_id, "run_id": attempt.run_id,
        "authority_hash": compiled.authority.hash, "authority": compiled.authority.material(),
        "slots": [asdict(slot) for slot in compiled.slots], "max_physical_calls": compiled.max_physical_calls,
        "max_new_exposure_usd": str(compiled.max_new_exposure_usd), "a3_state": "pending",
        "reservations": 0, "send_started": 0, "provider_attempts": 0, "created_at": now,
    }
    return catalog.register_scale_s0_locator_preprovider_checkpoint(checkpoint)


def prepare_locator_lifecycle(*, catalog: Any, attempt: Any, packet: Any, request: Any, cohort_id: str, now: datetime, attestation_window: dict[str, Any]) -> dict[str, Any]:
    """Persist one exact reservation and standard lifecycle, idempotently."""
    if request.provider_account_project != attestation_window["provider_account_project"] or request.execution_authority != attestation_window["execution_authority"]:
        raise ScalePreflightError("request A3 fields do not match the durable attestation")
    # Structured packets can only become live through their durable pending
    # checkpoint and a fresh A3 carrying the identical structured material.
    # The old opaque packet shape remains historical/read-only compatibility;
    # it cannot manufacture a structured checkpoint.
    structured_hash = attestation_window.get("structured_authority_hash")
    if structured_hash is not None:
        if structured_hash != packet.execution_authority or not attestation_window.get("structured_authority"):
            raise ScalePreflightError("A3 structured authority does not match packet authority hash")
        checkpoint = catalog.get_scale_s0_locator_preprovider_checkpoint(
            execution_attempt_id=attempt.attempt_id, authority_hash=structured_hash)
        if checkpoint is None:
            raise ScalePreflightError("structured locator packet has no durable preprovider checkpoint")
        slots = checkpoint["material"].get("slots", [])
        slot = next((x for x in slots if x["locator_subject_ref"] == packet.subject_id), None)
        if slot is None or (slot["executable_query"], slot["executable_body_sha256"]) != (packet.locator_query, locator_search_request_body_sha256(packet.locator_query)):
            raise ScalePreflightError("packet is not the checkpoint's sole executable query")
    task_key = packet_task_key(packet)
    # Finalise the immutable physical bundle before any reservation or provider
    # lifecycle can be considered executable.  Membership is derived from the
    # exact frozen packet and attempt, so re-entry is an identity check.
    stored_packet = catalog.get_scale_s0_frozen_packet(packet.packet_id)
    if stored_packet is None or stored_packet.get("execution_attempt_id") != attempt.attempt_id:
        raise ScalePreflightError("locator lifecycle requires an attempt-owned durable packet")
    mandate_row = catalog.get_scale_s0_mandate(attempt.mandate_id)
    if mandate_row is None:
        raise ScalePreflightError("locator lifecycle requires the durable mandate")
    mandate_data = mandate_row["material"]
    from .scale_s0 import ScaleMandate
    mandate = ScaleMandate(**mandate_data)
    for bundle in bundle_packets(mandate, (packet,), now=now, execution_attempt_id=attempt.attempt_id):
        catalog.register_scale_s0_physical_bundle(asdict(bundle), execution_attempt_id=attempt.attempt_id)
    catalog.register_task({"record_id": task_key, "subject_id": packet.subject_id, "scope_id": packet.scope_id,
                           "cohort_id": cohort_id, "task_type": "locator_search", "task_schema": packet.input_profile_id,
                           "cache_key": packet.content_hash, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=attempt.run_id, now=now)
    reservation_id = request.reservation_id
    amount = Decimal(packet.estimated_provider_cost)
    catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": attempt.run_id,
                          "reserved_amount": {"amount": str(amount), "currency": "USD"}, "model_task_ids": (task_key,),
                          "expires_at": attestation_window["valid_until"]}, now=now)
    catalog.record_scale_s0_reservation_binding({
        "reservation_id": reservation_id, "reservation_active": True,
        "reservation_mandate_id": attempt.mandate_id, "reservation_slice_id": attempt.slice_id,
        "reservation_task_key": task_key, "reservation_currency": "USD",
        "pricing_snapshot_id": packet.pricing_snapshot_id,
        "estimated_provider_cost": packet.estimated_provider_cost,
        # Persist the complete EconomicState shape expected by live preflight.
        # These are reservation-time values; actual provider spend is populated
        # only after a faithful receipt and governed reconciliation.
        "provider_calls": 0,
        "provider_spend": "0",
        "strong_model_spend": "0",
        "reservation_remaining": str(amount),
        "estimated_strong_cost": "0",
    }, recorded_at=now, execution_attempt_id=attempt.attempt_id)
    delivery_job_id = "deliveryjob:" + packet.provider_request_identity.split(":", 1)[-1]
    catalog.create_delivery_job(delivery_job_id=delivery_job_id, run_id=attempt.run_id, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id=packet.pricing_snapshot_id, now=now)
    catalog.prepare_physical_attempt(physical_attempt_id=request.physical_attempt_id, run_id=attempt.run_id, subject_id=packet.subject_id, delivery_mode="standard", provider_request_id=packet.provider_request_identity, model_task_ids=(task_key,), reservation_id=reservation_id, now=now)
    catalog.create_provider_request_item(provider_request_item_id=packet.provider_request_identity, run_id=attempt.run_id, model_task_id=task_key, provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=delivery_job_id, physical_attempt_id=request.physical_attempt_id, now=now)
    delivery_attempt_id = "delivery-attempt:" + __import__("hashlib").sha256(__import__("json").dumps({"locator_search": packet.provider_request_identity}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    catalog.create_provider_request_attempt(delivery_attempt_id=delivery_attempt_id, provider_request_item_id=packet.provider_request_identity, physical_attempt_id=request.physical_attempt_id, delivery_job_id=delivery_job_id, attempt_ordinal=1, authorization_id=attestation_window["window_id"], attempt_class="initial", predecessor_attempt_id=None, now=now)
    catalog.prepare_standard_transport_trace(
        delivery_attempt_id,
        client_request_id="locator-search-client:" + hashlib.sha256(json.dumps({"locator_search": packet.provider_request_identity}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        endpoint="https://api.openai.com/v1/responses",
        request_body_sha256=locator_search_request_body_sha256(packet.locator_query),
        now=now,
    )
    return {"reservation_id": reservation_id, "delivery_job_id": delivery_job_id, "delivery_attempt_id": delivery_attempt_id, "task_key": task_key}
