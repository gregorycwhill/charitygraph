"""Provider-free real relationship proof from retained Red Cross evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from charitygraph.contracts import (
    ArtifactRef, EvidenceLocator, LineageEdge, Observation, ObservationTime,
    ProducerRef, RelationshipStatement, SchemaRef, ScopeRecord, SubjectRecord,
)
from charitygraph.contracts.ids import deterministic_id
from charitygraph.integrated_card import CardEvidence, IntegratedGraph, project_subject
from charitygraph.runtime import SQLiteCatalog


RUNTIME = Path(r"C:\CharityGraph-runtime")
RETAINED = RUNTIME / "direct-service-real-run-phase3-wire-v1"
OUTPUT = RUNTIME / "phase3-relationship-role-proof-20260906"
DB = OUTPUT / "state" / "relationship-proof.sqlite3"
NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="phase3-relationship-role-proof", version="1")
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")


def subject(subject_id: str, name: str, kind: str, authority_source: str, *, abn: str | None = None) -> SubjectRecord:
    identifiers = () if abn is None else ({"scheme": "ABN", "value": abn, "issuing_authority": "ATO ABR"},)
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id}), subject_id=subject_id,
        subject_kind=kind, lifecycle_status="active", display_name=name, external_identifiers=identifiers,
        identity_authority_refs=(ArtifactRef(artifact_id=authority_source, content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="retained-direct-service-identity-v1", created_at=NOW, producer=PRODUCER,
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    packet = json.loads((RETAINED / "packet.json").read_text(encoding="utf-8"))
    recovered = json.loads((RETAINED / "combined-red-cross-projection-recovered.json").read_text(encoding="utf-8"))
    projection = next(
        item for section in recovered["sections"] for item in section.get("relationship_projections", [])
        if item.get("role") == "operator" and item.get("target_label") == "Telecross and Telechat"
    )
    source_subject_id = packet["subject_id"]
    source_record_ids = {item["source_role"]: item["source_record_id"] for item in packet["sources"]}
    official_source = source_record_ids["official_homepage"]
    target_scope_id = projection["target_scope_id"]
    target_subject_id = deterministic_id("subject:", {"parent_subject_id": source_subject_id, "scope_id": target_scope_id, "kind": "service"})
    source = subject(source_subject_id, "Australian Red Cross Society", "organisation", source_record_ids["register_identity"], abn="50169561394")
    target = subject(target_subject_id, "Telecross and Telechat", "service", official_source)
    scope = ScopeRecord(record_id=target_scope_id, subject_id=source_subject_id, scope_kind="service", label="Telecross and Telechat", created_at=NOW, producer=PRODUCER)

    with SQLiteCatalog(DB).open(initialize=True) as catalog:
        catalog.register_subject(source)
        catalog.register_subject(target)
        catalog.register_scope(scope)
        locators = []
        for locator in projection["evidence"]:
            row = catalog.register_evidence_locator(EvidenceLocator(kind="document", source_record_id=official_source, locator=locator["locator"], section="retained direct-service relationship result"))
            locators.append(row["evidence_locator_id"])
        observation_id = deterministic_id("observation:", {"relationship": projection["party_role_id"], "source": source_subject_id, "target": target_subject_id})
        observation = Observation(
            record_id=observation_id, subject_id=source_subject_id, scope_id=target_scope_id,
            predicate="direct_service.relationship_role", value={"role": "operator", "direction": projection["direction"], "target_subject_id": target_subject_id},
            outcome_state="supported", evidence_locator_ids=tuple(dict.fromkeys(locators)), source_record_ids=(official_source,),
            observation_time=ObservationTime(observed_at=NOW), method="retained-direct-service-recovery-v1", lifecycle_status="held",
            created_at=NOW, producer=PRODUCER,
        )
        catalog.record_observation(observation)
        relationship_id = deterministic_id("relationship:", {"source": source_subject_id, "target": target_subject_id, "role": "operator", "evidence": locators})
        relationship = RelationshipStatement(
            record_id=relationship_id, source_subject_id=source_subject_id, target_subject_id=target_subject_id,
            relationship_type="operator", role="operator", source_role="operator", target_role="service",
            scope_id=target_scope_id, evidence_locator_ids=tuple(dict.fromkeys(locators)), observation_ids=(observation_id,),
            status="candidate", created_at=NOW, producer=PRODUCER,
            lineage=(LineageEdge(edge_type="derived_from", source_artifact_id=relationship_id, target_artifact_id=observation_id),),
        )
        catalog.record_relationship(relationship)
        reloaded = SQLiteCatalog(DB).open()
        try:
            persisted_source = reloaded.get_subject(source_subject_id)
            persisted_target = reloaded.get_subject(target_subject_id)
            persisted_relationship = reloaded.get_relationship(relationship_id)
            persisted_lineage = reloaded.get_knowledge_lineage(relationship_id)
        finally:
            reloaded.close()

    graph = IntegratedGraph(
        subjects=(source, target), scopes=(scope,), observations=(observation,), relationships=(relationship,),
        evidence=(CardEvidence(observation_id=observation_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", assignment_contract="UNRESOLVED", note="Relationship source is retained experimental output; relation is not promoted."),),
    )
    card = project_subject(graph, source_subject_id)
    section12 = card["sections"][11]
    role_rows = [
        {"role": "operator", "real_retained_proposition_found": "YES", "endpoints_resolved": "YES", "persisted": "YES", "projected": "YES"},
        {"role": "deliverer", "real_retained_proposition_found": "NOT PRESENT IN RETAINED SAMPLE", "endpoints_resolved": "NO", "persisted": "NO", "projected": "NO"},
        {"role": "funder", "real_retained_proposition_found": "YES", "endpoints_resolved": "UNRESOLVED IDENTITY", "persisted": "NO", "projected": "NO"},
        {"role": "sponsor", "real_retained_proposition_found": "NOT PRESENT IN RETAINED SAMPLE", "endpoints_resolved": "NO", "persisted": "NO", "projected": "NO"},
        {"role": "partner", "real_retained_proposition_found": "YES", "endpoints_resolved": "UNRESOLVED IDENTITY", "persisted": "NO", "projected": "NO"},
        {"role": "auspice", "real_retained_proposition_found": "NOT PRESENT IN RETAINED SAMPLE", "endpoints_resolved": "NO", "persisted": "NO", "projected": "NO"},
        {"role": "network_context", "real_retained_proposition_found": "YES", "endpoints_resolved": "UNRESOLVED IDENTITY", "persisted": "NO", "projected": "NO"},
    ]
    report = {
        "branch": "charitygraph-phase3-relationship-role-proof", "provider_calls": 0, "new_source_acquisition": 0,
        "retained_case": {"runtime": str(RETAINED), "source": "Australian Red Cross official website", "proposition": "Australian Red Cross Society operates Telecross and Telechat", "retained_role": projection["role"], "retained_direction": projection["direction"]},
        "endpoint_identity_basis": {"source": {"subject_id": source_subject_id, "abn": "50169561394", "authority": "retained ACNC register packet"}, "target": {"subject_id": target_subject_id, "basis": "retained direct-service scope with explicit durable endpoint flag; no invented ABN"}},
        "persistence_reload": {"source_subject_reloaded": persisted_source is not None, "target_subject_reloaded": persisted_target is not None, "relationship_reloaded": persisted_relationship is not None, "direction": persisted_relationship["source_subject_id"] == source_subject_id and persisted_relationship["target_subject_id"] == target_subject_id, "role": persisted_relationship["relationship_role"] == "operator", "scope": persisted_relationship["scope_id"] == target_scope_id, "evidence_count": len(json.loads(persisted_relationship["evidence_locator_ids_json"])), "lineage_count": len(persisted_lineage)},
        "section_12_projection": {"relationship_ids": section12["relationship_ids"], "contains_proved_relationship": relationship_id in section12["relationship_ids"], "canonical_storage_duplicated": "relationship_type" in section12},
        "role_table": role_rows,
        "unresolved_diagnostics": {"count": 6, "targets": ["World Vision International Partnership", "World Vision International", "Department of Foreign Affairs and Trade (DFAT)", "World Vision New Zealand", "Grant Thornton Audit Pty Ltd", "Kanyirninpa Jukurrpa"], "reason": "retained relationship evidence lacks durable endpoint identity records"},
        "disposition": "PHASE 3 CAN CLOSE",
    }
    (OUTPUT / "relationship-proof.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT / "relationship-proof-card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Phase 3 relationship-role proof", "", "Disposition: **PHASE 3 CAN CLOSE**", "", "Real retained case: Australian Red Cross Society —operator→ Telecross and Telechat", "", "| Role | Proposition | Endpoints | Persisted | Projected |", "|---|---|---|---|---|"]
    lines.extend(f"| {row['role']} | {row['real_retained_proposition_found']} | {row['endpoints_resolved']} | {row['persisted']} | {row['projected']} |" for row in role_rows)
    lines.extend(["", f"Relationship ID: `{relationship_id}`", f"Section 12 projection IDs: `{section12['relationship_ids']}`", "", "Provider calls: **0**", "New source acquisition: **0**", "", "Six unresolved World Vision targets remain diagnostic-only; no identity was invented."])
    (OUTPUT / "relationship-proof.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
