"""One-shot, rights-pinned V5 Commitments confirmation runner.

The runner is intentionally limited to the previously approved Sunrise and
Greenpeace source packets. It persists all physical-attempt identities before
any POST and never retries.
"""

from __future__ import annotations

import hashlib
import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .openai_client import _output_text
from .phase5_openai_dry_run import conservative_standard_hard_max_aud, estimate_tokens, standard_actual_cost
from .phase5_standard_transport import (
    OpenAIHTTPStandardClient,
    StandardTransportError,
    body_sha256,
    canonical_standard_body_bytes,
    client_request_id_for_physical_attempt,
)
from .phase6_confirmation import (
    AUD_PER_USD,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PER_REQUEST_LIMIT_AUD,
    PROVIDER_SCHEMA_VERSION,
    PROVIDER_SCHEMA_SUBSET_VERSION,
    REASONING_EFFORT,
    V5_CONTRACT_VERSION,
    V5_SUPERSEDES_CONTRACT_VERSION,
    _canonical,
    _iter_strings,
    _sha,
    certify_provider_schema,
    prompt_v5,
    provider_schema_v5,
)
from .phase6_semantic_contracts import Phase6SemanticOutputV5, validate_scope_bindings
from .phase6_v4_resume import _source_task_map
from .source_rights import FAIR_DEALING_POLICY_ID, OPENAI_PROVIDER_POLICY_ID


RUN_ID = "phase6-commitments-v5-confirmation-20260913"
CONDITION_A_MANIFEST_SHA256 = "a85b99f5f786c30df1cf5817e2fca6080487071161d97e63140819bd4bdbdad5"
RIGHTS_LINEAGE_SHA256 = "03d613e6a40ceb9e7dffed0084182f59669bf97b38e59c12c20c168e6d43d94b"
RIGHTS_DECISIONS_SHA256 = "d8b28cf5dd5fff4ea1be46524dd1ff55cb96fb131953e6f6e7e31491605a59af"
ATTESTATION_SHA256 = "e64a9edf536c26c3240f60ebc29f59a97781810f43d619a8d090f46133ef19eb"
V4_WORST_CASE_RESERVE_AUD = Decimal("0.166419")
AGGREGATE_LIMIT_AUD = Decimal("1.50")
ATTEMPTS = (
    ("commitments", "65159324697", 1),
    ("commitments", "61002643852", 1),
    ("commitments", "61002643852", 2),
)


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _task_map(source_dir: Path) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    manifest_raw = (source_dir / "manifest.json").read_bytes()
    if _sha(manifest_raw) != CONDITION_A_MANIFEST_SHA256:
        raise ValueError("frozen V4 Condition A manifest identity mismatch")
    return _source_task_map(source_dir)


def _validate_rights(task: dict[str, Any], rights: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = {
        (item["source_artifact_id"], item["representation_sha256"]): item
        for item in rights["artifacts"]
    }
    checked: list[dict[str, Any]] = []
    for source in task["sources"]:
        digest = _sha(source["exact_transmitted_representation"].encode("utf-8"))
        if digest != source["evidence_representation_sha256"]:
            raise ValueError("source representation hash differs from frozen Condition A identity")
        item = decisions.get((source["source_artifact_id"], digest))
        if item is None:
            raise ValueError("no rights decision matches exact artifact and representation")
        expected = (
            item.get("disposition") == "included",
            item.get("provider_transmission_allowed") is True,
            item.get("rights_policy_id") == FAIR_DEALING_POLICY_ID,
            item.get("provider_processing_policy_id") == OPENAI_PROVIDER_POLICY_ID,
            item.get("source_record_id") == source["source_record_id"],
            item.get("source_role") == source["source_role"],
            item.get("source_origin_url") == source["source_locator"],
        )
        if not all(expected):
            raise ValueError("frozen artifact rights, policy, role, record or origin mismatch")
        checked.append({
            "source_artifact_id": source["source_artifact_id"],
            "source_record_id": source["source_record_id"],
            "representation_sha256": digest,
            "rights_decision_id": item["rights_decision_id"],
            "rights_basis": item["rights_basis"],
            "rights_policy_id": item["rights_policy_id"],
            "provider_processing_policy_id": item["provider_processing_policy_id"],
            "source_role": item["source_role"],
            "source_family": item["source_family"],
            "provider_transmission_allowed": True,
        })
    return checked


def prepare_v5_run(
    source_dir: Path,
    rights_lineage_path: Path,
    attestation_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Pin exact V5 request bytes, cost reserves, and all trace IDs offline."""
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError("V5 run directory is not empty")
    if _sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256:
        raise ValueError("frozen V4 rights-lineage file identity mismatch")
    if _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256:
        raise ValueError("product-owner provider-policy attestation identity mismatch")
    attestation = _json(attestation_path)
    if (
        attestation.get("setting") != "Share inputs and outputs with OpenAI"
        or attestation.get("observed_value") != "Disabled"
        or attestation.get("provider_processing_policy_id") != OPENAI_PROVIDER_POLICY_ID
    ):
        raise ValueError("provider-policy attestation does not satisfy the retained gate")
    rights = _json(rights_lineage_path)
    if rights.get("rights_decisions_sha256") != RIGHTS_DECISIONS_SHA256 or rights.get("policy_id") != FAIR_DEALING_POLICY_ID:
        raise ValueError("frozen rights-decision registry or policy lineage mismatch")
    source_manifest, tasks = _task_map(source_dir)
    if source_manifest.get("provider_calls") != 0 or source_manifest.get("source_acquisitions") != 0:
        raise ValueError("candidate-blind Condition A manifest records unexpected external activity")

    rows: list[dict[str, Any]] = []
    bodies: dict[str, bytes] = {}
    for slice_id, abn, ordinal in ATTEMPTS:
        task = tasks[(slice_id, abn)]
        if task.get("condition") != "A_source_only" or task.get("allowed_scope_ids", [{}])[0].get("scope_kind") != "organisation":
            raise ValueError("approved candidate-blind source task or organisation scope mismatch")
        if abn == "61002643852" and ordinal == 2:
            if not any(row["abn"] == abn and row["replicate_ordinal"] == 1 for row in rows):
                raise ValueError("Greenpeace repeat must follow an independently prepared first attempt")
        rights_items = _validate_rights(task, rights)
        scope = task["allowed_scope_ids"][0]
        locators = [source["evidence_locator_id"] for source in task["sources"]]
        prompt = prompt_v5(task)
        schema = provider_schema_v5(slice_id, task["subject_id"], scope, locators)
        certification = certify_provider_schema(schema, contract_version=V5_CONTRACT_VERSION)
        schema_name = f"phase6_{slice_id}_confirmation_v5"
        contract_hash = _sha(_canonical({
            "builder_contract_commit": "2a899f95a55a61e5fc93314afa664a92ff7df78c",
            "contract": V5_CONTRACT_VERSION,
            "supersedes": V5_SUPERSEDES_CONTRACT_VERSION,
            "slice_id": slice_id,
            "schema_sha256": certification["schema_sha256"],
            "prompt_sha256": _sha(prompt.encode("utf-8")),
        }))
        logical_id = f"phase6-v5-confirm:{slice_id}:{abn}:replicate-{ordinal}"
        body = {
            "model": MODEL,
            "reasoning": {"effort": REASONING_EFFORT},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
            "metadata": {"logical_task_id": logical_id, "semantic_contract_hash": contract_hash},
        }
        body_bytes = canonical_standard_body_bytes(body)
        request_hash = body_sha256(body_bytes)
        request_id = "requestitem:" + _sha(f"{RUN_ID}:{logical_id}:{request_hash}".encode())
        physical_id = "physicalattempt:" + _sha(f"{request_id}:physical:1".encode())
        trace_id = client_request_id_for_physical_attempt(physical_id)
        input_estimate = estimate_tokens(body)
        exposure = conservative_standard_hard_max_aud(
            input_estimate, MAX_OUTPUT_TOKENS, AUD_PER_USD, model=MODEL,
        )
        if exposure > Decimal(PER_REQUEST_LIMIT_AUD):
            raise ValueError(f"request {logical_id} exceeds AUD 0.25 conservative cap")
        row = {
            "run_id": RUN_ID,
            "logical_task_id": logical_id,
            "slice_id": slice_id,
            "abn": abn,
            "subject_id": task["subject_id"],
            "subject_name": task["subject_name"],
            "replicate_ordinal": ordinal,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "delivery_mode": "standard",
            "contract_version": V5_CONTRACT_VERSION,
            "supersedes_contract_version": V5_SUPERSEDES_CONTRACT_VERSION,
            "provider_schema_version": PROVIDER_SCHEMA_VERSION,
            "supported_subset_version": PROVIDER_SCHEMA_SUBSET_VERSION,
            "schema_name": schema_name,
            "schema_certification": certification,
            "schema_sha256": certification["schema_sha256"],
            "prompt_sha256": _sha(prompt.encode("utf-8")),
            "semantic_contract_hash": contract_hash,
            "request_item_id": request_id,
            "physical_attempt_id": physical_id,
            "client_request_id": trace_id,
            "request_body_sha256": request_hash,
            "source_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
            "source_task_id": task["task_id"],
            "source_task_sha256": next(item["task_sha256"] for item in source_manifest["tasks"] if item["task_id"] == task["task_id"]),
            "source_content_sha256": [source["evidence_representation_sha256"] for source in task["sources"]],
            "allowed_scope": scope,
            "allowed_locators": locators,
            "source_metadata": [{"evidence_locator_id": x["evidence_locator_id"], "source_role": x["source_role"]} for x in task["sources"]],
            "rights_artifacts": rights_items,
            "input_tokens_estimate": input_estimate,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "conservative_exposure_aud": str(exposure),
            "endpoint": "https://api.openai.com/v1/responses",
            "state": "prepared",
            "provider_posts": 0,
        }
        rows.append(row)
        bodies[request_id] = body_bytes

    total_exposure = sum((Decimal(row["conservative_exposure_aud"]) for row in rows), Decimal(0))
    if total_exposure + V4_WORST_CASE_RESERVE_AUD > AGGREGATE_LIMIT_AUD:
        raise ValueError("V4 retained worst-case exposure plus V5 requests exceeds AUD 1.50 campaign authority")
    if len({row["request_item_id"] for row in rows}) != 3 or len({row["physical_attempt_id"] for row in rows}) != 3 or len({row["client_request_id"] for row in rows}) != 3:
        raise ValueError("request, physical-attempt, and client trace identities must be unique")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "requests").mkdir()
    for request_id, body in bodies.items():
        _write_atomic(run_dir / "requests" / f"{request_id.replace(':', '_')}.json", body)
    manifest = {
        "run_id": RUN_ID,
        "execution_status": "prepared_not_sent",
        "authorization_status": "product-owner-authorized-in-current-user-instruction",
        "execution_authorized": True,
        "authorization_scope": {"capabilities": ["commitments"], "subjects": ["65159324697", "61002643852"], "attempts": 3},
        "contract_version": V5_CONTRACT_VERSION,
        "supersedes_contract_version": V5_SUPERSEDES_CONTRACT_VERSION,
        "builder_contract_commit": "2a899f95a55a61e5fc93314afa664a92ff7df78c",
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "rights_lineage_file_sha256": RIGHTS_LINEAGE_SHA256,
        "rights_decisions_sha256": RIGHTS_DECISIONS_SHA256,
        "provider_policy_attestation_sha256": ATTESTATION_SHA256,
        "provider": "openai",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "delivery_mode": "standard",
        "socket_timeout_seconds": 300,
        "automatic_retries": 0,
        "per_request_limit_aud": PER_REQUEST_LIMIT_AUD,
        "aggregate_campaign_limit_aud": str(AGGREGATE_LIMIT_AUD),
        "retained_v4_worst_case_reserve_aud": str(V4_WORST_CASE_RESERVE_AUD),
        "new_v5_conservative_exposure_aud": str(total_exposure),
        "combined_worst_case_exposure_aud": str(V4_WORST_CASE_RESERVE_AUD + total_exposure),
        "fx_aud_per_usd": AUD_PER_USD,
        "provider_calls": 0,
        "source_acquisitions": 0,
        "governed_promotions": 0,
        "attempts": rows,
    }
    manifest_bytes = _canonical(manifest) + b"\n"
    _write_atomic(run_dir / "execution-manifest.json", manifest_bytes)
    _write_atomic(run_dir / "provider-policy-attestation.json", attestation_path.read_bytes())
    db_path = run_dir / "tickets.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE tickets(request_item_id TEXT PRIMARY KEY, physical_attempt_id TEXT UNIQUE NOT NULL, client_request_id TEXT UNIQUE NOT NULL, request_body_sha256 TEXT NOT NULL, state TEXT NOT NULL, provider_posts INTEGER NOT NULL DEFAULT 0, send_started_at TEXT, completed_at TEXT, response_id TEXT, server_x_request_id TEXT, response_headers_received INTEGER, transport_exception TEXT, transport_exception_type TEXT, transport_cause_type TEXT, transport_errno INTEGER, usage_json TEXT, validation_error TEXT)")
        db.executemany("INSERT INTO tickets(request_item_id,physical_attempt_id,client_request_id,request_body_sha256,state) VALUES(?,?,?,?,?)", [(r["request_item_id"], r["physical_attempt_id"], r["client_request_id"], r["request_body_sha256"], "prepared") for r in rows])
        db.commit()
    return {
        "run_id": RUN_ID,
        "manifest_sha256": _sha(manifest_bytes),
        "attempts": len(rows),
        "conservative_exposure_aud": str(total_exposure),
        "retained_v4_worst_case_reserve_aud": str(V4_WORST_CASE_RESERVE_AUD),
        "combined_worst_case_aud": str(total_exposure + V4_WORST_CASE_RESERVE_AUD),
        "per_request_exposures_aud": [row["conservative_exposure_aud"] for row in rows],
        "provider_calls": 0,
        "source_acquisitions": 0,
    }


def preflight_v5_run(source_dir: Path, rights_lineage_path: Path, attestation_path: Path, run_dir: Path) -> dict[str, Any]:
    """Repeat all deterministic preflight checks before first provider crossing."""
    manifest_path = run_dir / "execution-manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if _sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256 or _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256:
        raise ValueError("rights lineage or product-owner policy attestation changed")
    if _sha(manifest_raw) != _sha(_canonical(manifest) + b"\n"):
        raise ValueError("V5 execution manifest bytes are not canonical")
    if manifest["execution_status"] != "prepared_not_sent" or not manifest["execution_authorized"] or manifest["provider_calls"] != 0:
        raise ValueError("V5 manifest is not an authorized, unsent run")
    if [ (r["slice_id"], r["abn"], r["replicate_ordinal"]) for r in manifest["attempts"] ] != list(ATTEMPTS):
        raise ValueError("V5 attempt cohort or sequential order differs from the authorized set")
    source_manifest, tasks = _task_map(source_dir)
    rights = _json(rights_lineage_path)
    attestation = _json(attestation_path)
    if source_manifest.get("provider_calls") != 0 or source_manifest.get("source_acquisitions") != 0:
        raise ValueError("Condition A source task manifest records external activity")
    for row in manifest["attempts"]:
        task = tasks.get((row["slice_id"], row["abn"]))
        if task is None or task["subject_id"] != row["subject_id"] or task["task_id"] != row["source_task_id"]:
            raise ValueError("V5 task identity no longer matches Condition A")
        source_row = next(x for x in source_manifest["tasks"] if x["task_id"] == task["task_id"])
        if source_row["task_sha256"] != row["source_task_sha256"]:
            raise ValueError("Condition A source task hash mismatch")
        rights_items = _validate_rights(task, rights)
        if rights_items != row["rights_artifacts"]:
            raise ValueError("rights preflight differs from frozen rights decision record")
        body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"]:
            raise ValueError("request body hash mismatch")
        body = json.loads(body_bytes.decode("utf-8"))
        if canonical_standard_body_bytes(body) != body_bytes:
            raise ValueError("request body bytes are not canonical")
        if body.get("model") != MODEL or body.get("reasoning", {}).get("effort") != "low" or body.get("store") is not False:
            raise ValueError("V5 request route or storage mode mismatch")
        schema = body["text"]["format"]["schema"]
        certification = certify_provider_schema(schema, contract_version=V5_CONTRACT_VERSION)
        if certification != row["schema_certification"]:
            raise ValueError("V5 provider schema certification mismatch")
        if row["client_request_id"] != client_request_id_for_physical_attempt(row["physical_attempt_id"]):
            raise ValueError("pre-recorded client request trace mismatch")
        if Decimal(row["conservative_exposure_aud"]) > Decimal(PER_REQUEST_LIMIT_AUD):
            raise ValueError("per-request conservative cost ceiling failed")
    with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
        tickets = db.execute("SELECT request_item_id,physical_attempt_id,client_request_id,request_body_sha256,state,provider_posts FROM tickets ORDER BY rowid").fetchall()
    expected_tickets = [(r["request_item_id"], r["physical_attempt_id"], r["client_request_id"], r["request_body_sha256"], "prepared", 0) for r in manifest["attempts"]]
    if tickets != expected_tickets:
        raise ValueError("tickets show a previous crossing, identity drift, or changed body")
    if any((run_dir / sub).exists() and any((run_dir / sub).iterdir()) for sub in ("responses", "candidate-packets")):
        raise ValueError("response or candidate artifacts already exist; refusing any repeat crossing")
    return {
        "preflight": "passed_no_provider_crossing",
        "attempts_certified": len(manifest["attempts"]),
        "rights_artifacts_certified": sum(len(r["rights_artifacts"]) for r in manifest["attempts"]),
        "provider_policy_attestation_sha256": _sha(attestation_path.read_bytes()),
        "per_request_exposures_aud": [r["conservative_exposure_aud"] for r in manifest["attempts"]],
        "conservative_exposure_total_aud": manifest["new_v5_conservative_exposure_aud"],
        "combined_v4_v5_worst_case_aud": manifest["combined_worst_case_exposure_aud"],
        "campaign_authority_aud": str(AGGREGATE_LIMIT_AUD),
        "provider_calls": 0,
    }


def _validate_v5_response(row: dict[str, Any], task: dict[str, Any], packet: dict[str, Any]) -> Phase6SemanticOutputV5:
    if packet.get("contract_version") != V5_CONTRACT_VERSION:
        raise ValueError("response contract version differs from V5")
    output = Phase6SemanticOutputV5.model_validate(packet)
    if output.slice_id != row["slice_id"] or output.subject_id != row["subject_id"]:
        raise ValueError("V5 response task identity mismatch")
    validate_scope_bindings(output, {row["allowed_scope"]["scope_id"]})
    sources = {source["evidence_locator_id"]: source for source in task["sources"]}
    source_texts = [source["exact_transmitted_representation"] for source in task["sources"]]
    for proposition in output.propositions:
        scope = proposition.scope
        if scope.scope_kind != row["allowed_scope"]["scope_kind"] or scope.scope_label != row["allowed_scope"]["label"]:
            raise ValueError("V5 response scope kind or label mismatch")
        for evidence in getattr(proposition, "evidence", ()):
            if evidence.locator_id not in sources:
                raise ValueError("V5 evidence locator is outside the frozen source allow-list")
            if evidence.source_role != sources[evidence.locator_id]["source_role"]:
                raise ValueError("V5 evidence source carrier role does not match the frozen locator")
            if evidence.source_date is not None or evidence.retrieved_at is not None:
                raise ValueError("V5 evidence dates are not recorded in the frozen Condition A manifest")
        for value in _iter_strings(proposition.model_dump(mode="json")):
            if len(value) >= 48 and any(value in source_text for source_text in source_texts):
                raise ValueError("candidate contains a verbatim source excerpt")
    return output


def execute_v5_run(source_dir: Path, rights_lineage_path: Path, attestation_path: Path, run_dir: Path) -> dict[str, Any]:
    """Run exact prepared bodies sequentially, stopping on ambiguity or invalid output."""
    preflight = preflight_v5_run(source_dir, rights_lineage_path, attestation_path, run_dir)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is unavailable; no provider attempt started")
    manifest = _json(run_dir / "execution-manifest.json")
    _, tasks = _task_map(source_dir)
    rights = _json(rights_lineage_path)
    client = OpenAIHTTPStandardClient()
    if client.socket_timeout_seconds != 300:
        raise ValueError("Standard transport socket timeout must remain exactly 300 seconds")
    results: list[dict[str, Any]] = []
    global_stop_reason: str | None = None
    for row in manifest["attempts"]:
        if global_stop_reason:
            results.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_stop", "provider_posts": 0, "stop_reason": global_stop_reason})
            continue
        task = tasks[(row["slice_id"], row["abn"])]
        # Recheck rights, policy, body, ticket and trace immediately before send.
        if _sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256 or _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256:
            global_stop_reason = "rights_or_policy_attestation_changed"
            results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0, "stop_reason": global_stop_reason})
            continue
        if _validate_rights(task, rights) != row["rights_artifacts"]:
            global_stop_reason = "rights_preflight_changed"
            results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0, "stop_reason": global_stop_reason})
            continue
        body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"] or _sha(_canonical(manifest) + b"\n") != _sha((run_dir / "execution-manifest.json").read_bytes()):
            global_stop_reason = "request_or_manifest_identity_changed"
            results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0, "stop_reason": global_stop_reason})
            continue
        started_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with sqlite3.connect(run_dir / "tickets.sqlite3", isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("SELECT state,provider_posts,request_body_sha256,physical_attempt_id,client_request_id FROM tickets WHERE request_item_id=?", (row["request_item_id"],)).fetchone()
            if ticket != ("prepared", 0, row["request_body_sha256"], row["physical_attempt_id"], row["client_request_id"]):
                db.execute("ROLLBACK")
                global_stop_reason = "ticket_identity_or_state_mismatch"
                results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0, "stop_reason": global_stop_reason})
                continue
            db.execute("UPDATE tickets SET state='send_started',provider_posts=1,send_started_at=? WHERE request_item_id=?", (started_at, row["request_item_id"]))
            db.commit()
        request_meta = {"request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "client_request_id": row["client_request_id"], "request_body_sha256": row["request_body_sha256"], "endpoint": row["endpoint"], "request_started_at": started_at, "provider_policy_attestation_sha256": ATTESTATION_SHA256, "rights_decisions_sha256": RIGHTS_DECISIONS_SHA256, "state": "crossing_started"}
        _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(request_meta) + b"\n")
        with (run_dir / "transport-audit.jsonl").open("ab") as stream:
            stream.write(_canonical({"event": "provider_crossing_started", **request_meta}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            response = client.create_response_once(body_bytes, client_request_id=row["client_request_id"], request_started_at=started_at)
        except StandardTransportError as exc:
            state = "ambiguous" if exc.ambiguous else "terminal_provider_response"
            if exc.raw_bytes is not None:
                _write_atomic(run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json", exc.raw_bytes)
            details = {**request_meta, "state": state, "http_status": exc.status_code, "server_x_request_id": exc.request_id, "response_headers_received": exc.response_headers_received, "transport_exception": str(exc), "transport_exception_type": exc.exception_type, "transport_cause_type": exc.cause_type, "transport_errno": exc.error_number, "transport_elapsed_seconds": exc.elapsed_seconds, "transport_state": exc.transport_state, "raw_response_sha256": None if exc.raw_bytes is None else _sha(exc.raw_bytes)}
            _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(details) + b"\n")
            with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
                db.execute("UPDATE tickets SET state=?,completed_at=?,server_x_request_id=?,response_headers_received=?,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=? WHERE request_item_id=?", (state, datetime.now(timezone.utc).isoformat(), exc.request_id, int(exc.response_headers_received), str(exc)[:512], exc.exception_type, exc.cause_type, exc.error_number, row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "client_request_id": row["client_request_id"], "server_x_request_id": exc.request_id, "conservative_exposure_aud": row["conservative_exposure_aud"], "transport_exception": str(exc), "transport_exception_type": exc.exception_type, "transport_cause_type": exc.cause_type})
            if exc.ambiguous or exc.systemic:
                global_stop_reason = "ambiguous_or_systemic_transport"
            else:
                global_stop_reason = "definite_provider_error_stop"
            continue
        except Exception as exc:
            state = "ambiguous"
            details = {**request_meta, "state": state, "transport_exception": f"{type(exc).__name__}: {exc}"[:512], "transport_exception_type": type(exc).__name__, "transport_cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None, "transport_errno": getattr(exc.__cause__ or exc, "errno", None), "response_headers_received": False}
            _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(details) + b"\n")
            with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
                db.execute("UPDATE tickets SET state='ambiguous',completed_at=?,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=?,response_headers_received=0 WHERE request_item_id=?", (datetime.now(timezone.utc).isoformat(), details["transport_exception"], details["transport_exception_type"], details["transport_cause_type"], details["transport_errno"], row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "client_request_id": row["client_request_id"], "conservative_exposure_aud": row["conservative_exposure_aud"], "transport_exception": details["transport_exception"], "transport_exception_type": details["transport_exception_type"], "transport_cause_type": details["transport_cause_type"]})
            global_stop_reason = "ambiguous_or_unclassified_transport"
            continue

        response_path = run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json"
        _write_atomic(response_path, response.raw_bytes)
        raw_usage = response.body.get("usage") or {}
        try:
            actual_usd, actual_aud = standard_actual_cost(raw_usage, AUD_PER_USD, model=MODEL)
            cost_error = None
        except Exception as exc:
            actual_usd = actual_aud = None
            cost_error = f"{type(exc).__name__}: {exc}"[:512]
        parsed: Phase6SemanticOutputV5 | None = None
        error: str | None = None
        structured_packet: dict[str, Any] | None = None
        try:
            if not (200 <= response.status_code < 300) or response.body.get("status") != "completed" or response.body.get("incomplete_details") is not None:
                raise ValueError("provider response is not completed")
            if response.body.get("model") != MODEL:
                raise ValueError("provider model identity differs from requested Luna model")
            output_text = _output_text(response.body)
            if not output_text:
                raise ValueError("provider response has no structured output text")
            structured_packet = json.loads(output_text)
            parsed = _validate_v5_response(row, task, structured_packet)
        except Exception as exc:
            error = str(exc)[:1200]
        meta = {**request_meta, "state": "completed" if parsed is not None else "completed_validation_failed", "http_status": response.status_code, "server_x_request_id": response.server_request_id, "response_id": response.body.get("id"), "response_headers_received": response.response_headers_received, "raw_response_sha256": _sha(response.raw_bytes), "provider_model": response.body.get("model"), "input_tokens": raw_usage.get("input_tokens"), "output_tokens": raw_usage.get("output_tokens"), "actual_cost_usd": None if actual_usd is None else str(actual_usd), "actual_cost_aud": None if actual_aud is None else str(actual_aud), "cost_error": cost_error, "validation_error": error}
        _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(meta) + b"\n")
        with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
            db.execute("UPDATE tickets SET state=?,completed_at=?,response_id=?,server_x_request_id=?,response_headers_received=?,usage_json=?,validation_error=? WHERE request_item_id=?", (meta["state"], datetime.now(timezone.utc).isoformat(), meta["response_id"], response.server_request_id, int(response.response_headers_received), json.dumps(raw_usage, sort_keys=True), error, row["request_item_id"]))
        result = {"request_item_id": row["request_item_id"], "state": meta["state"], "provider_posts": 1, "client_request_id": row["client_request_id"], "server_x_request_id": response.server_request_id, "response_id": meta["response_id"], "model": meta["provider_model"], "input_tokens": raw_usage.get("input_tokens"), "output_tokens": raw_usage.get("output_tokens"), "actual_cost_usd": meta["actual_cost_usd"], "actual_cost_aud": meta["actual_cost_aud"], "conservative_exposure_aud": row["conservative_exposure_aud"], "response_sha256": meta["raw_response_sha256"], "validation_error": error}
        if parsed is not None:
            candidate = {"candidate_status": "unreviewed_mechanical_candidate", "run_id": RUN_ID, "slice_id": row["slice_id"], "subject_id": row["subject_id"], "abn": row["abn"], "request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "provider_response_id": meta["response_id"], "client_request_id": row["client_request_id"], "server_x_request_id": response.server_request_id, "contract_version": V5_CONTRACT_VERSION, "schema_sha256": row["schema_sha256"], "source_task_sha256": row["source_task_sha256"], "source_content_sha256": row["source_content_sha256"], "request_body_sha256": row["request_body_sha256"], "response_body_sha256": meta["raw_response_sha256"], "propositions": [item.model_dump(mode="json") for item in parsed.propositions], "reviewer_dispositions": []}
            _write_atomic(run_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(candidate) + b"\n")
            result["proposition_count"] = len(parsed.propositions)
        else:
            # Preserve the completed raw response and stop on any mechanical
            # contract failure; no output repair or later call can hide it.
            global_stop_reason = "critical_v5_contract_validation_failure"
        results.append(result)

    report = {"run_id": RUN_ID, "contract_version": V5_CONTRACT_VERSION, "execution_status": "executed_or_stopped", "model": MODEL, "reasoning_effort": REASONING_EFFORT, "delivery_mode": "standard", "provider_calls": sum(item["provider_posts"] for item in results), "source_acquisitions": 0, "governed_promotions": 0, "global_stop_reason": global_stop_reason, "preflight": preflight, "results": results}
    _write_atomic(run_dir / "execution-results.json", _canonical(report) + b"\n")
    return report


def compare_greenpeace_repeats(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Produce a structural comparison without reconciling or adjudicating meaning."""
    def canonical_set(output: dict[str, Any]) -> set[str]:
        return {_canonical(item).decode("utf-8") for item in output["propositions"]}

    left = canonical_set(first)
    right = canonical_set(second)
    left_types = sorted(item["proposition_type"] for item in first["propositions"])
    right_types = sorted(item["proposition_type"] for item in second["propositions"])
    role_sets = lambda output: sorted({evidence["source_role"] for proposition in output["propositions"] for evidence in proposition.get("evidence", [])})
    epistemic_sets = lambda output: sorted({proposition["epistemic_class"] for proposition in output["propositions"]})
    evidence_sets = lambda output: sorted({evidence["locator_id"] for proposition in output["propositions"] for evidence in proposition.get("evidence", [])})
    return {
        "comparison": "independent_v5_repeat_structural_comparison",
        "reconciled": False,
        "proposition_counts": [len(first["propositions"]), len(second["propositions"])],
        "proposition_types": [left_types, right_types],
        "epistemic_statuses": [epistemic_sets(first), epistemic_sets(second)],
        "source_carrier_roles": [role_sets(first), role_sets(second)],
        "evidence_locators": [evidence_sets(first), evidence_sets(second)],
        "exact_unique_to_attempt_1": sorted(left - right),
        "exact_unique_to_attempt_2": sorted(right - left),
        "exact_common_propositions": sorted(left & right),
        "contradiction_review": {
            "status": "human_review_required",
            "controlled_epistemic_or_carrier_conflicts_observed": False,
            "free_text_semantic_contradictions_inferred": False,
            "note": "No polarity field exists in these proposition types; exact one-sided proposition records are provided for reviewer comparison.",
        },
        "answer_changing_structural_differences": sorted(left ^ right),
        "human_stability_judgment": None,
    }


def prepare_outcomes_v4_review_packet(
    source_dir: Path,
    v4_run_dir: Path,
    diagnostics_path: Path,
    review_root: Path,
) -> dict[str, Any]:
    """Prepare a private blind-source / historical-output Outcomes review packet."""
    if review_root.exists() and any(review_root.iterdir()):
        raise FileExistsError("Outcomes review packet directory is not empty")
    manifest, tasks = _task_map(source_dir)
    diagnostics = _json(diagnostics_path)
    diagnostic_by_id = {item["request_item_id"]: item for item in diagnostics["attempts"]}
    outcomes = [("28004778081", "requestitem:c3bc6dd61bf87f9084aa205664ad03de8279fcb73ca74f414ee267f28eaf12d5"),
                ("78053639115", "requestitem:bc4948dd9ef112e696329c52aaa74ededcc0ea09b141e076b15157620fbd86ce")]
    review_root.mkdir(parents=True, exist_ok=True)
    source_out = review_root / "condition-a-source-only"
    raw_out = review_root / "raw-v4-provider-responses"
    replay_out = review_root / "v5-offline-replay"
    lineage_out = review_root / "evidence-lineage"
    for path in (source_out, raw_out, replay_out, lineage_out):
        path.mkdir()
    worksheet_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, Any]] = []
    for abn, request_id in outcomes:
        task = tasks[("outcomes", abn)]
        condition_row = next(item for item in manifest["tasks"] if item["task_id"] == task["task_id"])
        task_bytes = (source_dir / condition_row["path"]).read_bytes()
        task_out = source_out / f"outcomes__{abn}.json"
        _write_atomic(task_out, task_bytes)
        response_name = f"{request_id.replace(':', '_')}.json"
        matches = list(v4_run_dir.glob(f"continuation-2026-09-13-authorized-six-*/responses/{response_name}"))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one retained V4 response for {request_id}")
        response_path = matches[0]
        response_bytes = response_path.read_bytes()
        response = json.loads(response_bytes.decode("utf-8"))
        packet = json.loads(_output_text(response))
        row = {
            "slice_id": "outcomes", "subject_id": task["subject_id"],
            "allowed_scope": task["allowed_scope_ids"][0],
            "allowed_locators": [source["evidence_locator_id"] for source in task["sources"]],
            "source_metadata": [{"evidence_locator_id": source["evidence_locator_id"], "source_role": source["source_role"]} for source in task["sources"]],
            "source_texts": [source["exact_transmitted_representation"] for source in task["sources"]],
        }
        from .phase6_confirmation import mechanical_validate_v5_replay
        parsed = mechanical_validate_v5_replay(row, packet)
        request_file = raw_out / f"{request_id.replace(':', '_')}.json"
        _write_atomic(request_file, response_bytes)
        replay_record = {
            "classification": "V5 offline replay of unchanged historical V4 response; not a V5 provider response",
            "request_item_id": request_id,
            "response_id": response.get("id"),
            "response_sha256": _sha(response_bytes),
            "contract_version_in_response": packet.get("contract_version"),
            "v4_status": "completed_parse_failed",
            "v4_validation_errors": diagnostic_by_id[request_id].get("failure"),
            "v5_offline_replay_status": "passes",
            "propositions": [item.model_dump(mode="json") for item in parsed.propositions],
            "reviewer_dispositions": [],
        }
        _write_atomic(replay_out / f"{request_id.replace(':', '_')}.json", _canonical(replay_record) + b"\n")
        _write_atomic(lineage_out / f"outcomes__{abn}.json", _canonical({
            "task_sha256": _sha(task_bytes),
            "sources": [{key: source.get(key) for key in (
                "source_artifact_id", "source_record_id", "source_family", "source_role",
                "source_locator", "evidence_locator_id", "evidence_representation_sha256",
            )} for source in task["sources"]],
        }) + b"\n")
        for index, proposition in enumerate(parsed.propositions):
            worksheet_rows.append({
                "request_item_id": request_id,
                "subject_id": task["subject_id"],
                "proposition_index": str(index),
                "proposition_type": proposition.proposition_type,
                "epistemic_class": proposition.epistemic_class,
                "scope_id": proposition.scope.scope_id,
                "evidence_locators": ";".join(e.locator_id for e in getattr(proposition, "evidence", ())),
                "source_roles": ";".join(sorted({e.source_role for e in getattr(proposition, "evidence", ())})),
                "reviewer_id": "",
                "human_disposition": "",
                "rationale": "",
                "accepted_proposition": "",
            })
        report_rows.append({
            "abn": abn,
            "subject_name": task["subject_name"],
            "request_item_id": request_id,
            "raw_response_sha256": _sha(response_bytes),
            "v4_validation": "failed: first-party epistemic class conflicts with source role",
            "v5_offline_replay": "passes; historical V4 bytes unchanged",
            "proposition_count": len(parsed.propositions),
            "candidate_blind_task_sha256": _sha(task_bytes),
        })
    import csv
    worksheet_path = review_root / "proposition-adjudication-worksheet.csv"
    fieldnames = list(worksheet_rows[0]) if worksheet_rows else []
    with worksheet_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(worksheet_rows)
    report = {
        "packet_status": "READY_FOR_HUMAN_REVIEW",
        "review_type": "independent proposition-level review",
        "subjects": report_rows,
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "v4_execution_manifest_sha256": "8671fac5be0755617ae60a2d1b947ff2418461e9bd8959af86e6c33ec2d85fee",
        "human_adjudication_performed": False,
        "reviewer_fields_initially_blank": True,
        "limitations": [
            "Reduced V4 Outcomes sample contains World Vision Australia and Bush Heritage only; it does not satisfy the original six-subject usefulness denominator.",
            "The two historical Smith attempts remain ambiguous and neither is included or retried.",
            "V5 replay is read-only mechanical validation and is not a new provider response or human adjudication.",
        ],
        "source_acquisitions": 0,
        "provider_calls_during_packet_preparation": 0,
    }
    _write_atomic(review_root / "review-packet-manifest.json", _canonical(report) + b"\n")
    return report


def prepare_commitments_v5_review_packet(
    source_dir: Path,
    run_dir: Path,
    review_root: Path,
) -> dict[str, Any]:
    """Prepare private Condition A and candidate material with blank reviewer fields."""
    if review_root.exists() and any(review_root.iterdir()):
        raise FileExistsError("Commitments review packet directory is not empty")
    manifest = _json(run_dir / "execution-manifest.json")
    _, tasks = _task_map(source_dir)
    condition_a = review_root / "condition-a-source-only"
    candidates = review_root / "v5-candidate-outputs"
    raw_responses = review_root / "raw-v5-provider-responses"
    lineage = review_root / "evidence-lineage"
    for directory in (condition_a, candidates, raw_responses, lineage):
        directory.mkdir(parents=True)
    rows: list[dict[str, str]] = []
    candidate_index: list[dict[str, Any]] = []
    repeat_packets: list[dict[str, Any]] = []
    for attempt in manifest["attempts"]:
        key = (attempt["slice_id"], attempt["abn"])
        task = tasks[key]
        condition_manifest = _json(source_dir / "manifest.json")
        task_ref = next(item for item in condition_manifest["tasks"] if item["task_id"] == task["task_id"])
        task_bytes = (source_dir / task_ref["path"]).read_bytes()
        source_out = condition_a / f"commitments__{attempt['abn']}.json"
        _write_atomic(source_out, task_bytes)
        rid_name = attempt["request_item_id"].replace(":", "_")
        raw_path = run_dir / "responses" / f"{rid_name}.json"
        raw_bytes = raw_path.read_bytes()
        response = _json(raw_path)
        packet = json.loads(_output_text(response))
        candidate_path = run_dir / "candidate-packets" / f"{rid_name}.json"
        candidate_bytes = candidate_path.read_bytes()
        candidate = _json(candidate_path)
        _write_atomic(raw_responses / f"{rid_name}.json", raw_bytes)
        _write_atomic(candidates / f"{rid_name}.json", candidate_bytes)
        _write_atomic(lineage / f"commitments__{attempt['abn']}__replicate-{attempt['replicate_ordinal']}.json", _canonical({
            "task_sha256": _sha(task_bytes),
            "source_task_id": task["task_id"],
            "source_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
            "source_artifacts": [{key: source.get(key) for key in (
                "source_artifact_id", "source_record_id", "source_family", "source_role",
                "source_locator", "evidence_locator_id", "evidence_representation_sha256",
            )} for source in task["sources"]],
        }) + b"\n")
        for index, proposition in enumerate(candidate["propositions"]):
            rows.append({
                "abn": attempt["abn"], "subject_name": attempt["subject_name"],
                "replicate_ordinal": str(attempt["replicate_ordinal"]),
                "request_item_id": attempt["request_item_id"],
                "proposition_index": str(index),
                "proposition_type": proposition["proposition_type"],
                "epistemic_class": proposition["epistemic_class"],
                "source_carrier_roles": ";".join(sorted({item["source_role"] for item in proposition.get("evidence", [])})),
                "evidence_locators": ";".join(item["locator_id"] for item in proposition.get("evidence", [])),
                "reviewer_id": "", "human_disposition": "", "rationale": "",
                "accepted_or_corrected_proposition": "",
            })
        result = next(item for item in _json(run_dir / "execution-results.json")["results"] if item["request_item_id"] == attempt["request_item_id"])
        candidate_index.append({
            "abn": attempt["abn"], "subject_name": attempt["subject_name"],
            "replicate_ordinal": attempt["replicate_ordinal"],
            "request_item_id": attempt["request_item_id"],
            "response_id": response.get("id"),
            "raw_response_sha256": _sha(raw_bytes),
            "candidate_sha256": _sha(candidate_bytes),
            "candidate_status": candidate["candidate_status"],
            "mechanical_validation": result["state"],
            "proposition_count": len(candidate["propositions"]),
            "reviewer_dispositions": [],
        })
        if attempt["abn"] == "61002643852":
            repeat_packets.append(packet)
    worksheet = review_root / "proposition-adjudication-worksheet.csv"
    with worksheet.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    comparison = compare_greenpeace_repeats(repeat_packets[0], repeat_packets[1])
    comparison["attempt_1_request_item_id"] = next(r["request_item_id"] for r in manifest["attempts"] if r["abn"] == "61002643852" and r["replicate_ordinal"] == 1)
    comparison["attempt_2_request_item_id"] = next(r["request_item_id"] for r in manifest["attempts"] if r["abn"] == "61002643852" and r["replicate_ordinal"] == 2)
    comparison["interpretation_limit"] = "Exact structured differences are surfaced for reviewers. They are not an automated semantic stability judgment; potential contradictions and answer-changing status remain for human adjudication."
    _write_atomic(review_root / "greenpeace-repeat-comparison.json", _canonical(comparison) + b"\n")
    analyst_tasks = [{
        "abn": abn,
        "subject_name": tasks[("commitments", abn)]["subject_name"],
        "task_id": tasks[("commitments", abn)]["task_id"],
        "analyst_questions": tasks[("commitments", abn)]["analyst_questions"],
        "allowed_scope_ids": tasks[("commitments", abn)]["allowed_scope_ids"],
        "source_only_file": f"condition-a-source-only/commitments__{abn}.json",
        "answer_condition": "A_source_only; do not consult V5 candidates during independent source-only analysis",
        "analyst_id": "",
        "answer": "",
        "confidence": "",
        "time_minutes": "",
    } for abn in ("65159324697", "61002643852")]
    _write_atomic(review_root / "analyst-task-material.json", _canonical({"reviewer_fields_blank": True, "tasks": analyst_tasks}) + b"\n")
    report = {
        "packet_status": "READY_FOR_HUMAN_REVIEW",
        "review_type": "candidate and proposition adjudication; no outcome is pre-accepted",
        "contract_version": V5_CONTRACT_VERSION,
        "subjects_and_attempts": candidate_index,
        "greenpeace_repeat_comparison": "greenpeace-repeat-comparison.json",
        "candidate_blind_material": "condition-a-source-only/",
        "candidate_outputs": "v5-candidate-outputs/",
        "raw_provider_responses": "raw-v5-provider-responses/",
        "adjudication_worksheet": "proposition-adjudication-worksheet.csv",
        "analyst_task_material": "analyst-task-material.json",
        "human_adjudication_performed": False,
        "reviewer_fields_initially_blank": True,
        "limitations": [
            "Only Sunrise and Greenpeace were executed; no replacement subjects or Red Cross request were included.",
            "All three outputs pass the mechanical V5 gates, but human proposition adjudication remains necessary.",
            "Greenpeace produced four commitment propositions and three implementation activities on attempt 1, versus four commitments and two activities on attempt 2. Both attempts have first_party_claim status and consistent carrier-role/locator sets; their exact proposition records differ. Human reviewers must determine whether those differences change the analyst answer.",
            "No repeat was reconciled. Human stability judgment is blank; reliability/advancement is not claimed.",
        ],
        "provider_calls": 3,
        "source_acquisitions": 0,
        "governed_promotions": 0,
    }
    _write_atomic(review_root / "review-packet-manifest.json", _canonical(report) + b"\n")
    return report
