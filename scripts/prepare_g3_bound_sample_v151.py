"""Compile v1.5.1 requests from the authoritative frozen question-first sample.

This is a provider-free deterministic preparation path.  It binds the exact
question-first v2 pairs to the matching old candidate envelopes, and admits
only existing source-native ACNC Register/AIS records with contemporaneous
content and acquisition metadata.  All outputs are private runtime artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from charitygraph.generic_discovery_provider_v151 import (
    PROVIDER_INTERFACE,
    SCHEMA_NAME,
    render_prompt,
    response_schema,
)
from charitygraph.phase5_openai_dry_run import conservative_standard_hard_max_usd
from charitygraph.source_rights import (
    ArtifactRightsDecision,
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_FACTS_ONLY_POLICY_ID,
    require_provider_rights,
)


ROOT = Path(__file__).parents[1]
BOUND_PATH = Path(
    r"C:\CharityGraph-question-design\g3-fresh-36\output\question-first-v2-bound-sample\frozen-bound-question-instances.json"
)
BOUND_LEDGER_PATH = BOUND_PATH.with_name("deterministic-subject-selection-ledger.json")
PACKETS_PATH = ROOT / "evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json"
SELECTED_PATH = ROOT / "evidence/gate3-fresh-semantic-holdout-preparation/frozen-selected-holdout-manifest.json"
ACQUISITION_PATH = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1\acquisition-ledger.json")
BUNDLE_PATH = Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829\evidence-bundles.json")
PO_DECISION_PATH = ROOT / "evidence/gate3-fresh36-semantic-execution-v2/governance/product-owner-government-data-transmission-decision.json"
BOUND_IDENTITY = "e34bf830170d055f1691743a4e60120a48a932e953d7bcdbf0caa832bbe25994"
LEDGER_SHA256 = "e4a181eadea002d12cb4f4e7616c464ce043522b8a5a9728351fdc57f7c10494"
PACKETS_SHA256 = "bc321f06a5873997562828fda0b689995a101ab56e9848b6e4dbbbfb4b4f60db"
SELECTED_SHA256 = "41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9"
MODEL = "gpt-5.6-luna"
REASONING = "low"
MAX_OUTPUT_TOKENS = 8_000


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


def abn_for_bound(row: dict[str, Any]) -> str:
    values = [str(item["value"]) for item in row["governed_subject"]["external_authority_identifiers"]
              if item.get("authority") == "ACNC" and item.get("scheme") == "ABN"
              and item.get("scope") == "registered_charity_legal_entity"]
    if len(values) != 1:
        raise ValueError("bound subject must have exactly one ACNC registered-charity ABN")
    return values[0]


def params_for_bound(row: dict[str, Any]) -> dict[str, str]:
    params = {str(item["slot_id"]): str(item["exact_value"])
              for item in row.get("bound_user_choice_parameters", [])}
    if len(params) != len(row.get("bound_user_choice_parameters", [])):
        raise ValueError("bound user parameter slots are not unique")
    return params


def validate_parameter_binding(row: dict[str, Any], envelope: dict[str, Any]) -> list[dict[str, str]]:
    frozen = params_for_bound(row)
    compiled = envelope.get("semantic_user_parameters", {})
    if not isinstance(compiled, dict) or set(frozen) != set(compiled):
        raise ValueError(f"frozen parameter slots differ for {row.get('bound_question_identity')}")
    decisions = envelope.get("compatibility_decisions", [])
    aliases: list[dict[str, str]] = []
    for slot, original in frozen.items():
        value = compiled[slot]
        if original == value:
            continue
        match = [item for item in decisions if item.get("type") == "GRAMMATICAL_RENDERING_ALIAS"
                 and item.get("slot_id") == slot and item.get("frozen_value") == original
                 and item.get("semantic_input_value") == value]
        if len(match) != 1:
            raise ValueError(f"parameter mismatch without exact approved grammatical alias for {row.get('bound_question_identity')}/{slot}")
        aliases.extend(match)
    return aliases


def recursively_find_abn(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() == "abn" and isinstance(item, (str, int)):
                found.add(str(item))
            found |= recursively_find_abn(item)
    elif isinstance(value, list):
        for item in value:
            found |= recursively_find_abn(item)
    return found


def validate_pairing(bound: dict[str, Any], packets: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    bound_rows = bound.get("instances")
    packet_rows = packets.get("packets")
    if not isinstance(bound_rows, list) or len(bound_rows) != 36 or not isinstance(packet_rows, list) or len(packet_rows) != 36:
        raise ValueError("expected 36 frozen bound questions and 36 candidate packets")
    by_question = {row.get("envelope", {}).get("bound_question_identity"): row for row in packet_rows
                   if isinstance(row, dict) and isinstance(row.get("envelope"), dict)}
    if len(by_question) != 36:
        raise ValueError("candidate packet question identities are absent or non-unique")
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for row in bound_rows:
        question_id = row.get("bound_question_identity")
        if not isinstance(question_id, str) or question_id in seen or question_id not in by_question:
            raise ValueError("bound question does not map uniquely to a candidate packet by explicit question identity")
        seen.add(question_id)
        packet = by_question[question_id]
        envelope = packet["envelope"]
        bound_subject = row["governed_subject"]
        packet_subject = envelope["subject"]
        if bound_subject["governed_subject_id"] != packet_subject.get("governed_subject_id"):
            raise ValueError(f"subject ID mismatch for {question_id}")
        if abn_for_bound(row) != next((str(item["value"]) for item in packet_subject.get("external_authority_identifiers", [])
                                      if item.get("authority") == "ACNC" and item.get("scheme") == "ABN"
                                      and item.get("scope") == "registered_charity_legal_entity"), None):
            raise ValueError(f"ACNC ABN mismatch for {question_id}")
        if row["question_text"] != envelope.get("question_text"):
            raise ValueError(f"frozen wording mismatch for {question_id}")
        validate_parameter_binding(row, envelope)
        frozen_template = row.get("final_template_identity")
        compiled_template = envelope.get("template_contract", {}).get("template_identity")
        if frozen_template != compiled_template:
            # This is the already-audited serialization-only @vN/-vN alias.
            # Accept it only when the frozen candidate packet explicitly
            # records that compatibility decision; never normalize question text.
            alias = frozen_template.replace("@v", "-v") if isinstance(frozen_template, str) else None
            alias_recorded = any(item.get("type") == "VERSION_SERIALIZATION_ALIAS"
                                 for item in envelope.get("compatibility_decisions", []))
            if alias != compiled_template or not alias_recorded:
                raise ValueError(f"template lineage mismatch for {question_id}")
        pairs.append((row, packet))
    if len(seen) != 36 or set(by_question) != seen:
        raise ValueError("frozen question/packet identity sets differ")
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output-name", default="g3fresh36-semantic-execution-v1.5.1-authoritative-bound-sample-20261020")
    parser.add_argument("--dry-run", action="store_true", help="validate and forecast without writing private artifacts")
    args = parser.parse_args()
    out = args.runtime_root / args.output_name
    if out.exists():
        raise FileExistsError(f"immutable output already exists: {out}")
    for path, expected in ((PACKETS_PATH, PACKETS_SHA256), (SELECTED_PATH, SELECTED_SHA256)):
        if sha_file(path) != expected:
            raise ValueError(f"frozen input identity mismatch: {path.name}")
    bound = json.loads(BOUND_PATH.read_text(encoding="utf-8"))
    ledger = json.loads(BOUND_LEDGER_PATH.read_text(encoding="utf-8"))
    packets = json.loads(PACKETS_PATH.read_text(encoding="utf-8"))
    selected = json.loads(SELECTED_PATH.read_text(encoding="utf-8"))
    if ledger.get("selection_input_manifest_sha256") != bound.get("selection_input_manifest_sha256"):
        raise ValueError("bound sample and contemporaneous selection ledger input hashes differ")
    if ledger.get("selected_subject_count") != 36 or ledger.get("fallback_invoked") is not False:
        raise ValueError("original selection ledger does not attest the frozen 36 subject cohort")
    if sha_file(BOUND_LEDGER_PATH) != LEDGER_SHA256:
        raise ValueError("original selection ledger hash mismatch")
    pairs = validate_pairing(bound, packets)
    # The disjoint later manifest is preserved and recorded as non-authoritative.
    if sha_file(SELECTED_PATH) != SELECTED_SHA256:
        raise ValueError("non-authoritative selected-subject conflict artifact changed")

    acquisition = json.loads(ACQUISITION_PATH.read_text(encoding="utf-8"))
    bundles_doc = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    bundles = {str(row["abn"]): row for row in bundles_doc["bundles"]}
    if len(bundles) != 100:
        raise ValueError("expected frozen 100-charity source bundle set")
    acquisition_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in acquisition:
        acquisition_by_key.setdefault((str(item.get("abn")), str(item.get("source_family"))), []).append(item)

    decision_doc = json.loads(PO_DECISION_PATH.read_text(encoding="utf-8"))
    if decision_doc.get("decision_status") != "BINDING_PRODUCT_OWNER_POLICY_DECISION":
        raise ValueError("government-data transmission authority is not a binding decision")
    decision_sha = sha_file(PO_DECISION_PATH)
    rights: list[dict[str, Any]] = []
    retentions: list[dict[str, Any]] = []
    prepared: list[dict[str, Any]] = []
    instance_manifest: list[dict[str, Any]] = []
    lineage_index: list[dict[str, Any]] = []
    rights_units: list[dict[str, str]] = []
    today = date.today().isoformat()

    for ordinal, (bound_row, packet) in enumerate(pairs, 1):
        question_id = bound_row["bound_question_identity"]
        subject_id = bound_row["governed_subject"]["governed_subject_id"]
        abn = abn_for_bound(bound_row)
        parameter_aliases = validate_parameter_binding(bound_row, packet["envelope"])
        instance_manifest.append({
            "ordinal": ordinal,
            "question_id": question_id,
            "subject_id": subject_id,
            "authority_identifier": {"authority": "ACNC", "scheme": "ABN", "scope": "registered_charity_legal_entity", "value": abn},
            "final_template_identity": bound_row["final_template_identity"],
            "compiled_contract_template_identity": packet["envelope"]["template_contract"]["template_identity"],
            "question_text": bound_row["question_text"],
            "parameters": params_for_bound(bound_row),
            "semantic_input_parameters": packet["envelope"]["semantic_user_parameters"],
            "parameter_compatibility_decisions": parameter_aliases,
            "selection_provenance": bound_row["selection_provenance"],
            "bound_sample_identity": BOUND_IDENTITY,
        })

        bundle = bundles.get(abn)
        if not isinstance(bundle, dict):
            raise ValueError(f"no existing source bundle for bound ABN {abn}")
        evidence: list[dict[str, Any]] = []
        for family, legacy_family in (("acnc_register", "acnc-profile"), ("acnc_ais_bundle", "acnc-profile-ais")):
            lineage_rows = acquisition_by_key.get((abn, family), [])
            if len(lineage_rows) != 1:
                raise ValueError(f"missing or ambiguous original acquisition lineage for {abn}/{family}")
            lineage = lineage_rows[0]
            if lineage.get("state") != "acquired_available" or lineage.get("subject_id") != subject_id:
                raise ValueError(f"original acquisition is not available and bound to the exact subject for {abn}/{family}")
            records = [item for item in bundle.get("evidence_records", []) if item.get("source_family") == legacy_family]
            if len(records) != 1:
                raise ValueError(f"missing or ambiguous original source representation for {abn}/{family}")
            source = records[0]
            raw_text = source.get("text")
            if not isinstance(raw_text, str) or sha_bytes(raw_text.encode("utf-8")) != source.get("content_hash"):
                raise ValueError(f"original source representation hash mismatch for {abn}/{family}")
            parsed = json.loads(raw_text)
            if not isinstance(parsed, dict) or abn not in recursively_find_abn(parsed):
                raise ValueError(f"source-native JSON does not bind the exact authority ID {abn}")
            locator = source.get("resolved_url") or source.get("source_url")
            if not isinstance(locator, str) or not locator.startswith("https://www.acnc.gov.au/"):
                raise ValueError(f"unexpected source locator for {abn}/{family}")
            source_id = source.get("evidence_id")
            if not isinstance(source_id, str) or not any(source_id.startswith(f"{prefix}:{abn}:") for prefix in ("top100", "v31")):
                raise ValueError("original frozen source artifact identity is missing")
            representation_hash = source["content_hash"]
            role = "ACNC_REGISTER_STRUCTURED_FACTS" if family == "acnc_register" else "ACNC_RETURN_STRUCTURED_FACTS"
            rights_id = "rights:g3fresh36-bound-v151:" + hashlib.sha256(
                f"{source_id}:{representation_hash}:{decision_sha}".encode()
            ).hexdigest()
            # Use the actual frozen source evidence identity as the lineage
            # reference.  Do not mint a synthetic acquisition-receipt ID.
            lineage_ref = source_id
            source_record_id = locator.rsplit("/", 1)[-1]
            if not source_record_id or len(source_record_id) != 36:
                raise ValueError(f"ACNC source locator does not end in a record UUID for {abn}/{family}")
            decision = ArtifactRightsDecision(
                decision_id=rights_id,
                source_artifact_id=source_id,
                source_record_id=source_record_id,
                source_origin_url=locator,
                source_role=role,
                acquisition_lineage_ids=(lineage_ref,),
                transmitted_representation_sha256=representation_hash,
                rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
                provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
                rights_basis="public_facts_only",
                evidence_locator=decision_doc["decision_id"],
                evidence_sha256=decision_sha,
                assessed_on=today,
                assessment_scope=(
                    "Exact source-native structured ACNC government record verified by the frozen evidence bundle content hash and "
                    "the contemporaneous acquisition-ledger row for this ABN/family/subject. Transmitted solely under the binding "
                    "Product Owner decision for CharityGraph private analytical processing. This excludes separately identifiable "
                    "third-party works; only this JSON record is transmitted. No public redistribution is authorized."
                ),
                attribution="Australian Charities and Not-for-profits Commission (ACNC)",
                restrictions="Private analytical processing only; no public redistribution; separately identifiable restricted third-party works excluded.",
                assessment_notes=(
                    f"Authority decision {decision_doc['decision_id']} (SHA-256 {decision_sha}); source lineage records are "
                    f"{ACQUISITION_PATH} and {BUNDLE_PATH}; original evidence ID {source_id}; source content SHA-256 {representation_hash}."
                ),
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
            rights.append(decision.model_dump(mode="json"))
            rights_units.append({
                "source_artifact_id": source_id,
                "source_record_id": source_record_id,
                "source_locator": locator,
                "source_role": role,
                "exact_transmitted_representation": raw_text,
            })
            # Retention is not inferred from transmission permission. Existing
            # source bytes remain in their original governed archive; this plan
            # references them by hash and does not create a separate retention grant.
            evidence_id = "evidence:" + representation_hash
            evidence.append({
                "evidence_id": evidence_id,
                "source_family": family,
                "source_artifact_id": source_id,
                "source_record_id": source_record_id,
                "acquisition_lineage_ids": [lineage_ref],
                "source_origin_url": locator,
                "source_role": role,
                "retrieved_at": source.get("retrieved_at"),
                "representation_sha256": representation_hash,
                "rights_decision_id": rights_id,
                "provider_processing_policy_id": OPENAI_PROVIDER_POLICY_ID,
                "representation": raw_text,
            })
            lineage_index.append({
                "question_id": question_id,
                "subject_id": subject_id,
                "abn": abn,
                "source_family": family,
                "source_id": source_id,
                "locator": locator,
                "retrieved_at": source.get("retrieved_at"),
                "representation_sha256": representation_hash,
                "representation_bytes": source.get("byte_size"),
                "acquisition_ledger_row": lineage,
                "rights_decision_id": rights_id,
                "source_lineage_files": {
                    str(ACQUISITION_PATH): sha_file(ACQUISITION_PATH),
                    str(BUNDLE_PATH): sha_file(BUNDLE_PATH),
                },
            })

        contract = packet["envelope"]["template_contract"]
        evidence_ids = [item["evidence_id"] for item in evidence]
        schema = response_schema(contract, evidence_ids)
        prompt = render_prompt(
            contract=contract,
            question_text=bound_row["question_text"],
            subject=bound_row["governed_subject"],
            identity_bindings=bound_row["governed_subject"]["external_authority_identifiers"],
            evidence=evidence,
        )
        schema_hash = sha_bytes(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        body = {
            "model": MODEL,
            "reasoning": {"effort": REASONING},
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
            "input": [{"role": "developer", "content": [{"type": "input_text", "text": prompt}]}],
            "text": {"format": {"type": "json_schema", "name": SCHEMA_NAME, "strict": True, "schema": schema}},
            "metadata": {
                "logical_task_id": "modeltask:g3fresh36-bound-v151:" + hashlib.sha256(question_id.encode()).hexdigest(),
                "semantic_contract_hash": contract["contract_identity"],
                "provider_request_item_id": "pending-plan-binding",
                "delivery_job_id": "g3fresh36-bound-v151-standard",
            },
        }
        prebind_hash = sha_bytes(canonical(body))
        request_id = "requestitem:" + hashlib.sha256(f"{question_id}:{prebind_hash}".encode()).hexdigest()
        body["metadata"]["provider_request_item_id"] = request_id
        body_hash = sha_bytes(canonical(body))
        input_token_ceiling = (len(canonical(body)) + 1) // 2
        hard_usd = conservative_standard_hard_max_usd(input_token_ceiling, MAX_OUTPUT_TOKENS, model=MODEL)
        prepared.append({
            "ordinal": ordinal,
            "question_id": question_id,
            "subject_id": subject_id,
            "abn": abn,
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
            "semantic_contract_identity": contract["contract_identity"],
            "semantic_contract_version": contract["contract_version"],
            "provider_interface": PROVIDER_INTERFACE,
            "evidence_ids": evidence_ids,
            "evidence_families": [item["source_family"] for item in evidence],
            "evidence_representation_hashes": [item["representation_sha256"] for item in evidence],
            "conservative_input_token_ceiling": input_token_ceiling,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "hard_max_usd": str(hard_usd),
        })

    if len(prepared) != 36 or len({r["question_id"] for r in prepared}) != 36:
        raise ValueError("execution plan must include exactly 36 unique frozen question IDs")
    total_hard_usd = sum((Decimal(item["hard_max_usd"]) for item in prepared), Decimal("0"))
    if total_hard_usd > Decimal("2.00"):
        raise ValueError("conservative maximum exceeds the existing US$2.00 authorization")
    parsed_rights = [ArtifactRightsDecision.model_validate(item) for item in rights]
    rights_blockers = require_provider_rights(parsed_rights, rights_units)
    if rights_blockers or len(parsed_rights) != 72 or len(rights_units) != 72:
        raise ValueError(f"exact representation-bound provider rights validation failed: {rights_blockers}")

    if args.dry_run:
        print(json.dumps({
            "status": "DRY_RUN_VALIDATED",
            "matched_question_subject_pairs": len(instance_manifest),
            "rights_decisions": len(rights),
            "rights_exact_binding_validation": "PASS_72_OF_72",
            "evidence_records": sum(len(item["evidence_families"]) for item in prepared),
            "family_counts": {family: sum(item["evidence_families"].count(family) for item in prepared)
                              for family in ("acnc_register", "acnc_ais_bundle")},
            "request_count": len(prepared),
            "conservative_max_usd": str(total_hard_usd),
            "provider_calls": 0,
            "output_written": False,
        }, sort_keys=True))
        return 0

    out.mkdir(parents=True)
    inputs = {
        "authoritative_bound_sample_sha256": sha_file(BOUND_PATH),
        "authoritative_bound_sample_content_identity": BOUND_IDENTITY,
        "original_selection_ledger_sha256": sha_file(BOUND_LEDGER_PATH),
        "candidate_packet_manifest_sha256": sha_file(PACKETS_PATH),
        "non_authoritative_disjoint_selected_subject_manifest_sha256": sha_file(SELECTED_PATH),
        "acquisition_ledger_sha256": sha_file(ACQUISITION_PATH),
        "source_bundle_sha256": sha_file(BUNDLE_PATH),
        "product_owner_transmission_decision_sha256": decision_sha,
    }
    dump(out / "execution-instance-manifest.json", {
        "schema": "charitygraph.g3.execution-instance-manifest/v1",
        "cohort_authority": "ORIGINAL_FROZEN_QUESTION_FIRST_V2_BOUND_SAMPLE",
        "instance_count": 36,
        "instances": instance_manifest,
        "input_identities": inputs,
        "preserved_conflict": {
            "manifest_sha256": SELECTED_SHA256,
            "status": "NON_AUTHORITATIVE_DISJOINT_SUBJECT_COHORT_PRESERVED_NOT_USED",
            "subject_or_abn_overlap_with_authoritative_bound_sample": 0,
        },
    })
    dump(out / "acquisition-lineage-index.json", {"schema": "charitygraph.g3.acquisition-lineage-index/v1", "rows": lineage_index})
    dump(out / "rights-decisions.json", {"schema": "charitygraph.g3.v151.rights-decisions/v1", "decisions": rights})
    # Do not make a second retained copy of source bodies in the plan.  Each
    # exact request is frozen by its SHA-256 and its deterministic inputs; the
    # original source representations remain in their original archive.
    frozen_request_identities = [
        {key: value for key, value in item.items() if key != "request_body"}
        for item in prepared
    ]
    dump(out / "prepared-requests.json", {
        "schema": "charitygraph.g3.v151.prepared-request-identities/v1",
        "request_bodies_persisted": False,
        "request_body_persistence_reason": "No separate local-retention authority; exact request hashes and immutable source references are frozen, with source bodies remaining in their original archive.",
        "requests": frozen_request_identities,
    })
    request_path = out / "prepared-requests.json"
    rights_path = out / "rights-decisions.json"
    instance_path = out / "execution-instance-manifest.json"
    lineage_path = out / "acquisition-lineage-index.json"
    plan = {
        "schema": "charitygraph.g3.fresh36.execution-plan/v1.5.1",
        "run_id": "run:g3fresh36-question-first-v2-v151-20261020",
        "compiler_script_sha256": sha_file(Path(__file__)),
        "implementation_version": PROVIDER_INTERFACE,
        "implementation_timing": "POST_SAMPLE_SELECTION",
        "authoritative_bound_sample_content_identity": BOUND_IDENTITY,
        "authoritative_bound_sample_file_sha256": sha_file(BOUND_PATH),
        "original_selection_ledger_sha256": sha_file(BOUND_LEDGER_PATH),
        "candidate_packet_manifest_sha256": sha_file(PACKETS_PATH),
        "non_authoritative_subject_manifest_sha256": sha_file(SELECTED_PATH),
        "execution_instance_manifest_sha256": sha_file(instance_path),
        "acquisition_lineage_index_sha256": sha_file(lineage_path),
        "product_owner_transmission_decision_sha256": decision_sha,
        "rights_decisions_sha256": sha_file(rights_path),
        "prepared_requests_sha256": sha_file(request_path),
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
        "request_body_persistence": "HASH_ONLY_SOURCE_BODIES_NOT_DUPLICATED",
        "source_family_counts": {family: sum(item["evidence_families"].count(family) for item in prepared)
                                  for family in ("acnc_register", "acnc_ais_bundle")},
        "rights_decision_count": len(rights),
        "exact_question_subject_pairs": 36,
    }
    plan["execution_plan_sha256"] = sha_bytes(canonical(plan))
    dump(out / "execution-plan.json", plan)
    names = ("execution-instance-manifest.json", "acquisition-lineage-index.json", "rights-decisions.json", "prepared-requests.json", "execution-plan.json")
    inventory = {"artifacts": {name: sha_file(out / name) for name in names}}
    dump(out / "artifact-inventory.json", inventory)
    print(json.dumps({
        "status": "PREPARED_NOT_EXECUTED",
        "request_count": len(prepared),
        "rights_decision_count": len(rights),
        "source_family_counts": plan["source_family_counts"],
        "conservative_max_usd": plan["conservative_max_usd"],
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "inventory_sha256": sha_file(out / "artifact-inventory.json"),
        "output": str(out),
        "provider_calls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
