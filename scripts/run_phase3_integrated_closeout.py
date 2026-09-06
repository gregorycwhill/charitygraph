"""Compile the private Phase 3 reality slice from retained local artefacts.

No network, provider SDK, or source acquisition path is imported here.  The
inputs are fixed retained files and all model-derived material remains held as
experimental input unless a governed identity source is present.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from charitygraph.contracts.knowledge import Observation, ObservationTime, SubjectRecord
from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.integrated_card import CardEvidence, IntegratedGraph, compile_coverage, project_subject


RUNTIME = Path(r"C:\CharityGraph-runtime")
OUTPUT = RUNTIME / "phase3-integrated-card-closeout-20260906"
NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")
SELECTED = (
    ("The Smith Family", "28000030179", "section18-smith-20260902", "private-review.json"),
    ("World Vision Australia", "28004778081", "worldvision-luna-knowledge-v02-20260830T103756Z", "parsed-output.json"),
    ("The Fred Hollows Foundation", "46070556642", "whole-card-calibration-v01-20260830T024044Z", "returned-output.json"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest(root: Path, packet: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for index, source in enumerate(packet.get("sources", []), 1):
        key = f"S{index:03d}"
        family = str(source.get("source_family", "retained_unknown"))
        role = str(source.get("source_role", "retained_input"))
        payload_hash = str(source.get("payload_hash", ""))
        if len(payload_hash) != 64:
            payload_hash = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
        record_id = deterministic_id("srcrec:", {"source_family": family, "source_version": None, "source_locator": f"{root.name}:{key}", "payload_hash": payload_hash})
        ids[key] = record_id
        rows.append({"source_key": key, "source_record_id": record_id, "source_family": family, "source_role": role, "payload_hash": payload_hash, "retained_root": root.name})
    return rows, ids


def make_subject(name: str, abn: str, source_record_id: str) -> SubjectRecord:
    subject_id = deterministic_id("subject:", {"abn": abn})
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id}), subject_id=subject_id,
        subject_kind="organisation", lifecycle_status="active", display_name=name,
        external_identifiers=({"scheme": "ABN", "value": abn, "issuing_authority": "ATO ABR"},),
        identity_authority_refs=(ArtifactRef(artifact_id=source_record_id, content_hash="0" * 64, schema=SCHEMA),),
        identity_policy_id="phase3.retained-source-identity.v1", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="phase3-integrated-card-closeout", version="1"),
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subjects: list[SubjectRecord] = []
    observations: list[Observation] = []
    evidence: list[CardEvidence] = []
    source_rows: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    unresolved_relationships: list[dict[str, Any]] = []

    for name, abn, root_name, result_name in SELECTED:
        root = RUNTIME / root_name
        packet = json.loads((root / "packet.json").read_text(encoding="utf-8"))
        sources, source_ids = source_manifest(root, packet)
        source_rows.extend(sources)
        authority_id = next((row["source_record_id"] for row in sources if row["source_family"] in {"acnc_register", "ato_abr_dgr"}), sources[0]["source_record_id"])
        subject = make_subject(name, abn, authority_id)
        subjects.append(subject)
        selection.append({"name": name, "abn": abn, "subject_id": subject.subject_id, "retained_root": root_name, "result": result_name, "source_count": len(sources)})

        # Identity is governed only when the retained packet carries a regulator/ABR source.
        identity_disposition = "REUSABLE_GOVERNED" if any(row["source_family"] in {"acnc_register", "ato_abr_dgr"} for row in sources) else "IDENTITY_OR_LINEAGE_UNRESOLVED"
        identity_id = deterministic_id("observation:", {"subject_id": subject.subject_id, "predicate": "identity.abn", "abn": abn})
        observations.append(Observation(
            record_id=identity_id, subject_id=subject.subject_id, predicate="identity.abn", value={"abn": abn, "name": name},
            outcome_state="supported" if identity_disposition == "REUSABLE_GOVERNED" else "unknown",
            source_record_ids=(authority_id,), observation_time=ObservationTime(observed_at=NOW), method="retained-source-identity-v1",
            lifecycle_status="accepted" if identity_disposition == "REUSABLE_GOVERNED" else "held", created_at=NOW,
            producer=ProducerRef(kind="code", producer_id="phase3-integrated-card-closeout", version="1"),
        ))
        evidence.append(CardEvidence(observation_id=identity_id, disposition=identity_disposition, section_ids=(1,)))

        result = json.loads((root / result_name).read_text(encoding="utf-8"))
        if root_name == "section18-smith-20260902":
            claims = [{**atom, "section_id": 18} for atom in result.get("atoms", [])]
        else:
            claims = list(result.get("observations", []))
        for index, claim in enumerate(claims):
            proposition = str(claim.get("proposition", "")).strip()
            if not proposition:
                continue
            section_id = claim.get("section_id")
            sections = (int(section_id),) if isinstance(section_id, int) and 1 <= section_id <= 20 else ()
            obs_id = deterministic_id("observation:", {"subject_id": subject.subject_id, "retained_root": root_name, "index": index, "proposition": proposition})
            source_refs = tuple(source_ids.values())
            observations.append(Observation(
                record_id=obs_id, subject_id=subject.subject_id, predicate="retained_proposition",
                value={"proposition": proposition, "scope": claim.get("scope"), "epistemic_status": claim.get("epistemic_status"), "qualifications": claim.get("qualifications", [])},
                outcome_state="supported" if claim.get("epistemic_status") == "supported" else "unknown",
                source_record_ids=source_refs, observation_time=ObservationTime(observed_at=NOW),
                method=f"retained:{root_name}:{result_name}", lifecycle_status="held", created_at=NOW,
                producer=ProducerRef(kind="code", producer_id="phase3-integrated-card-closeout", version="1"),
            ))
            evidence.append(CardEvidence(observation_id=obs_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=sections, note="Retained prior output; not promoted to governed assertion."))
        if root_name.startswith("worldvision-"):
            parsed = result.get("relationships", [])
            unresolved_relationships.extend(parsed if isinstance(parsed, list) else [])

    graph = IntegratedGraph(subjects=tuple(subjects), scopes=(), observations=tuple(observations), evidence=tuple(evidence))
    coverage = compile_coverage(graph)
    (OUTPUT / "selection-inventory.json").write_text(json.dumps({"data_commit": "6bd1622f4a34d88ab10a77c8b06b95da1720778d", "provider_calls": 0, "new_source_acquisition": 0, "selected": selection, "sources": source_rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT / "integrated-graph.json").write_text(json.dumps(graph.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    (OUTPUT / "coverage-matrix.json").write_text(json.dumps([item.model_dump(mode="json") for item in coverage], indent=2, ensure_ascii=False), encoding="utf-8")
    for item in subjects:
        card = project_subject(graph, item.subject_id)
        card_name = f"card-{item.subject_id.split(':', 1)[1]}"
        (OUTPUT / f"{card_name}.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
        card_lines = [f"# {item.display_name}", "", f"Subject ID: `{item.subject_id}`", "", "This private projection references durable observation IDs; it does not duplicate observation content.", "", "| Section | Status | Observations |", "|---:|---|---:|"]
        card_lines.extend(f"| {row['section_id']} — {row['title']} | {row['missingness']} | {len(row['observation_ids'])} |" for row in card["sections"])
        (OUTPUT / f"{card_name}.md").write_text("\n".join(card_lines) + "\n", encoding="utf-8")
    matrix_lines = ["# Coverage matrix", "", "| Section | Title | Status | Observations |", "|---:|---|---|---:|"]
    matrix_lines.extend(f"| {row.section_id} | {row.title} | {row.missingness} | {len(row.observation_ids)} |" for row in coverage)
    (OUTPUT / "coverage-matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    diagnostics = {
        "integrated_assembly": "PARTIALLY", "provider_calls": 0, "new_source_acquisition": 0,
        "selected_charities": [item["name"] for item in selection], "observations": len(observations),
        "governed_observations": sum(item.disposition == "REUSABLE_GOVERNED" for item in evidence),
        "experimental_observations": sum(item.disposition == "REUSABLE_EXPERIMENTAL_INPUT" for item in evidence),
        "relationship_role_result": "UNRESOLVED_TARGETS_RETAINED_DIAGNOSTIC_ONLY" if unresolved_relationships else "NO_TYPED_RELATIONSHIPS_AVAILABLE",
        "missingness_result": "EMPTY_SECTIONS_ARE_SOURCE_SILENT_AND_NOT_NEGATIVE_FACTS",
        "gaps": [
            {"class": "HISTORICAL_IDENTITY", "blocking": False, "detail": "Some retained result packets do not resolve every external relationship target."},
            {"class": "EVIDENCE_COVERAGE", "blocking": False, "detail": "Sections 2-20 are sparse or experimental for at least one selected charity."},
            {"class": "PROJECTION", "blocking": False, "detail": "Relationship and source manifests remain private inspection outputs in this tranche."},
        ],
        "next_tranche": "ONE TARGETED STRUCTURAL/INTEGRATION REPAIR",
        "unresolved_relationship_count": len(unresolved_relationships),
    }
    (OUTPUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Phase 3 integrated-card closeout", "", f"Integrated assembly: **{diagnostics['integrated_assembly']}**", "", "Provider calls: **0**  ", "New source acquisition: **0**  ", f"Observations retained: **{len(observations)}**", "", "## Selected charities", ""]
    lines.extend(f"- {item['name']} (ABN {item['abn']}) — {item['source_count']} retained sources" for item in selection)
    lines.extend(["", "## Result", "", "The private projection reuses durable subject and observation IDs across sections. Prior model outputs remain visibly experimental; empty sections are `SOURCE_SILENT`, not absence claims.", "", f"Next tranche: **{diagnostics['next_tranche']}**"])
    (OUTPUT / "closeout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
