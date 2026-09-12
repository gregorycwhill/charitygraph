"""Append-only supersession for immutable private Phase-5 execution tickets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from decimal import Decimal
from typing import Any, Mapping


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_superseding_ticket(
    *, predecessor_path: Path, predecessor_bytes: bytes, builder_commit: str,
    preparation_bytes: bytes, jsonl_bytes: bytes, excluded_request_id: str,
    exclusion_evidence: Mapping[str, Any], supersession_reason: str,
) -> dict[str, Any]:
    """Build a deterministic v2 ticket, proving only the authorized zero-crossing exclusion."""
    if not predecessor_path.is_file() or predecessor_path.read_bytes() != predecessor_bytes:
        raise ValueError("unknown or changed predecessor ticket")
    old = json.loads(predecessor_bytes.decode("utf-8"))
    prep = json.loads(preparation_bytes.decode("utf-8"))
    if old.get("ticket_version") != "phase5-direct-service-v1.2-future-execution-ticket-v1":
        raise ValueError("unsupported predecessor ticket version")
    if sha256(preparation_bytes) != old.get("preparation_manifest_sha256") or len(preparation_bytes) != old.get("preparation_manifest_bytes"):
        raise ValueError("campaign preparation differs from predecessor ticket")
    if sha256(jsonl_bytes) != old.get("jsonl_sha256") or len(jsonl_bytes) != old.get("jsonl_bytes"):
        raise ValueError("campaign JSONL differs from predecessor ticket")
    if (old.get("excluded_terminal_429") != prep.get("terminal_429_excluded")
            or set(old.get("excluded_v1_1_requests", ())) != set(prep.get("old_v1_1_requests_excluded", ()))):
        raise ValueError("historical V1.1 exclusions differ from predecessor ticket")
    if not builder_commit or not supersession_reason.strip():
        raise ValueError("builder commit and supersession reason are required")
    request_rows = prep.get("request_items")
    if not isinstance(request_rows, list) or len(request_rows) != 18:
        raise ValueError("expected the exact original 18-request V1.2 preparation")
    original_ids = [r.get("provider_request_item_id") for r in request_rows]
    if len(set(original_ids)) != 18 or excluded_request_id not in original_ids:
        raise ValueError("request membership is malformed or exclusion is unknown")
    evidence = dict(exclusion_evidence)
    if (evidence.get("request_item_id") != excluded_request_id
            or evidence.get("request_status") != "failed"
            or evidence.get("physical_status") != "failed"
            or evidence.get("failure_class") != "pre_send_validation"
            or evidence.get("send_started") is not False
            or evidence.get("provider_crossings") != 0
            or evidence.get("provider_request_id") is not None
            or evidence.get("provider_receipt_id") is not None
            or evidence.get("usage") is not None
            or evidence.get("builder_reservation_status") != "released"
            or evidence.get("mandate_reservation_status") != "settled"
            or Decimal(str(evidence.get("actual_aud", "-1"))) != 0):
        raise ValueError("excluded request is not proven to be a terminal zero-crossing pre-send failure")

    lines = [json.loads(line) for line in jsonl_bytes.decode("utf-8", errors="strict").splitlines() if line]
    by_id = {line.get("custom_id"): line for line in lines}
    if len(lines) != 18 or set(by_id) != set(original_ids):
        raise ValueError("JSONL request membership differs from the preparation")
    for row in request_rows:
        rid = row["provider_request_item_id"]
        line = by_id[rid]
        if line.get("body") != row.get("request_body"):
            raise ValueError(f"provider body differs between preparation and JSONL: {rid}")
        body_hash = sha256(canonical_bytes(row["request_body"]))
        if body_hash != row.get("request_body_sha256"):
            raise ValueError(f"pinned provider body hash is invalid: {rid}")

    survivors = [r for r in request_rows if r["provider_request_item_id"] != excluded_request_id]
    if len(survivors) != 17:
        raise ValueError("superseding ticket must contain exactly 17 surviving requests")
    first = survivors[0]
    row_contract_identity = {
        key: first[key] for key in (
            "contract_id", "contract_version", "contract_identity_hash", "prompt_sha256",
            "schema_id", "schema_version", "schema_hash", "provider_schema_name",
        )
    }
    historical_identity = old.get("contract_identity")
    if not isinstance(historical_identity, dict):
        raise ValueError("predecessor semantic contract identity is missing")
    for key in ("contract_id", "contract_version", "provider_schema_name"):
        if historical_identity.get(key) != row_contract_identity.get(key):
            raise ValueError(f"predecessor semantic contract identity differs: {key}")
    for row in survivors:
        if any(row.get(key) != value for key, value in row_contract_identity.items()):
            raise ValueError("surviving requests contain multiple semantic contract identities")
    contract_identity = dict(row_contract_identity)
    contract_identity["task_profile"] = historical_identity.get("task_profile")
    contract_identity["task_profile_version"] = historical_identity.get("task_profile_version")
    if not contract_identity["task_profile"] or not contract_identity["task_profile_version"]:
        raise ValueError("predecessor production task profile identity is missing")
    if (prep.get("model") != old.get("model") or prep.get("reasoning_effort") != old.get("reasoning_effort")
            or prep.get("delivery_mode") != old.get("delivery_mode")
            or prep.get("max_output_tokens") != old.get("max_output_tokens")
            or prep.get("mandate_id_required") != old.get("mandate_id_required")):
        raise ValueError("route or mandate differs from predecessor ticket")
    request_material = [
        {"provider_request_item_id": r["provider_request_item_id"],
         "logical_task_id": r["logical_task_id"], "subject_id": r["subject_id"],
         "request_body_sha256": r["request_body_sha256"], "wire_fingerprint": r["wire_fingerprint"],
         "hard_max_usd": r["hard_max_usd"], "hard_max_aud": r["hard_max_aud"]}
        for r in survivors
    ]
    request_set_sha = sha256(canonical_bytes([r["provider_request_item_id"] for r in survivors]))
    provider_material_sha = sha256(canonical_bytes(request_material))
    aggregate_usd = sum((Decimal(str(r["hard_max_usd"])) for r in survivors), Decimal("0"))
    aggregate_aud = sum((Decimal(str(r["hard_max_aud"])) for r in survivors), Decimal("0"))
    return {
        "ticket_version": "phase5-execution-ticket-v2",
        "ticket_status": "current_superseding_ticket",
        "campaign": old["campaign"], "run_id": old["run_id"], "delivery_job_id": old["delivery_job_id"],
        "supersedes": {"path": str(predecessor_path.resolve()), "sha256": sha256(predecessor_bytes),
                       "ticket_version": old["ticket_version"], "builder_commit": old["builder_commit_required"]},
        "supersession_reason": supersession_reason,
        "builder_commit_required": builder_commit,
        "preparation": {"path": str(predecessor_path.parent / "preparation.json"),
                        "sha256": sha256(preparation_bytes), "bytes": len(preparation_bytes)},
        "original_jsonl": {"path": str(predecessor_path.parent / "requests.jsonl"),
                           "sha256": sha256(jsonl_bytes), "bytes": len(jsonl_bytes),
                           "original_request_count": len(request_rows)},
        "request_set": {"count": len(survivors), "ordered_ids_sha256": request_set_sha,
                        "provider_material_sha256": provider_material_sha, "requests": request_material,
                        "excluded_zero_crossing_canary": evidence},
        "semantic_contract": contract_identity,
        "route": {"provider": "openai", "model": prep["model"],
                  "reasoning_effort": prep["reasoning_effort"], "delivery_mode": prep["delivery_mode"],
                  "provider_service_tier": prep.get("provider_service_tier"),
                  "max_output_tokens": prep["max_output_tokens"]},
        "mandate_id_required": prep["mandate_id_required"],
        "limits": {"max_concurrency": prep["max_concurrency"], "automatic_retries": 0,
                   "semantic_retries": 0, "fallbacks": [], "ambiguous_resend": False,
                   "one_transmission_per_request": True, "aggregate_hard_max_usd": format(aggregate_usd, ".6f"),
                   "aggregate_hard_max_aud": format(aggregate_aud, ".6f"),
                   "per_request_hard_max_aud": old["per_request_hard_aud"],
                   "governed_promotions": 0, "source_acquisitions": 0},
    }


def validate_superseding_ticket(
    *, ticket_path: Path, predecessor_path: Path, builder_commit: str,
    preparation_bytes: bytes, jsonl_bytes: bytes, excluded_request_id: str,
    exclusion_evidence: Mapping[str, Any], supersession_reason: str,
) -> dict[str, Any]:
    if ticket_path.resolve() == predecessor_path.resolve():
        raise ValueError("historical execution ticket cannot be the current ticket")
    if not ticket_path.is_file():
        raise ValueError("current superseding ticket is missing")
    expected = build_superseding_ticket(
        predecessor_path=predecessor_path, predecessor_bytes=predecessor_path.read_bytes(),
        builder_commit=builder_commit, preparation_bytes=preparation_bytes, jsonl_bytes=jsonl_bytes,
        excluded_request_id=excluded_request_id, exclusion_evidence=exclusion_evidence,
        supersession_reason=supersession_reason,
    )
    actual_raw = ticket_path.read_bytes()
    if actual_raw != canonical_bytes(expected):
        raise ValueError("current ticket is stale, ambiguous, or differs from deterministic supersession")
    successors = []
    for candidate in ticket_path.parent.glob("future-execution-ticket*.json"):
        if candidate.resolve() == predecessor_path.resolve() or not candidate.is_file():
            continue
        try:
            value = json.loads(candidate.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if value.get("supersedes", {}).get("sha256") == expected["supersedes"]["sha256"]:
            successors.append(candidate.resolve())
    if successors != [ticket_path.resolve()]:
        raise ValueError("ticket supersession has duplicate or ambiguous successors")
    _validate_chain(ticket_path, expected)
    return expected


def build_completed_canary_ticket(
    *, predecessor_path: Path, predecessor_bytes: bytes, predecessor_sha256: str,
    builder_commit: str, preparation_bytes: bytes, jsonl_bytes: bytes,
    completed_canary: Mapping[str, Any],
) -> dict[str, Any]:
    """Append a same-scope execution checkpoint after one already-completed canary."""
    if not predecessor_path.is_file() or predecessor_path.read_bytes() != predecessor_bytes:
        raise ValueError("v2 predecessor ticket is missing or changed")
    if sha256(predecessor_bytes) != predecessor_sha256:
        raise ValueError("v2 predecessor ticket hash differs from pinned checkpoint")
    prior = json.loads(predecessor_bytes.decode("utf-8"))
    if prior.get("ticket_version") != "phase5-execution-ticket-v2":
        raise ValueError("completed-canary ticket requires the approved v2 predecessor")
    if (sha256(preparation_bytes) != prior.get("preparation", {}).get("sha256")
            or len(preparation_bytes) != prior.get("preparation", {}).get("bytes")
            or sha256(jsonl_bytes) != prior.get("original_jsonl", {}).get("sha256")
            or len(jsonl_bytes) != prior.get("original_jsonl", {}).get("bytes")):
        raise ValueError("immutable preparation or original JSONL differs from v2")
    if not builder_commit:
        raise ValueError("current Builder commit is required")
    requests = prior.get("request_set", {}).get("requests")
    if prior.get("request_set", {}).get("count") != 17 or not isinstance(requests, list) or len(requests) != 17:
        raise ValueError("v2 ticket does not contain the exact 17 authorized survivors")
    ids = [r.get("provider_request_item_id") for r in requests]
    if len(set(ids)) != 17:
        raise ValueError("v2 request identities are malformed")
    evidence = dict(completed_canary)
    canary_id = evidence.get("request_item_id")
    if (canary_id not in ids or evidence.get("request_status") != "completed"
            or evidence.get("delivery_attempt_status") != "completed"
            or evidence.get("provider_crossings") != 1
            or not evidence.get("provider_request_id") or not evidence.get("provider_receipt_id")
            or not evidence.get("responses_id") or not evidence.get("raw_response_sha256")
            or evidence.get("corrected_interpretation") != "directly_valid_v12_wire_and_domain"
            or evidence.get("exact_evidence_validation") != "valid"
            or evidence.get("provider_operations_during_reconciliation") != 0):
        raise ValueError("completed canary evidence is incomplete or does not match the pinned V1.2 contract")
    outstanding = [rid for rid in ids if rid != canary_id]
    if len(outstanding) != 16:
        raise ValueError("exactly 16 authorized request items must remain")
    return {
        "ticket_version": "phase5-execution-ticket-v3",
        "ticket_status": "current_same_scope_continuation_after_completed_canary",
        "campaign": prior["campaign"], "run_id": prior["run_id"], "delivery_job_id": prior["delivery_job_id"],
        "supersedes": {"path": str(predecessor_path.resolve()), "sha256": sha256(predecessor_bytes),
                       "ticket_version": prior["ticket_version"],
                       "builder_commit": prior["builder_commit_required"]},
        "builder_commit_required": builder_commit,
        "preparation": prior["preparation"], "original_jsonl": prior["original_jsonl"],
        "request_set": {
            "count": 17, "ordered_ids_sha256": prior["request_set"]["ordered_ids_sha256"],
            "provider_material_sha256": prior["request_set"]["provider_material_sha256"],
            "requests": requests, "completed_canary": evidence,
            "outstanding_request_item_ids": outstanding,
            "outstanding_request_item_ids_sha256": sha256(canonical_bytes(outstanding)),
        },
        "semantic_contract": prior["semantic_contract"], "route": prior["route"],
        "mandate_id_required": prior["mandate_id_required"],
        "limits": {**prior["limits"], "already_transmitted_once": [canary_id],
                   "remaining_one_transmission_request_count": 16},
    }


def validate_completed_canary_ticket(
    *, ticket_path: Path, predecessor_path: Path, predecessor_sha256: str,
    builder_commit: str, preparation_bytes: bytes, jsonl_bytes: bytes,
    completed_canary: Mapping[str, Any],
) -> dict[str, Any]:
    if ticket_path.resolve() == predecessor_path.resolve() or not ticket_path.is_file():
        raise ValueError("current v3 ticket is missing or aliases its predecessor")
    expected = build_completed_canary_ticket(
        predecessor_path=predecessor_path, predecessor_bytes=predecessor_path.read_bytes(),
        predecessor_sha256=predecessor_sha256, builder_commit=builder_commit,
        preparation_bytes=preparation_bytes, jsonl_bytes=jsonl_bytes,
        completed_canary=completed_canary,
    )
    if ticket_path.read_bytes() != canonical_bytes(expected):
        raise ValueError("current v3 ticket is stale or differs from completed-canary evidence")
    successors = []
    for candidate in ticket_path.parent.glob("future-execution-ticket*.json"):
        if candidate.resolve() == predecessor_path.resolve() or not candidate.is_file():
            continue
        try:
            value = json.loads(candidate.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if value.get("supersedes", {}).get("sha256") == predecessor_sha256:
            successors.append(candidate.resolve())
    if successors != [ticket_path.resolve()]:
        raise ValueError("v3 ticket supersession has duplicate or ambiguous successors")
    _validate_chain(ticket_path, expected)
    return expected


def create_completed_canary_ticket(*, ticket_path: Path, **kwargs: Any) -> tuple[dict[str, Any], bool]:
    predecessor_path = kwargs["predecessor_path"]
    if ticket_path.resolve() == predecessor_path.resolve():
        raise ValueError("v3 ticket path must be distinct from its predecessor")
    value = build_completed_canary_ticket(**kwargs)
    raw = canonical_bytes(value)
    if ticket_path.exists():
        if ticket_path.read_bytes() != raw:
            raise ValueError("v3 ticket path already contains different bytes")
        validate_completed_canary_ticket(
            ticket_path=ticket_path,
            predecessor_path=predecessor_path,
            predecessor_sha256=kwargs["predecessor_sha256"],
            builder_commit=kwargs["builder_commit"],
            preparation_bytes=kwargs["preparation_bytes"],
            jsonl_bytes=kwargs["jsonl_bytes"],
            completed_canary=kwargs["completed_canary"],
        )
        return value, False
    with ticket_path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
    return value, True


def _validate_chain(ticket_path: Path, current: Mapping[str, Any]) -> None:
    seen = {ticket_path.resolve()}
    cursor = current
    while cursor.get("supersedes"):
        prior = Path(cursor["supersedes"]["path"]).resolve()
        if prior in seen or not prior.is_file():
            raise ValueError("ticket supersession chain has a cycle or unknown predecessor")
        seen.add(prior)
        prior_raw = prior.read_bytes()
        if sha256(prior_raw) != cursor["supersedes"].get("sha256"):
            raise ValueError("ticket predecessor identity mismatch")
        old = json.loads(prior_raw.decode("utf-8"))
        cursor = old


def create_superseding_ticket(*, ticket_path: Path, **kwargs: Any) -> tuple[dict[str, Any], bool]:
    """Create a new path exclusively; identical replay is a no-op, conflicts fail closed."""
    predecessor_path = kwargs["predecessor_path"]
    if ticket_path.resolve() == predecessor_path.resolve():
        raise ValueError("superseding ticket path must be distinct from predecessor")
    value = build_superseding_ticket(**kwargs)
    raw = canonical_bytes(value)
    if ticket_path.exists():
        if ticket_path.read_bytes() != raw:
            raise ValueError("superseding ticket path already contains different bytes")
        validate_superseding_ticket(ticket_path=ticket_path, **{k: v for k, v in kwargs.items() if k != "predecessor_bytes"})
        return value, False
    # Exclusive creation is append-only: never truncate, replace, or rename the predecessor.
    with ticket_path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
    return value, True


__all__ = ["build_completed_canary_ticket", "build_superseding_ticket", "canonical_bytes", "create_completed_canary_ticket", "create_superseding_ticket", "sha256", "validate_completed_canary_ticket", "validate_superseding_ticket"]
