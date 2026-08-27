"""Production-native, evidence-bound program/service discovery task builder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .contracts import (
    EvidenceInput,
    ModelTask,
    SchemaRef,
    discovery_output_schema_ref,
    model_task_cache_key,
)
from .contracts.ids import deterministic_id
from .runtime import CatalogError, SQLiteCatalog


TASK_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:program-service-discovery-task:1.0",
    schema_version="1.0",
)


def build_discovery_task(
    catalog: SQLiteCatalog,
    *,
    subject_id: str,
    evidence_ids: Iterable[str],
    prompt_template_id: str,
    prompt_template_version: str,
    provider_id: str,
    model_snapshot: str,
    parameters: dict[str, Any] | None = None,
) -> ModelTask:
    """Construct a typed task from evidence already present in the catalogue."""

    ordered_ids = tuple(evidence_ids)
    if not ordered_ids or len(set(ordered_ids)) != len(ordered_ids):
        raise CatalogError("discovery tasks require unique ordered evidence IDs")
    inputs: list[EvidenceInput] = []
    with catalog._connection() as conn:
        for evidence_id in ordered_ids:
            row = conn.execute(
                "SELECT * FROM evidence_locators WHERE evidence_locator_id=?",
                (evidence_id,),
            ).fetchone()
            if row is None:
                raise CatalogError(f"unknown evidence {evidence_id}")
            content_hash = catalog._evidence_content_hash(conn, row)
            if content_hash is None:
                raise CatalogError(f"evidence {evidence_id} has no recoverable content hash")
            inputs.append(EvidenceInput(
                evidence_id=evidence_id,
                content_hash=content_hash,
                selection_hash=str(row["material_hash"]),
            ))
    evidence = tuple(inputs)
    output_schema = discovery_output_schema_ref(ordered_ids)
    task_parameters = parameters or {}
    cache_key = model_task_cache_key(
        task_type="semantic_interpretation",
        task_schema=TASK_SCHEMA,
        output_schema=output_schema,
        evidence_inputs=evidence,
        prompt_template_id=prompt_template_id,
        prompt_template_version=prompt_template_version,
        policy_refs=(),
        provider_id=provider_id,
        model_snapshot=model_snapshot,
        parameters=task_parameters,
        material_tool_versions=(),
    )
    record_id = deterministic_id(
        "modeltask:",
        {
            "subject_id": subject_id,
            "scope_id": None,
            "task_type": "semantic_interpretation",
            "cache_key": cache_key,
            "output_schema": output_schema,
        },
    )
    return ModelTask(
        record_id=record_id,
        created_at=datetime.now(timezone.utc),
        producer={"kind": "code", "producer_id": "native-discovery-builder", "version": "1"},
        subject_id=subject_id,
        task_type="semantic_interpretation",
        task_schema=TASK_SCHEMA,
        output_schema=output_schema,
        evidence_inputs=evidence,
        prompt_template_id=prompt_template_id,
        prompt_template_version=prompt_template_version,
        provider_id=provider_id,
        model_snapshot=model_snapshot,
        parameters=task_parameters,
        paid_output_categories=("semantic_judgement",),
        cache_key=cache_key,
    )
