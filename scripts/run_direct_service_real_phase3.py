"""Run the bounded Phase 3 direct-service task for Australian Red Cross.

The script deliberately keeps packet, prompt and provider response material in
the private runtime tree.  It reuses the frozen baseline corpus and the stable
catalogue; no source acquisition is performed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.contracts import (
    DIRECT_SERVICE_OUTPUT_SCHEMA,
    DirectServiceSemanticOutput,
    EvidenceInput,
    ModelTask,
    SchemaRef,
    ScopeRecord,
    model_task_cache_key,
    project_observation,
    validate_scope_bindings,
)
from charitygraph.contracts.ids import deterministic_id
from charitygraph.openai_client import estimate_response_cost, responses_create
from charitygraph.runtime import SQLiteCatalog
from charitygraph.strict_schema import strictify_schema, validate_strict_schema


SUBJECT_ID = "subject:d10dfad31cb04c5fb27ada0a81f36b69"
CORPUS_ID = "corpus:a7dd2f638bb5be4960b006ec9ce05927a51fd41e076e4ea32605a035fab29dbf"
MODEL = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 8000
MAX_ATTEMPTS = 2
OWNER = "direct-service-phase3-worker"
PROMPT_ID = "direct_service_semantics"
PROMPT_VERSION = "v1"
PRICING_ID = "pricing:direct-service-luna-v1"
FX_ID = "fx:direct-service-aud-v1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _find_artifact(root: Path, artifact_id: str) -> Path:
    digest = artifact_id.split(":", 1)[-1]
    roots = [root, Path(r"C:\CharityGraph-runtime\state")]
    for base in roots:
        for candidate in (
            base / "objects" / "objects" / "sha256" / digest[:2] / digest,
            base / "objects" / "sha256" / digest[:2] / digest,
        ):
            if candidate.is_file():
                return candidate
    # Historical baseline stores are private and immutable; search only the
    # known runtime root, never the workspace or arbitrary user directories.
    runtime = Path(r"C:\CharityGraph-runtime")
    for candidate in runtime.glob(f"**/objects/**/sha256/{digest[:2]}/{digest}"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"private artifact not found: {artifact_id}")


def _source_content(runtime_root: Path, source: dict[str, Any], member: dict[str, Any]) -> tuple[str, str, str]:
    """Return deterministic represented content, content kind and gap state."""
    artifact_id = str(member["artifact_ids"][0])
    payload = _find_artifact(runtime_root, artifact_id).read_bytes()
    representation = member.get("representation_artifact_ids") or []
    if representation:
        rep_path = _find_artifact(runtime_root, str(representation[0]))
        try:
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
            payload_rep = rep.get("representation", rep) if isinstance(rep, dict) else {}
            pages = payload_rep.get("pages") if isinstance(payload_rep, dict) else None
            if isinstance(pages, list):
                chunks = []
                for page in pages:
                    if isinstance(page, dict):
                        text = page.get("text") or page.get("content") or ""
                        chunks.append(f"Page {page.get('page', len(chunks) + 1)}:\n{text}")
                return "\n\n".join(chunks), "pdf_native_pages", "partial" if member.get("representation_gaps") else "complete"
        except (OSError, ValueError, UnicodeError):
            pass
    media = str(source.get("material", {}).get("media_type") or "")
    if "json" in media or payload.lstrip().startswith((b"{", b"[")):
        try:
            return json.dumps(json.loads(payload.decode("utf-8")), ensure_ascii=False, indent=2, sort_keys=True), "structured_json", "complete"
        except (UnicodeError, ValueError):
            pass
    text = payload.decode("utf-8", errors="replace")
    return text, ("html" if "html" in media else "text"), "complete"


def _prompt(subject_id: str, scopes: list[dict[str, str]], evidence: str) -> str:
    scope_text = "\n".join(f"{s['scope_id']} | {s['scope_kind']} | {s['label']}" for s in scopes)
    return f"""You are performing the bounded CharityGraph Phase 3 direct-service semantics task.
Return only the strict JSON object matching the supplied schema. Use ONLY the supplied evidence.
The target subject is {subject_id}. Emit sparse propositions only where the evidence supports them.
Use one of the task-visible scope IDs below exactly; never invent IDs or bind by fuzzy label matching.
Keep participation opportunity distinct from participation measure; service offer distinct from
availability/capacity; eligibility/access distinct from scheme membership/accreditation. Do not make
quality, effectiveness, compliance or outcome claims. Coverage states such as source_silent,
not_found and unknown must remain distinct. Cite supplied packet locators in every supported or
asserted-absence proposition. Relationships are directed and must preserve operator, deliverer,
funder, sponsor, partner, auspice and network_context as distinct roles. Do not inherit or propagate
claims from parent, network, partner or funder scopes. Cite evidence for each relationship.

TASK-VISIBLE SCOPES:
{scope_text}

PACKET EVIDENCE:
{evidence}
"""


def _report_path(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root / "run-report.json"


def _recover_exact_prior_attempt(catalog: SQLiteCatalog, task_id: str, run_id: str, now: datetime) -> str | None:
    """Close only the exact task/run left running by the rejected-schema try."""
    task = catalog.get_task(task_id)
    if not task or task.get("status") != "running" or (run_id and task.get("run_id") != run_id):
        return None
    run_id = str(task["run_id"])
    with catalog._connection() as conn:
        row = conn.execute("SELECT task_run_id, reservation_id FROM task_attempts WHERE model_task_id=? AND status='running'", (task_id,)).fetchone()
    if row is None:
        return None
    task_run_id = str(row["task_run_id"])
    catalog.finish_failed_attempt(task_run_id, owner=OWNER, completed_at=now, retryable=False, error_class="provider_request", error_message_redacted="provider rejected strict schema before response")
    if row["reservation_id"]:
        reservation = catalog.get_reservation(str(row["reservation_id"]))
        if reservation:
            with catalog._connection() as conn:
                released = conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE reservation_id=? AND entry_type='reservation_release'", (row["reservation_id"],)).fetchone()[0]
            remaining = Decimal(str(reservation["reserved_aud"])) - Decimal(str(released))
            if remaining > 0:
                catalog.release_cost(str(row["reservation_id"]), {"amount": str(remaining), "currency": "AUD"}, now=now, entry_key=f"release:preflight:{row['reservation_id']}")
    catalog.transition_run(run_id, "failed", now=now)
    return task_run_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogue", default=r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
    ap.add_argument("--corpus-report", default=r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
    ap.add_argument("--runtime-root", default=r"C:\CharityGraph-runtime\direct-service-real-run-phase3")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    runtime_root = Path(args.runtime_root)
    report = json.loads(Path(args.corpus_report).read_text(encoding="utf-8"))
    corpus = next(c for c in report["corpora"] if c["corpus_id"] == CORPUS_ID)
    catalog = SQLiteCatalog(args.catalogue).open()
    try:
        # The stable catalogue may lag the current supported migration level;
        # apply only the repository's already-defined append-only migrations.
        catalog.migrate()
        members = [m for m in corpus["material_members"] if m["source_family"] != "official_website" or m["source_record_ids"][0] not in {"srcrec:5cca527cb8eb830c79636d63a24ea538b817947ddd1804102947fa86c0a17f46", "srcrec:790bf3e15f069f34e66ab2ea888af45ac22ec9778c75c120c75756cf7b8b6ab8"}]
        packet_sources = []
        scope_specs = [("organisation", "Australian Red Cross Society")]
        labels = ["Community services", "Migrants in transition", "Telecross and Telechat", "First aid training", "Restoring Family Links"]
        for label in labels:
            scope_specs.append(("service", label))
        scope_specs.append(("site", "Australian Red Cross official website"))
        scopes: list[dict[str, str]] = []
        for kind, label in scope_specs:
            sid = deterministic_id("scope:", {"subject_id": SUBJECT_ID, "kind": kind, "label": label})
            scope = ScopeRecord(record_id=sid, created_at=now, producer={"kind": "code", "producer_id": "direct-service-runner", "version": "1"}, subject_id=SUBJECT_ID, scope_kind=kind, label=label)
            if catalog.get_scope(sid) is None:
                catalog.register_scope(scope)
            scopes.append({"scope_id": sid, "scope_kind": kind, "label": label})
        chunks: list[str] = []
        evidence_ids: list[str] = []
        source_meta: list[dict[str, Any]] = []
        selection_hashes: list[str] = []
        for idx, member in enumerate(members, 1):
            source_id = member["source_record_ids"][0]
            source = catalog.get_source_record(source_id)
            if source is None:
                raise RuntimeError(f"unknown source record {source_id}")
            content, content_kind, readiness = _source_content(runtime_root, source, member)
            key = f"S{idx:03d}"
            locator = f"[{key}:L0001]"
            chunks.append(f"{locator} source_record_id={source_id} family={member['source_family']} role={source.get('source_role')}\n{content}")
            locator_row = catalog.register_evidence_locator({"kind": "document", "source_record_id": source_id, "locator": locator}, evidence_locator_id=locator, now=now)
            evidence_ids.append(locator)
            selection_hashes.append(str(locator_row["material_hash"]))
            source_meta.append({"source_record_id": source_id, "source_family": member["source_family"], "source_role": source.get("source_role"), "representation": content_kind, "representation_readiness": readiness, "characters": len(content), "artifact_id": member["artifact_ids"][0]})
        packet = {"corpus_id": CORPUS_ID, "subject_id": SUBJECT_ID, "scopes": scopes, "sources": source_meta, "evidence": chunks}
        packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        prompt = _prompt(SUBJECT_ID, scopes, "\n\n".join(chunks))
        prompt_bytes = prompt.encode("utf-8")
        packet_sha, prompt_sha = _sha(packet_bytes), _sha(prompt_bytes)
        runtime_root.mkdir(parents=True, exist_ok=True)
        (runtime_root / "packet.json").write_bytes(packet_bytes)
        (runtime_root / "prompt.txt").write_bytes(prompt_bytes)
        strict_schema = strictify_schema(DirectServiceSemanticOutput.model_json_schema())
        validate_strict_schema(strict_schema)
        task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:direct-service-task:1.0", schema_version="1.0")
        inputs = tuple(EvidenceInput(evidence_id=x, content_hash=source_meta[i]["artifact_id"].split(":", 1)[-1], selection_hash=selection_hashes[i]) for i, x in enumerate(evidence_ids))
        old_parameters = {"max_output_tokens": MAX_OUTPUT_TOKENS, "reasoning": "high", "scope_ids": [x["scope_id"] for x in scopes]}
        old_cache = model_task_cache_key(task_type="direct_service_semantics", task_schema=task_schema, output_schema=DIRECT_SERVICE_OUTPUT_SCHEMA, evidence_inputs=inputs, prompt_template_id=PROMPT_ID, prompt_template_version=PROMPT_VERSION, policy_refs=(), provider_id="openai", model_snapshot=MODEL, parameters=old_parameters, material_tool_versions=())
        old_task_id = deterministic_id("modeltask:", {"subject_id": SUBJECT_ID, "scope_id": None, "task_type": "direct_service_semantics", "cache_key": old_cache, "output_schema": DIRECT_SERVICE_OUTPUT_SCHEMA})
        old_run_id = ""
        recovered_prior_attempt = _recover_exact_prior_attempt(catalog, old_task_id, old_run_id, now)
        parameters = {"max_output_tokens": MAX_OUTPUT_TOKENS, "reasoning": "high", "scope_ids": [x["scope_id"] for x in scopes], "schema_transport_revision": "empty-enum-omitted-v2"}
        cache_key = model_task_cache_key(task_type="direct_service_semantics", task_schema=task_schema, output_schema=DIRECT_SERVICE_OUTPUT_SCHEMA, evidence_inputs=inputs, prompt_template_id=PROMPT_ID, prompt_template_version=PROMPT_VERSION, policy_refs=(), provider_id="openai", model_snapshot=MODEL, parameters=parameters, material_tool_versions=())
        task_id = deterministic_id("modeltask:", {"subject_id": SUBJECT_ID, "scope_id": None, "task_type": "direct_service_semantics", "cache_key": cache_key, "output_schema": DIRECT_SERVICE_OUTPUT_SCHEMA})
        task = ModelTask(record_id=task_id, created_at=now, producer={"kind": "code", "producer_id": "direct-service-runner", "version": "1"}, subject_id=SUBJECT_ID, cohort_id=None, task_type="direct_service_semantics", task_schema=task_schema, output_schema=DIRECT_SERVICE_OUTPUT_SCHEMA, evidence_inputs=inputs, prompt_template_id=PROMPT_ID, prompt_template_version=PROMPT_VERSION, provider_id="openai", model_snapshot=MODEL, parameters=parameters, paid_output_categories=("semantic_judgement",))
        cohort_id, run_id = deterministic_id("cohort:", {"code": "DIRECT-SERVICE-PHASE3", "subject": SUBJECT_ID}), deterministic_id("run:", {"cohort": CORPUS_ID, "packet": packet_sha, "task": task_id})
        cap = Decimal("0.50")
        if catalog.get_cohort(cohort_id) is None:
            catalog.register_cohort({"record_id": cohort_id, "cohort_code": "SPIKE", "definition_version": "direct-service-v1", "membership_hash": _sha(SUBJECT_ID.encode()), "budget_cap": {"amount": str(cap), "currency": "AUD"}, "created_at": now})
        if catalog.get_run(run_id) is None:
            catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "direct_service_real_run", "status": "planned", "configuration_hash": _sha((packet_sha + prompt_sha).encode()), "created_at": now})
        if catalog.get_task(task_id) is None:
            catalog.register_task(task, run_id=run_id, now=now)
        # A prior local preflight may have reserved this exact task before the
        # run was made unique.  Release only that reservation's unused amount.
        with catalog._connection() as conn:
            prior = conn.execute("SELECT r.reservation_id, r.reserved_aud FROM budget_reservations r JOIN reservation_tasks rt ON rt.reservation_id=r.reservation_id WHERE rt.model_task_id=? AND r.status='active'", (task_id,)).fetchall()
        for prow in prior:
            catalog.release_cost(str(prow["reservation_id"]), {"amount": str(prow["reserved_aud"]), "currency": "AUD"}, now=now, entry_key=f"release:retry:{prow['reservation_id']}")
        estimated_usd = (Decimal(len(prompt_bytes)) / Decimal(4) * Decimal("0.20") / Decimal(1_000_000) + Decimal(MAX_OUTPUT_TOKENS) * Decimal("1.20") / Decimal(1_000_000)).quantize(Decimal("0.000001"))
        reservation_id = deterministic_id("reservation:", {"run": run_id, "task": task_id})
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(cap), "currency": "AUD"}, "model_task_ids": (task_id,)}, now=now)
        preflight = {"packet_sha256": packet_sha, "prompt_sha256": prompt_sha, "estimated_max_usd": str(estimated_usd), "max_output_tokens": MAX_OUTPUT_TOKENS, "max_attempts": MAX_ATTEMPTS, "provider_calls": 0, "sources": source_meta, "scopes": scopes, "recovered_prior_attempt": recovered_prior_attempt, "dry_run": args.dry_run}
        (runtime_root / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True), encoding="utf-8")
        if args.dry_run:
            _report_path(runtime_root).write_text(json.dumps(preflight, indent=2, sort_keys=True), encoding="utf-8")
            return 0
        catalog.transition_run(run_id, "running", now=now)
        owner = OWNER
        catalog.claim_task(task_id, owner=owner, lease_expires_at=now + timedelta(hours=2), now=now)
        task_run_id = deterministic_id("taskrun:", {"task_id": task_id, "run_id": run_id, "attempt": 1})
        catalog.begin_task_attempt(task_id, owner=owner, task_run_id=task_run_id, now=now, reservation_id=reservation_id)
        slot = catalog.claim_authorized_call(authorization_scope_hash=_sha((CORPUS_ID + packet_sha + task_id).encode()), subject_id=SUBJECT_ID, task_family="direct_service_semantics", material_hash=packet_sha, measurement_id="production", owner=owner, now=now, lease_expires_at=now + timedelta(hours=2))
        catalog.mark_authorized_call_transmitted(slot["slot_key"], now=now)
        response = responses_create(model=MODEL, input_text=prompt, text_format={"type": "json_schema", "name": "direct_service_semantic_output", "strict": True, "schema": strict_schema}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=MAX_ATTEMPTS, timeout_seconds=300, reasoning={"effort": "high"})
        response_path = runtime_root / "response.json"
        response_path.write_text(json.dumps({"response_id": response.response_id, "model": response.model, "status": response.status, "output_text": response.output_text, "usage": response.usage.__dict__, "transport_requests": response.transport_requests}, ensure_ascii=False, indent=2), encoding="utf-8")
        output = None
        errors: list[str] = []
        try:
            output = DirectServiceSemanticOutput.model_validate_json(response.output_text)
            validate_scope_bindings(output, {s["scope_id"] for s in scopes})
            valid_locators = set(evidence_ids)
            for proposition in output.propositions:
                if any(ref.locator not in valid_locators for ref in proposition.evidence):
                    raise ValueError("proposition evidence locator is not present in the frozen packet")
            for relationship in output.relationships:
                if any(ref.locator not in valid_locators for ref in relationship.evidence):
                    raise ValueError("relationship evidence locator is not present in the frozen packet")
        except Exception as exc:
            errors.append(str(exc)[:500])
        actual_usd = estimate_response_cost(response.model, response.usage)
        usage = {"input_tokens": response.usage.input_tokens or 0, "output_tokens": response.usage.output_tokens or 0, "cached_input_tokens": 0, "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0, "other_billable_units": []}
        actual_aud = (actual_usd or Decimal("0")) * Decimal("1.52")
        catalog.record_cost_entry({"cohort_id": cohort_id, "run_id": run_id, "task_run_id": task_run_id, "reservation_id": reservation_id, "pricing_snapshot_id": PRICING_ID, "fx_snapshot_id": FX_ID, "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd or Decimal("0")), "currency": "USD"}, "aud_cost": {"amount": str(actual_aud.quantize(Decimal('0.000001'))), "currency": "AUD"}, "usage": usage, "recorded_at": now}, entry_key=f"actual:{task_run_id}")
        status = "valid" if not errors else "invalid"
        result_id = deterministic_id("modelresult:", {"task_run_id": task_run_id, "response_id": response.response_id, "output_hash": _sha(response.output_text.encode())})
        # ModelResult is persisted through a small JSON projection because the
        # direct-service output is intentionally not exposed by the catalogue's
        # legacy proposal-evidence extractor.
        projection = {"model_result_id": result_id, "validation_status": status, "validation_errors": errors, "output": output.model_dump(mode="json") if output else None, "response_id": response.response_id, "usage": usage, "actual_usd": str(actual_usd or Decimal("0")), "actual_aud": str(actual_aud.quantize(Decimal('0.000001'))), "packet_sha256": packet_sha, "prompt_sha256": prompt_sha}
        (runtime_root / "projection.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        if output is not None and not errors:
            for index, proposition in enumerate(output.propositions):
                cited = tuple(dict.fromkeys(next(x["source_record_id"] for x in source_meta if f"S{evidence_ids.index(ref.locator)+1:03d}" in ref.locator) for ref in proposition.evidence))
                obs = project_observation(proposition, record_id=deterministic_id("observation:", {"result": result_id, "index": index}), subject_id=SUBJECT_ID, scope_id=proposition.scope_id, source_record_ids=cited, created_at=now, producer={"kind": "model", "producer_id": MODEL, "version": "direct-service-v1"})
                # Evidence IDs are packet locators registered above, so the
                # append-only observation remains fully source-bound.
                catalog.record_observation(obs)
        catalog.complete_authorized_call(slot["slot_key"], now=now, result_ref=result_id, terminal_failure=bool(errors))
        catalog.finish_successful_attempt(task_run_id, owner=owner, completed_at=now, result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_ID, fx_snapshot_id=FX_ID) if not errors else catalog.finish_failed_attempt(task_run_id, owner=owner, completed_at=now, retryable=False, error_class="output_validation", error_message_redacted="direct-service output validation failed", result_artifact_id=result_id, provider_request_id=response.response_id, usage=usage, pricing_snapshot_id=PRICING_ID, fx_snapshot_id=FX_ID)
        catalog.transition_run(run_id, "succeeded" if not errors else "failed", now=now)
        report_out = preflight | {"provider_calls": 1, "response_id": response.response_id, "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "transport_requests": response.transport_requests, "actual_usd": str(actual_usd or Decimal("0")), "actual_aud": str(actual_aud.quantize(Decimal('0.000001'))), "validation_status": status, "validation_errors": errors, "proposition_count": len(output.propositions) if output else 0, "relationship_count": len(output.relationships) if output else 0}
        _report_path(runtime_root).write_text(json.dumps(report_out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return 0
    finally:
        catalog.close()


if __name__ == "__main__":
    raise SystemExit(main())
