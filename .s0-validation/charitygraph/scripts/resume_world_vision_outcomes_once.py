"""Freshly preflight and make the single owner-authorized World Vision POST."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import run_product_value_semantic_campaign as campaign
from charitygraph.openai_client import _output_text
from charitygraph.phase5_openai_dry_run import (
    PRICING, STANDARD_INPUT_BOUND_FACTOR, conservative_standard_hard_max_aud,
    standard_actual_cost,
)
from charitygraph.phase5_standard_transport import (
    OpenAIHTTPStandardClient, StandardTransportError,
    canonical_standard_body_bytes,
    client_request_id_for_physical_attempt,
)
from charitygraph.phase6_v6_campaign import _validate_v6_packet
from charitygraph.product_value_baseline import validate_source_only_packet
from charitygraph.source_rights import FAIR_DEALING_POLICY_ID, OPENAI_PROVIDER_POLICY_ID


RUN_ID = "product-value-resume-world-vision-outcomes-20260914-v1"
RUN_DIR_NAME = "campaign-execution-2026-09-14-resumed-world-vision-v1"
EXPECTED_BASELINE_LOCK_SHA = "dd269e6837e940601e1855e3a9b38b0e96ee669362889d91ae461bf621332d56"
EXPECTED_CAMPAIGN_MANIFEST_SHA = "779bdbdf74c5fd5d1ea12ef708cbd52b8d87d6f60dbd6d927194f360bd931241"
EXPECTED_CANDIDATE_SHA = "bbeac4843bce4714b778c8ec90c678528990b906d23b5a680a1657224e5b666b"
RBA_USD_PER_AUD = Decimal("0.7149")  # RBA 14 September 2026 daily observation
AUD_PER_USD_RESERVED = Decimal("1.40")  # reciprocal rounded upward
ATTEMPT_CAP_AUD = Decimal("0.25")
MAX_OUTPUT_TOKENS = 8000
SETTING = "Share inputs and outputs with OpenAI = Disabled"


def _preflight(builder: Path, data: Path, now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = campaign._paths(builder, data)
    run_dir = paths["work"] / RUN_DIR_NAME
    if run_dir.exists():
        raise ValueError("resumed World Vision run directory already exists; refusing replay")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is unavailable")

    baseline_manifest_sha = validate_source_only_packet(paths["packet"])
    lock_raw = paths["lock"].read_bytes()
    if campaign._sha(lock_raw) != EXPECTED_BASELINE_LOCK_SHA:
        raise ValueError("locked source-only baseline changed")
    campaign_raw = (paths["campaign"] / "execution-manifest.json").read_bytes()
    if campaign._sha(campaign_raw) != EXPECTED_CAMPAIGN_MANIFEST_SHA:
        raise ValueError("frozen five-request campaign manifest changed")
    frozen = json.loads(campaign_raw.decode("utf-8"))
    if frozen.get("campaign_status") != "PREPARED_NOT_SENT" or frozen.get("provider_calls") != 0:
        raise ValueError("immutable request packet is not pristine")

    prior_dir = paths["work"] / "campaign-execution-2026-09-14"
    prior = campaign._json(prior_dir / "execution-results.json")
    prior_manifest = campaign._json(prior_dir / "execution-manifest.json")
    prior_attempt = campaign._json(prior_dir / "attempts" / "01-attempt.json")
    if (prior.get("campaign_state") != "TRANSPORT_FAILURE_CAMPAIGN_STOPPED"
            or prior.get("provider_calls") != 0
            or prior.get("local_transport_invocations") != 1
            or prior.get("candidate_propositions") != 0
            or prior_manifest.get("provider_calls") != 0
            or prior_manifest.get("attempts", [{}])[0].get("provider_posts") != 0
            or prior_attempt.get("transport_state") != "LOCAL_SOCKET_PERMISSION_DENIED"
            or prior_attempt.get("response_headers_received") is not False
            or prior_attempt.get("server_request_id") is not None
            or any(any((prior_dir / name).iterdir()) for name in ("responses",))):
        raise ValueError("prior local pre-send failure does not reconcile to zero provider POSTs")

    context = campaign._json(paths["adjudicated"] / "readiness-and-reconciliation.json")
    candidates_raw = (paths["deterministic"] / "candidates.json").read_bytes()
    if campaign._sha(candidates_raw) != EXPECTED_CANDIDATE_SHA:
        raise ValueError("deterministic candidate inventory changed")
    governed = campaign._json(paths["adjudicated"] / "governed-items.json")
    governed_items = governed.get("proposition_items", []) + governed.get("coverage_items", [])
    if (context.get("readiness") != "DETERMINISTIC_CONTEXT_READY_FOR_SEMANTIC_EXECUTION"
            or len(governed.get("proposition_items", [])) != 106
            or len(governed.get("coverage_items", [])) != 105
            or any(item.get("canonical_public") is not False for item in governed_items)):
        raise ValueError("private deterministic context failed integrity or privacy checks")

    rows = frozen.get("attempts", [])
    if len(rows) != 5:
        raise ValueError("frozen request inventory no longer contains exactly five requests")
    row = rows[0]
    if (row.get("abn") != "28004778081" or row.get("subject_name") != "World Vision Australia"
            or row.get("slice_id") != "outcomes"
            or row.get("contract_version") != "phase6-corrected-contracts-v6"
            or row.get("state") != "PREPARED_NOT_SENT" or row.get("provider_post_count") != 0):
        raise ValueError("authorized World Vision V6 request identity or pristine state changed")
    body_path = paths["requests"] / "28004778081.json"
    body_bytes = body_path.read_bytes()
    body = json.loads(body_bytes.decode("utf-8"))
    if campaign._sha(canonical_standard_body_bytes(body)) != row["request_body_sha256"]:
        raise ValueError("frozen World Vision request body hash mismatch")
    if (body.get("model") != "gpt-5.6-luna"
            or body.get("reasoning", {}).get("effort") != "low"
            or body.get("store") is not False
            or body.get("max_output_tokens") != MAX_OUTPUT_TOKENS
            or body.get("metadata", {}).get("logical_task_id") != row["logical_task_id"]
            or body.get("text", {}).get("format", {}).get("name") != row["provider_schema_name"]
            or campaign._sha(campaign._canonical(body["text"]["format"]["schema"])) != row["provider_schema_sha256"]
            or row.get("semantic_contract_sha256") != "cdfdb68765641400fac367ec50f95a9ef184b81d6991fc8c31fc5c575243b27d"):
        raise ValueError("World Vision schema, contract, or route identity changed")
    client_id = client_request_id_for_physical_attempt(row["physical_attempt_id"])
    if client_id != row.get("x_client_request_id"):
        raise ValueError("World Vision immutable client request ID policy mismatch")

    metadata = campaign._json(paths["source_metadata"]).get("sources", [])
    metadata_by_pair = {(item["source_artifact_id"], item["representation_sha256"]): item for item in metadata}
    lineage_raw = paths["rights_lineage"].read_bytes()
    lineage = json.loads(lineage_raw.decode("utf-8"))
    v6_manifest = campaign._json(paths["v6_manifest"])
    if (campaign._sha(lineage_raw) != v6_manifest.get("rights_lineage_file_sha256")
            or lineage.get("policy_id") != FAIR_DEALING_POLICY_ID):
        raise ValueError("exact-hash rights lineage identity or policy changed")
    lineage_by_pair = {(item["source_artifact_id"], item["representation_sha256"]): item for item in lineage["artifacts"]}
    rights_items = []
    rights_by_decision = {}
    if len(row.get("source_rights", [])) != 2:
        raise ValueError("World Vision request no longer binds exactly two authorized sources")
    for source in row["source_rights"]:
        pair = (source["source_artifact_id"], source["representation_sha256"])
        meta, lineage_item = metadata_by_pair.get(pair), lineage_by_pair.get(pair)
        if meta is None or lineage_item is None:
            raise ValueError("World Vision exact-hash rights record is absent")
        representation = paths["packet"] / meta["representation_path"]
        comparisons = (
            campaign._sha(representation.read_bytes()) == source["representation_sha256"],
            source["abn"] == row["abn"] == meta["abn"] == lineage_item["abn"],
            source["subject_id"] == row["subject_id"] == meta["subject_id"],
            source["subject_name"] == row["subject_name"] == meta["subject_name"] == lineage_item["subject_name"] if "subject_name" in lineage_item else True,
            source["source_artifact_id"] == meta["source_artifact_id"] == lineage_item["source_artifact_id"],
            meta["source_record_id"] == source["source_record_id"] == lineage_item["source_record_id"],
            meta["source_locator"] == source["source_origin_url"] == lineage_item["source_origin_url"],
            meta["source_role"] == source["source_role"] == lineage_item["source_role"],
            meta["evidence_locator_id"] == source["evidence_locator_id"],
            meta["source_family"] == source["source_family"] == lineage_item["source_family"],
            meta["legal_scope"] == source["legal_scope"] == "organisation",
            meta["retention_status"] == source["retention_status"] == "authorized",
            meta["retention_decision_id"] == source["retention_decision_id"],
            meta["retention_policy_id"] == source["retention_policy_id"],
            meta["retention_policy_version"] == source["retention_policy_version"],
            meta["provider_rights_decision_id"] == source["provider_rights_decision_id"],
            meta["provider_transmission_status"] == "separately_authorized_for_exact_hash_subject_to_revalidation",
            source["provider_transmission_allowed_in_frozen_decision"] is True,
            source["provider_rights_decision_disposition"] == "included",
            lineage_item["disposition"] == "included" and lineage_item["provider_transmission_allowed"] is True,
            source["rights_policy_id"] == lineage_item["rights_policy_id"] == FAIR_DEALING_POLICY_ID,
            source["provider_processing_policy_id"] == lineage_item["provider_processing_policy_id"] == OPENAI_PROVIDER_POLICY_ID,
            source["acquisition_lineage_ids"] == lineage_item["acquisition_lineage_ids"] and bool(source["acquisition_lineage_ids"]),
            source["provider_rights_decision_id"] == lineage_item["rights_decision_id"],
        )
        if not all(comparisons):
            raise ValueError("World Vision exact representation, scope, rights or lineage revalidation failed")
        rights_by_decision[source["provider_rights_decision_id"]] = source
        rights_items.append({
            "source_artifact_id": source["source_artifact_id"],
            "source_record_id": source["source_record_id"],
            "representation_sha256": source["representation_sha256"],
            "rights_decision_id": source["provider_rights_decision_id"],
            "rights_policy_id": FAIR_DEALING_POLICY_ID,
            "provider_processing_policy_id": OPENAI_PROVIDER_POLICY_ID,
            "provider_transmission_authorized": True,
            "source_role": source["source_role"], "legal_scope": source["legal_scope"],
            "acquisition_lineage_ids": source["acquisition_lineage_ids"],
            "source_acquisitions": 0,
        })

    if (PRICING["gpt-5.6-luna"]["input"] != Decimal("0.20")
            or PRICING["gpt-5.6-luna"]["output"] != Decimal("1.20")
            or PRICING["gpt-5.6-luna"]["cache_write_input"] != Decimal("0.25")):
        raise ValueError("local Luna pricing table differs from current published pricing")
    exposure = conservative_standard_hard_max_aud(
        row["input_tokens_estimate"], MAX_OUTPUT_TOKENS, AUD_PER_USD_RESERVED,
        model="gpt-5.6-luna", input_bound_factor=STANDARD_INPUT_BOUND_FACTOR,
    )
    if exposure > ATTEMPT_CAP_AUD:
        raise ValueError("World Vision conservative exposure exceeds its AUD 0.25 cap")
    client = OpenAIHTTPStandardClient()
    if client.socket_timeout_seconds != 300:
        raise ValueError("Standard route timeout is not 300 seconds")

    owner_attestation = {
        "attested_by": "Greg", "setting": SETTING, "observed_value": "Disabled",
        "attested_at": now.isoformat(),
        "evidence_type": "fresh product-owner confirmation in the resumed campaign handoff",
        "provider_calls": 0,
    }
    preflight = {
        "run_id": RUN_ID, "preflight_status": "PASSED", "checked_at": now.isoformat(),
        "prior_failure_reconciliation": {
            "prior_run_id": "product-value-five-request-semantic-campaign-20260914-v1",
            "prior_local_transport_invocations": 1, "prior_provider_calls": 0,
            "prior_provider_response_files": 0, "prior_semantic_candidates": 0,
            "prior_transport_state": "LOCAL_SOCKET_PERMISSION_DENIED",
            "response_headers_received": False, "server_request_id": None,
        },
        "baseline": {"status": "validated_unchanged", "manifest_sha256": baseline_manifest_sha,
            "lock_sha256": campaign._sha(lock_raw)},
        "deterministic_context": {"status": context["readiness"],
            "candidate_inventory_sha256": campaign._sha(candidates_raw),
            "proposition_items": 106, "coverage_states": 105,
            "private_only": True, "regenerated": False},
        "authorized_request": {"subject": "World Vision Australia", "contract": "Outcomes V6",
            "request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"],
            "request_body_sha256": row["request_body_sha256"],
            "schema_sha256": row["provider_schema_sha256"],
            "semantic_contract_sha256": row["semantic_contract_sha256"],
            "client_request_id": client_id, "body_unchanged": True,
            "remaining_four_requests_authorized": False},
        "source_rights": {"status": "authorized", "exact_representations": len(rights_items),
            "rights_lineage_sha256": campaign._sha(lineage_raw), "items": rights_items,
            "source_substitution": False, "source_acquisitions": 0},
        "owner_attestation": owner_attestation,
        "provider_data_policy": {"policy_id": OPENAI_PROVIDER_POLICY_ID,
            "official_source": "https://openai.com/business-data/",
            "no_training_by_default": True},
        "pricing": {"model": "gpt-5.6-luna", "input_usd_per_million": "0.20",
            "cached_input_usd_per_million": "0.02", "cache_write_usd_per_million": "0.25",
            "output_usd_per_million": "1.20",
            "source_url": campaign.OPENAI_PRICE_URL, "checked_at": now.isoformat()},
        "fx": {"rba_observation_date": "2026-09-14", "usd_per_aud": str(RBA_USD_PER_AUD),
            "aud_per_usd_used": str(AUD_PER_USD_RESERVED), "rounded_up": True,
            "source_url": campaign.RBA_FX_URL, "checked_at": now.isoformat()},
        "budget": {"attempt_reservation_aud": str(exposure),
            "per_attempt_cap_aud": str(ATTEMPT_CAP_AUD),
            "remaining_four_reserved_or_spent": False, "campaign_aggregate_reservation_aud": str(exposure)},
        "transport": {"provider": "OpenAI", "endpoint": client.base_url,
            "model": "gpt-5.6-luna", "reasoning": "low", "delivery": "Standard",
            "timeout_seconds": 300, "automatic_retries": 0, "manual_retries": 0,
            "maximum_provider_posts_this_resume": 1, "canary": False,
            "network_execution_context": "escalated network-enabled command",
            "proxy_configuration": campaign._proxy_inventory()},
        "provider_calls_before_post": 0, "source_acquisitions": 0,
        "semantic_governed_promotions": 0,
    }
    task_map = campaign._source_tasks(builder, data, {"attempts": [row]})
    return preflight, {"paths": paths, "run_dir": run_dir, "row": row, "body_bytes": body_bytes,
        "exposure": exposure, "task": task_map[row["request_item_id"]], "frozen": frozen,
        "owner_attestation": owner_attestation}


def execute(builder: Path, data: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    preflight, prepared = _preflight(builder, data, now)
    run_dir: Path = prepared["run_dir"]
    run_dir.mkdir(parents=False, exist_ok=False)
    for name in ("responses", "attempts", "human-adjudication-packet"):
        (run_dir / name).mkdir()
    campaign._write_atomic(run_dir / "preflight.json", campaign._canonical(preflight) + b"\n")
    campaign._write_atomic(run_dir / "provider-policy-attestation.json", campaign._canonical(prepared["owner_attestation"]) + b"\n")
    row = prepared["row"]
    attempt = {
        "subject": "World Vision Australia", "contract": "Outcomes V6",
        "request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"],
        "client_request_id": row["x_client_request_id"],
        "request_body_sha256": row["request_body_sha256"],
        "provider_schema_sha256": row["provider_schema_sha256"],
        "semantic_contract_sha256": row["semantic_contract_sha256"],
        "model": "gpt-5.6-luna", "reasoning": "low", "delivery": "Standard",
        "timeout_seconds": 300, "automatic_retries": 0, "manual_retries": 0,
        "request_started_at": None, "provider_posts": 0,
        "local_transport_invocations": 0,
        "conservative_reserved_exposure_aud": str(prepared["exposure"]),
    }
    manifest = {"run_id": RUN_ID, "status": "PREFLIGHT_PASSED_NOT_SENT",
        "created_at": now.isoformat(), "preflight_sha256": campaign._sha(campaign._canonical(preflight)),
        "maximum_physical_provider_posts": 1, "automatic_retries": 0,
        "manual_retries": 0, "provider_calls": 0, "source_acquisitions": 0,
        "semantic_governed_promotions": 0, "attempts": [attempt]}
    results = {"run_id": RUN_ID, "campaign_state": "PREFLIGHT_PASSED_NOT_SENT",
        "provider_calls": 0, "local_transport_invocations": 0,
        "source_acquisitions": 0, "semantic_governed_promotions": 0,
        "candidate_propositions": 0, "candidate_coverage_count": 0,
        "attempts": [attempt], "remaining_four_requests": "FROZEN_UNSENT_NOT_AUTHORIZED"}
    campaign._write_atomic(run_dir / "execution-manifest.json", campaign._canonical(manifest) + b"\n")
    campaign._write_atomic(run_dir / "execution-results.json", campaign._canonical(results) + b"\n")

    started = datetime.now(timezone.utc)
    attempt.update({"request_started_at": started.isoformat(), "provider_posts": 1,
        "local_transport_invocations": 1, "status": "PHYSICAL_ATTEMPT_STARTED"})
    manifest.update({"status": "PHYSICAL_ATTEMPT_STARTED", "provider_calls": 1,
        "attempts": [attempt]})
    results.update({"campaign_state": "PHYSICAL_ATTEMPT_STARTED", "provider_calls": 1,
        "local_transport_invocations": 1, "attempts": [attempt]})
    campaign._write_atomic(run_dir / "execution-manifest.json", campaign._canonical(manifest) + b"\n")
    campaign._write_atomic(run_dir / "execution-results.json", campaign._canonical(results) + b"\n")
    campaign._write_atomic(run_dir / "attempts" / "01-attempt.json", campaign._canonical(attempt) + b"\n")
    with (run_dir / "transport-audit.jsonl").open("ab") as audit:
        audit.write(campaign._canonical({"event": "one_authorized_provider_post_invoked", **attempt}) + b"\n")
        audit.flush()
        os.fsync(audit.fileno())

    client = OpenAIHTTPStandardClient()
    try:
        response = client.create_response_once(prepared["body_bytes"],
            client_request_id=attempt["client_request_id"], request_started_at=started.isoformat())
    except StandardTransportError as exc:
        provider_posts = 1 if exc.ambiguous or exc.response_headers_received else 0
        if exc.raw_bytes is not None:
            campaign._write_atomic(run_dir / "responses" / "01-error.bin", exc.raw_bytes)
        attempt.update({"provider_posts": provider_posts,
            "local_transport_invocations": 1, "status": "AMBIGUOUS_PHYSICAL_ATTEMPT" if exc.ambiguous else "TRANSPORT_FAILURE",
            "transport_state": exc.transport_state, "http_status": exc.status_code,
            "server_request_id": exc.request_id, "response_headers_received": exc.response_headers_received,
            "exception_type": exc.exception_type, "cause_type": exc.cause_type,
            "error_number": exc.error_number, "exception": str(exc),
            "raw_error_body_sha256": campaign._sha(exc.raw_bytes) if exc.raw_bytes is not None else None,
            "elapsed_seconds": exc.elapsed_seconds})
        if exc.ambiguous:
            state = "FIRST_SEMANTIC_REQUEST_AMBIGUOUS_CAMPAIGN_STOPPED"
        elif provider_posts == 0:
            state = "PRE_SEND_TRANSPORT_FAILURE_CAMPAIGN_STOPPED"
        else:
            state = "FIRST_SEMANTIC_REQUEST_PROVIDER_REJECTION_CAMPAIGN_STOPPED"
        return _persist_final(run_dir, manifest, results, attempt, state, None)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"[:1000]
        attempt.update({"provider_posts": 1, "local_transport_invocations": 1,
            "status": "AMBIGUOUS_PHYSICAL_ATTEMPT", "exception_type": type(exc).__name__,
            "cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None,
            "exception": detail, "response_headers_received": False})
        return _persist_final(run_dir, manifest, results, attempt,
            "FIRST_SEMANTIC_REQUEST_AMBIGUOUS_CAMPAIGN_STOPPED", None)

    raw = response.raw_bytes
    campaign._write_atomic(run_dir / "responses" / "01-response.json", raw)
    usage = response.body.get("usage") or {}
    try:
        actual_usd, actual_aud = standard_actual_cost(usage, AUD_PER_USD_RESERVED, model="gpt-5.6-luna")
        cost_error = None
    except Exception as exc:
        actual_usd = actual_aud = None
        cost_error = f"{type(exc).__name__}: {exc}"[:500]

    parsed = None
    validation_error = None
    try:
        if (not 200 <= response.status_code < 300 or response.body.get("status") != "completed"
                or response.body.get("incomplete_details") is not None):
            raise ValueError("provider response was not completed")
        if response.body.get("model") != "gpt-5.6-luna":
            raise ValueError("served model identity differs from the frozen Luna request")
        output_text = _output_text(response.body)
        if not output_text:
            raise ValueError("completed response has no structured output text")
        packet = json.loads(output_text)
        row = prepared["row"]
        validation_row = {"slice_id": row["slice_id"], "subject_id": row["subject_id"],
            "allowed_scope": row["allowed_scope"], "allowed_locators": row["allowed_locators"],
            "source_metadata": [{"evidence_locator_id": s["evidence_locator_id"],
                "source_role": s["source_role"], "source_date": None, "retrieved_at": None}
                for s in prepared["task"]["sources"]],
            "source_texts": [s["exact_transmitted_representation"] for s in prepared["task"]["sources"]]}
        parsed = _validate_v6_packet(validation_row, prepared["task"], packet)
    except Exception as exc:
        validation_error = f"{type(exc).__name__}: {exc}"[:1200]
    mechanical = "MECHANICAL_PASS" if parsed is not None else "MECHANICAL_FAIL"
    response_meta = {"status": mechanical, "http_status": response.status_code,
        "response_id": response.body.get("id"), "server_request_id": response.server_request_id,
        "provider_model": response.body.get("model"), "response_headers_received": True,
        "request_started_at": response.request_started_at or started.isoformat(),
        "elapsed_seconds": response.elapsed_seconds, "response_body_sha256": campaign._sha(raw),
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "usage": usage, "actual_cost_usd": str(actual_usd) if actual_usd is not None else None,
        "actual_cost_aud": str(actual_aud) if actual_aud is not None else None,
        "cost_error": cost_error, "mechanical_validation": mechanical,
        "validation_error": validation_error,
        "conservative_reserved_exposure_aud": str(prepared["exposure"])}
    attempt.update(response_meta)
    attempt["provider_posts"] = 1
    state = ("FIRST_SEMANTIC_REQUEST_COMPLETED_AWAITING_NEXT_EXECUTION_AUTHORITY"
        if mechanical == "MECHANICAL_PASS" and cost_error is None
        else "FIRST_SEMANTIC_REQUEST_COMPLETED_WITH_MECHANICAL_FAILURE_AWAITING_PRODUCT_OWNER_DECISION")
    packet_record = None
    if parsed is not None:
        governed = campaign._json(prepared["paths"]["adjudicated"] / "governed-items.json")
        coverage = [{"item_id": item["item_id"], "coverage_state": item["coverage_state"],
            "coverage_proposition_type": item["governed_proposition_type"],
            "reviewed_evidence_universe_id": item["reviewed_evidence_universe_id"]}
            for item in governed["coverage_items"] if item["subject_id"] == row["subject_id"]]
        packet_record = campaign._human_packet(row, parsed, prepared["task"], response_meta, coverage)
        campaign._write_atomic(run_dir / "human-adjudication-packet" / "01-28004778081.json",
            campaign._canonical(packet_record) + b"\n")
        packet_record = {"proposition_count": len(parsed.propositions),
            "candidate_coverage_count": 0, "packet_items": len(parsed.propositions)}
    results.update({"campaign_state": state, "provider_calls": 1,
        "local_transport_invocations": 1, "source_acquisitions": 0,
        "semantic_governed_promotions": 0,
        "candidate_propositions": len(parsed.propositions) if parsed is not None else 0,
        "candidate_coverage_count": 0,
        "mechanical_validation": mechanical, "validation_error": validation_error,
        "attempts": [attempt], "candidate_packet": packet_record,
        "actual_cost_usd": response_meta["actual_cost_usd"],
        "actual_cost_aud": response_meta["actual_cost_aud"],
        "conservative_exposure_aud": str(prepared["exposure"]),
        "remaining_four_requests": "FROZEN_UNSENT_NOT_AUTHORIZED"})
    manifest.update({"status": state, "provider_calls": 1,
        "candidate_propositions": results["candidate_propositions"],
        "attempts": [attempt], "completed_at": datetime.now(timezone.utc).isoformat()})
    campaign._write_atomic(run_dir / "attempts" / "01-attempt.json", campaign._canonical(attempt) + b"\n")
    campaign._write_atomic(run_dir / "execution-results.json", campaign._canonical(results) + b"\n")
    campaign._write_atomic(run_dir / "execution-manifest.json", campaign._canonical(manifest) + b"\n")
    return results


def _persist_final(run_dir: Path, manifest: dict[str, Any], results: dict[str, Any],
                   attempt: dict[str, Any], state: str, unused: Any) -> dict[str, Any]:
    posts = attempt["provider_posts"]
    attempt["campaign_state"] = state
    results.update({"campaign_state": state, "provider_calls": posts,
        "local_transport_invocations": 1, "source_acquisitions": 0,
        "semantic_governed_promotions": 0, "candidate_propositions": 0,
        "candidate_coverage_count": 0, "attempts": [attempt],
        "actual_cost_usd": "0", "actual_cost_aud": "0",
        "conservative_exposure_aud": str(attempt["conservative_reserved_exposure_aud"] if posts else Decimal("0")),
        "remaining_four_requests": "FROZEN_UNSENT_NOT_AUTHORIZED"})
    manifest.update({"status": state, "provider_calls": posts, "attempts": [attempt],
        "completed_at": datetime.now(timezone.utc).isoformat()})
    campaign._write_atomic(run_dir / "attempts" / "01-attempt.json", campaign._canonical(attempt) + b"\n")
    campaign._write_atomic(run_dir / "execution-results.json", campaign._canonical(results) + b"\n")
    campaign._write_atomic(run_dir / "execution-manifest.json", campaign._canonical(manifest) + b"\n")
    return results


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    data = repo.parent / "charitygraph-data"
    print(json.dumps(execute(repo, data), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
