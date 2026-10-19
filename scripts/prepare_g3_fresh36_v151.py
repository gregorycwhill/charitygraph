"""Prepare an immutable, provider-free v1.5.1 Gate 3 request plan.

All generated request/evidence artifacts are written to the private runtime
directory, never into the Git repository. No provider or oracle is contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

from charitygraph.generic_discovery_provider_v151 import (
    PROVIDER_INTERFACE,
    SCHEMA_NAME,
    assert_same_selected_subjects,
    render_prompt,
    response_schema,
)
from charitygraph.source_rights import (
    BoundedLocalRetentionDecision,
    LOCAL_RETENTION_POLICY_ID,
    ArtifactRightsDecision,
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_FACTS_ONLY_POLICY_ID,
)


ROOT = Path(__file__).parents[1]
PACKETS = ROOT / "evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json"
SELECTION = ROOT / "evidence/gate3-fresh-semantic-holdout-preparation/frozen-selected-holdout-manifest.json"
LINEAGE = ROOT / "evidence/gate3-fresh36-bounded-recovery-v1/source-lineage-recovery.json"
PO_DECISION = ROOT / "evidence/gate3-fresh36-semantic-execution-v2/governance/product-owner-government-data-transmission-decision.json"
FROZEN_HEAD = "5cd1b7e3688481336f619e8fd6b07cd423a25099"
MODEL = "gpt-5.6-luna"
REASONING = "low"
MAX_OUTPUT_TOKENS = 8_000
INPUT_USD_PER_M = Decimal("0.20")
OUTPUT_USD_PER_M = Decimal("1.20")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def dump(path: Path, value: Any) -> str:
    data = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha_bytes(data)


def abn_for(packet: dict[str, Any]) -> str:
    ids = packet["envelope"]["subject"].get("external_authority_identifiers", [])
    values = [str(item["value"]) for item in ids if item.get("authority") == "ACNC" and item.get("scheme") == "ABN"]
    if len(values) != 1:
        raise ValueError("frozen subject must have exactly one governed ACNC-scoped ABN binding")
    return values[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root
    source_root = runtime / "objects/objects/sha256"
    packets_doc = json.loads(PACKETS.read_text(encoding="utf-8"))
    selection_doc = json.loads(SELECTION.read_text(encoding="utf-8"))
    lineage_doc = json.loads(LINEAGE.read_text(encoding="utf-8"))
    decision_doc = json.loads(PO_DECISION.read_text(encoding="utf-8"))
    decision_sha = sha_file(PO_DECISION)
    if sha_file(SELECTION) != "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9":
        raise ValueError("frozen selected subject manifest identity mismatch")
    assert_same_selected_subjects(selection_doc, packets_doc)
    objects = lineage_doc["source_object_records"]
    out = runtime / "g3fresh36-semantic-execution-v1.5.1"
    if out.exists():
        raise FileExistsError(f"immutable output already exists: {out}")
    out.mkdir(parents=True)

    prepared: list[dict[str, Any]] = []
    rights: list[dict[str, Any]] = []
    retentions: list[dict[str, Any]] = []
    source_checks: list[dict[str, Any]] = []
    today = date.today().isoformat()

    for ordinal, packet in enumerate(packets_doc["packets"], start=1):
        if packet.get("packet_status") != "FROZEN_PROVIDER_FREE_CANDIDATE":
            raise ValueError("input packet is not the expected frozen provider-free candidate")
        abn = abn_for(packet)
        contract = packet["envelope"]["template_contract"]
        evidence: list[dict[str, Any]] = []
        for family in ("acnc_register", "acnc_ais_bundle"):
            matches = [row for row in objects
                       if row.get("authority_scoped_abn") == abn
                       and row.get("source_family") == family
                       and row.get("object_present") is True
                       and row.get("object_hash_matches") is True
                       and row.get("lineage_recovery") in {
                           "ORIGINAL_REUSED_WITH_CONTEMPORANEOUS_MATCH",
                           "SUCCESSOR_ACQUISITION_RECEIPT_RECOVERED",
                       }]
            if len(matches) != 1:
                continue
            source = matches[0]
            digest = source["sha256_expected"]
            object_path = source_root / digest[:2] / digest
            raw = object_path.read_bytes()
            if sha_bytes(raw) != digest:
                raise ValueError("source object failed its content-address verification")
            # Only JSON structured government records are admitted here. HTML
            # pages, PDFs, websites and third-party document works are omitted.
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, (dict, list)):
                raise ValueError("government source representation is not structured JSON")
            source_records = source.get("source_record_ids") or []
            receipt_ids = source.get("acquisition_receipt_ids") or []
            if len(source_records) != 1 or not receipt_ids:
                raise ValueError("government source object lacks a unique governed record or receipt lineage")
            locator = source.get("acquisition", {}).get("resolved_locator") or source.get("acquisition", {}).get("requested_locator")
            if not isinstance(locator, str) or not locator.startswith("https://"):
                raise ValueError("government source has no verified HTTPS locator")
            representation = raw.decode("utf-8")
            representation_hash = sha_bytes(representation.encode("utf-8"))
            evidence_id = "evidence:" + representation_hash
            role = "ACNC_REGISTER_STRUCTURED_FACTS" if family == "acnc_register" else "ACNC_RETURN_STRUCTURED_FACTS"
            rights_id = "rights:g3fresh36-v151:" + hashlib.sha256(
                f"{source['source_artifact_id']}:{representation_hash}:{decision_sha}".encode()
            ).hexdigest()
            rights_decision = ArtifactRightsDecision(
                decision_id=rights_id,
                source_artifact_id=source["source_artifact_id"],
                source_record_id=source_records[0],
                source_origin_url=locator,
                source_role=role,
                acquisition_lineage_ids=tuple(receipt_ids),
                transmitted_representation_sha256=representation_hash,
                rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
                provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
                rights_basis="public_facts_only",
                evidence_locator=decision_doc["decision_id"],
                evidence_sha256=decision_sha,
                assessed_on=today,
                assessment_scope="This exact structured factual representation of a government-published ACNC record may be transmitted to the semantic provider solely for CharityGraph private analytical processing under the recorded Product Owner decision. No public redistribution. This excludes separately identifiable restricted third-party works; only the source-native JSON entity/return record is admitted.",
                attribution="Australian Charities and Not-for-profits Commission (ACNC)",
                restrictions="Private analytical processing only; no public redistribution; exclude separately identifiable restricted third-party works.",
                assessment_notes=f"Binding Product Owner authority {decision_doc['decision_id']}; exact source object, source record, receipt lineage and UTF-8 transmitted representation are hash-bound.",
                local_retention_allowed=False,
                provider_transmission_allowed=True,
                public_redistribution_allowed=False,
                factual_representation_only=True,
                representation_class="structured_factual",
                publicly_accessible_without_circumvention=True,
                access_controls_bypassed=False,
                lawfully_acquired=True,
                analytical_purpose="semantic_analysis",
                explicit_prohibition_found=False,
                provider_no_training_default=True,
                provider_data_sharing_opt_in=False,
            )
            rights_row = rights_decision.model_dump(mode="json")
            rights.append(rights_row)
            retention = BoundedLocalRetentionDecision(
                decision_id="retention:g3fresh36-v151:" + hashlib.sha256(
                    f"{source['source_artifact_id']}:{representation_hash}".encode()
                ).hexdigest(),
                source_artifact_id=source["source_artifact_id"],
                source_record_id=source_records[0],
                source_role=role,
                acquisition_lineage_ids=tuple(receipt_ids),
                representation_sha256=representation_hash,
                rights_basis="statutory_exception",
                representation_class="structured_factual",
                purpose="bounded_experiment_reproducibility",
                scope="Private frozen Gate 3 v1.5.1 experiment request and result reproducibility only.",
                one_source_native_entity_record=True,
                lawful_access_confirmed=True,
                circumvention_used=False,
                explicit_prohibition_found=False,
                retention_status="authorized",
                lifecycle_status="active_until_review",
                review_due_on=date.fromisoformat(today).replace(year=date.fromisoformat(today).year + 1),
                provider_transmission_decision_id=rights_id,
                provider_transmission_status="authorized",
            )
            retentions.append(retention.model_dump(mode="json"))
            evidence.append({
                "evidence_id": evidence_id,
                "source_family": family,
                "source_artifact_id": source["source_artifact_id"],
                "source_record_id": source_records[0],
                "acquisition_receipt_ids": receipt_ids,
                "source_origin_url": locator,
                "source_role": role,
                "representation_sha256": representation_hash,
                "rights_decision_id": rights_id,
                "provider_processing_policy_id": OPENAI_PROVIDER_POLICY_ID,
                "representation": representation,
            })
            source_checks.append({
                "source_artifact_id": source["source_artifact_id"],
                "source_record_id": source_records[0],
                "acquisition_receipt_ids": receipt_ids,
                "family": family,
                "representation_sha256": representation_hash,
                "representation_bytes": len(raw),
                "content_address_verified": True,
                "rights_decision_id": rights_id,
            })

        evidence_ids = [item["evidence_id"] for item in evidence]
        schema = response_schema(contract, evidence_ids)
        prompt = render_prompt(
            contract=contract,
            question_text=packet["envelope"]["question_text"],
            subject=packet["envelope"]["subject"],
            identity_bindings=packet["envelope"]["subject"].get("external_authority_identifiers", []),
            evidence=evidence,
        )
        logical_task_id = "modeltask:g3fresh36-v151:" + hashlib.sha256(
            packet["envelope"]["bound_question_identity"].encode()
        ).hexdigest()
        contract_hash = contract["contract_identity"]
        schema_hash = sha_bytes(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        body = {
            "model": MODEL,
            "reasoning": {"effort": REASONING},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "input": [{"role": "developer", "content": [{"type": "input_text", "text": prompt}]}],
            "text": {"format": {"type": "json_schema", "name": SCHEMA_NAME, "strict": True, "schema": schema}},
            "metadata": {
                "logical_task_id": logical_task_id,
                "semantic_contract_hash": contract_hash,
                "provider_request_item_id": "pending-plan-binding",
                "delivery_job_id": "g3fresh36-v151-standard",
            },
        }
        request_hash = sha_bytes(canonical(body))
        request_id = "requestitem:" + hashlib.sha256(
            f"{packet['envelope']['bound_question_identity']}:{request_hash}".encode()
        ).hexdigest()
        body["metadata"]["provider_request_item_id"] = request_id
        body_hash = sha_bytes(canonical(body))
        input_tokens_ceiling = (len(canonical(body)) + 1) // 2
        hard_usd = ((Decimal(input_tokens_ceiling) * INPUT_USD_PER_M
                     + Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_USD_PER_M) / Decimal(1_000_000))
        prepared.append({
            "ordinal": ordinal,
            "instance_id": packet["envelope"]["bound_question_identity"],
            "subject_id": packet["envelope"]["subject"]["governed_subject_id"],
            "provider_request_item_id": request_id,
            "model": MODEL,
            "reasoning_effort": REASONING,
            "delivery_mode": "standard",
            "automatic_retries": 0,
            "semantic_retries": 0,
            "request_body": body,
            "request_body_sha256": body_hash,
            "prompt_sha256": sha_bytes(prompt.encode("utf-8")),
            "schema_sha256": schema_hash,
            "schema_name": SCHEMA_NAME,
            "semantic_contract_identity": contract_hash,
            "semantic_contract_version": contract["contract_version"],
            "provider_interface": PROVIDER_INTERFACE,
            "evidence_ids": evidence_ids,
            "evidence_families": [item["source_family"] for item in evidence],
            "evidence_representation_hashes": [item["representation_sha256"] for item in evidence],
            "conservative_input_token_ceiling": input_tokens_ceiling,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "hard_max_usd": str(hard_usd.quantize(Decimal("0.000001"), rounding=ROUND_CEILING)),
        })

    if len(prepared) != 36 or len({item["instance_id"] for item in prepared}) != 36:
        raise ValueError("request plan must bind exactly 36 unique frozen questions")
    total_hard_usd = sum((Decimal(item["hard_max_usd"]) for item in prepared), Decimal("0"))
    if total_hard_usd > Decimal("2.00"):
        raise ValueError("conservative plan exposure exceeds the authorized US$2.00 ceiling")
    rights_path = out / "rights-decisions.json"
    retention_path = out / "local-retention-decisions.json"
    requests_path = out / "prepared-requests.json"
    dump(rights_path, {"schema": "charitygraph.g3.v151.rights-decisions/v1", "decisions": rights})
    dump(retention_path, {"schema": "charitygraph.g3.v151.retention-decisions/v1", "decisions": retentions})
    dump(requests_path, {"schema": "charitygraph.g3.v151.prepared-requests/v1", "requests": prepared})
    plan = {
        "schema": "charitygraph.g3.fresh36.execution-plan/v1.5.1",
        "implementation_version": PROVIDER_INTERFACE,
        "implementation_timing": "POST_SAMPLE_SELECTION",
        "frozen_question_source_sha256": sha_file(PACKETS),
        "source_lineage_sha256": sha_file(LINEAGE),
        "product_owner_decision_sha256": decision_sha,
        "rights_decisions_sha256": sha_file(rights_path),
        "local_retention_decisions_sha256": sha_file(retention_path),
        "prepared_requests_sha256": sha_file(requests_path),
        "model": MODEL,
        "reasoning_effort": REASONING,
        "delivery_mode": "standard",
        "max_requests": 36,
        "retries": 0,
        "usd_ceiling": "2.00",
        "conservative_max_usd": str(total_hard_usd),
        "provider_calls": 0,
        "oracle_access": 0,
        "source_acquisition": 0,
        "source_family_counts": {
            family: sum(item["evidence_families"].count(family) for item in prepared)
            for family in sorted({family for item in prepared for family in item["evidence_families"]})
        },
        "source_checks": source_checks,
    }
    plan_path = out / "execution-plan.json"
    plan["execution_plan_sha256"] = sha_bytes(canonical(plan))
    dump(plan_path, plan)
    inventory = {
        "artifacts": {
            path.name: sha_file(path)
            for path in (rights_path, retention_path, requests_path, plan_path)
        }
    }
    inventory_path = out / "artifact-inventory.json"
    dump(inventory_path, inventory)
    print(json.dumps({
        "status": "PREPARED_NOT_EXECUTED",
        "request_count": len(prepared),
        "rights_decision_count": len(rights),
        "retention_decision_count": len(retentions),
        "source_family_counts": plan["source_family_counts"],
        "conservative_max_usd": plan["conservative_max_usd"],
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "inventory_sha256": sha_file(inventory_path),
        "output": str(out),
        "provider_calls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
