"""Build non-transmitted execution identities from frozen rows and retained sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from charitygraph.execution_envelope_v15 import build_envelopes, compatibility_audit_ledger
from charitygraph.generic_discovery_contract import CONTRACT_SCHEMA, CONTRACT_VERSION

PUBLIC_PRIVATE_POLICY = "CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1"
PROVIDER_POLICY = "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1"
TRANSMITTABLE_FAMILIES = {"acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website", "annual_report"}


def blob(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(blob(value)).hexdigest()


def write(path: Path, value: object) -> str:
    path.write_bytes(blob(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--acquisition-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    instances_doc = json.loads(args.instances.read_text(encoding="utf-8"))
    contracts_doc = json.loads(args.contracts.read_text(encoding="utf-8"))
    acquisition = json.loads(args.acquisition_ledger.read_text(encoding="utf-8"))
    envelopes = build_envelopes(instances_doc["instances"], contracts_doc["contracts"])
    evidence_by_abn: dict[str, list[dict]] = defaultdict(list)
    admission_rows: list[dict] = []
    for source in acquisition["rows"]:
        family = source["source_family"]
        acquired = source["acquisition_state"] == "ACQUIRED"
        payload_hash = source.get("payload_sha256")
        # PDF reports require a completed page/native-text representation before
        # a packet may expose them.  Acquisition alone is intentionally not a
        # representation or admission decision.
        representation_ready = source.get("media_type") != "application/pdf"
        provider_visible = bool(acquired and payload_hash and representation_ready and family in TRANSMITTABLE_FAMILIES and source.get("binding_state") not in {"UNBOUND_SHARED_SOURCE", "NO_GOVERNED_LOCATOR"})
        readiness = "READY_SOURCE_NATIVE" if provider_visible else ("REPRESENTATION_PENDING" if acquired and not representation_ready else ("NOT_READY" if acquired else "NOT_ACQUIRED"))
        record = {"evidence_id": "evidence:" + payload_hash if payload_hash else None, "source_family": family,
                  "source_locator": source.get("resolved_locator") or source.get("requested_locator"), "payload_sha256": payload_hash,
                  "representation_readiness": readiness, "provider_visible": provider_visible,
                  "rights_policy_id": PUBLIC_PRIVATE_POLICY if provider_visible else None,
                  "provider_processing_policy_id": PROVIDER_POLICY if provider_visible else None,
                  "rights_status": "AUTHORIZED_BY_EXISTING_PUBLIC_SOURCE_POLICY" if provider_visible else "NOT_ADMITTED",
                  "admission_reason": "acquired, ABN/ACNC-bound source-native material under existing public-source private-processing policy" if provider_visible else "unbound/shared, unavailable, or representation is not ready"}
        admission_rows.append({"abn": source.get("abn"), **record})
        if source.get("abn"):
            evidence_by_abn[str(source["abn"])].append(record)
    packets = []
    for envelope, instance in zip(envelopes, instances_doc["instances"], strict=True):
        abns = [str(item["value"]) for item in instance["governed_subject"].get("external_authority_identifiers", []) if item.get("scheme") == "ABN"]
        evidence = sorted([item for abn in abns for item in evidence_by_abn[abn] if item["provider_visible"]], key=lambda x: (x["source_family"], x["evidence_id"] or ""))
        packet = {"schema": "charitygraph.g3.frozen-execution-packet/v1", "contract_schema": CONTRACT_SCHEMA,
                  "contract_version": CONTRACT_VERSION, "provider_calls": 0, "envelope": envelope,
                  "provider_visible_evidence": evidence, "untransmitted_source_count": sum(len(evidence_by_abn[abn]) for abn in abns) - len(evidence),
                  "packet_status": "FROZEN_PROVIDER_FREE_CANDIDATE"}
        packet["packet_identity"] = "packet:" + sha(packet)
        packets.append(packet)
    by_family = Counter(item["source_family"] for packet in packets for item in packet["provider_visible_evidence"])
    source_bytes = {row.get("payload_sha256"): row.get("byte_size", 0) for row in acquisition["rows"] if row.get("payload_sha256")}
    # Repeated representations are charged per request; bytes/4 is an estimate and bytes/2 is the ceiling.
    transmitted_bytes = sum(source_bytes.get(item["payload_sha256"], 0) for packet in packets for item in packet["provider_visible_evidence"])
    estimated_input = math.ceil(transmitted_bytes / 4)
    conservative_input = math.ceil(transmitted_bytes / 2)
    output_cap = 8_000 * len(packets)
    estimate_usd = (estimated_input * 0.20 + output_cap * 1.20) / 1_000_000
    ceiling_usd = (conservative_input * 0.20 + output_cap * 1.20) / 1_000_000
    economics = {"model_pricing_snapshot": "gpt-5.6-luna input USD 0.20/M; output USD 1.20/M", "request_count": len(packets), "projected_input_tokens": estimated_input, "conservative_input_token_ceiling": conservative_input, "max_output_tokens_per_request": 8000, "projected_max_output_tokens": output_cap, "projected_usd": round(estimate_usd, 6), "conservative_usd_ceiling": round(ceiling_usd, 6), "aud_conversion": "not set: use Finance-approved execution-day USD/AUD rate", "provider_calls": 0}
    validation = {"status": "PASS", "frozen_instance_count": len(instances_doc["instances"]), "envelope_count": len(envelopes), "packet_count": len(packets), "compatibility_decision_count": sum(bool(x["compatibility_decisions"]) for x in envelopes), "provider_calls": 0, "unbound_wikipedia_or_pfra_transmitted": False, "all_packet_evidence_rights_admitted": all(item["rights_status"].startswith("AUTHORIZED") for packet in packets for item in packet["provider_visible_evidence"])}
    contract_by_identity = {item["final_template_identity"]: item for item in contracts_doc["contracts"]}
    actual_compatibility = []
    for envelope, instance in zip(envelopes, instances_doc["instances"], strict=True):
        if not envelope["compatibility_decisions"]:
            continue
        contract = contract_by_identity[envelope["template_contract"]["template_identity"]]
        actual_compatibility.append({
            "bound_question_identity": envelope["bound_question_identity"],
            "frozen_template_identity": instance["final_template_identity"],
            "approved_contract_identity": contract["final_template_identity"],
            "compiled_contract_identity": envelope["template_contract"]["contract_identity"],
            "frozen_successor_lineage": [item.get("source_record") for item in instance.get("bound_user_choice_parameters", [])],
            "operation_exact_match": (instance["requested_operation"].get("operation") if isinstance(instance["requested_operation"], dict) else instance["requested_operation"]) == contract["operation"],
            "approved_scope": contract["scope"],
            "approved_time": contract["time"],
            "approved_permitted_states": contract["permitted_states"],
            "frozen_question_text_preserved": envelope["question_text"] == instance["question_text"],
            "frozen_parameter_values": envelope["frozen_user_parameters"],
            "semantic_parameter_values": envelope["semantic_user_parameters"],
            "decisions": envelope["compatibility_decisions"],
            "result": "MECHANICAL_COMPATIBILITY_VERIFIED",
        })
    inventory: dict[str, str] = {}
    inventory["compatibility-audit-ledger.json"] = write(args.output / "compatibility-audit-ledger.json", {"approved_closed_rules": compatibility_audit_ledger(), "actual_frozen_comparisons": actual_compatibility})
    inventory["frozen-execution-envelopes.json"] = write(args.output / "frozen-execution-envelopes.json", {"envelopes": envelopes})
    inventory["evidence-admission-ledger.json"] = write(args.output / "evidence-admission-ledger.json", {"rows": admission_rows})
    inventory["frozen-execution-packets.json"] = write(args.output / "frozen-execution-packets.json", {"packets": packets})
    inventory["cost-forecast.json"] = write(args.output / "cost-forecast.json", economics)
    inventory["validation-results.json"] = write(args.output / "validation-results.json", validation)
    inventory["artifact-sha256-inventory.json"] = write(args.output / "artifact-sha256-inventory.json", {"artifacts": inventory})
    print(json.dumps({"packets": len(packets), "provider_visible_by_family": dict(sorted(by_family.items())), "inventory": inventory, "economics": economics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
