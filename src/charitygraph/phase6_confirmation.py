"""Bounded, private runner for the approved Phase 6 confirmation experiment.

The runner uses only the already-exported Condition-A material. Request and
response bytes stay in a private temporary directory. Every physical request
has a unique SQLite ticket that is changed to ``send_started`` before the
one-shot Standard POST; an interrupted send is never retried.
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
from .phase5_openai_dry_run import (
    PRICING,
    conservative_standard_hard_max_aud,
    estimate_tokens,
    standard_actual_cost,
)
from .phase5_standard_transport import (
    OpenAIHTTPStandardClient,
    StandardTransportError,
    body_sha256,
    canonical_standard_body_bytes,
)
from .phase6_semantic_contracts import (
    CurrentAvailability,
    Phase6SemanticOutput,
    validate_scope_bindings,
)


RUN_ID = "phase6-corrected-confirmation-20260913-v2"
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 8000
AUD_PER_USD = "1.52"  # Frozen FX snapshot from the approved Phase-6 preparation.
PER_REQUEST_LIMIT_AUD = "0.25"
AGGREGATE_LIMIT_AUD = "1.50"
CONDITION_A_MANIFEST_SHA256 = "62fa35105741f92fc5f297183745b798062b36eb41653a231a159d5acc3cfd81"
BUILDER_CONTRACT_COMMIT = "7896e6e41423f5a17612eece0d2665e58913fe07"
AUTHORIZATION_SOURCE_SHA256 = "48a3484e952c7c7013f8a49dbb5c12877f9a7d5a54008530dea32b425abdfd1d"

# One predeclared hard-case repeat in each capability cohort. It adds no new
# subject and directly exercises the boundary named in the approved design.
COHORTS = {
    "outcomes": {
        "28000030179": ("Smith Family outcome versus output boundary", True),
        "28004778081": ("World Vision reach and participation boundary", False),
        "78053639115": ("Bush Heritage protected-area output versus outcome boundary", False),
    },
    "commitments": {
        "65159324697": ("Sunrise Project stated commitments and reported action", False),
        "50169561394": ("Australian Red Cross first-party versus external evidence boundary", False),
        "61002643852": ("Greenpeace ambiguous commitment and implementation scope", True),
    },
    "capacity": {
        "32565549842": ("SGCH access pathway versus housing scale boundary", True),
        "80009663478": ("RFDS Queensland dated 24/7 availability boundary", False),
        "57057493017": ("Leukaemia Foundation information versus access pathway boundary", False),
    },
}

CAPABILITY_INSTRUCTIONS = {
    "outcomes": (
        "Classify each supported report as activity, output, reach/participation, observed outcome, "
        "contribution claim, reported causal attribution, or independently supported causal evidence. "
        "Do not upgrade reach, service delivery, hectares, expenditure, surplus, or organizational scale "
        "into a beneficiary outcome. Keep the measured population, indicator, denominator, unit, period, "
        "and scope when the source supports them. Source causal language remains attributed to that source."
    ),
    "commitments": (
        "Separate a stated commitment, adopted policy/standard, first-party implementation report, "
        "independently observed implementation, external/regulatory implementation evidence, and a "
        "reported implementation outcome. A first-party action is never independently observed practice. "
        "A commitment or policy alone does not prove implementation, compliance, completeness, or effect."
    ),
    "capacity": (
        "Separate service existence, intended beneficiary, formal eligibility, access information, actual "
        "entry pathway, historical volume, resources/workforce, service scale, capacity, dated availability, "
        "and unknown availability. A beneficiary group is not an eligibility rule; an address is not a "
        "pathway; throughput, housing stock, expenditure, staff, beds, and locations are not a capacity "
        "limit; service existence is not availability. Do not emit current_availability in this experiment: "
        "the frozen packets have no recorded source date or retrieval timestamp. Use a dated source claim "
        "only when its date is explicit in the supplied evidence; otherwise use availability_unknown."
    ),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _definition_names_for_slice(schema: dict[str, Any], slice_id: str) -> list[str]:
    groups = schema["properties"]["propositions"]["items"]["anyOf"]
    group_index = {"outcomes": 0, "commitments": 1, "capacity": 2}[slice_id]
    return [
        item["$ref"].rsplit("/", 1)[-1]
        for item in groups[group_index]["oneOf"]
        if not (slice_id == "capacity" and item["$ref"].endswith("/CurrentAvailability"))
    ]


def _reachable_definitions(definitions: dict[str, Any], roots: list[str]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected[name] = definitions[name]
        refs: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                ref = value.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/"):
                    refs.append(ref.rsplit("/", 1)[-1])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(selected[name])
        pending.extend(refs)
    return selected


def provider_schema(slice_id: str, subject_id: str, scope: dict[str, Any], locators: list[str]) -> dict[str, Any]:
    """Make a strict, task-bound provider schema from the approved Pydantic models."""
    if slice_id not in COHORTS or not locators or len(locators) != len(set(locators)):
        raise ValueError("invalid capability or evidence-locator allow-list")
    schema = Phase6SemanticOutput.model_json_schema()
    names = _definition_names_for_slice(schema, slice_id)
    root = {
        key: value for key, value in schema.items()
        if key not in {"$defs", "title", "description"}
    }
    root["properties"]["slice_id"] = {"type": "string", "enum": [slice_id]}
    root["properties"]["subject_id"] = {"type": "string", "enum": [subject_id]}
    root["properties"]["propositions"]["items"] = {
        "anyOf": [{"$ref": f"#/$defs/{name}"} for name in names]
    }
    definitions = _reachable_definitions(schema["$defs"], names)
    definitions["Phase6Scope"]["properties"]["scope_id"] = {
        "type": "string", "enum": [scope["scope_id"]]
    }
    definitions["Phase6Scope"]["properties"]["scope_kind"] = {
        "type": "string", "enum": [scope["scope_kind"]]
    }
    definitions["Phase6Scope"]["properties"]["scope_label"] = {
        "type": "string", "enum": [scope["label"]]
    }
    definitions["Phase6EvidenceRef"]["properties"]["locator_id"] = {
        "type": "string", "enum": locators
    }

    def strict_subset(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("title", None)
            value.pop("default", None)
            value.pop("discriminator", None)
            if "const" in value:
                value["enum"] = [value.pop("const")]
            if "oneOf" in value:
                raise ValueError("provider schema unexpectedly contains oneOf")
            if value.get("type") == "object" and isinstance(value.get("properties"), dict):
                value["additionalProperties"] = False
                value["required"] = list(value["properties"])
            for child in value.values():
                strict_subset(child)
        elif isinstance(value, list):
            for child in value:
                strict_subset(child)

    root["$defs"] = definitions
    strict_subset(root)
    return root


def _prompt(task: dict[str, Any]) -> str:
    intro = (
        "You are performing a bounded CharityGraph Phase 6 semantic confirmation on frozen evidence only. "
        "Return candidate assertions only; do not make a human decision, do not infer absence from silence, "
        "and do not use external knowledge or search. Use only the exact allowed organization scope and "
        "the evidence locator IDs supplied below. Every positive assertion must cite one or more allowed "
        "locators and preserve the source's role. If evidence does not support a proposition, omit it. "
        "Do not include quotations or source-content excerpts in your output. For evidence source_date and "
        "retrieved_at, use null because the frozen manifests record neither."
    )
    question = (
        f"Capability: {task['slice_id']}\n"
        f"Subject: {task['subject_name']} (ABN {task['abn']})\n"
        f"Task focus: {COHORTS[task['slice_id']][task['abn']][0]}\n"
        f"Allowed proposition distinctions: {CAPABILITY_INSTRUCTIONS[task['slice_id']]}\n"
        f"Analyst questions: {json.dumps(task['analyst_questions'], ensure_ascii=False)}\n"
        f"Allowed scopes: {json.dumps(task['allowed_scope_ids'], ensure_ascii=False, sort_keys=True)}\n"
        f"Unavailable-source records: {json.dumps(task['unavailable_sources'], ensure_ascii=False, sort_keys=True)}\n"
        f"Frozen evidence records: {json.dumps(task['sources'], ensure_ascii=False, sort_keys=True)}"
    )
    return intro + "\n\n" + question


def _load_approved_source_export(export_dir: Path) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    manifest_path = export_dir / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    if _sha(manifest_raw) != CONDITION_A_MANIFEST_SHA256:
        raise ValueError("Condition A manifest hash does not match the owner-approved identity")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if manifest.get("provider_calls") != 0 or manifest.get("source_acquisitions") != 0:
        raise ValueError("Condition A export has unexpected provider/source-acquisition activity")
    if manifest.get("candidate_outputs_read") != 0 or manifest.get("candidate_propositions_included") != 0:
        raise ValueError("Condition A export is not candidate-blind")
    tasks: dict[tuple[str, str], dict[str, Any]] = {}
    for row in manifest.get("tasks", []):
        path = export_dir / row["path"]
        raw = path.read_bytes()
        if _sha(raw) != row["task_sha256"]:
            raise ValueError("Condition A task hash mismatch")
        task = json.loads(raw.decode("utf-8"))
        key = (task["slice_id"], task["abn"])
        if key in tasks:
            raise ValueError("Condition A export contains duplicate subject/capability tasks")
        tasks[key] = task
    return manifest, tasks


def _ticket_id(logical_task_id: str, body_hash: str) -> str:
    return "requestitem:" + _sha(f"{RUN_ID}:{logical_task_id}:{body_hash}".encode())


def prepare_run(export_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Preflight and materialize private, immutable requests without a provider call."""
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError("confirmation run directory is non-empty; refusing to overwrite")
    condition_a_manifest, tasks = _load_approved_source_export(export_dir)
    rows: list[dict[str, Any]] = []
    for slice_id, subjects in COHORTS.items():
        for abn, (focus, repeat) in subjects.items():
            task = tasks.get((slice_id, abn))
            if task is None or task.get("condition") != "A_source_only" or task.get("abn") != abn:
                raise ValueError(f"approved subject missing from Condition A export: {slice_id}/{abn}")
            if len(task.get("allowed_scope_ids", [])) != 1:
                raise ValueError("confirmation requires exactly one retained organization scope")
            scope = task["allowed_scope_ids"][0]
            sources = task.get("sources", [])
            locators = [source["evidence_locator_id"] for source in sources]
            if not sources or len(locators) != len(set(locators)):
                raise ValueError("source packet has missing or duplicate evidence locators")
            source_hashes = []
            for source in sources:
                if not isinstance(source.get("exact_transmitted_representation"), str) or not source["exact_transmitted_representation"]:
                    raise ValueError("frozen source representation is missing")
                source_hashes.append(_sha(source["exact_transmitted_representation"].encode("utf-8")))
            repeats = (1, 2) if repeat else (1,)
            for ordinal in repeats:
                prompt_text = _prompt(task)
                schema = provider_schema(slice_id, task["subject_id"], scope, locators)
                schema_hash = _sha(_canonical(schema))
                prompt_hash = _sha(prompt_text.encode("utf-8"))
                contract_hash = _sha(_canonical({
                    "builder_commit": BUILDER_CONTRACT_COMMIT,
                    "contract": "phase6-semantic-correction-v2-confirmation",
                    "slice_id": slice_id,
                    "schema_sha256": schema_hash,
                    "prompt_sha256": prompt_hash,
                }))
                logical_task_id = f"phase6-confirm:{slice_id}:{abn}:replicate-{ordinal}"
                body = {
                    "model": MODEL,
                    "reasoning": {"effort": REASONING_EFFORT},
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "store": False,
                    "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt_text}]}],
                    "text": {"format": {
                        "type": "json_schema",
                        "name": f"phase6_{slice_id}_confirmation_v2",
                        "strict": True,
                        "schema": schema,
                    }},
                    "metadata": {
                        "logical_task_id": logical_task_id,
                        "semantic_contract_hash": contract_hash,
                    },
                }
                body_bytes = canonical_standard_body_bytes(body)
                body_hash = body_sha256(body_bytes)
                estimate = estimate_tokens(body)
                exposure = conservative_standard_hard_max_aud(
                    estimate, MAX_OUTPUT_TOKENS, AUD_PER_USD, model=MODEL,
                )
                request_id = _ticket_id(logical_task_id, body_hash)
                physical_id = "physicalattempt:" + _sha((request_id + ":physical:1").encode())
                row = {
                    "run_id": RUN_ID,
                    "slice_id": slice_id,
                    "abn": abn,
                    "subject_id": task["subject_id"],
                    "subject_name": task["subject_name"],
                    "logical_task_id": logical_task_id,
                    "replicate_ordinal": ordinal,
                    "replicate_count": len(repeats),
                    "focus": focus,
                    "request_item_id": request_id,
                    "physical_attempt_id": physical_id,
                    "model": MODEL,
                    "reasoning_effort": REASONING_EFFORT,
                    "delivery_mode": "standard",
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "provider_schema_name": f"phase6_{slice_id}_confirmation_v2",
                    "semantic_contract_hash": contract_hash,
                    "schema_sha256": schema_hash,
                    "prompt_sha256": prompt_hash,
                    "request_body_sha256": body_hash,
                    "source_export_task_sha256": next(
                        item["task_sha256"] for item in condition_a_manifest["tasks"]
                        if item["task_id"] == task["task_id"]
                    ),
                    "source_input_hashes": next(
                        item["source_input_hashes"] for item in condition_a_manifest["tasks"]
                        if item["task_id"] == task["task_id"]
                    ),
                    "source_content_sha256": source_hashes,
                    "allowed_scope": scope,
                    "allowed_locators": locators,
                    "source_metadata": [
                        {"evidence_locator_id": source["evidence_locator_id"], "source_role": source["source_role"]}
                        for source in sources
                    ],
                    "input_tokens_estimate": estimate,
                    "conservative_exposure_aud": str(exposure),
                    "state": "prepared",
                    "provider_posts": 0,
                    "body": body,
                }
                if exposure > Decimal(PER_REQUEST_LIMIT_AUD):
                    row["state"] = "economic_exclusion"
                    row["failure_reason"] = "conservative request exposure exceeds AUD 0.25"
                rows.append(row)

    total_exposure = sum((Decimal(row["conservative_exposure_aud"]) for row in rows if row["state"] == "prepared"), Decimal("0"))
    if total_exposure > Decimal(AGGREGATE_LIMIT_AUD):
        raise ValueError("conservative aggregate request exposure exceeds AUD 1.50")
    if len({row["request_item_id"] for row in rows}) != len(rows):
        raise ValueError("execution-ticket identity collision")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "requests").mkdir()
    for row in rows:
        (run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json").write_bytes(
            canonical_standard_body_bytes(row["body"])
        )
    public_rows = [{key: value for key, value in row.items() if key != "body"} for row in rows]
    manifest = {
        "run_id": RUN_ID,
        "execution_status": "prepared_not_sent",
        "authorization_request_sha256": AUTHORIZATION_SOURCE_SHA256,
        "authorization_scope": {
            "capabilities": ["outcomes", "commitments", "capacity"],
            "provider": "openai",
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "delivery_mode": "standard",
            "physical_posts_per_ticket": 1,
            "automatic_retries": 0,
            "fallbacks": [],
        },
        "builder_contract_commit": BUILDER_CONTRACT_COMMIT,
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "provider": "openai",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "delivery_mode": "standard",
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "per_request_limit_aud": PER_REQUEST_LIMIT_AUD,
        "aggregate_limit_aud": AGGREGATE_LIMIT_AUD,
        "fx_aud_per_usd": AUD_PER_USD,
        "repeat_policy": "one independent repeat for the predeclared hard case in each capability",
        "provider_calls": 0,
        "source_acquisitions": 0,
        "governed_promotions": 0,
        "tasks": public_rows,
        "conservative_exposure_total_aud": str(total_exposure),
    }
    manifest_path = run_dir / "execution-manifest.json"
    manifest_path.write_bytes(_canonical(manifest) + b"\n")
    manifest_hash = _sha(manifest_path.read_bytes())
    (run_dir / "tickets.sqlite3").touch()
    with sqlite3.connect(run_dir / "tickets.sqlite3") as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS tickets (request_item_id TEXT PRIMARY KEY, physical_attempt_id TEXT UNIQUE NOT NULL, request_body_sha256 TEXT NOT NULL, state TEXT NOT NULL, provider_posts INTEGER NOT NULL DEFAULT 0, send_started_at TEXT, completed_at TEXT, response_id TEXT, provider_request_id TEXT, usage_json TEXT, failure_class TEXT, failure_message TEXT)")
        db.executemany(
            "INSERT INTO tickets(request_item_id,physical_attempt_id,request_body_sha256,state) VALUES(?,?,?,?)",
            [(row["request_item_id"], row["physical_attempt_id"], row["request_body_sha256"], row["state"]) for row in rows],
        )
        db.commit()
    return {
        "manifest_sha256": manifest_hash,
        "task_count": len(rows),
        "pre_send_exclusions": sum(row["state"] == "economic_exclusion" for row in rows),
        "provider_calls": 0,
        "source_acquisitions": 0,
        "conservative_exposure_total_aud": str(total_exposure),
        "run_directory": str(run_dir),
    }


def _mechanical_validate(row: dict[str, Any], packet: dict[str, Any]) -> Phase6SemanticOutput:
    parsed = Phase6SemanticOutput.model_validate(packet)
    if parsed.slice_id != row["slice_id"] or parsed.subject_id != row["subject_id"]:
        raise ValueError("response task identity mismatch")
    validate_scope_bindings(parsed, {row["allowed_scope"]["scope_id"]})
    for proposition in parsed.propositions:
        if proposition.scope.scope_kind != row["allowed_scope"]["scope_kind"] or proposition.scope.scope_label != row["allowed_scope"]["label"]:
            raise ValueError("scope ID, kind, or label does not match the frozen organization scope")
        if isinstance(proposition, CurrentAvailability):
            raise ValueError("current_availability is prohibited: frozen evidence lacks a mechanical contemporaneous-date binding")
        for evidence in getattr(proposition, "evidence", ()):
            if evidence.locator_id not in row["allowed_locators"]:
                raise ValueError("evidence locator is outside the task's frozen source allow-list")
            source = next((item for item in row["source_metadata"] if item["evidence_locator_id"] == evidence.locator_id), None)
            if source is None or evidence.source_role != source["source_role"]:
                raise ValueError("source-role/locator binding mismatch")
            if evidence.source_date is not None or evidence.retrieved_at is not None:
                raise ValueError("source date/retrieval timestamp is not present in the frozen packet")
        # Candidate packets must contain claims and locators, never copied
        # source excerpts. Exact long-substring detection is a privacy check,
        # not a semantic classifier.
        for value in _iter_strings(proposition.model_dump(mode="json")):
            if len(value) >= 48 and any(value in source_text for source_text in row["source_texts"]):
                raise ValueError("candidate contains a verbatim source excerpt; no candidate packet emitted")
    return parsed


def execute_run(run_dir: Path, export_dir: Path) -> dict[str, Any]:
    """Execute prepared one-shot requests in order; stop on any uncertain crossing."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is unavailable; no provider attempt started")
    manifest_path = run_dir / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_bytes().decode("utf-8"))
    if manifest.get("run_id") != RUN_ID or manifest.get("execution_status") != "prepared_not_sent" or manifest.get("provider_calls") != 0:
        raise ValueError("run manifest is not an unsent prepared manifest")
    if manifest.get("authorization_request_sha256") != AUTHORIZATION_SOURCE_SHA256:
        raise ValueError("one-off provider authorization identity does not match the owner request")
    if manifest.get("condition_a_manifest_sha256") != CONDITION_A_MANIFEST_SHA256:
        raise ValueError("approved Condition A identity changed")
    if manifest.get("model") != MODEL or manifest.get("reasoning_effort") != REASONING_EFFORT or manifest.get("delivery_mode") != "standard":
        raise ValueError("approved model route does not match the prepared manifest")
    tickets_path = run_dir / "tickets.sqlite3"
    if not tickets_path.is_file():
        raise ValueError("execution tickets are absent")
    _condition_a_manifest, frozen_tasks = _load_approved_source_export(export_dir)
    if len({row["request_item_id"] for row in manifest["tasks"]}) != len(manifest["tasks"]):
        raise ValueError("request ticket IDs are not unique")
    if len({row["physical_attempt_id"] for row in manifest["tasks"]}) != len(manifest["tasks"]):
        raise ValueError("physical attempt IDs are not unique")
    expected_tasks = {
        (slice_id, abn, ordinal)
        for slice_id, subjects in COHORTS.items()
        for abn, (_focus, repeat) in subjects.items()
        for ordinal in ((1, 2) if repeat else (1,))
    }
    actual_tasks = {(row["slice_id"], row["abn"], row["replicate_ordinal"]) for row in manifest["tasks"]}
    if actual_tasks != expected_tasks:
        raise ValueError("manifest cohort/repeat set differs from the explicit owner authorization")
    if any(Decimal(row["conservative_exposure_aud"]) > Decimal(PER_REQUEST_LIMIT_AUD) for row in manifest["tasks"] if row["state"] == "prepared"):
        raise ValueError("per-request conservative exposure exceeds the owner limit")
    if sum((Decimal(row["conservative_exposure_aud"]) for row in manifest["tasks"] if row["state"] == "prepared"), Decimal("0")) > Decimal(AGGREGATE_LIMIT_AUD):
        raise ValueError("prepared requests exceed the approved aggregate exposure")
    body_cache: dict[str, bytes] = {}
    with sqlite3.connect(tickets_path) as db:
        existing_tickets = db.execute("SELECT request_item_id,physical_attempt_id,request_body_sha256,state FROM tickets").fetchall()
    if len(existing_tickets) != len(manifest["tasks"]):
        raise ValueError("ticket count does not match frozen manifest; no send")
    ticket_map = {item[0]: item[1:] for item in existing_tickets}
    for row in manifest["tasks"]:
        expected_ticket = ticket_map.get(row["request_item_id"])
        if expected_ticket is None or expected_ticket[:2] != (row["physical_attempt_id"], row["request_body_sha256"]):
            raise ValueError("ticket identity/body binding mismatch; no send")
        if row["state"] == "prepared" and expected_ticket[2] != "prepared":
            raise ValueError("request has an ambiguous or prior provider crossing; no send")
        if row["state"] == "economic_exclusion":
            continue
        task = frozen_tasks.get((row["slice_id"], row["abn"]))
        if task is None or task["subject_id"] != row["subject_id"]:
            raise ValueError("approved source subject identity mismatch; no send")
        source_task_row = next((item for item in _condition_a_manifest["tasks"] if item["task_id"] == task["task_id"]), None)
        if source_task_row is None or source_task_row["task_sha256"] != row["source_export_task_sha256"]:
            raise ValueError("source task hash mismatch; no send")
        source_hashes = [_sha(source["exact_transmitted_representation"].encode("utf-8")) for source in task["sources"]]
        if source_hashes != row["source_content_sha256"]:
            raise ValueError("frozen source representation identity mismatch; no send")
        metadata = [{"evidence_locator_id": source["evidence_locator_id"], "source_role": source["source_role"]} for source in task["sources"]]
        if metadata != row["source_metadata"]:
            raise ValueError("frozen source locator/role identity mismatch; no send")
        row["source_texts"] = [source["exact_transmitted_representation"] for source in task["sources"]]
        body_path = run_dir / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
        body_bytes = body_path.read_bytes()
        if body_sha256(body_bytes) != row["request_body_sha256"]:
            raise ValueError("frozen request body hash mismatch; no send")
        body = json.loads(body_bytes.decode("utf-8"))
        if body.get("model") != MODEL or body.get("reasoning", {}).get("effort") != REASONING_EFFORT or body.get("max_output_tokens") != MAX_OUTPUT_TOKENS:
            raise ValueError("provider request route mismatch; no send")
        if "service_tier" in body:
            raise ValueError("request contains an unauthorized service tier; no send")
        if body.get("metadata") != {"logical_task_id": row["logical_task_id"], "semantic_contract_hash": row["semantic_contract_hash"]}:
            raise ValueError("request metadata identity mismatch; no send")
        input_text = body.get("input", [{}])[0].get("content", [{}])[0].get("text")
        if not isinstance(input_text, str) or _sha(input_text.encode("utf-8")) != row["prompt_sha256"] or input_text != _prompt(task):
            raise ValueError("pinned prompt/source packet identity mismatch; no send")
        text_format = body.get("text", {}).get("format", {})
        if text_format.get("type") != "json_schema" or text_format.get("strict") is not True or text_format.get("name") != row["provider_schema_name"]:
            raise ValueError("provider structured-output route mismatch; no send")
        expected_schema = provider_schema(row["slice_id"], row["subject_id"], row["allowed_scope"], row["allowed_locators"])
        if text_format.get("schema") != expected_schema or _sha(_canonical(expected_schema)) != row["schema_sha256"]:
            raise ValueError("provider schema identity mismatch; no send")
        body_cache[row["request_item_id"]] = body_bytes
    for folder in (run_dir / "responses", run_dir / "candidate-packets"):
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("prior response/candidate artifacts exist; previous provider crossing is uncertain")
    results: list[dict[str, Any]] = []
    client = OpenAIHTTPStandardClient()
    stopped_slices: set[str] = set()
    global_stop = False
    for row in manifest["tasks"]:
        if global_stop:
            results.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_global_stop", "provider_posts": 0})
            continue
        if row["slice_id"] in stopped_slices:
            results.append({"request_item_id": row["request_item_id"], "state": "not_attempted_after_capability_stop", "provider_posts": 0})
            continue
        if row["state"] != "prepared":
            results.append({"request_item_id": row["request_item_id"], "state": row["state"], "provider_posts": 0})
            continue
        body_bytes = body_cache[row["request_item_id"]]
        body = json.loads(body_bytes.decode("utf-8"))
        with sqlite3.connect(tickets_path, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = db.execute("SELECT state,request_body_sha256 FROM tickets WHERE request_item_id=? AND physical_attempt_id=?", (row["request_item_id"], row["physical_attempt_id"])).fetchone()
            if ticket is None or ticket[0] != "prepared" or ticket[1] != row["request_body_sha256"]:
                db.execute("ROLLBACK")
                raise ValueError("execution ticket is non-unique, changed, or already crossed; no resend")
            db.execute("UPDATE tickets SET state='send_started',send_started_at=?,provider_posts=1 WHERE request_item_id=? AND state='prepared'", (_now(), row["request_item_id"]))
            db.execute("COMMIT")
        try:
            response = client.create_response_once(body_bytes)
        except StandardTransportError as exc:
            state = "ambiguous" if exc.ambiguous else "failed_terminal"
            with sqlite3.connect(tickets_path) as db:
                db.execute("UPDATE tickets SET state=?,completed_at=?,failure_class=?,failure_message=? WHERE request_item_id=? AND state='send_started'", (state, _now(), "ambiguous_transport" if exc.ambiguous else "terminal_provider", str(exc)[:512], row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "error": str(exc)[:512]})
            if exc.ambiguous or exc.systemic:
                global_stop = True
            else:
                stopped_slices.add(row["slice_id"])
            continue
        except Exception as exc:
            with sqlite3.connect(tickets_path) as db:
                db.execute("UPDATE tickets SET state='ambiguous',failure_class='transport_after_send_started',failure_message=? WHERE request_item_id=? AND state='send_started'", (str(exc)[:512], row["request_item_id"]))
            results.append({"request_item_id": row["request_item_id"], "state": "ambiguous", "provider_posts": 1, "error": str(exc)[:512]})
            global_stop = True
            continue
        response_file = run_dir / "responses" / f"{row['request_item_id'].replace(':', '_')}.json"
        response_file.parent.mkdir(exist_ok=True)
        response_file.write_bytes(response.raw_bytes)
        response_meta = {"status_code": response.status_code, "provider_request_id": response.request_id}
        response_file.with_suffix(".meta.json").write_bytes(_canonical(response_meta) + b"\n")
        response_id = response.body.get("id")
        usage = response.body.get("usage", {})
        actual_cost_usd = actual_cost_aud = None
        try:
            actual_cost_usd, actual_cost_aud = standard_actual_cost(usage, AUD_PER_USD, model=MODEL)
        except Exception:
            # The pre-reserved conservative amount remains the authority if
            # token accounting is missing or malformed.
            pass
        state = "completed"
        error = None
        output: Phase6SemanticOutput | None = None
        try:
            if response.body.get("status") != "completed" or response.body.get("incomplete_details") is not None:
                raise ValueError("provider response is not completed")
            actual_model = response.body.get("model")
            if actual_model != MODEL:
                raise ValueError("provider response model identity differs from the pinned model")
            output_text = _output_text(response.body)
            if not output_text:
                raise ValueError("completed response has no structured output text")
            packet = json.loads(output_text)
            output = _mechanical_validate(row, packet)
        except Exception as exc:
            state = "completed_parse_failed"
            error = str(exc)[:512]
        with sqlite3.connect(tickets_path) as db:
            db.execute("UPDATE tickets SET state=?,completed_at=?,response_id=?,provider_request_id=?,usage_json=?,failure_class=?,failure_message=? WHERE request_item_id=? AND state='send_started'", (
                state, _now(), response_id, response.request_id, json.dumps(usage, sort_keys=True), "mechanical_validation" if error else None, error, row["request_item_id"],
            ))
        if output is not None:
            candidate = {
                "candidate_status": "unreviewed_mechanical_candidate",
                "run_id": RUN_ID,
                "slice_id": row["slice_id"],
                "subject_id": row["subject_id"],
                "abn": row["abn"],
                "logical_task_id": row["logical_task_id"],
                "physical_attempt_id": row["physical_attempt_id"],
                "provider_response_id": response_id,
                "contract_commit": BUILDER_CONTRACT_COMMIT,
                "semantic_contract_hash": row["semantic_contract_hash"],
                "source_task_sha256": row["source_export_task_sha256"],
                "source_input_hashes": row["source_input_hashes"],
                "source_content_sha256": row["source_content_sha256"],
                "request_body_sha256": row["request_body_sha256"],
                "response_body_sha256": _sha(response.raw_bytes),
                "propositions": [item.model_dump(mode="json") for item in output.propositions],
                "reviewer_dispositions": [],
            }
            candidate_path = run_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json"
            candidate_path.parent.mkdir(exist_ok=True)
            candidate_path.write_bytes(_canonical(candidate) + b"\n")
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "proposition_count": len(output.propositions), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "provider_cost_usd": str(actual_cost_usd) if actual_cost_usd is not None else None, "provider_cost_aud": str(actual_cost_aud) if actual_cost_aud is not None else None, "response_id": response_id, "response_body_sha256": _sha(response.raw_bytes)})
        else:
            results.append({"request_item_id": row["request_item_id"], "state": state, "provider_posts": 1, "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "provider_cost_usd": str(actual_cost_usd) if actual_cost_usd is not None else None, "provider_cost_aud": str(actual_cost_aud) if actual_cost_aud is not None else None, "response_id": response_id, "error": error})
        if state != "completed":
            stopped_slices.add(row["slice_id"])
    report = {
        "run_id": RUN_ID,
        "execution_status": "executed_or_stopped",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "provider_calls": sum(item["provider_posts"] for item in results),
        "source_acquisitions": 0,
        "governed_promotions": 0,
        "results": results,
    }
    (run_dir / "execution-results.json").write_bytes(_canonical(report) + b"\n")
    return report


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            result.update(_flatten(child, f"{prefix}.{key}" if prefix else key))
        return result
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def prepare_review_materials(run_dir: Path, export_dir: Path) -> dict[str, Any]:
    """Build private source-only, adjudication, and paired-task materials with blank reviewer fields."""
    manifest, tasks = _load_approved_source_export(export_dir)
    selected_keys = {(slice_id, abn) for slice_id, subjects in COHORTS.items() for abn in subjects}
    review_dir = run_dir / "review-materials"
    review_dir.mkdir(parents=True, exist_ok=True)
    source_a = review_dir / "condition-a-source-only"
    source_a.mkdir(exist_ok=True)
    for key in selected_keys:
        task = tasks[key]
        task_path = next(
            item["path"] for item in manifest["tasks"] if item["task_id"] == task["task_id"]
        )
        raw = (export_dir / task_path).read_bytes()
        (source_a / f"{key[0]}__{key[1]}.json").write_bytes(raw)
    pairs: list[dict[str, Any]] = []
    for slice_id, subjects in COHORTS.items():
        for abn in subjects:
            task = tasks[(slice_id, abn)]
            pairs.append({
                "slice_id": slice_id,
                "abn": abn,
                "subject_id": task["subject_id"],
                "subject_name": task["subject_name"],
                "analyst_questions": task["analyst_questions"],
                "conditions": [
                    {"condition": "A", "answer": "", "active_minutes": "", "confidence": "", "material_omissions": [], "reviewer_disposition": ""},
                    {"condition": "B", "answer": "", "active_minutes": "", "confidence": "", "material_omissions": [], "reviewer_disposition": ""},
                ],
                "paired_result": "",
                "reviewer_disposition": "",
            })
    (review_dir / "paired-analyst-tasks.json").write_bytes(_canonical({"status": "unadministered", "tasks": pairs}) + b"\n")
    worksheet_rows = []
    diff_rows = []
    valid_candidates: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in json.loads((run_dir / "execution-manifest.json").read_bytes().decode("utf-8"))["tasks"]:
        candidate_path = run_dir / "candidate-packets" / f"{row['request_item_id'].replace(':', '_')}.json"
        if not candidate_path.exists():
            continue
        packet = json.loads(candidate_path.read_bytes().decode("utf-8"))
        valid_candidates[(row["slice_id"], row["abn"], row["replicate_ordinal"])] = packet
        for index, proposition in enumerate(packet["propositions"], start=1):
            worksheet_rows.append({
                "slice_id": row["slice_id"], "abn": row["abn"], "subject_id": row["subject_id"],
                "replicate_ordinal": row["replicate_ordinal"], "proposition_ordinal": index,
                "proposition_type": proposition["proposition_type"],
                "proposition_json": json.dumps(proposition, ensure_ascii=False, sort_keys=True),
                "source_role_disposition": "", "epistemic_disposition": "", "scope_disposition": "",
                "type_disposition": "", "evidence_disposition": "", "missingness_disposition": "",
                "overall_disposition": "", "reviewer_rationale": "",
            })
    for slice_id, subjects in COHORTS.items():
        for abn, (_focus, has_repeat) in subjects.items():
            if not has_repeat:
                continue
            first = valid_candidates.get((slice_id, abn, 1))
            second = valid_candidates.get((slice_id, abn, 2))
            if first is None or second is None:
                diff_rows.append({"slice_id": slice_id, "abn": abn, "status": "comparison_unavailable", "reviewer_disposition": ""})
                continue
            left = sorted((_flatten(item) for item in first["propositions"]), key=lambda item: json.dumps(item, sort_keys=True))
            right = sorted((_flatten(item) for item in second["propositions"]), key=lambda item: json.dumps(item, sort_keys=True))
            diff_rows.append({
                "slice_id": slice_id,
                "abn": abn,
                "status": "mechanical_field_comparison_only",
                "replicate_1_response_id": first["provider_response_id"],
                "replicate_2_response_id": second["provider_response_id"],
                "replicate_1_fields": left,
                "replicate_2_fields": right,
                "field_sets_equal": left == right,
                "answer_changing_adjudication": "",
                "reviewer_disposition": "",
            })
    worksheet_fields = ["slice_id", "abn", "subject_id", "replicate_ordinal", "proposition_ordinal", "proposition_type", "proposition_json", "source_role_disposition", "epistemic_disposition", "scope_disposition", "type_disposition", "evidence_disposition", "missingness_disposition", "overall_disposition", "reviewer_rationale"]
    with (review_dir / "proposition-adjudication-worksheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=worksheet_fields)
        writer.writeheader()
        writer.writerows(worksheet_rows)
    (review_dir / "repeat-comparisons.json").write_bytes(_canonical({"status": "mechanical_only_no_reconciliation", "comparisons": diff_rows}) + b"\n")
    return {
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "condition_a_selected_task_count": len(selected_keys),
        "paired_task_count": len(pairs),
        "adjudication_row_count": len(worksheet_rows),
        "repeat_comparison_count": len(diff_rows),
        "reviewer_fields_empty": True,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--condition-a", type=Path, required=True)
    prepare.add_argument("--run-dir", type=Path, required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--run-dir", type=Path, required=True)
    execute.add_argument("--condition-a", type=Path, required=True)
    review = sub.add_parser("prepare-review-materials")
    review.add_argument("--condition-a", type=Path, required=True)
    review.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_run(args.condition_a, args.run_dir)
    elif args.command == "execute":
        result = execute_run(args.run_dir, args.condition_a)
    else:
        result = prepare_review_materials(args.run_dir, args.condition_a)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
