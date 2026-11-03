"""Provider-free certification over the exact hydrated Standard execution row."""
from __future__ import annotations

import hashlib, json
from decimal import Decimal
from typing import Any, Mapping

from .phase5_standard_transport import canonical_standard_body_bytes


REQUIRED = ("provider", "provider_request_item_id", "logical_task_id", "contract_id", "contract_version", "contract_identity_hash", "task_profile", "task_profile_version", "prompt_sha256", "schema_id", "schema_version", "schema_hash", "provider_schema_name", "model", "reasoning_effort", "delivery_mode", "max_output_tokens", "request_body_sha256", "hard_max_aud", "reservation_id", "mandate_reservation_id", "physical_attempt_id", "delivery_attempt_id")


def certify_standard_execution_row(catalog: Any, row: Mapping[str, Any], *, mandate_id: str) -> dict[str, Any]:
    """Fail closed before send if executor-consumed durable material is incomplete."""
    missing = [key for key in REQUIRED if row.get(key) in (None, "")]
    if missing:
        raise ValueError("execution certification missing mandatory fields: " + ",".join(missing))
    if row["provider"] != "openai" or row["model"] != "gpt-5.6-luna" or row["reasoning_effort"] != "low" or row["delivery_mode"] != "standard" or row["max_output_tokens"] != 8000:
        raise ValueError("execution certification route mismatch")
    if row.get("provider_service_tier") not in (None, "omitted"):
        raise ValueError("execution certification requires omitted Standard service tier")
    body = canonical_standard_body_bytes(row["request_body"])
    if hashlib.sha256(body).hexdigest() != row["request_body_sha256"]:
        raise ValueError("execution certification request body hash mismatch")
    fmt = row["request_body"].get("text", {}).get("format", {})
    if fmt.get("name") != row["provider_schema_name"] or fmt.get("type") != "json_schema" or fmt.get("strict") is not True:
        raise ValueError("execution certification structured-output identity mismatch")
    schema_hash = hashlib.sha256(json.dumps(fmt.get("schema"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if schema_hash != row["schema_hash"]:
        raise ValueError("execution certification schema hash mismatch")
    item = catalog.get_provider_request_item(row["provider_request_item_id"])
    if item is None or item["status"] != "prepared" or item["physical_attempt_id"] != row["physical_attempt_id"]:
        raise ValueError("execution certification request item is not prepared")
    if item.get("provider_request_id") or item.get("provider_receipt_id") or item.get("usage_json"):
        raise ValueError("execution certification request item already has provider crossing evidence")
    physical = catalog.get_physical_attempt(row["physical_attempt_id"])
    if physical is None or physical["status"] != "prepared" or physical["delivery_mode"] != "standard":
        raise ValueError("execution certification physical attempt is not prepared")
    if physical.get("send_started_at") or physical.get("receipt_persisted_at") or physical.get("reservation_id") != row["mandate_reservation_id"]:
        raise ValueError("execution certification physical attempt is sent or reservation-mismatched")
    attempt = catalog.get_provider_request_attempt(row["delivery_attempt_id"])
    if attempt is None or attempt["status"] != "prepared" or attempt["physical_attempt_id"] != row["physical_attempt_id"] or attempt["authorization_id"] != mandate_id:
        raise ValueError("execution certification delivery attempt is not correctly bound")
    if attempt.get("provider_request_id") or attempt.get("provider_receipt_id") or attempt.get("usage_json") or attempt.get("submitted_at"):
        raise ValueError("execution certification delivery attempt already has provider crossing evidence")
    with catalog._authorization_connection() as conn:
        authorization = conn.execute(
            "SELECT e.status mandate_status,e.per_request_hard_aud,r.status mandate_reservation_status,r.reserved_aud mandate_reserved_aud,"
            "b.status budget_status,b.reserved_aud budget_reserved_aud "
            "FROM execution_mandate_reservations r JOIN execution_mandates e ON e.mandate_id=r.mandate_id "
            "JOIN budget_reservations b ON b.reservation_id=r.reservation_id "
            "WHERE r.mandate_id=? AND r.reservation_id=?",
            (mandate_id, row["mandate_reservation_id"]),
        ).fetchone()
    required = Decimal(str(row["hard_max_aud"]))
    if (authorization is None or authorization["mandate_status"] != "active"
            or authorization["mandate_reservation_status"] != "active"
            or authorization["budget_status"] != "active"
            or Decimal(authorization["mandate_reserved_aud"]) != Decimal(authorization["budget_reserved_aud"])
            or Decimal(authorization["mandate_reserved_aud"]) < required
            or required > Decimal(authorization["per_request_hard_aud"])):
        raise ValueError("execution certification authority or active corrected reservation is missing, insufficient, or over cap")
    return {"status": "READY_TO_CROSS_PROVIDER_BOUNDARY", "provider_request_item_id": row["provider_request_item_id"], "request_body_sha256": row["request_body_sha256"], "provider_material_sha256": row["request_body_sha256"], "mandate_id": mandate_id}


__all__ = ["REQUIRED", "certify_standard_execution_row"]
