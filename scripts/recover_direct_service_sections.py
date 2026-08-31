"""Revalidate the completed Red Cross responses under the corrected wire boundary."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from charitygraph.contracts import ModelResult, project_observation, wire_to_domain
from charitygraph.contracts.direct_service import DirectServiceSemanticOutput
from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput
from charitygraph.contracts.direct_service import DIRECT_SERVICE_OUTPUT_SCHEMA
from charitygraph.direct_service_planning import SECTIONS
from charitygraph.direct_service_recovery import RECOVERY_ADAPTER_VERSION, recover_historical_wire, recovery_identity
from charitygraph.runtime import SQLiteCatalog
from charitygraph.strict_schema import strictify_schema


ROOT = Path(r"C:\CharityGraph-runtime\direct-service-real-run-phase3-wire-v1")
PACKET = ROOT / "packet.json"
CATALOGUE = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
OLD_SCHEMA_SHA = "514c2503cff309b436473fada8a03ca341a0b156e5a7af061717209bba488b2a"
SUBJECT_ID = "subject:d10dfad31cb04c5fb27ada0a81f36b69"
RECOVERY_POLICY_VERSION = "direct-service-wire-schema-strip-v1-per-item-validation-v2"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    sources = packet["sources"]
    scopes = {item["scope_id"] for item in packet["scopes"]}
    # Recovery is a replayable processing event, not a new model execution.
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    catalog = SQLiteCatalog(CATALOGUE).open()
    sections = []
    try:
        catalog.migrate()
        for number in ("6", "11", "13"):
            runtime = ROOT / "sections" / f"section-{number}"
            response = json.loads((runtime / "response.json").read_text(encoding="utf-8"))
            response_id = response["response_id"]
            raw = response["output_text"]
            parsed = json.loads(raw)
            if response.get("status") != "completed" or not isinstance(parsed, dict) or "schema" not in parsed:
                raise ValueError(f"{number}: historical response is not a completed JSON object with schema")
            historical_schema = parsed["schema"]
            wire = recover_historical_wire(raw)
            locator_sources: dict[str, str] = {}
            for index, source in enumerate(sources, 1):
                base = f"S{index:03d}:L0001"
                catalog.register_evidence_locator({"kind": "document", "source_record_id": source["source_record_id"], "locator": base}, evidence_locator_id=base, now=now)
                locator_sources[base] = source["source_record_id"]
            for item in list(wire.propositions) + list(wire.relationships):
                for ref in item.evidence:
                    locator = ref.locator
                    base = locator.split("#", 1)[0]
                    if base not in locator_sources:
                        raise ValueError(f"{number}: unknown evidence locator namespace {locator}")
                    catalog.register_evidence_locator({"kind": "document", "source_record_id": locator_sources[base], "locator": locator}, evidence_locator_id=locator, now=now)
            all_locators = set(locator_sources) | {ref.locator for item in list(wire.propositions) + list(wire.relationships) for ref in item.evidence}
            # Validate evidence and domain typing first; scope is assessed per
            # proposition so one bad model scope cannot erase good items.
            rejected: dict[str, list[dict[str, object]]] = {}
            valid_props = []
            for index, item in enumerate(wire.propositions):
                try:
                    one = wire_to_domain(DirectServiceWireOutput(section=wire.section, propositions=(item,)), evidence_locators=all_locators)
                    proposition = one.propositions[0]
                    if proposition.scope_id not in scopes and proposition.scope_id != SUBJECT_ID:
                        raise ValueError(f"unknown proposition scope_id: {proposition.scope_id}")
                    if number == "11" and proposition.proposition_type == "capacity_measure" and index in {6, 10, 14, 19}:
                        raise RuntimeError("capacity_measure is a delivered/activity volume, not a capacity claim")
                    valid_props.append(proposition)
                except RuntimeError as exc:
                    rejected.setdefault("rejected_contract", []).append({"index": index, "reason": str(exc)})
                except ValueError as exc:
                    rejected.setdefault("rejected_scope" if "scope_id" in str(exc) else "rejected_contract", []).append({"index": index, "reason": str(exc)[:300]})
            valid_rels = []
            relationship_rejected_scope = 0
            for index, item in enumerate(wire.relationships):
                try:
                    one = wire_to_domain(DirectServiceWireOutput(section=wire.section, relationships=(item,)), evidence_locators=all_locators)
                    relationship = one.relationships[0]
                    if relationship.source_scope_id not in scopes or relationship.target_scope_id not in scopes:
                        raise ValueError("relationship scope is not task-visible")
                    valid_rels.append(relationship)
                except ValueError as exc:
                    if "scope" in str(exc):
                        relationship_rejected_scope += 1
                    rejected.setdefault("rejected_scope" if "scope" in str(exc) else "rejected_contract", []).append({"relationship_index": index, "reason": str(exc)[:300]})
            domain = DirectServiceSemanticOutput(section=wire.section, propositions=tuple(valid_props), relationships=tuple(valid_rels))
            if domain.section != SECTIONS[number][0]:
                raise ValueError(f"{number}: returned section mismatch")
            recovery_id = recovery_identity(response_id=response_id, old_wire_schema_sha=OLD_SCHEMA_SHA, domain_schema_id=DIRECT_SERVICE_OUTPUT_SCHEMA.schema_id, policy_version=RECOVERY_POLICY_VERSION)
            task_report = json.loads((runtime / "run-report.json").read_text(encoding="utf-8"))
            model_result = ModelResult(record_id=recovery_id, created_at=now, producer={"kind": "code", "producer_id": "direct-service-revalidation", "version": RECOVERY_ADAPTER_VERSION}, model_task_id=task_report["task_id"], task_run_id=task_report["task_run_id"], output_schema=DIRECT_SERVICE_OUTPUT_SCHEMA, output=domain, validation_status="valid", raw_response_ref=response_id, completed_at=now, provider_id="openai", model_snapshot="gpt-5.6-luna")
            catalog.register_model_result(model_result)
            catalog.record_knowledge_lineage(recovery_id, task_report["task_id"], "derived_from", material={"validation_policy": RECOVERY_POLICY_VERSION, "original_response_id": response_id}, created_at=now)
            accepted = []
            for index, proposition in enumerate(domain.propositions):
                source_ids = tuple(dict.fromkeys(locator_sources[ref.locator.split("#", 1)[0]] for ref in proposition.evidence))
                # Subject-level propositions use the Observation subject itself;
                # only explicit child scopes become Observation.scope_id values.
                observation_scope = None if proposition.scope_id == SUBJECT_ID else proposition.scope_id
                observation = project_observation(proposition, record_id="observation:" + _sha((recovery_id + str(index)).encode())[:64], subject_id=SUBJECT_ID, scope_id=observation_scope, source_record_ids=source_ids, created_at=now, producer={"kind": "model", "producer_id": "gpt-5.6-luna", "version": "direct-service-v1"}, method="direct_service_revalidation_v1")
                catalog.record_observation(observation)
                catalog.record_knowledge_lineage(observation.record_id, recovery_id, "derived_from", material={"validation_policy": RECOVERY_POLICY_VERSION}, created_at=now)
                accepted.append({"index": index, "observation_id": observation.record_id, "proposition_type": proposition.proposition_type, "scope_id": proposition.scope_id, "scope_kind": proposition.scope_kind, "coverage_state": proposition.coverage_state, "evidence": [ref.model_dump(mode="json") for ref in proposition.evidence], "source_record_ids": source_ids})
            sections.append({"section": number, "response_id": response_id, "original_schema": historical_schema, "original_validation": "failed_schema_identity", "recovery_validation_id": recovery_id, "wire_valid": True, "domain_valid": True, "proposed": len(wire.propositions), "accepted": len(accepted), "rejected": rejected, "relationships_proposed": len(wire.relationships), "relationships_accepted": len(domain.relationships), "relationships_rejected_scope": relationship_rejected_scope, "relationship_persistence": "blocked_scoped_relationship_target_requires_product_primitive" if domain.relationships else "none", "accepted_items": accepted})
        projection = {"private": True, "packet_sha256": _sha((json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()), "subject_id": SUBJECT_ID, "sections": sections, "history": "original provider responses remain completed; original validation failed; deterministic recovery removes only obsolete top-level schema"}
        (ROOT / "combined-red-cross-projection-recovered.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        new_wire_schema = strictify_schema(DirectServiceWireOutput.model_json_schema())
        report = {"private": True, "adapter": {"old_wire_schema_sha": OLD_SCHEMA_SHA, "new_wire_schema_sha": _sha(json.dumps(new_wire_schema, sort_keys=True, separators=(",", ":")).encode()), "removed_provider_field": "schema", "canonical_domain_schema": DIRECT_SERVICE_OUTPUT_SCHEMA.model_dump(mode="json"), "recovery_adapter_version": RECOVERY_ADAPTER_VERSION, "recovery_policy_version": RECOVERY_POLICY_VERSION}, "sections": sections, "aggregate": {"accepted": sum(x["accepted"] for x in sections), "proposed": sum(x["proposed"] for x in sections), "rejected": sum(sum(len(v) for v in x["rejected"].values()) for x in sections), "relationships_proposed": sum(x["relationships_proposed"] for x in sections), "relationships_accepted": sum(x["relationships_accepted"] for x in sections), "relationships_rejected_scope": sum(x["relationships_rejected_scope"] for x in sections), "relationship_persistence": "blocked_scoped_relationship_target_requires_product_primitive", "new_provider_calls": 0, "new_provider_cost_usd": "0", "original_provider_cost_usd": "0.130508", "original_provider_cost_aud": "0.198372", "coverage_states": sorted({item["coverage_state"] for section in sections for item in section["accepted_items"]}), "new_durable_primitive_required": any(x["relationships_proposed"] for x in sections)}, "combined_projection_path": str(ROOT / "combined-red-cross-projection-recovered.json")}
        (ROOT / "recovery-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report["aggregate"], indent=2))
        return 0
    finally:
        catalog.close()


if __name__ == "__main__":
    raise SystemExit(main())
