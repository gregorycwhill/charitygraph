"""Execute the one-shot, run-bound Gate 3 v1.5.1 Standard request plan.

The executor reconstructs each body in memory from the immutable request
identities and original source archive, verifies its frozen hash, and passes
it through the default-deny local authorization gate before a single POST.
It persists provider responses and reconciled usage immediately in private
runtime storage; it never retries or accesses oracle material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.generic_discovery_provider_v151 import (
    SCHEMA_NAME,
    render_prompt,
    response_schema,
    validate_provider_result,
)
from charitygraph.phase5_openai_dry_run import (
    RealProviderExecutionGate,
    standard_actual_cost,
)
from charitygraph.phase5_standard_transport import (
    OpenAIHTTPStandardClient,
    StandardTransportError,
)
from charitygraph.source_rights import ArtifactRightsDecision, require_provider_rights


ROOT = Path(__file__).parents[1]
BOUND_PATH = Path(r"C:\CharityGraph-question-design\g3-fresh-36\output\question-first-v2-bound-sample\frozen-bound-question-instances.json")
PACKETS_PATH = ROOT / "evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json"
ACQUISITION_PATH = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\acquisition-ledger.json")
BUNDLE_PATH = Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829\evidence-bundles.json")
PO_DECISION_PATH = ROOT / "evidence/gate3-fresh36-semantic-execution-v2/governance/product-owner-government-data-transmission-decision.json"
APPROVED_PROVIDER_PROJECT = "proj_vnAuU8uxocL0Rosg3SulgmRI"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def atomic_json(path: Path, value: Any) -> None:
    data = canonical(value)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def abn_for(row: dict[str, Any]) -> str:
    values = [str(item["value"]) for item in row["governed_subject"]["external_authority_identifiers"]
              if item.get("authority") == "ACNC" and item.get("scheme") == "ABN"
              and item.get("scope") == "registered_charity_legal_entity"]
    if len(values) != 1:
        raise ValueError("bound question does not have exactly one ACNC legal-entity ABN")
    return values[0]


def body_for(question: dict[str, Any], packet: dict[str, Any], source_bundle: dict[str, Any],
             acquisition_by_key: dict[tuple[str, str], list[dict[str, Any]]],
             decision_sha: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    abn = abn_for(question)
    evidence: list[dict[str, Any]] = []
    rights_units: list[dict[str, str]] = []
    for family, legacy_family in (("acnc_register", "acnc-profile"), ("acnc_ais_bundle", "acnc-profile-ais")):
        lineage = acquisition_by_key[(abn, family)]
        if len(lineage) != 1 or lineage[0].get("state") != "acquired_available" or lineage[0].get("subject_id") != question["governed_subject"]["governed_subject_id"]:
            raise ValueError(f"verified original lineage is absent for {abn}/{family}")
        items = [item for item in source_bundle.get("evidence_records", []) if item.get("source_family") == legacy_family]
        if len(items) != 1:
            raise ValueError(f"source record missing or ambiguous for {abn}/{family}")
        source = items[0]
        text = source.get("text")
        if not isinstance(text, str) or sha_bytes(text.encode("utf-8")) != source.get("content_hash"):
            raise ValueError(f"source content hash mismatch for {abn}/{family}")
        locator = source.get("resolved_url") or source.get("source_url")
        source_id = source.get("evidence_id")
        record_id = locator.rsplit("/", 1)[-1]
        role = "ACNC_REGISTER_STRUCTURED_FACTS" if family == "acnc_register" else "ACNC_RETURN_STRUCTURED_FACTS"
        rights_id = "rights:g3fresh36-bound-v151:" + hashlib.sha256(
            f"{source_id}:{source['content_hash']}:{decision_sha}".encode()
        ).hexdigest()
        evidence.append({
            "evidence_id": "evidence:" + source["content_hash"],
            "source_family": family,
            "source_artifact_id": source_id,
            "source_record_id": record_id,
            "acquisition_lineage_ids": [source_id],
            "source_origin_url": locator,
            "source_role": role,
            "retrieved_at": source.get("retrieved_at"),
            "representation_sha256": source["content_hash"],
            "rights_decision_id": rights_id,
            "provider_processing_policy_id": "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
            "representation": text,
        })
        rights_units.append({
            "source_artifact_id": source_id,
            "source_record_id": record_id,
            "source_locator": locator,
            "source_role": role,
            "exact_transmitted_representation": text,
        })
    contract = packet["envelope"]["template_contract"]
    schema = response_schema(contract, [item["evidence_id"] for item in evidence])
    prompt = render_prompt(
        contract=contract,
        question_text=question["question_text"],
        subject=question["governed_subject"],
        identity_bindings=question["governed_subject"]["external_authority_identifiers"],
        evidence=evidence,
    )
    body: dict[str, Any] = {
        "model": "gpt-5.6-luna",
        "reasoning": {"effort": "low"},
        "max_output_tokens": 8_000,
        "store": False,
        "input": [{"role": "developer", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": SCHEMA_NAME, "strict": True, "schema": schema}},
        "metadata": {
            "logical_task_id": "modeltask:g3fresh36-bound-v151:" + hashlib.sha256(question["bound_question_identity"].encode()).hexdigest(),
            "semantic_contract_hash": contract["contract_identity"],
            "provider_request_item_id": "pending-plan-binding",
            "delivery_job_id": "g3fresh36-bound-v151-standard",
        },
    }
    prebind_hash = sha_bytes(canonical(body))
    request_id = "requestitem:" + hashlib.sha256(f"{question['bound_question_identity']}:{prebind_hash}".encode()).hexdigest()
    body["metadata"]["provider_request_item_id"] = request_id
    return body, evidence, rights_units


def output_text(response_body: dict[str, Any]) -> str:
    direct = response_body.get("output_text")
    if isinstance(direct, str):
        return direct
    fragments: list[str] = []
    for item in response_body.get("output", []):
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                fragments.append(part["text"])
    if not fragments:
        raise ValueError("completed Responses object contains no output text")
    return "".join(fragments)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--package-name", default="g3fresh36-semantic-execution-v1.5.1-authoritative-bound-sample-20261020-v4")
    parser.add_argument("--direct-confirmation", required=True)
    parser.add_argument("--provider-project", default=APPROVED_PROVIDER_PROJECT)
    parser.add_argument("--verify-only", action="store_true", help="validate all frozen bodies and rights without creating results or contacting a provider")
    args = parser.parse_args()
    package = args.runtime_root / args.package_name
    plan = json.loads((package / "execution-plan.json").read_text(encoding="utf-8"))
    requests_doc = json.loads((package / "prepared-requests.json").read_text(encoding="utf-8"))
    instances_doc = json.loads((package / "execution-instance-manifest.json").read_text(encoding="utf-8"))
    rights_doc = json.loads((package / "rights-decisions.json").read_text(encoding="utf-8"))
    inventory = json.loads((package / "artifact-inventory.json").read_text(encoding="utf-8"))
    for name, expected in inventory["artifacts"].items():
        if sha_file(package / name) != expected:
            raise ValueError(f"frozen package inventory mismatch: {name}")
    if len(requests_doc.get("requests", [])) != 36 or len(instances_doc.get("instances", [])) != 36:
        raise ValueError("frozen package does not contain 36 request identities and instances")
    if args.direct_confirmation != "Approve this exact run":
        raise PermissionError("run-bound confirmation text does not match the direct Product Owner response")
    run_id, plan_hash = plan["run_id"], plan["execution_plan_sha256"]
    if run_id != "run:g3fresh36-question-first-v2-v151-20261020" or plan_hash != "31834cc1e133d6c4c80c80ae787e3cab00a5819d15c84c26353618c801095efc":
        raise PermissionError("run ID or plan hash differs from the confirmed exact execution")

    authorization = {
        "schema": "charitygraph.g3.run-bound-provider-authorization/v1",
        "real_provider_enabled": True,
        "approved_run": run_id,
        "plan_hash": plan_hash,
        "max_usd": "2.00",
        "max_physical_requests": 36,
        "retries": 0,
        "provider_project": args.provider_project,
        "source": "direct Product Owner response to exact run-bound confirmation in current conversation",
        "confirmation_text": args.direct_confirmation,
        "confirmation_text_sha256": sha_bytes(args.direct_confirmation.encode("utf-8")),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    RealProviderExecutionGate(authorization).assert_allowed(
        run_id=run_id, plan_hash=plan_hash, exposure_usd=Decimal(plan["conservative_max_usd"])
    )

    bound = json.loads(BOUND_PATH.read_text(encoding="utf-8"))
    packets_doc = json.loads(PACKETS_PATH.read_text(encoding="utf-8"))
    packets = {row["envelope"]["bound_question_identity"]: row for row in packets_doc["packets"]}
    questions = {row["bound_question_identity"]: row for row in bound["instances"]}
    bundles_doc = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    bundles = {str(row["abn"]): row for row in bundles_doc["bundles"]}
    acquisition = json.loads(ACQUISITION_PATH.read_text(encoding="utf-8"))
    acquisition_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in acquisition:
        acquisition_by_key.setdefault((str(row.get("abn")), str(row.get("source_family"))), []).append(row)
    decision_sha = sha_file(PO_DECISION_PATH)
    rights = [ArtifactRightsDecision.model_validate(item) for item in rights_doc["decisions"]]
    prepared_by_question = {item["question_id"]: item for item in requests_doc["requests"]}
    instance_by_question = {item["question_id"]: item for item in instances_doc["instances"]}
    if set(prepared_by_question) != set(questions) or set(instance_by_question) != set(questions):
        raise ValueError("request identities do not exactly cover the bound question set")

    evidence_by_question: dict[str, list[dict[str, Any]]] = {}
    rights_units_all: list[dict[str, str]] = []
    bodies: dict[str, dict[str, Any]] = {}
    for question_id, question in questions.items():
        body, evidence, units = body_for(question, packets[question_id], bundles[abn_for(question)], acquisition_by_key, decision_sha)
        evidence_by_question[question_id] = evidence
        rights_units_all.extend(units)
        prepared = prepared_by_question[question_id]
        if sha_bytes(canonical(body)) != prepared["request_body_sha256"]:
            raise ValueError(f"request body does not reproduce frozen hash for {question_id}")
        if body["metadata"]["provider_request_item_id"] != prepared["provider_request_item_id"]:
            raise ValueError(f"provider request identity mismatch for {question_id}")
        if sha_bytes(body["input"][0]["content"][0]["text"].encode("utf-8")) != prepared["prompt_sha256"]:
            raise ValueError(f"prompt hash mismatch for {question_id}")
        schema = body["text"]["format"]["schema"]
        schema_hash = sha_bytes(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if schema_hash != prepared["schema_sha256"]:
            raise ValueError(f"schema hash mismatch for {question_id}")
        bodies[question_id] = body
    blockers = require_provider_rights(rights, rights_units_all)
    if blockers or len(rights) != 72:
        raise PermissionError(f"artifact-bound rights validation failed immediately before execution: {blockers}")

    if args.verify_only:
        print(json.dumps({"verification": "PASS", "request_count": len(bodies), "rights_decisions": len(rights),
                          "rights_blockers": 0, "provider_calls": 0, "plan_sha256": plan_hash,
                          "provider_project": args.provider_project}, sort_keys=True))
        return 0

    result_dir = package / "execution-results-v1"
    if result_dir.exists():
        raise FileExistsError("execution results already exist; physical request replay is forbidden")
    result_dir.mkdir(parents=True)
    atomic_json(result_dir / "run-bound-authorization.json", authorization)

    attempts: list[dict[str, Any]] = []
    atomic_json(result_dir / "attempt-ledger.json", {
        "schema": "charitygraph.g3.fresh36.attempt-ledger/v1",
        "run_id": run_id,
        "plan_sha256": plan_hash,
        "attempts": attempts,
    })
    client = OpenAIHTTPStandardClient(provider_account_project=args.provider_project)
    requests_issued = 0
    usd_actual = Decimal("0")
    usd_unknown_reserve = Decimal("0")
    input_tokens = output_tokens = 0
    stop_reason: str | None = None

    for item in requests_doc["requests"]:
        question_id = item["question_id"]
        request_hash = item["request_body_sha256"]
        hard_max = Decimal(item["hard_max_usd"])
        if usd_actual + usd_unknown_reserve + hard_max > Decimal(authorization["max_usd"]):
            stop_reason = "remaining authorization is insufficient for next request's conservative maximum"
            attempts.append({"question_id": question_id, "status": "NOT_ISSUED_BUDGET_STOP", "request_body_sha256": request_hash, "physical_requests": 0})
            break
        RealProviderExecutionGate(authorization).assert_allowed(
            run_id=run_id, plan_hash=plan_hash, exposure_usd=usd_actual + usd_unknown_reserve + hard_max
        )
        row: dict[str, Any] = {
            "ordinal": item["ordinal"],
            "question_id": question_id,
            "subject_id": item["subject_id"],
            "provider_request_item_id": item["provider_request_item_id"],
            "request_body_sha256": request_hash,
            "status": "SEND_STARTED",
            "physical_requests": 0,
            "response_sha256": None,
            "validation": "NOT_RUN",
            "usage": None,
            "actual_cost_usd": None,
            "failure": None,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        attempts.append(row)
        atomic_json(result_dir / "attempt-ledger.json", {"schema": "charitygraph.g3.fresh36.attempt-ledger/v1", "run_id": run_id, "plan_sha256": plan_hash, "attempts": attempts})
        try:
            response = client.create_response_once(canonical(bodies[question_id]), client_request_id=item["provider_request_item_id"])
            requests_issued += 1
            row["physical_requests"] = 1
            response_path = result_dir / "responses" / f"{item['ordinal']:02d}-{question_id}.json"
            response_path.parent.mkdir(parents=True, exist_ok=True)
            response_path.write_bytes(response.raw_bytes)
            row["response_sha256"] = sha_bytes(response.raw_bytes)
            row["provider_status_code"] = response.status_code
            row["provider_request_id"] = response.request_id
            row["provider_response_id"] = response.body.get("id")
            row["provider_metadata"] = {key: response.body.get(key) for key in ("model", "status", "service_tier", "created_at") if key in response.body}
            usage = response.body.get("usage")
            row["usage"] = usage
            if isinstance(usage, dict):
                input_tokens += int(usage.get("input_tokens", 0))
                output_tokens += int(usage.get("output_tokens", 0))
                actual_usd, _ = standard_actual_cost(usage, Decimal("1"), model="gpt-5.6-luna")
                usd_actual += actual_usd
                row["actual_cost_usd"] = str(actual_usd)
            else:
                usd_unknown_reserve += hard_max
                row["actual_cost_usd"] = "UNKNOWN; conservative request maximum reserved"
            if response.status_code < 200 or response.status_code >= 300 or response.body.get("status") != "completed":
                row["status"] = "FAILED_PROVIDER_RESPONSE_PRESERVED"
                row["failure"] = "provider response was non-success or non-completed"
            else:
                try:
                    result = json.loads(output_text(response.body))
                    validate_provider_result(packets[question_id]["envelope"]["template_contract"], result,
                                             [e["evidence_id"] for e in evidence_by_question[question_id]])
                    row["validation"] = "VALID"
                    row["status"] = "COMPLETED_VALID"
                except Exception as validation_error:  # Preserve invalid results; never repair or retry.
                    row["validation"] = "INVALID"
                    row["validation_error"] = f"{type(validation_error).__name__}: {str(validation_error)[:500]}"
                    row["status"] = "COMPLETED_INVALID_PRESERVED"
            row["persisted_response_path"] = str(response_path)
        except StandardTransportError as exc:
            crossed = bool(exc.response_headers_received or exc.ambiguous or exc.status_code is not None)
            if crossed:
                requests_issued += 1
                row["physical_requests"] = 1
                usd_unknown_reserve += hard_max
            row["status"] = "TRANSPORT_FAILURE_PRESERVED"
            row["failure"] = {
                "message": str(exc),
                "status_code": exc.status_code,
                "ambiguous": exc.ambiguous,
                "systemic": exc.systemic,
                "transport_state": exc.transport_state,
                "response_headers_received": exc.response_headers_received,
            }
            if exc.raw_bytes is not None:
                err_path = result_dir / "responses" / f"{item['ordinal']:02d}-{question_id}-transport-error.bin"
                err_path.parent.mkdir(parents=True, exist_ok=True)
                err_path.write_bytes(exc.raw_bytes)
                row["response_sha256"] = sha_bytes(exc.raw_bytes)
                row["persisted_response_path"] = str(err_path)
        except Exception as exc:
            row["status"] = "LOCAL_FAILURE_PRESERVED"
            row["failure"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
        atomic_json(result_dir / "attempt-ledger.json", {"schema": "charitygraph.g3.fresh36.attempt-ledger/v1", "run_id": run_id, "plan_sha256": plan_hash, "attempts": attempts})
        if usd_actual + usd_unknown_reserve > Decimal(authorization["max_usd"]):
            stop_reason = "actual or conservatively reserved exposure reached the authorization ceiling"
            break

    result = {
        "schema": "charitygraph.g3.fresh36.execution-result/v1",
        "run_id": run_id,
        "plan_sha256": plan_hash,
        "authorization_sha256": sha_file(result_dir / "run-bound-authorization.json"),
        "status": "COMPLETED" if len(attempts) == 36 else "STOPPED_OR_INCOMPLETE",
        "request_count": len(attempts),
        "physical_provider_requests": requests_issued,
        "successful_http_responses": sum(1 for row in attempts if row.get("provider_status_code", 0) == 200),
        "valid_outputs": sum(1 for row in attempts if row.get("validation") == "VALID"),
        "invalid_outputs": sum(1 for row in attempts if row.get("validation") == "INVALID"),
        "failed_or_not_issued": sum(1 for row in attempts if row.get("status") not in {"COMPLETED_VALID", "COMPLETED_INVALID_PRESERVED"}),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "known_actual_usd": str(usd_actual),
        "unknown_spend_reserved_usd": str(usd_unknown_reserve),
        "max_authorized_usd": authorization["max_usd"],
        "stop_reason": stop_reason,
        "retries": 0,
        "oracle_access": 0,
    }
    result_path = result_dir / "execution-result.json"
    atomic_json(result_path, result)
    hashes = {}
    for path in sorted(result_dir.rglob("*")):
        if path.is_file() and path.name != "artifact-inventory.json":
            hashes[str(path.relative_to(result_dir))] = sha_file(path)
    atomic_json(result_dir / "artifact-inventory.json", {"schema": "charitygraph.g3.execution-result-inventory/v1", "artifacts": hashes})
    print(json.dumps({**result, "result_sha256": sha_file(result_path), "inventory_sha256": sha_file(result_dir / "artifact-inventory.json"), "result_dir": str(result_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
