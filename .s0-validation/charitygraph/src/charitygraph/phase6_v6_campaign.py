"""Rights-pinned, one-shot Phase 6 Outcomes V6 confirmation campaign."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .openai_client import _output_text
from .phase5_openai_dry_run import conservative_standard_hard_max_aud, estimate_tokens, standard_actual_cost
from .phase5_standard_transport import (
    OpenAIHTTPStandardClient, StandardTransportError, body_sha256,
    canonical_standard_body_bytes, client_request_id_for_physical_attempt,
)
from .phase6_confirmation import (
    AUD_PER_USD, MAX_OUTPUT_TOKENS, MODEL, PER_REQUEST_LIMIT_AUD,
    PROVIDER_SCHEMA_VERSION, PROVIDER_SCHEMA_SUBSET_VERSION, REASONING_EFFORT,
    V6_CONTRACT_VERSION, V6_SUPERSEDES_CONTRACT_VERSION, _canonical, _iter_strings,
    _sha, certify_provider_schema, prompt_v6_outcomes, provider_schema_v6_outcomes,
)
from .phase6_semantic_contracts import OutcomeObservedReportedV6, Phase6SemanticOutputV6
from .phase6_v5_campaign import (
    AGGREGATE_LIMIT_AUD, ATTESTATION_SHA256, CONDITION_A_MANIFEST_SHA256,
    RIGHTS_DECISIONS_SHA256, RIGHTS_LINEAGE_SHA256, V4_WORST_CASE_RESERVE_AUD,
    _json, _task_map, _validate_rights, _write_atomic,
)
from .source_rights import FAIR_DEALING_POLICY_ID, OPENAI_PROVIDER_POLICY_ID


RUN_ID = "phase6-outcomes-v6-confirmation-20260914"
V4_RESPONSE_SHA256 = {
    "28004778081": "fcade75f78b78635999434e1fd9fe3dd5d6bfeb9b1c8d9cc9e3405422da56534",
    "78053639115": "0a4127ac8a3c823e3d73118c5aa917c33f1dcbf0978dadfc5b7b70e9deffc4d0",
}
V4_REQUEST_IDS = {
    "28004778081": "c3bc6dd61bf87f9084aa205664ad03de8279fcb73ca74f414ee267f28eaf12d5",
    "78053639115": "bc4948dd9ef112e696329c52aaa74ededcc0ea09b141e076b15157620fbd86ce",
}
ATTEMPTS = (("outcomes", "28004778081"), ("outcomes", "78053639115"))
NEW_CAMPAIGN_LIMIT_AUD = Decimal("0.50")


def _builder_commit() -> str:
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def prepare_v6_run(source_dir: Path, rights_lineage_path: Path, attestation_path: Path, run_dir: Path) -> dict[str, Any]:
    """Build exact requests and persist trace identities without provider access."""
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError("V6 run directory is not empty")
    if _sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256:
        raise ValueError("frozen V4 rights-lineage identity mismatch")
    if _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256:
        raise ValueError("provider-policy attestation identity mismatch")
    attestation = _json(attestation_path)
    if (attestation.get("setting") != "Share inputs and outputs with OpenAI"
            or attestation.get("observed_value") != "Disabled"
            or attestation.get("provider_processing_policy_id") != OPENAI_PROVIDER_POLICY_ID
            or attestation.get("rights_policy_id") != FAIR_DEALING_POLICY_ID):
        raise ValueError("retained provider-policy attestation does not satisfy the gate")
    rights = _json(rights_lineage_path)
    if rights.get("rights_decisions_sha256") != RIGHTS_DECISIONS_SHA256 or rights.get("policy_id") != FAIR_DEALING_POLICY_ID:
        raise ValueError("frozen rights-decision lineage mismatch")
    source_manifest, tasks = _task_map(source_dir)
    if source_manifest.get("provider_calls") != 0 or source_manifest.get("source_acquisitions") != 0:
        raise ValueError("frozen Condition A source packet records external activity")

    rows: list[dict[str, Any]] = []
    request_bodies: dict[str, bytes] = {}
    for slice_id, abn in ATTEMPTS:
        task = tasks[(slice_id, abn)]
        if task.get("condition") != "A_source_only" or task.get("abn") != abn:
            raise ValueError("V6 subject does not match frozen source-only task")
        if len(task.get("allowed_scope_ids", [])) != 1:
            raise ValueError("V6 task must have exactly one frozen organisation scope")
        scope = task["allowed_scope_ids"][0]
        if scope.get("scope_kind") != "organisation":
            raise ValueError("V6 scope is not the frozen organisation scope")
        sources = task.get("sources", [])
        locators = [source["evidence_locator_id"] for source in sources]
        if not sources or len(locators) != len(set(locators)):
            raise ValueError("frozen sources or locators are missing/duplicated")
        rights_items = _validate_rights(task, rights)
        prompt = prompt_v6_outcomes(task)
        schema = provider_schema_v6_outcomes(task["subject_id"], scope, locators)
        certification = certify_provider_schema(schema, contract_version=V6_CONTRACT_VERSION)
        schema_name = "phase6_outcomes_confirmation_v6"
        logical_id = f"phase6-v6-confirm:outcomes:{abn}"
        contract_hash = _sha(_canonical({
            "contract": V6_CONTRACT_VERSION,
            "supersedes": V6_SUPERSEDES_CONTRACT_VERSION,
            "schema_sha256": certification["schema_sha256"],
            "prompt_sha256": _sha(prompt.encode("utf-8")),
        }))
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
        body_hash = body_sha256(body_bytes)
        request_id = "requestitem:" + _sha(f"{RUN_ID}:{logical_id}:{body_hash}".encode())
        physical_id = "physicalattempt:" + _sha(f"{request_id}:physical:1".encode())
        exposure = conservative_standard_hard_max_aud(estimate_tokens(body), MAX_OUTPUT_TOKENS, AUD_PER_USD, model=MODEL)
        if exposure > Decimal(PER_REQUEST_LIMIT_AUD):
            raise ValueError(f"{logical_id} exceeds the AUD 0.25 per-request authority")
        task_manifest_row = next(item for item in source_manifest["tasks"] if item["task_id"] == task["task_id"])
        row = {
            "run_id": RUN_ID, "slice_id": slice_id, "abn": abn, "subject_id": task["subject_id"],
            "subject_name": task["subject_name"], "logical_task_id": logical_id,
            "model": MODEL, "reasoning_effort": REASONING_EFFORT, "delivery_mode": "standard",
            "contract_version": V6_CONTRACT_VERSION, "supersedes_contract_version": V6_SUPERSEDES_CONTRACT_VERSION,
            "provider_schema_version": PROVIDER_SCHEMA_VERSION,
            "supported_subset_version": PROVIDER_SCHEMA_SUBSET_VERSION,
            "schema_name": schema_name, "schema_certification": certification,
            "schema_sha256": certification["schema_sha256"], "prompt_sha256": _sha(prompt.encode("utf-8")),
            "semantic_contract_hash": contract_hash, "request_item_id": request_id,
            "physical_attempt_id": physical_id,
            "client_request_id": client_request_id_for_physical_attempt(physical_id),
            "request_body_sha256": body_hash, "source_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
            "source_task_id": task["task_id"], "source_task_sha256": task_manifest_row["task_sha256"],
            "source_content_sha256": [source["evidence_representation_sha256"] for source in sources],
            "allowed_scope": scope, "allowed_locators": locators,
            "source_metadata": [{"evidence_locator_id": source["evidence_locator_id"], "source_role": source["source_role"]} for source in sources],
            "rights_artifacts": rights_items, "input_tokens_estimate": estimate_tokens(body),
            "max_output_tokens": MAX_OUTPUT_TOKENS, "conservative_exposure_aud": str(exposure),
            "endpoint": "https://api.openai.com/v1/responses", "state": "prepared", "provider_posts": 0,
        }
        rows.append(row)
        request_bodies[request_id] = body_bytes

    total = sum((Decimal(row["conservative_exposure_aud"]) for row in rows), Decimal(0))
    if len(rows) != 2 or tuple(row["abn"] for row in rows) != tuple(abn for _, abn in ATTEMPTS):
        raise ValueError("V6 request set must be exactly World Vision then Bush Heritage")
    if total > NEW_CAMPAIGN_LIMIT_AUD:
        raise ValueError("V6 Outcomes exposure exceeds AUD 0.50")
    if total + V4_WORST_CASE_RESERVE_AUD > AGGREGATE_LIMIT_AUD:
        raise ValueError("retained V4 reserve plus V6 exposure exceeds campaign ceiling")

    run_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ("requests", "responses", "transport", "candidate-packets"):
        (run_dir / subdir).mkdir()
    for request_id, body in request_bodies.items():
        _write_atomic(run_dir / "requests" / f"{request_id.replace(':', '_')}.json", body)
    manifest = {
        "run_id": RUN_ID, "execution_status": "prepared_not_sent",
        "authorization_status": "explicitly-authorized-by-current-user-instruction-conditional-on-all-gates",
        "execution_authorized": True,
        "authorization_scope": {"capability": "outcomes", "subjects": [row["abn"] for row in rows], "attempts": 2},
        "contract_version": V6_CONTRACT_VERSION, "supersedes_contract_version": V6_SUPERSEDES_CONTRACT_VERSION,
        "builder_contract_commit": _builder_commit(),
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "rights_lineage_file_sha256": RIGHTS_LINEAGE_SHA256,
        "rights_decisions_sha256": RIGHTS_DECISIONS_SHA256,
        "provider_policy_attestation_sha256": ATTESTATION_SHA256,
        "provider": "openai", "model": MODEL, "reasoning_effort": REASONING_EFFORT,
        "delivery_mode": "standard", "socket_timeout_seconds": 300, "automatic_retries": 0,
        "per_request_limit_aud": str(PER_REQUEST_LIMIT_AUD),
        "new_v6_outcomes_limit_aud": str(NEW_CAMPAIGN_LIMIT_AUD),
        "retained_v4_worst_case_reserve_aud": str(V4_WORST_CASE_RESERVE_AUD),
        "new_v6_conservative_exposure_aud": str(total),
        "combined_v4_reserve_and_v6_exposure_aud": str(V4_WORST_CASE_RESERVE_AUD + total),
        "smith_unknown_exposure_separately_retained": "0.042120",
        "fx_aud_per_usd": AUD_PER_USD,
        "provider_calls": 0, "source_acquisitions": 0, "governed_promotions": 0,
        "attempts": rows,
    }
    _write_atomic(run_dir / "execution-manifest.json", _canonical(manifest) + b"\n")
    _write_atomic(run_dir / "provider-policy-attestation.json", attestation_path.read_bytes())
    with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
        db.execute("CREATE TABLE tickets(request_item_id TEXT PRIMARY KEY, physical_attempt_id TEXT UNIQUE NOT NULL, client_request_id TEXT UNIQUE NOT NULL, request_body_sha256 TEXT NOT NULL, state TEXT NOT NULL, provider_posts INTEGER NOT NULL DEFAULT 0, send_started_at TEXT, completed_at TEXT, response_id TEXT, server_x_request_id TEXT, response_headers_received INTEGER, transport_exception TEXT, transport_exception_type TEXT, transport_cause_type TEXT, transport_errno INTEGER, usage_json TEXT, validation_error TEXT)")
        db.executemany("INSERT INTO tickets(request_item_id,physical_attempt_id,client_request_id,request_body_sha256,state) VALUES(?,?,?,?,?)", [(row["request_item_id"], row["physical_attempt_id"], row["client_request_id"], row["request_body_sha256"], "prepared") for row in rows])
    return {"run_id": RUN_ID, "attempts": 2, "per_request_exposure_aud": [row["conservative_exposure_aud"] for row in rows], "conservative_exposure_total_aud": str(total), "provider_calls": 0, "source_acquisitions": 0}


def preflight_v6_run(source_dir: Path, rights_lineage_path: Path, attestation_path: Path, run_dir: Path) -> dict[str, Any]:
    """Recompute schema, source, rights, identities, cost and zero-crossing state."""
    manifest_raw = (run_dir / "execution-manifest.json").read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if _sha(manifest_raw) != _sha(_canonical(manifest) + b"\n"):
        raise ValueError("V6 manifest bytes are not canonical")
    if manifest.get("execution_status") != "prepared_not_sent" or not manifest.get("execution_authorized") or manifest.get("provider_calls") != 0:
        raise ValueError("V6 execution manifest is not in its authorized unsent state")
    if _builder_commit() != manifest.get("builder_contract_commit"):
        raise ValueError("Builder contract commit changed after V6 request preparation")
    if (_sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256
            or _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256
            or _sha((run_dir / "provider-policy-attestation.json").read_bytes()) != ATTESTATION_SHA256):
        raise ValueError("rights or provider-policy attestation changed")
    _, tasks = _task_map(source_dir)
    rights = _json(rights_lineage_path)
    if len(manifest["attempts"]) != 2 or [row["abn"] for row in manifest["attempts"]] != [abn for _, abn in ATTEMPTS]:
        raise ValueError("V6 attempt subject/order differs from exact authorization")
    for row in manifest["attempts"]:
        task = tasks.get(("outcomes", row["abn"]))
        if task is None or task["task_id"] != row["source_task_id"] or task["subject_id"] != row["subject_id"]:
            raise ValueError("frozen Condition A task identity changed")
        manifest_task = next(item for item in _json(source_dir / "manifest.json")["tasks"] if item["task_id"] == task["task_id"])
        if manifest_task["task_sha256"] != row["source_task_sha256"]:
            raise ValueError("frozen task hash changed")
        if _validate_rights(task, rights) != row["rights_artifacts"]:
            raise ValueError("source transmission rights no longer match the pinned decision")
        body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"] or canonical_standard_body_bytes(json.loads(body_bytes)) != body_bytes:
            raise ValueError("V6 request body hash or canonical bytes changed")
        body = json.loads(body_bytes.decode("utf-8"))
        if body.get("model") != "gpt-5.6-luna" or body.get("reasoning", {}).get("effort") != "low" or body.get("store") is not False:
            raise ValueError("V6 route/model/storage mode mismatch")
        certification = certify_provider_schema(body["text"]["format"]["schema"], contract_version=V6_CONTRACT_VERSION)
        if certification != row["schema_certification"]:
            raise ValueError("V6 provider schema certification changed")
        if row["client_request_id"] != client_request_id_for_physical_attempt(row["physical_attempt_id"]):
            raise ValueError("pre-recorded Standard client trace does not match physical attempt")
        if Decimal(row["conservative_exposure_aud"]) > Decimal("0.25"):
            raise ValueError("V6 per-request conservative exposure exceeds authority")
    with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
        tickets = db.execute("SELECT request_item_id,physical_attempt_id,client_request_id,request_body_sha256,state,provider_posts FROM tickets ORDER BY rowid").fetchall()
    expected = [(row["request_item_id"], row["physical_attempt_id"], row["client_request_id"], row["request_body_sha256"], "prepared", 0) for row in manifest["attempts"]]
    if tickets != expected:
        raise ValueError("ticket ledger is not a pristine zero-crossing V6 run")
    if any(any((run_dir / subdir).iterdir()) for subdir in ("responses", "transport", "candidate-packets")):
        raise ValueError("V6 run contains prior crossing artifacts")
    return {"preflight": "passed_no_provider_crossing", "attempts_certified": 2, "rights_artifacts_certified": sum(len(row["rights_artifacts"]) for row in manifest["attempts"]), "provider_policy_attestation_sha256": ATTESTATION_SHA256, "conservative_exposure_total_aud": manifest["new_v6_conservative_exposure_aud"], "provider_calls": 0}


def _validate_v6_packet(row: dict[str, Any], task: dict[str, Any], packet: dict[str, Any]) -> Phase6SemanticOutputV6:
    if packet.get("contract_version") != V6_CONTRACT_VERSION:
        raise ValueError("response contract version differs from V6")
    output = Phase6SemanticOutputV6.model_validate(packet)
    if output.slice_id != "outcomes" or output.subject_id != row["subject_id"]:
        raise ValueError("V6 response task identity mismatch")
    from .phase6_semantic_contracts import validate_scope_bindings
    validate_scope_bindings(output, {row["allowed_scope"]["scope_id"]})
    source_map = {source["evidence_locator_id"]: source for source in task["sources"]}
    source_texts = [source["exact_transmitted_representation"] for source in task["sources"]]
    for proposition in output.propositions:
        if proposition.scope.scope_kind != row["allowed_scope"]["scope_kind"] or proposition.scope.scope_label != row["allowed_scope"]["label"]:
            raise ValueError("V6 response scope kind/label mismatch")
        for evidence in getattr(proposition, "evidence", ()):
            source = source_map.get(evidence.locator_id)
            if source is None or evidence.locator_id not in row["allowed_locators"]:
                raise ValueError("V6 evidence locator is outside the exact frozen allow-list")
            if evidence.source_role != source["source_role"]:
                raise ValueError("V6 carrier role differs from the frozen locator")
            if evidence.source_date is not None or evidence.retrieved_at is not None:
                raise ValueError("V6 evidence dates are absent from frozen source task")
        if isinstance(proposition, OutcomeObservedReportedV6) and not proposition.observation_details.strip():
            raise ValueError("V6 observed outcome lacks the identified observation details")
        for value in _iter_strings(proposition.model_dump(mode="json")):
            if len(value) >= 48 and any(value in text for text in source_texts):
                raise ValueError("V6 candidate includes a verbatim source excerpt")
    return output


def execute_v6_run(source_dir: Path, rights_lineage_path: Path, attestation_path: Path, run_dir: Path) -> dict[str, Any]:
    """Execute each exact request once; quarantine ambiguity and stop later sends."""
    preflight = preflight_v6_run(source_dir, rights_lineage_path, attestation_path, run_dir)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY unavailable; no V6 attempt started")
    manifest = _json(run_dir / "execution-manifest.json")
    _, tasks = _task_map(source_dir)
    rights = _json(rights_lineage_path)
    client = OpenAIHTTPStandardClient()
    if client.socket_timeout_seconds != 300:
        raise ValueError("Standard transport timeout must be exactly 300 seconds")
    results: list[dict[str, Any]] = []
    stop_reason = None
    for row in manifest["attempts"]:
        if stop_reason:
            results.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_stop", "provider_posts": 0, "stop_reason": stop_reason})
            continue
        task = tasks[("outcomes", row["abn"])]
        if (_sha(rights_lineage_path.read_bytes()) != RIGHTS_LINEAGE_SHA256
                or _sha(attestation_path.read_bytes()) != ATTESTATION_SHA256
                or _validate_rights(task, rights) != row["rights_artifacts"]):
            stop_reason = "rights_or_attestation_changed_before_send"
            results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0})
            continue
        body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"] or _sha(_canonical(manifest) + b"\n") != _sha((run_dir / "execution-manifest.json").read_bytes()):
            stop_reason = "request_or_manifest_changed_before_send"
            results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0})
            continue
        started = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with sqlite3.connect(run_dir / "tickets.sqlite3", isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("SELECT state,provider_posts,request_body_sha256,physical_attempt_id,client_request_id FROM tickets WHERE request_item_id=?", (row["request_item_id"],)).fetchone()
            expected_ticket = ("prepared", 0, row["request_body_sha256"], row["physical_attempt_id"], row["client_request_id"])
            if ticket != expected_ticket:
                db.execute("ROLLBACK")
                stop_reason = "ticket_state_or_identity_changed"
                results.append({"request_item_id": row["request_item_id"], "state": "failed_local_pre_send", "provider_posts": 0})
                continue
            db.execute("UPDATE tickets SET state='send_started',provider_posts=1,send_started_at=? WHERE request_item_id=?", (started, row["request_item_id"]))
        request_meta = {"request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "client_request_id": row["client_request_id"], "request_body_sha256": row["request_body_sha256"], "endpoint": row["endpoint"], "request_started_at": started, "provider_policy_attestation_sha256": ATTESTATION_SHA256, "rights_decisions_sha256": RIGHTS_DECISIONS_SHA256}
        _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical({**request_meta, "state": "crossing_started"}) + b"\n")
        with (run_dir / "transport-audit.jsonl").open("ab") as stream:
            stream.write(_canonical({"event": "provider_crossing_started", **request_meta}) + b"\n")
            stream.flush(); os.fsync(stream.fileno())
        try:
            response = client.create_response_once(body_bytes, client_request_id=row["client_request_id"], request_started_at=started)
        except StandardTransportError as exc:
            state = "ambiguous" if exc.ambiguous else "terminal_provider_response"
            raw_sha = None
            if exc.raw_bytes is not None:
                _write_atomic(run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json", exc.raw_bytes)
                raw_sha = _sha(exc.raw_bytes)
            details = {**request_meta, "state": state, "http_status": exc.status_code, "server_x_request_id": exc.request_id, "response_headers_received": exc.response_headers_received, "transport_exception": str(exc), "transport_exception_type": exc.exception_type, "transport_cause_type": exc.cause_type, "transport_errno": exc.error_number, "transport_elapsed_seconds": exc.elapsed_seconds, "transport_state": exc.transport_state, "raw_response_sha256": raw_sha}
            _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(details) + b"\n")
            with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
                db.execute("UPDATE tickets SET state=?,completed_at=?,server_x_request_id=?,response_headers_received=?,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=? WHERE request_item_id=?", (state, datetime.now(timezone.utc).isoformat(), exc.request_id, int(exc.response_headers_received), str(exc)[:512], exc.exception_type, exc.cause_type, exc.error_number, row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "client_request_id": row["client_request_id"], "server_x_request_id": exc.request_id, "conservative_exposure_aud": row["conservative_exposure_aud"], "transport_exception": str(exc), "transport_exception_type": exc.exception_type, "transport_cause_type": exc.cause_type})
            stop_reason = "ambiguous_or_terminal_provider_transport"
            continue
        except Exception as exc:
            details = {**request_meta, "state": "ambiguous", "transport_exception": f"{type(exc).__name__}: {exc}"[:512], "transport_exception_type": type(exc).__name__, "transport_cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None, "transport_errno": getattr(exc.__cause__ or exc, "errno", None), "response_headers_received": False}
            _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(details) + b"\n")
            with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
                db.execute("UPDATE tickets SET state='ambiguous',completed_at=?,transport_exception=?,transport_exception_type=?,transport_cause_type=?,transport_errno=?,response_headers_received=0 WHERE request_item_id=?", (datetime.now(timezone.utc).isoformat(), details["transport_exception"], details["transport_exception_type"], details["transport_cause_type"], details["transport_errno"], row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": "ambiguous", "provider_posts": 1, **details})
            stop_reason = "ambiguous_or_unclassified_transport"
            continue

        response_path = run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json"
        _write_atomic(response_path, response.raw_bytes)
        usage = response.body.get("usage") or {}
        try:
            usd, aud = standard_actual_cost(usage, AUD_PER_USD, model=MODEL)
            cost_error = None
        except Exception as exc:
            usd = aud = None
            cost_error = f"{type(exc).__name__}: {exc}"[:512]
        parsed = None
        error = None
        try:
            if not (200 <= response.status_code < 300) or response.body.get("status") != "completed" or response.body.get("incomplete_details") is not None:
                raise ValueError("provider response is not completed")
            if response.body.get("model") != MODEL:
                raise ValueError("provider model identity differs from requested Luna model")
            output_text = _output_text(response.body)
            if not output_text:
                raise ValueError("provider response has no structured output text")
            parsed = _validate_v6_packet(row, task, json.loads(output_text))
        except Exception as exc:
            error = str(exc)[:1200]
        meta = {**request_meta, "state": "completed" if parsed is not None else "completed_validation_failed", "http_status": response.status_code, "server_x_request_id": response.server_request_id, "response_id": response.body.get("id"), "response_headers_received": response.response_headers_received, "raw_response_sha256": _sha(response.raw_bytes), "provider_model": response.body.get("model"), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "actual_cost_usd": None if usd is None else str(usd), "actual_cost_aud": None if aud is None else str(aud), "cost_error": cost_error, "validation_error": error}
        _write_atomic(run_dir / "transport" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(meta) + b"\n")
        with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
            db.execute("UPDATE tickets SET state=?,completed_at=?,response_id=?,server_x_request_id=?,response_headers_received=?,usage_json=?,validation_error=? WHERE request_item_id=?", (meta["state"], datetime.now(timezone.utc).isoformat(), meta["response_id"], response.server_request_id, int(response.response_headers_received), json.dumps(usage, sort_keys=True), error, row["request_item_id"]))
        result = {"request_item_id": row["request_item_id"], "state": meta["state"], "provider_posts": 1, "client_request_id": row["client_request_id"], "server_x_request_id": response.server_request_id, "response_id": meta["response_id"], "model": meta["provider_model"], "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "actual_cost_usd": meta["actual_cost_usd"], "actual_cost_aud": meta["actual_cost_aud"], "conservative_exposure_aud": row["conservative_exposure_aud"], "response_sha256": meta["raw_response_sha256"], "validation_error": error}
        if parsed is not None:
            candidate = {"candidate_status": "unreviewed_mechanical_candidate", "run_id": RUN_ID, "slice_id": "outcomes", "subject_id": row["subject_id"], "abn": row["abn"], "request_item_id": row["request_item_id"], "physical_attempt_id": row["physical_attempt_id"], "provider_response_id": meta["response_id"], "client_request_id": row["client_request_id"], "server_x_request_id": response.server_request_id, "contract_version": V6_CONTRACT_VERSION, "schema_sha256": row["schema_sha256"], "source_task_sha256": row["source_task_sha256"], "source_content_sha256": row["source_content_sha256"], "request_body_sha256": row["request_body_sha256"], "response_body_sha256": meta["raw_response_sha256"], "propositions": [item.model_dump(mode="json") for item in parsed.propositions], "reviewer_dispositions": []}
            _write_atomic(run_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json", _canonical(candidate) + b"\n")
            result["proposition_count"] = len(parsed.propositions)
        else:
            stop_reason = "critical_v6_contract_validation_failure"
        results.append(result)

    report = {"run_id": RUN_ID, "contract_version": V6_CONTRACT_VERSION, "execution_status": "executed_or_stopped", "model": MODEL, "reasoning_effort": REASONING_EFFORT, "delivery_mode": "standard", "provider_calls": sum(row["provider_posts"] for row in results), "source_acquisitions": 0, "governed_promotions": 0, "global_stop_reason": stop_reason, "preflight": preflight, "results": results}
    _write_atomic(run_dir / "execution-results.json", _canonical(report) + b"\n")
    return report


def prepare_v6_review_packet(source_dir: Path, run_dir: Path, v4_review_dir: Path, review_dir: Path) -> dict[str, Any]:
    """Assemble a private candidate-blind source packet and blank adjudication materials."""
    if review_dir.exists() and any(review_dir.iterdir()):
        raise FileExistsError("V6 review packet directory is not empty")
    manifest, tasks = _task_map(source_dir)
    results = _json(run_dir / "execution-results.json")
    if results.get("provider_calls") != 2 or any(row.get("state") != "completed" for row in results["results"]):
        raise ValueError("both V6 outputs must be mechanically eligible before preparing the review packet")
    for name in ("condition-a-source-only", "raw-v6-provider-responses", "v6-candidate-packets", "evidence-lineage", "v4-comparison"):
        (review_dir / name).mkdir(parents=True, exist_ok=True)
    worksheet: list[dict[str, str]] = []
    comparisons = []
    for row in _json(run_dir / "execution-manifest.json")["attempts"]:
        task = tasks[("outcomes", row["abn"])]
        task_record = next(item for item in manifest["tasks"] if item["task_id"] == task["task_id"])
        task_bytes = (source_dir / task_record["path"]).read_bytes()
        _write_atomic(review_dir / "condition-a-source-only" / f"outcomes__{row['abn']}.json", task_bytes)
        response_file = run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json"
        _write_atomic(review_dir / "raw-v6-provider-responses" / response_file.name, response_file.read_bytes())
        candidate_file = run_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json"
        candidate_bytes = candidate_file.read_bytes()
        _write_atomic(review_dir / "v6-candidate-packets" / candidate_file.name, candidate_bytes)
        candidate = json.loads(candidate_bytes)
        _write_atomic(review_dir / "evidence-lineage" / f"outcomes__{row['abn']}.json", _canonical({"source_task_sha256": row["source_task_sha256"], "sources": [{key: source.get(key) for key in ("source_artifact_id", "source_record_id", "source_family", "source_role", "source_locator", "evidence_locator_id", "evidence_representation_sha256")} for source in task["sources"]]}) + b"\n")
        for index, prop in enumerate(candidate["propositions"]):
            worksheet.append({"subject_id": row["subject_id"], "proposition_index": str(index), "proposition_type": prop["proposition_type"], "epistemic_class": prop["epistemic_class"], "scope_id": prop["scope"]["scope_id"], "evidence_locators": ";".join(item["locator_id"] for item in prop.get("evidence", [])), "reviewer_id": "", "human_disposition": "", "rationale": "", "accepted_proposition": ""})
        old_request_id = V4_REQUEST_IDS[row["abn"]]
        old_path = v4_review_dir / "raw-v4-provider-responses" / f"requestitem_{old_request_id}.json"
        old_replay = v4_review_dir / "v5-offline-replay" / f"requestitem_{old_request_id}.json"
        prior_result = (
            "V5 replay passed for all 5 propositions; human review found reach/participation were not promoted to outcomes and evidence did not provide a measured beneficiary outcome."
            if row["abn"] == "28004778081" else
            "V5 replay passed for all 12 propositions; human review rejected proposition 11 as an observed outcome because the report gave no indicator, method, comparator, structured assessment, or reported observation basis."
        )
        comparisons.append({"abn": row["abn"], "v4_response_sha256": V4_RESPONSE_SHA256[row["abn"]], "v6_response_sha256": _sha(response_file.read_bytes()), "v4_human_review_result": prior_result, "v6_candidate_proposition_count": len(candidate["propositions"]), "comparison_note": "Reviewer should compare independently; this packet makes no human adjudication."})
        _write_atomic(review_dir / "v4-comparison" / f"v4-response-{old_path.name}", old_path.read_bytes())
        _write_atomic(review_dir / "v4-comparison" / f"v5-replay-{old_replay.name}", old_replay.read_bytes())
    with (review_dir / "proposition-adjudication-worksheet.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(worksheet[0]) if worksheet else [])
        writer.writeheader(); writer.writerows(worksheet)
    analyst = {"reviewer_fields_blank": True, "tasks": [task.get("analyst_questions", []) for task in (tasks[("outcomes", abn)] for _, abn in ATTEMPTS)]}
    _write_atomic(review_dir / "analyst-task-material.json", _canonical(analyst) + b"\n")
    replay_path = run_dir / "v4-v6-offline-replay.json"
    if not replay_path.is_file():
        raise ValueError("V6 offline replay report is required in the comparison packet")
    _write_atomic(review_dir / "v4-comparison" / "v6-offline-replay.json", replay_path.read_bytes())
    report = {"packet_status": "READY_FOR_HUMAN_REVIEW", "review_type": "independent proposition and analyst-task review", "contract_version": V6_CONTRACT_VERSION, "subjects": comparisons, "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256, "reviewer_fields_initially_blank": True, "human_adjudication_performed": False, "governed_promotions": 0, "source_acquisitions": 0, "provider_calls_during_packet_preparation": 0, "smith_unknown_exposure_retained_separately": "0.042120", "limitations": ["Two-subject bounded confirmation only; does not satisfy the original six-subject usefulness denominator.", "The V4 and V5 results remain immutable historical records.", "This packet does not establish Outcomes advancement; independent human adjudication remains required."]}
    _write_atomic(review_dir / "review-packet-manifest.json", _canonical(report) + b"\n")
    return report
