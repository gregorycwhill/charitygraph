"""Explicit, idempotent S0 live preparation for a future fresh attempt."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

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
    return catalog.register_scale_s0_attestation_window(window)


def prepare_locator_lifecycle(*, catalog: Any, attempt: Any, packet: Any, request: Any, cohort_id: str, now: datetime, attestation_window: dict[str, Any]) -> dict[str, Any]:
    """Persist one exact reservation and standard lifecycle, idempotently."""
    if request.provider_account_project != attestation_window["provider_account_project"] or request.execution_authority != attestation_window["execution_authority"]:
        raise ScalePreflightError("request A3 fields do not match the durable attestation")
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
