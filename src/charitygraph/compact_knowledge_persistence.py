"""Deterministic adapter from compact v0.2 atoms to governed observations."""
from __future__ import annotations

from datetime import date, datetime
from typing import Mapping, Any

from .compact_knowledge import CompactKnowledgeOutputV02
from .contracts.common import LineageEdge, ProducerRef
from .contracts.ids import deterministic_id
from .contracts.knowledge import Observation, ObservationTime, ScopeRecord


def _iso(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def adapt_compact_v02(
    output: CompactKnowledgeOutputV02 | Mapping[str, Any], *, subject_id: str,
    observed_at: datetime, model_result_id: str, task_id: str,
    evidence_locator_map: Mapping[tuple[str, str], str],
    source_record_map: Mapping[str, str], existing_scopes: Mapping[str, ScopeRecord] | None = None,
) -> tuple[tuple[ScopeRecord, ...], tuple[Observation, ...]]:
    """Map valid atoms without creating assertions or applying semantic inference."""
    result = output if isinstance(output, CompactKnowledgeOutputV02) else CompactKnowledgeOutputV02.model_validate(output)
    scopes = dict(existing_scopes or {})
    new_scopes: list[ScopeRecord] = []
    observations: list[Observation] = []
    for index, atom in enumerate(result.atoms):
        scope_id = None
        if atom.scope_kind != "subject":
            scope_kind = {"named_program_or_service": "program", "other_named_scope": "other", "reporting_group": "reporting_group", "uncertain": "other"}[atom.scope_kind]
            label = atom.scope_label or "Unlabelled scope"
            scope_id = deterministic_id("scope:", {"subject_id": subject_id, "scope_kind": scope_kind, "label": label})
            if scope_id not in scopes:
                scope = ScopeRecord(record_id=scope_id, subject_id=subject_id, scope_kind=scope_kind, label=label, created_at=observed_at, producer=ProducerRef(kind="code", producer_id="compact-knowledge-persistence", version="0.1"))
                scopes[scope_id] = scope; new_scopes.append(scope)
        evidence_ids=[]; source_ids=[]
        for ref in atom.evidence:
            key=(ref.source, ref.locator)
            if key not in evidence_locator_map:
                raise ValueError(f"unresolved compact evidence locator: {ref.source}/{ref.locator}")
            evidence_ids.append(evidence_locator_map[key])
            if ref.source not in source_record_map:
                raise ValueError(f"missing source record mapping: {ref.source}")
            source_ids.append(source_record_map[ref.source])
        times=ObservationTime(effective_from=_iso(atom.effective_from, "effective_from"), effective_to=_iso(atom.effective_to, "effective_to"), reporting_period=atom.reporting_period, observed_at=observed_at)
        obs_id=deterministic_id("observation:", {"task_id": task_id, "model_result_id": model_result_id, "atom_index": index, "atom": atom.model_dump(mode="json")})
        observations.append(
            Observation(
                record_id=obs_id, subject_id=subject_id, scope_id=scope_id,
                predicate="compact_statement",
                value={"proposition": atom.proposition, "epistemic_status": atom.epistemic_status, "scope_label": atom.scope_label},
                outcome_state="supported", evidence_locator_ids=tuple(dict.fromkeys(evidence_ids)),
                source_record_ids=tuple(dict.fromkeys(source_ids)), observation_time=times,
                method="model:compact-knowledge-v0.2", lifecycle_status="candidate",
                qualifications=atom.qualifications, created_at=observed_at,
                producer=ProducerRef(kind="model", producer_id="gpt-5.6-luna"),
                about_subject_ids=(subject_id,),
                lineage=(
                    LineageEdge(edge_type="derived_from", source_artifact_id=obs_id, target_artifact_id=model_result_id),
                    LineageEdge(edge_type="derived_from", source_artifact_id=obs_id, target_artifact_id=task_id),
                ),
            )
        )
    return tuple(new_scopes), tuple(observations)
