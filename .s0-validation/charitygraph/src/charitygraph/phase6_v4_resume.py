"""Sequential, ambiguity-isolating continuation for the frozen Phase 6 V4 packet.

The execution manifest and request bytes are immutable. Continuation events,
trace identifiers, raw responses and review material live in a sibling folder.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .openai_client import _output_text
from .phase5_openai_dry_run import standard_actual_cost
from .phase5_standard_transport import (
    OpenAIHTTPStandardClient,
    StandardTransportError,
    body_sha256,
    canonical_standard_body_bytes,
    client_request_id_for_physical_attempt,
)
from .phase6_confirmation import (
    AUD_PER_USD,
    CONTRACT_VERSION,
    MODEL,
    PER_REQUEST_LIMIT_AUD,
    PROVIDER_SCHEMA_VERSION,
    REASONING_EFFORT,
    _canonical,
    _mechanical_validate,
    _sha,
    certify_provider_schema,
)

PINNED_EXECUTION_MANIFEST_SHA256 = "8671fac5be0755617ae60a2d1b947ff2418461e9bd8959af86e6c33ec2d85fee"
PINNED_CONDITION_A_MANIFEST_SHA256 = "a85b99f5f786c30df1cf5817e2fca6080487071161d97e63140819bd4bdbdad5"
PINNED_ATTESTATION_SHA256 = "e64a9edf536c26c3240f60ebc29f59a97781810f43d619a8d090f46133ef19eb"
PINNED_RIGHTS_DECISIONS_SHA256 = "d8b28cf5dd5fff4ea1be46524dd1ff55cb96fb131953e6f6e7e31491605a59af"
PINNED_RIGHTS_LINEAGE_FILE_SHA256 = "03d613e6a40ceb9e7dffed0084182f59669bf97b38e59c12c20c168e6d43d94b"
CAMPAIGN_ID = "phase6-corrected-confirmation-20260913-v4-rights-minimized"
CONTINUATION_ID = "continuation-2026-09-13-client-request-id"
ENDPOINT = "https://api.openai.com/v1/responses"
AGGREGATE_LIMIT_AUD = Decimal("1.50")
PRIOR_AMBIGUOUS_REQUEST_ID = "requestitem:247cea23c9565b92cc82da50e146dea4a93d7c77bbdd5fad467cacdd77dd82de"
PRIOR_SMITH_REPEAT_REQUEST_ID = "requestitem:c2b58b6694ddd7fa91bf2fb2c9046e8080b052ff81e007f3536183d5dbc06890"
AUTHORIZED_REMAINING = (
    ("outcomes", "28000030179", 2),
    ("outcomes", "28004778081", 1),
    ("outcomes", "78053639115", 1),
    ("commitments", "65159324697", 1),
    ("commitments", "50169561394", 1),
    ("commitments", "61002643852", 1),
    ("commitments", "61002643852", 2),
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append_fsynced(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(_canonical(record) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _source_task_map(condition_a_dir: Path) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    manifest_path = condition_a_dir / "manifest.json"
    raw = manifest_path.read_bytes()
    if _sha(raw) != PINNED_CONDITION_A_MANIFEST_SHA256:
        raise ValueError("V4 Condition A manifest identity changed")
    manifest = json.loads(raw.decode("utf-8"))
    tasks: dict[tuple[str, str], dict[str, Any]] = {}
    for item in manifest.get("tasks", []):
        task_raw = (condition_a_dir / item["path"]).read_bytes()
        if _sha(task_raw) != item["task_sha256"]:
            raise ValueError("V4 Condition A task bytes differ from the pinned manifest")
        task = json.loads(task_raw.decode("utf-8"))
        key = (task["slice_id"], task["abn"])
        if key in tasks:
            raise ValueError("V4 Condition A task identity is duplicated")
        tasks[key] = task
    return manifest, tasks


def _ensure_transport_columns(db: sqlite3.Connection) -> None:
    present = {row[1] for row in db.execute("PRAGMA table_info(tickets)")}
    additions = {
        "client_request_id": "TEXT",
        "endpoint": "TEXT",
        "response_headers_received": "INTEGER",
        "server_request_id": "TEXT",
        "transport_exception": "TEXT",
        "transport_state": "TEXT",
        "transport_exception_type": "TEXT",
        "transport_cause_type": "TEXT",
        "transport_errno": "INTEGER",
        "transport_elapsed_seconds": "REAL",
        "actual_cost_usd": "TEXT",
        "actual_cost_aud": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in present:
            db.execute(f"ALTER TABLE tickets ADD COLUMN {name} {sql_type}")


def recertify_v4(run_dir: Path, campaign_dir: Path, *, prior_ambiguous_request_ids: tuple[str, ...] = (PRIOR_AMBIGUOUS_REQUEST_ID,), prior_response_continuation_dir: Path | None = None) -> dict[str, Any]:
    """Recheck exact identities, rights, route and remaining-ticket state offline."""
    prior_ambiguous_ids = set(prior_ambiguous_request_ids)
    if PRIOR_AMBIGUOUS_REQUEST_ID not in prior_ambiguous_ids or not prior_ambiguous_ids <= {PRIOR_AMBIGUOUS_REQUEST_ID, PRIOR_SMITH_REPEAT_REQUEST_ID}:
        raise ValueError("only the two retained Smith ambiguities may be excluded as prior crossings")
    manifest_path = run_dir / "execution-manifest.json"
    manifest_raw = manifest_path.read_bytes()
    if _sha(manifest_raw) != PINNED_EXECUTION_MANIFEST_SHA256:
        raise ValueError("V4 execution manifest does not match its pinned hash")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if manifest.get("run_id") != CAMPAIGN_ID or manifest.get("condition_a_manifest_sha256") != PINNED_CONDITION_A_MANIFEST_SHA256:
        raise ValueError("V4 campaign or Condition A lineage mismatch")
    if (manifest.get("model"), manifest.get("reasoning_effort"), manifest.get("delivery_mode")) != (MODEL, REASONING_EFFORT, "standard"):
        raise ValueError("V4 model route differs from authorization")
    attestation_raw = (run_dir / "provider-policy-attestation.json").read_bytes()
    if _sha(attestation_raw) != PINNED_ATTESTATION_SHA256:
        raise ValueError("provider-policy attestation bytes differ from the recorded owner attestation")
    attestation = json.loads(attestation_raw.decode("utf-8"))
    if attestation.get("setting") != "Share inputs and outputs with OpenAI" or attestation.get("observed_value") != "Disabled":
        raise ValueError("provider-policy attestation does not satisfy the authorized gate")

    sufficiency = _read_json(campaign_dir / "v4-sufficiency-and-lineage.json")
    rights_raw = (campaign_dir / "v4-artifact-rights-lineage.json").read_bytes()
    if _sha(rights_raw) != PINNED_RIGHTS_LINEAGE_FILE_SHA256:
        raise ValueError("V4 artifact rights lineage file bytes changed")
    rights = json.loads(rights_raw.decode("utf-8"))
    if sufficiency.get("condition_a_v4_manifest_sha256") != PINNED_CONDITION_A_MANIFEST_SHA256 or sufficiency.get("rights_decisions_sha256") != PINNED_RIGHTS_DECISIONS_SHA256:
        raise ValueError("V4 sufficiency registry lineage changed")
    if manifest.get("rights_decisions_sha256") != PINNED_RIGHTS_DECISIONS_SHA256 or rights.get("rights_decisions_sha256") != PINNED_RIGHTS_DECISIONS_SHA256:
        raise ValueError("V4 rights decision identity changed")
    if rights.get("policy_id") != "AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1":
        raise ValueError("V4 rights policy identity changed")
    rights_by_representation = {
        (item["source_artifact_id"], item["representation_sha256"]): item
        for item in rights.get("artifacts", [])
    }
    condition_a, source_tasks = _source_task_map(campaign_dir / "condition-a-v4-source-only")
    if condition_a.get("provider_calls") != 0 or condition_a.get("source_acquisitions") != 0:
        raise ValueError("V4 Condition A material records unexpected external activity")

    expected = set(AUTHORIZED_REMAINING) | {("outcomes", "28000030179", 1)}
    seen = set()
    rows_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    total_reserved = Decimal("0")
    for row in manifest.get("tasks", []):
        key = (row["slice_id"], row["abn"], row["replicate_ordinal"])
        if key in seen:
            raise ValueError("V4 campaign contains duplicate physical-attempt identity")
        seen.add(key)
        rows_by_key[key] = row
        if (row.get("model"), row.get("reasoning_effort"), row.get("delivery_mode")) != (MODEL, REASONING_EFFORT, "standard"):
            raise ValueError("V4 request route mismatch")
        if Decimal(row["conservative_exposure_aud"]) > Decimal(PER_REQUEST_LIMIT_AUD):
            raise ValueError("V4 request exceeds its approved conservative per-request limit")
        request_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        request_raw = request_path.read_bytes()
        if body_sha256(request_raw) != row["request_body_sha256"]:
            raise ValueError("V4 certified request bytes changed")
        body = json.loads(request_raw.decode("utf-8"))
        if canonical_standard_body_bytes(body) != request_raw:
            raise ValueError("V4 request serialization changed")
        if body.get("model") != MODEL or body.get("reasoning", {}).get("effort") != REASONING_EFFORT or body.get("max_output_tokens") != row["max_output_tokens"]:
            raise ValueError("V4 request body model/output route mismatch")
        if body.get("metadata", {}).get("logical_task_id") != row["logical_task_id"] or body.get("metadata", {}).get("semantic_contract_hash") != row["semantic_contract_hash"]:
            raise ValueError("V4 request contract identity mismatch")
        prompt = body.get("input", [{}])[0].get("content", [{}])[0].get("text")
        if not isinstance(prompt, str) or _sha(prompt.encode("utf-8")) != row["prompt_sha256"]:
            raise ValueError("V4 request prompt hash mismatch")
        expected_contract_hash = _sha(_canonical({
            "builder_commit": manifest["builder_contract_commit"],
            "contract": row["contract_version"],
            "supersedes": row["supersedes_contract_version"],
            "slice_id": row["slice_id"],
            "schema_sha256": row["schema_sha256"],
            "prompt_sha256": row["prompt_sha256"],
        }))
        if expected_contract_hash != row["semantic_contract_hash"]:
            raise ValueError("V4 semantic contract hash does not bind the frozen prompt/schema")
        text_format = body.get("text", {}).get("format", {})
        schema = text_format.get("schema")
        if text_format.get("type") != "json_schema" or text_format.get("strict") is not True or text_format.get("name") != row["provider_schema_name"]:
            raise ValueError("V4 strict provider schema identity mismatch")
        certification = certify_provider_schema(schema, contract_version=row["contract_version"])
        if certification.get("schema_sha256") != row["schema_sha256"] or row["schema_sha256"] != row["schema_certification"].get("schema_sha256"):
            raise ValueError("V4 provider schema hash/certification mismatch")
        task = source_tasks.get((row["slice_id"], row["abn"]))
        if task is None or task.get("condition") != "A_source_only" or task.get("allowed_scope_ids") != [row["allowed_scope"]]:
            raise ValueError("V4 Condition A task or legal organization scope mismatch")
        condition_item = next((item for item in condition_a["tasks"] if item["task_id"] == task["task_id"]), None)
        if condition_item is None or condition_item["task_sha256"] != row["source_export_task_sha256"]:
            raise ValueError("V4 Condition A source task hash mismatch")
        source_hashes = [_sha(source["exact_transmitted_representation"].encode("utf-8")) for source in task["sources"]]
        if source_hashes != row["source_content_sha256"]:
            raise ValueError("V4 frozen source representation hash mismatch")
        locators = [source["evidence_locator_id"] for source in task["sources"]]
        roles = [{"evidence_locator_id": source["evidence_locator_id"], "source_role": source["source_role"]} for source in task["sources"]]
        if locators != row["allowed_locators"] or roles != row["source_metadata"]:
            raise ValueError("V4 evidence locator/source-role allow-list mismatch")
        for source in task["sources"]:
            artifact = rights_by_representation.get((source["source_artifact_id"], source["evidence_representation_sha256"]))
            if artifact is None or artifact.get("provider_transmission_allowed") is not True or artifact.get("rights_policy_id") != "AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1" or artifact.get("provider_processing_policy_id") != "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1":
                raise ValueError("V4 source artifact no longer has an exact authorized rights decision")
            if artifact.get("source_record_id") != source["source_record_id"] or artifact.get("source_role") != source["source_role"] or artifact.get("source_origin_url") != source["source_locator"]:
                raise ValueError("V4 source artifact acquisition identity/role differs from the frozen packet")
        total_reserved += Decimal(row["conservative_exposure_aud"])
    if seen != expected:
        raise ValueError("V4 certified attempt set differs from the exact authorized eight-attempt set")
    if total_reserved != Decimal(manifest["conservative_exposure_total_aud"]):
        raise ValueError("V4 conservative exposure sum differs from the frozen campaign total")
    if total_reserved > AGGREGATE_LIMIT_AUD:
        raise ValueError("V4 total conservative exposure exceeds the AUD 1.50 ceiling")

    db_path = run_dir / "tickets.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        _ensure_transport_columns(db)
        tickets = {row["request_item_id"]: dict(row) for row in db.execute("SELECT * FROM tickets")}
    if len(tickets) != 8:
        raise ValueError("V4 execution ledger ticket count changed")
    ambiguous = tickets.get(PRIOR_AMBIGUOUS_REQUEST_ID)
    if ambiguous is None or ambiguous["state"] != "ambiguous" or ambiguous["provider_posts"] != 1 or ambiguous["response_id"] is not None or ambiguous["provider_request_id"] is not None:
        raise ValueError("historical Smith physical attempt is not preserved as ambiguous")
    if ambiguous["client_request_id"] is not None:
        raise ValueError("historical Smith client trace ID cannot be invented retrospectively")
    if PRIOR_SMITH_REPEAT_REQUEST_ID in prior_ambiguous_ids:
        smith_repeat = tickets.get(PRIOR_SMITH_REPEAT_REQUEST_ID)
        repeat_row = next((row for row in manifest["tasks"] if row["request_item_id"] == PRIOR_SMITH_REPEAT_REQUEST_ID), None)
        if repeat_row is None or smith_repeat is None or smith_repeat["physical_attempt_id"] != repeat_row["physical_attempt_id"] or smith_repeat["request_body_sha256"] != repeat_row["request_body_sha256"] or smith_repeat["state"] != "ambiguous" or smith_repeat["provider_posts"] != 1 or smith_repeat["response_id"] is not None or smith_repeat["provider_request_id"] is not None:
            raise ValueError("second historical Smith attempt is not preserved exactly as ambiguous")
        if smith_repeat["client_request_id"] != client_request_id_for_physical_attempt(repeat_row["physical_attempt_id"]) or smith_repeat["response_headers_received"] not in (0, None):
            raise ValueError("second historical Smith trace or no-header status changed")
    with sqlite3.connect(db_path) as db:
        observed_ambiguous_ids = {row[0] for row in db.execute("SELECT request_item_id FROM tickets WHERE state='ambiguous'")}
    if observed_ambiguous_ids != prior_ambiguous_ids:
        raise ValueError("V4 ambiguous-ticket set differs from the explicitly retained Smith attempts")
    prior_response_outcomes: dict[str, dict[str, Any]] = {}
    if prior_response_continuation_dir is not None:
        prior_results_path = prior_response_continuation_dir / "execution-results.json"
        prior_ledger_path = prior_response_continuation_dir / "recertification.json"
        if not prior_results_path.is_file() or not prior_ledger_path.is_file():
            raise ValueError("prior response continuation lacks its durable execution result or recertification")
        prior_ledger = _read_json(prior_ledger_path)
        prior_results = _read_json(prior_results_path)
        if prior_results.get("continuation_id") != prior_ledger.get("continuation_id") or prior_ledger.get("execution_manifest_sha256") != PINNED_EXECUTION_MANIFEST_SHA256:
            raise ValueError("prior response continuation lineage does not match the frozen campaign")
        prior_schedule = {item["request_item_id"]: item for item in prior_ledger.get("scheduled_attempts", [])}
        for outcome in prior_results.get("outcomes", []):
            if not outcome.get("provider_posts"):
                continue
            request_id = outcome.get("request_item_id")
            row = next((item for item in manifest["tasks"] if item["request_item_id"] == request_id), None)
            prior_attempt = prior_schedule.get(request_id)
            expected_client_id = None if row is None else client_request_id_for_physical_attempt(row["physical_attempt_id"])
            if row is None or prior_attempt is None or prior_attempt.get("physical_attempt_id") != row["physical_attempt_id"] or prior_attempt.get("client_request_id") != expected_client_id or outcome.get("client_request_id") != expected_client_id or request_id in prior_ambiguous_ids or outcome.get("state") not in {"completed_parse_failed", "completed", "completed_economic_stop"}:
                raise ValueError("prior response continuation contains an unrecognized or ambiguous crossing")
            ticket = tickets.get(request_id)
            if ticket is None or ticket["physical_attempt_id"] != row["physical_attempt_id"] or ticket["request_body_sha256"] != row["request_body_sha256"] or ticket["state"] != outcome["state"] or ticket["provider_posts"] != 1 or ticket["response_id"] != outcome.get("response_id") or ticket["provider_request_id"] != outcome.get("server_x_request_id"):
                raise ValueError("prior provider response ticket differs from its recorded execution outcome")
            stem = request_id.replace(":", "_")
            transport = _read_json(prior_response_continuation_dir / "transport" / f"{stem}.json")
            raw = (prior_response_continuation_dir / "responses" / f"{stem}.json").read_bytes()
            response_body = json.loads(raw.decode("utf-8"))
            if transport.get("client_request_id") != expected_client_id or transport.get("state") != "PROVIDER_RESPONSE_RECEIVED" or transport.get("response_body_sha256") != _sha(raw) or transport.get("response_id") != outcome.get("response_id") or response_body.get("id") != outcome.get("response_id") or response_body.get("model") != MODEL or transport.get("provider_model_identity") != MODEL:
                raise ValueError("prior provider response bytes or model identity failed continuity verification")
            if request_id in prior_response_outcomes:
                raise ValueError("prior continuation repeats a physical request outcome")
            prior_response_outcomes[request_id] = outcome
    ready: list[dict[str, Any]] = []
    for key in AUTHORIZED_REMAINING:
        row = rows_by_key[key]
        if row["request_item_id"] in prior_ambiguous_ids:
            continue
        if row["request_item_id"] in prior_response_outcomes:
            continue
        ticket = tickets.get(row["request_item_id"])
        if ticket is None or ticket["physical_attempt_id"] != row["physical_attempt_id"] or ticket["request_body_sha256"] != row["request_body_sha256"]:
            raise ValueError("V4 request ticket identity/body hash mismatch")
        if ticket["state"] != "prepared" or ticket["provider_posts"] != 0 or ticket["response_id"] is not None:
            raise ValueError("remaining V4 physical attempt is not uniquely unused")
        row = dict(row)
        row["body_path"] = str(run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json")
        row["task"] = source_tasks[(row["slice_id"], row["abn"])]
        row["body"] = json.loads(Path(row["body_path"]).read_bytes().decode("utf-8"))
        ready.append(row)
    remaining_reserved = sum((Decimal(row["conservative_exposure_aud"]) for row in ready), Decimal("0"))
    ambiguous_reserve = sum((Decimal(rows_by_key[key]["conservative_exposure_aud"]) for key in rows_by_key if rows_by_key[key]["request_item_id"] in prior_ambiguous_ids), Decimal("0"))
    prior_response_reserve = sum((Decimal(row["conservative_exposure_aud"]) for row in manifest["tasks"] if row["request_item_id"] in prior_response_outcomes), Decimal("0"))
    if ambiguous_reserve + prior_response_reserve + remaining_reserved > AGGREGATE_LIMIT_AUD:
        raise ValueError("ambiguous Smith reserve plus all remaining worst-case costs exceeds campaign ceiling")
    return {
        "manifest": manifest,
        "rows": ready,
        "tickets": tickets,
        "ambiguous_exposure_reserved_aud": str(ambiguous_reserve),
        "prior_response_request_ids": sorted(prior_response_outcomes),
        "prior_response_exposure_reserved_aud": str(prior_response_reserve),
        "prior_ambiguous_request_ids": sorted(prior_ambiguous_ids),
        "remaining_exposure_reserved_aud": str(remaining_reserved),
        "campaign_worst_case_aud": str(ambiguous_reserve + prior_response_reserve + remaining_reserved),
        "campaign_ceiling_aud": str(AGGREGATE_LIMIT_AUD),
        "provider_calls": 0,
        "source_acquisitions": 0,
    }


def _adapter_row(row: dict[str, Any]) -> dict[str, Any]:
    task = row["task"]
    return {
        **row,
        "source_texts": [source["exact_transmitted_representation"] for source in task["sources"]],
    }


def _transport_meta_path(root: Path, request_item_id: str) -> Path:
    return root / "transport" / f"{request_item_id.replace(':', '_')}.json"


def _build_support_packet(*, row: dict[str, Any], client_request_id: str | None, endpoint: str, request_started_at: str | None, transport_exception: str | None, response_headers_received: bool, server_request_id: str | None) -> dict[str, Any]:
    return {
        "status": "prepared_for_manual_support_lookup_only",
        "support_contacted": False,
        "client_request_id": client_request_id,
        "request_item_id": row["request_item_id"],
        "physical_attempt_id": row["physical_attempt_id"],
        "endpoint": endpoint,
        "project_reference": None,
        "organization_reference": None,
        "request_started_at": request_started_at,
        "request_body_sha256": row["request_body_sha256"],
        "model_requested": row["model"],
        "transport_exception": transport_exception,
        "response_headers_received": response_headers_received,
        "server_x_request_id": server_request_id,
        "provider_acceptance": "unknown",
        "billing": "unknown; retain full conservative request exposure",
        "conservative_exposure_aud": row["conservative_exposure_aud"],
        "reconciliation_note": "Manual Support lookup only. The client ID is a trace identifier, not an idempotency key; do not retry this physical attempt.",
    }


def _pre_send_guard(run_dir: Path, campaign_dir: Path, continuation_dir: Path, row: dict[str, Any], expected_client_id: str, *, prior_ambiguous_request_ids: tuple[str, ...]) -> None:
    """Recheck mutable local inputs immediately before this physical POST."""
    if _sha((run_dir / "execution-manifest.json").read_bytes()) != PINNED_EXECUTION_MANIFEST_SHA256:
        raise ValueError("execution manifest changed at the per-request gate")
    if _sha((campaign_dir / "condition-a-v4-source-only" / "manifest.json").read_bytes()) != PINNED_CONDITION_A_MANIFEST_SHA256:
        raise ValueError("Condition A manifest changed at the per-request gate")
    if _sha((run_dir / "provider-policy-attestation.json").read_bytes()) != PINNED_ATTESTATION_SHA256:
        raise ValueError("provider-policy attestation changed at the per-request gate")
    rights_raw = (campaign_dir / "v4-artifact-rights-lineage.json").read_bytes()
    if _sha(rights_raw) != PINNED_RIGHTS_LINEAGE_FILE_SHA256:
        raise ValueError("rights-lineage file bytes changed at the per-request gate")
    rights = json.loads(rights_raw.decode("utf-8"))
    if rights.get("rights_decisions_sha256") != PINNED_RIGHTS_DECISIONS_SHA256:
        raise ValueError("rights-decision lineage changed at the per-request gate")
    task = row["task"]
    decisions = {(item["source_artifact_id"], item["representation_sha256"]): item for item in rights["artifacts"]}
    for source in task["sources"]:
        decision = decisions.get((source["source_artifact_id"], source["evidence_representation_sha256"]))
        if decision is None or decision.get("provider_transmission_allowed") is not True or decision.get("rights_policy_id") != "AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1" or decision.get("provider_processing_policy_id") != "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1" or decision.get("source_record_id") != source["source_record_id"] or decision.get("source_role") != source["source_role"] or decision.get("source_origin_url") != source["source_locator"]:
            raise ValueError("source rights are no longer authorized at the per-request gate")
    body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
    body_bytes = body_path.read_bytes()
    if body_sha256(body_bytes) != row["request_body_sha256"]:
        raise ValueError("certified request bytes changed at the per-request gate")
    body = json.loads(body_bytes.decode("utf-8"))
    if canonical_standard_body_bytes(body) != body_bytes or body.get("model") != MODEL or body.get("reasoning", {}).get("effort") != REASONING_EFFORT:
        raise ValueError("request canonical bytes or route changed at the per-request gate")
    if certify_provider_schema(body["text"]["format"]["schema"], contract_version=row["contract_version"]).get("schema_sha256") != row["schema_sha256"]:
        raise ValueError("provider schema changed at the per-request gate")
    if Decimal(row["conservative_exposure_aud"]) > Decimal(PER_REQUEST_LIMIT_AUD):
        raise ValueError("request cost authority changed at the per-request gate")
    metadata = _read_json(_transport_meta_path(continuation_dir, row["request_item_id"]))
    if metadata.get("client_request_id") != expected_client_id or expected_client_id != client_request_id_for_physical_attempt(row["physical_attempt_id"]):
        raise ValueError("client trace mapping changed at the per-request gate")
    with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
        ticket = db.execute("SELECT state,provider_posts,physical_attempt_id,request_body_sha256,client_request_id FROM tickets WHERE request_item_id=?", (row["request_item_id"],)).fetchone()
        ambiguous_ids = {item[0] for item in db.execute("SELECT request_item_id FROM tickets WHERE state='ambiguous'")}
    if ticket is None or ticket != ("prepared", 0, row["physical_attempt_id"], row["request_body_sha256"], expected_client_id):
        raise ValueError("physical-attempt ticket changed or was previously crossed")
    if ambiguous_ids != set(prior_ambiguous_request_ids):
        raise ValueError("ambiguous provider crossings changed after offline recertification")


def prepare_continuation(run_dir: Path, campaign_dir: Path, continuation_dir: Path, *, continuation_id: str = CONTINUATION_ID, prior_ambiguous_request_ids: tuple[str, ...] = (PRIOR_AMBIGUOUS_REQUEST_ID,), prior_response_continuation_dir: Path | None = None) -> dict[str, Any]:
    """Offline recertify and immutably assign IDs before any resumed POST."""
    cert = recertify_v4(run_dir, campaign_dir, prior_ambiguous_request_ids=prior_ambiguous_request_ids, prior_response_continuation_dir=prior_response_continuation_dir)
    continuation_dir.mkdir(parents=True, exist_ok=True)
    body_records = []
    for row in cert["rows"]:
        client_id = client_request_id_for_physical_attempt(row["physical_attempt_id"])
        body_records.append({
            "request_item_id": row["request_item_id"],
            "physical_attempt_id": row["physical_attempt_id"],
            "request_body_sha256": row["request_body_sha256"],
            "schema_sha256": row["schema_sha256"],
            "source_content_sha256": row["source_content_sha256"],
            "client_request_id": client_id,
            "endpoint": ENDPOINT,
            "state": "NOT_SENT",
        })
    if len({row["client_request_id"] for row in body_records}) != len(body_records):
        raise ValueError("deterministic client request IDs collided")
    recertification_path = continuation_dir / "recertification.json"
    if recertification_path.exists():
        old = _read_json(recertification_path)
        old_ids = [(item.get("request_item_id"), item.get("physical_attempt_id"), item.get("client_request_id")) for item in old.get("scheduled_attempts", [])]
        new_ids = [(item["request_item_id"], item["physical_attempt_id"], item["client_request_id"]) for item in body_records]
        if old.get("continuation_id") != continuation_id or old.get("execution_manifest_sha256") != PINNED_EXECUTION_MANIFEST_SHA256 or old_ids != new_ids:
            raise ValueError("existing continuation has different or changed immutable trace assignments")
        if (continuation_dir / "transport-audit.jsonl").exists():
            raise ValueError("transport execution has begun; continuation preparation cannot be repeated")
    ledger = {
        "continuation_id": continuation_id,
        "campaign_id": CAMPAIGN_ID,
        "execution_manifest_sha256": PINNED_EXECUTION_MANIFEST_SHA256,
        "condition_a_manifest_sha256": PINNED_CONDITION_A_MANIFEST_SHA256,
        "attestation_sha256": PINNED_ATTESTATION_SHA256,
        "rights_decisions_sha256": PINNED_RIGHTS_DECISIONS_SHA256,
        "rights_lineage_file_sha256": PINNED_RIGHTS_LINEAGE_FILE_SHA256,
        "preflight_status": "passed_before_any_resumed_provider_crossing",
        "scheduled_attempts": body_records,
        "prior_ambiguous_request_ids": sorted(prior_ambiguous_request_ids),
        "prior_response_request_ids": cert["prior_response_request_ids"],
        "ambiguous_prior_reserved_exposure_aud": cert["ambiguous_exposure_reserved_aud"],
        "prior_response_reserved_exposure_aud": cert["prior_response_exposure_reserved_aud"],
        "remaining_reserved_exposure_aud": cert["remaining_exposure_reserved_aud"],
        "worst_case_campaign_exposure_aud": cert["campaign_worst_case_aud"],
        "aggregate_limit_aud": str(AGGREGATE_LIMIT_AUD),
        "provider_calls": 0,
        "source_acquisitions": 0,
        "governed_promotions": 0,
    }
    _write_atomic(recertification_path, _canonical(ledger) + b"\n")
    # This is a manual-support template only. No identifier is fabricated for
    # the historic crossing, which was sent before this header was implemented.
    prior = cert["tickets"][PRIOR_AMBIGUOUS_REQUEST_ID]
    prior_row = next(row for row in _read_json(run_dir / "execution-manifest.json")["tasks"] if row["request_item_id"] == PRIOR_AMBIGUOUS_REQUEST_ID)
    support = _build_support_packet(row=prior_row, client_request_id=None, endpoint=ENDPOINT, request_started_at=prior["send_started_at"], transport_exception=prior["failure_message"], response_headers_received=False, server_request_id=None)
    support["reconciliation_note"] = "No X-Client-Request-Id was transmitted; do not invent one retrospectively. Do not retry this physical attempt."
    _write_atomic(continuation_dir / "openai-support-reconciliation-packet.json", _canonical(support) + b"\n")
    db_path = run_dir / "tickets.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        _ensure_transport_columns(db)
        db.execute("BEGIN IMMEDIATE")
        for item in body_records:
            old = db.execute("SELECT state,provider_posts,client_request_id FROM tickets WHERE request_item_id=? AND physical_attempt_id=?", (item["request_item_id"], item["physical_attempt_id"])).fetchone()
            if old is None or old["state"] != "prepared" or old["provider_posts"] != 0:
                db.execute("ROLLBACK")
                raise ValueError("ticket changed after offline certification")
            if old["client_request_id"] not in (None, item["client_request_id"]):
                db.execute("ROLLBACK")
                raise ValueError("physical attempt already has a different client request ID")
            db.execute("UPDATE tickets SET client_request_id=?,endpoint=?,transport_state='NOT_SENT' WHERE request_item_id=? AND state='prepared' AND provider_posts=0", (item["client_request_id"], ENDPOINT, item["request_item_id"]))
        db.commit()
    for item in body_records:
        _write_atomic(_transport_meta_path(continuation_dir, item["request_item_id"]), _canonical(item) + b"\n")
    return ledger


def _write_candidate(continuation_dir: Path, row: dict[str, Any], response: Any, output: Any, usage: dict[str, Any], cost_usd: Decimal | None, cost_aud: Decimal | None, client_id: str, continuation_id: str) -> dict[str, Any]:
    candidate = {
        "candidate_status": "unreviewed_mechanical_candidate",
        "campaign_id": CAMPAIGN_ID,
        "continuation_id": continuation_id,
        "slice_id": row["slice_id"],
        "subject_id": row["subject_id"],
        "abn": row["abn"],
        "logical_task_id": row["logical_task_id"],
        "physical_attempt_id": row["physical_attempt_id"],
        "request_item_id": row["request_item_id"],
        "client_request_id": client_id,
        "server_x_request_id": response.server_request_id,
        "response_id": response.body.get("id"),
        "model_identity": response.body.get("model"),
        "contract_version": row["contract_version"],
        "semantic_contract_hash": row["semantic_contract_hash"],
        "request_body_sha256": row["request_body_sha256"],
        "schema_sha256": row["schema_sha256"],
        "source_content_sha256": row["source_content_sha256"],
        "rights_decisions_sha256": PINNED_RIGHTS_DECISIONS_SHA256,
        "provider_policy_attestation_sha256": PINNED_ATTESTATION_SHA256,
        "response_body_sha256": _sha(response.raw_bytes),
        "usage": usage,
        "actual_cost_usd": None if cost_usd is None else str(cost_usd),
        "actual_cost_aud": None if cost_aud is None else str(cost_aud),
        "propositions": [item.model_dump(mode="json") for item in output.propositions],
        "reviewer_dispositions": [],
    }
    path = continuation_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json"
    _write_atomic(path, _canonical(candidate) + b"\n")
    return candidate


def _atomic_db_update(db_path: Path, sql: str, args: tuple[Any, ...]) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(sql, args)
        db.commit()


def execute_continuation(run_dir: Path, campaign_dir: Path, continuation_dir: Path, *, client: Any | None = None, continuation_id: str = CONTINUATION_ID, prior_ambiguous_request_ids: tuple[str, ...] = (PRIOR_AMBIGUOUS_REQUEST_ID,), prior_response_continuation_dir: Path | None = None) -> dict[str, Any]:
    """Execute the recertified unused tickets serially; any new ambiguity stops all."""
    if not (continuation_dir / "recertification.json").is_file():
        raise ValueError("continuation must be prepared and offline-certified first")
    cert = recertify_v4(run_dir, campaign_dir, prior_ambiguous_request_ids=prior_ambiguous_request_ids, prior_response_continuation_dir=prior_response_continuation_dir)
    ledger = _read_json(continuation_dir / "recertification.json")
    expected_schedule = [(row["request_item_id"], row["physical_attempt_id"], client_request_id_for_physical_attempt(row["physical_attempt_id"])) for row in cert["rows"]]
    ledger_schedule = [(item.get("request_item_id"), item.get("physical_attempt_id"), item.get("client_request_id")) for item in ledger.get("scheduled_attempts", [])]
    if ledger.get("continuation_id") != continuation_id or ledger.get("prior_ambiguous_request_ids") != sorted(prior_ambiguous_request_ids) or ledger.get("prior_response_request_ids") != cert["prior_response_request_ids"] or ledger_schedule != expected_schedule or ledger.get("execution_manifest_sha256") != PINNED_EXECUTION_MANIFEST_SHA256 or ledger.get("preflight_status") != "passed_before_any_resumed_provider_crossing":
        raise ValueError("continuation recertification lineage/status is invalid")
    db_path = run_dir / "tickets.sqlite3"
    client = client or OpenAIHTTPStandardClient()
    if not os.environ.get("OPENAI_API_KEY") and isinstance(client, OpenAIHTTPStandardClient):
        raise RuntimeError("OPENAI_API_KEY unavailable; no resumed provider attempt started")
    result_path = continuation_dir / "execution-results.json"
    if result_path.exists():
        raise FileExistsError("continuation result already exists; refusing replay or overwrite")
    outcomes: list[dict[str, Any]] = []
    new_ambiguity = False
    economic_stop = False
    actual_cost_known = Decimal("0")
    actual_cost_known_usd = Decimal("0")
    if prior_response_continuation_dir is not None:
        prior_result = _read_json(prior_response_continuation_dir / "execution-results.json")
        actual_cost_known += sum((Decimal(item["actual_cost_aud"]) for item in prior_result["outcomes"] if item.get("provider_posts") and item.get("actual_cost_aud") is not None), Decimal("0"))
        actual_cost_known_usd += sum((Decimal(item["actual_cost_usd"]) for item in prior_result["outcomes"] if item.get("provider_posts") and item.get("actual_cost_usd") is not None), Decimal("0"))
    accepted = 0
    definitely_rejected = 0
    local_pre_send_failures = 0
    continuation_dir.mkdir(parents=True, exist_ok=True)
    audit_path = continuation_dir / "transport-audit.jsonl"

    for row in cert["rows"]:
        if new_ambiguity:
            outcomes.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_new_ambiguity", "provider_posts": 0})
            continue
        if economic_stop:
            outcomes.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_economic_stop", "provider_posts": 0})
            continue
        meta_path = _transport_meta_path(continuation_dir, row["request_item_id"])
        metadata = _read_json(meta_path)
        expected_client_id = client_request_id_for_physical_attempt(row["physical_attempt_id"])
        if metadata.get("client_request_id") != expected_client_id or metadata.get("state") != "NOT_SENT":
            raise ValueError("pre-recorded client request ID is absent, changed, or already used")
        body_path = Path(row["body_path"])
        _pre_send_guard(run_dir, campaign_dir, continuation_dir, row, expected_client_id, prior_ambiguous_request_ids=prior_ambiguous_request_ids)
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"]:
            raise ValueError("request bytes changed after final recertification")
        started_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        metadata.update({"state": "CROSSING_STARTED", "request_started_at": started_at})
        # ID, ticket, exact hashes, and timestamp are durable before entering
        # urlopen; a process interruption is quarantined and never resent.
        with sqlite3.connect(db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("SELECT state,provider_posts,request_body_sha256,physical_attempt_id,client_request_id FROM tickets WHERE request_item_id=?", (row["request_item_id"],)).fetchone()
            if ticket is None or ticket[0] != "prepared" or ticket[1] != 0 or ticket[2] != row["request_body_sha256"] or ticket[3] != row["physical_attempt_id"] or ticket[4] != expected_client_id:
                db.execute("ROLLBACK")
                raise ValueError("ticket changed or was used after offline recertification")
            db.execute("UPDATE tickets SET state='send_started',transport_state='CROSSING_STARTED',provider_posts=1,send_started_at=?,endpoint=?,transport_exception=NULL WHERE request_item_id=? AND state='prepared'", (started_at, ENDPOINT, row["request_item_id"]))
            db.commit()
        _write_atomic(meta_path, _canonical(metadata) + b"\n")
        _append_fsynced(audit_path, {
            "event": "provider_crossing_started",
            "request_item_id": row["request_item_id"],
            "physical_attempt_id": row["physical_attempt_id"],
            "client_request_id": expected_client_id,
            "endpoint": ENDPOINT,
            "request_started_at": started_at,
            "request_body_sha256": row["request_body_sha256"],
            "schema_sha256": row["schema_sha256"],
            "source_content_sha256": row["source_content_sha256"],
            "rights_decisions_sha256": PINNED_RIGHTS_DECISIONS_SHA256,
            "provider_policy_attestation_sha256": PINNED_ATTESTATION_SHA256,
            "model_requested": MODEL,
        })
        adapter_row = _adapter_row(row)
        try:
            response = client.create_response_once(body_bytes, client_request_id=expected_client_id, request_started_at=started_at)
        except StandardTransportError as exc:
            state = "PROVIDER_CROSSING_AMBIGUOUS" if exc.ambiguous else (
                "PRE_PROVIDER_FAILURE" if exc.transport_state in {"DNS_FAILURE", "CONNECT_FAILURE", "TLS_SETUP_FAILURE", "LOCAL_SOCKET_PERMISSION_DENIED"}
                else ("PROVIDER_RESPONSE_BODY_FAILURE" if exc.response_headers_received else "PROVIDER_REJECTED")
            )
            # Under this campaign authorization only a new ambiguous crossing
            # stops later POSTs. Definite provider outcomes are recorded and
            # the next untouched physical attempt remains eligible.
            if exc.ambiguous:
                new_ambiguity = True
            elif state == "PROVIDER_REJECTED":
                definitely_rejected += 1
            if exc.raw_bytes is not None:
                _write_atomic(continuation_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json", exc.raw_bytes)
            transport = {
                **metadata,
                "state": state,
                "response_headers_received": exc.response_headers_received,
                "server_x_request_id": exc.request_id,
                "transport_exception": str(exc),
                "transport_exception_type": exc.exception_type,
                "transport_cause_type": exc.cause_type,
                "transport_errno": exc.error_number,
                "transport_elapsed_seconds": exc.elapsed_seconds,
                "http_status": exc.status_code,
                "raw_response_sha256": None if exc.raw_bytes is None else _sha(exc.raw_bytes),
            }
            _write_atomic(meta_path, _canonical(transport) + b"\n")
            if exc.ambiguous:
                _write_atomic(continuation_dir / "support-packets" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(_build_support_packet(row=row, client_request_id=expected_client_id, endpoint=ENDPOINT, request_started_at=metadata.get("request_started_at"), transport_exception=str(exc), response_headers_received=exc.response_headers_received, server_request_id=exc.request_id)) + b"\n")
            durable_state = "ambiguous" if exc.ambiguous else ("pre_provider_failure" if state == "PRE_PROVIDER_FAILURE" else ("response_body_failure" if state == "PROVIDER_RESPONSE_BODY_FAILURE" else "provider_rejected"))
            _atomic_db_update(db_path, "UPDATE tickets SET state=?,transport_state=?,provider_posts=CASE WHEN ?='PRE_PROVIDER_FAILURE' THEN 0 ELSE provider_posts END,response_headers_received=?,server_request_id=?,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=?,transport_elapsed_seconds=?,completed_at=? WHERE request_item_id=?", (durable_state, state, state, int(exc.response_headers_received), exc.request_id, str(exc)[:512], exc.exception_type, exc.cause_type, exc.error_number, exc.elapsed_seconds, datetime.now(timezone.utc).isoformat(), row["request_item_id"]))
            _append_fsynced(audit_path, {"event": "provider_crossing_outcome", **transport})
            outcomes.append({"request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "client_request_id": expected_client_id, "state": state, "provider_posts": 0 if state == "PRE_PROVIDER_FAILURE" else 1, "response_headers_received": exc.response_headers_received, "server_x_request_id": exc.request_id, "http_status": exc.status_code, "error": str(exc)[:512], "conservative_exposure_aud": row["conservative_exposure_aud"]})
            if exc.ambiguous:
                new_ambiguity = True
            continue
        except Exception as exc:
            # Any unclassified exception after CROSSING_STARTED is ambiguous.
            new_ambiguity = True
            transport = {**metadata, "state": "PROVIDER_CROSSING_AMBIGUOUS", "response_headers_received": False, "server_x_request_id": None, "transport_exception": f"{type(exc).__name__}: {exc}"[:512], "transport_exception_type": type(exc).__name__, "transport_cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None, "transport_errno": getattr(exc.__cause__ or exc, "errno", None)}
            _write_atomic(meta_path, _canonical(transport) + b"\n")
            _atomic_db_update(db_path, "UPDATE tickets SET state='ambiguous',transport_state=?,response_headers_received=0,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=?,completed_at=? WHERE request_item_id=?", ("PROVIDER_CROSSING_AMBIGUOUS", transport["transport_exception"], transport["transport_exception_type"], transport["transport_cause_type"], transport["transport_errno"], datetime.now(timezone.utc).isoformat(), row["request_item_id"]))
            _append_fsynced(audit_path, {"event": "provider_crossing_outcome", **transport})
            outcomes.append({"request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "client_request_id": expected_client_id, "state": "PROVIDER_CROSSING_AMBIGUOUS", "provider_posts": 1, "response_headers_received": False, "error": transport["transport_exception"], "conservative_exposure_aud": row["conservative_exposure_aud"]})
            continue

        accepted += 1
        response_file = continuation_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json"
        _write_atomic(response_file, response.raw_bytes)
        usage = response.body.get("usage") or {}
        actual_usd = actual_aud = None
        try:
            actual_usd, actual_aud = standard_actual_cost(usage, AUD_PER_USD, model=MODEL)
        except Exception:
            pass
        state = "PROVIDER_RESPONSE_RECEIVED"
        response_meta = {
            **metadata,
            "state": state,
            "response_headers_received": response.response_headers_received,
            "server_x_request_id": response.server_request_id,
            "response_id": response.body.get("id"),
            "provider_model_identity": response.body.get("model"),
            "usage": usage,
            "actual_cost_usd": None if actual_usd is None else str(actual_usd),
            "actual_cost_aud": None if actual_aud is None else str(actual_aud),
            "response_body_sha256": _sha(response.raw_bytes),
        }
        _write_atomic(meta_path, _canonical(response_meta) + b"\n")
        _atomic_db_update(db_path, "UPDATE tickets SET transport_state=?,response_headers_received=?,server_request_id=?,response_id=?,provider_request_id=?,usage_json=?,actual_cost_usd=?,actual_cost_aud=? WHERE request_item_id=?", (state, int(response.response_headers_received), response.server_request_id, response.body.get("id"), response.server_request_id, json.dumps(usage, sort_keys=True), None if actual_usd is None else str(actual_usd), None if actual_aud is None else str(actual_aud), row["request_item_id"]))
        _append_fsynced(audit_path, {"event": "provider_response_received", **response_meta})
        state = "completed"
        failure = None
        output = None
        try:
            if response.body.get("status") != "completed" or response.body.get("incomplete_details") is not None:
                raise ValueError("provider response is not completed")
            if response.body.get("model") != MODEL:
                raise ValueError("provider response model identity differs from pinned model")
            output_text = _output_text(response.body)
            if not output_text:
                raise ValueError("completed response has no structured output text")
            output = _mechanical_validate(adapter_row, json.loads(output_text))
        except Exception as exc:
            state = "completed_parse_failed"
            failure = str(exc)[:512]
            # Keep the exact response as a failed attempt, but do not add a
            # capability stop: the owner authorized continuing after definite
            # responses unless an ambiguity or the economic gate stops us.
        exposure_for_gate = Decimal(row["conservative_exposure_aud"])
        known_cost = actual_aud if actual_aud is not None else exposure_for_gate
        prior_crossed_exposure = sum((
            Decimal(item["actual_cost_aud"]) if item.get("state") == "completed" and item.get("actual_cost_aud") is not None
            else Decimal(item["conservative_exposure_aud"]) if item.get("provider_posts", 0) else Decimal("0")
            for item in outcomes
        ), Decimal("0"))
        projected_worst = Decimal(cert["ambiguous_exposure_reserved_aud"]) + Decimal(cert["prior_response_exposure_reserved_aud"]) + prior_crossed_exposure + known_cost + sum(
            (Decimal(other["conservative_exposure_aud"]) for other in cert["rows"] if other["request_item_id"] not in {item["request_item_id"] for item in outcomes} and other["request_item_id"] != row["request_item_id"]), Decimal("0")
        )
        if actual_aud is not None:
            actual_cost_known += actual_aud
        if actual_usd is not None:
            actual_cost_known_usd += actual_usd
        if (actual_aud is not None and actual_aud > Decimal(PER_REQUEST_LIMIT_AUD)) or projected_worst > AGGREGATE_LIMIT_AUD:
            state = "completed_economic_stop"
            failure = "actual or projected worst-case provider cost exceeds authorized economic controls"
            economic_stop = True
        candidate = None
        if output is not None and state == "completed":
            candidate = _write_candidate(continuation_dir, row, response, output, usage, actual_usd, actual_aud, expected_client_id, continuation_id)
        _atomic_db_update(db_path, "UPDATE tickets SET state=?,transport_state=?,failure_class=?,failure_message=?,completed_at=? WHERE request_item_id=?", ("completed" if state == "completed" else state, "COMPLETED" if state == "completed" else "PROVIDER_RESPONSE_RECEIVED", "mechanical_validation" if failure else None, failure, datetime.now(timezone.utc).isoformat(), row["request_item_id"]))
        outcome = {
            "request_item_id": row["request_item_id"],
            "physical_attempt_id": row["physical_attempt_id"],
            "client_request_id": expected_client_id,
            "server_x_request_id": response.server_request_id,
            "response_id": response.body.get("id"),
            "model_identity": response.body.get("model"),
            "state": state,
            "provider_posts": 1,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "actual_cost_usd": None if actual_usd is None else str(actual_usd),
            "actual_cost_aud": None if actual_aud is None else str(actual_aud),
            "conservative_exposure_aud": row["conservative_exposure_aud"],
            "strict_schema_pass": state == "completed",
            "proposition_count": None if output is None else len(output.propositions),
            "failure": failure,
        }
        outcomes.append(outcome)
        if state == "completed":
            _append_fsynced(audit_path, {"event": "mechanical_validation_completed", "request_item_id": row["request_item_id"], "candidate_status": candidate["candidate_status"] if candidate else None, "proposition_count": outcome["proposition_count"]})

    final = {
        "campaign_id": CAMPAIGN_ID,
        "continuation_id": continuation_id,
        "execution_manifest_sha256": PINNED_EXECUTION_MANIFEST_SHA256,
        "condition_a_manifest_sha256": PINNED_CONDITION_A_MANIFEST_SHA256,
        "model_requested": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "delivery_mode": "standard",
        "prior_ambiguous_attempt_count": len(prior_ambiguous_request_ids),
        "prior_response_attempt_count": len(cert["prior_response_request_ids"]),
        "resumed_authorized_attempts": len(cert["rows"]),
        "provider_calls_this_continuation": sum(row.get("provider_posts", 0) for row in outcomes),
        "completed": sum(row["state"] == "completed" for row in outcomes),
        "definite_provider_rejections": definitely_rejected,
        "additional_ambiguous_crossings": sum(row["state"] == "PROVIDER_CROSSING_AMBIGUOUS" for row in outcomes),
        "local_pre_send_failures": local_pre_send_failures,
        "unattempted_after_stops": sum(str(row["state"]).startswith("not_attempted") for row in outcomes),
        "outcomes": outcomes,
        "actual_cost_known_aud": str(actual_cost_known),
        "actual_cost_known_usd": str(actual_cost_known_usd),
        "unknown_cost_exposure_aud": str(Decimal(cert["ambiguous_exposure_reserved_aud"]) + sum((Decimal(row["conservative_exposure_aud"]) for row in outcomes if row.get("provider_posts", 0) and row.get("actual_cost_aud") is None), Decimal("0"))),
        "worst_case_campaign_ceiling_aud": str(AGGREGATE_LIMIT_AUD),
        "campaign_worst_case_at_start_aud": cert["campaign_worst_case_aud"],
        "source_acquisitions": 0,
        "governed_promotions": 0,
    }
    _write_atomic(result_path, _canonical(final) + b"\n")
    _prepare_review_packet(run_dir, continuation_dir, cert["rows"], outcomes, continuation_id=continuation_id)
    return final


def _prepare_review_packet(run_dir: Path, continuation_dir: Path, rows: list[dict[str, Any]], outcomes: list[dict[str, Any]], *, continuation_id: str = CONTINUATION_ID) -> None:
    candidate_dir = continuation_dir / "candidate-packets"
    candidates = {}
    for path in candidate_dir.glob("*.json"):
        value = _read_json(path)
        candidates[value["request_item_id"]] = value
    review = continuation_dir / "review-materials"
    review.mkdir(exist_ok=True)
    existing_review = run_dir / "review-materials"
    for name in ("condition-a-source-only", "paired-analyst-tasks.json"):
        source = existing_review / name
        if source.exists():
            target = review / name
            if source.is_dir():
                import shutil
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                _write_atomic(target, source.read_bytes())
    worksheet = review / "proposition-adjudication-worksheet.csv"
    fields = ["slice_id", "abn", "request_item_id", "replicate_ordinal", "proposition_ordinal", "proposition_type", "proposition_json", "source_role_disposition", "epistemic_disposition", "scope_disposition", "type_disposition", "evidence_disposition", "missingness_disposition", "overall_disposition", "reviewer_rationale"]
    worksheet.parent.mkdir(parents=True, exist_ok=True)
    with worksheet.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            candidate = candidates.get(row["request_item_id"])
            if not candidate:
                continue
            for index, proposition in enumerate(candidate["propositions"], 1):
                writer.writerow({"slice_id": row["slice_id"], "abn": row["abn"], "request_item_id": row["request_item_id"], "replicate_ordinal": row["replicate_ordinal"], "proposition_ordinal": index, "proposition_type": proposition.get("proposition_type"), "proposition_json": json.dumps(proposition, ensure_ascii=False, sort_keys=True)})
    repeat_comparisons = []
    for slice_id, abn, first_request_id in (("outcomes", "28000030179", PRIOR_AMBIGUOUS_REQUEST_ID), ("commitments", "61002643852", None)):
        pair = [row for row in rows if row["slice_id"] == slice_id and row["abn"] == abn]
        pair.sort(key=lambda row: row["replicate_ordinal"])
        if first_request_id is not None:
            first_row = None
            second_row = next((row for row in pair if row["replicate_ordinal"] == 2), None)
        else:
            first_row = next((row for row in pair if row["replicate_ordinal"] == 1), None)
            second_row = next((row for row in pair if row["replicate_ordinal"] == 2), None)
        left = candidates.get(first_request_id) if first_request_id is not None else (candidates.get(first_row["request_item_id"]) if first_row else None)
        right = candidates.get(second_row["request_item_id"]) if second_row else None
        if not left or not right:
            status = "pending_original_ambiguous" if first_request_id is not None and not left else "comparison_unavailable"
            repeat_comparisons.append({"slice_id": slice_id, "abn": abn, "status": status, "replicate_1_observed": bool(left), "replicate_2_observed": bool(right), "stability_scoring_allowed": bool(left and right), "note": "Only observed responses may be adjudicated; Smith stability cannot be scored unless both responses become available." if first_request_id is not None else "", "reviewer_disposition": ""})
            continue
        first_props, second_props = left["propositions"], right["propositions"]
        first_types = sorted(item["proposition_type"] for item in first_props)
        second_types = sorted(item["proposition_type"] for item in second_props)
        first_evidence = sorted(json.dumps(item.get("evidence", []), ensure_ascii=False, sort_keys=True) for item in first_props)
        second_evidence = sorted(json.dumps(item.get("evidence", []), ensure_ascii=False, sort_keys=True) for item in second_props)
        repeat_comparisons.append({"slice_id": slice_id, "abn": abn, "status": "mechanical_field_comparison_only", "exact_candidate_agreement": first_props == second_props, "semantic_type_agreement": first_types == second_types, "evidence_agreement": first_evidence == second_evidence, "replicate_1_only": [item for item in first_props if item not in second_props], "replicate_2_only": [item for item in second_props if item not in first_props], "reviewer_disposition": ""})
    _write_atomic(review / "repeat-comparisons.json", _canonical({"comparisons": repeat_comparisons, "human_adjudication_performed": False, "reviewer_fields_empty": True}) + b"\n")
    _write_atomic(review / "candidate-index.json", _canonical({"candidate_packet_paths": [str(path.relative_to(continuation_dir)) for path in sorted(candidate_dir.glob("*.json"))], "candidate_count": len(candidates), "condition_a_material_reused": (review / "condition-a-source-only").exists(), "human_adjudication_performed": False, "reviewer_fields_empty": True}) + b"\n")
