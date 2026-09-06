"""Private Phase 4 P4-E1 packaging/routing experiment contracts.

This module contains only experiment-local transport contracts.  It does not
create canonical knowledge, infer relationships, or resolve durable targets.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, StrictStr

from .contracts.common import StrictModel, require_nonblank
from .contracts.knowledge import RelationshipRole
from .contracts.direct_service import RelationshipDirection, ScopeKind
from .compact_knowledge import CompactKnowledgeOutputV02


class P4E1EvidenceRef(StrictModel):
    locator: StrictStr
    role: Literal["supporting", "corroborating", "context"]

    @classmethod
    def validate_locator(cls, value: str) -> str:
        return require_nonblank(value, "locator")


class P4E1Temporal(StrictModel):
    effective_from: date | datetime | None = None
    effective_to: date | datetime | None = None
    reporting_period: StrictStr | None = None
    observed_at: date | datetime | None = None


class P4E1Relationship(StrictModel):
    source_scope_kind: ScopeKind
    source_scope_id: StrictStr
    source_label: StrictStr
    target_scope_kind: ScopeKind | None = None
    target_scope_id: StrictStr | None = None
    target_label: StrictStr
    role: RelationshipRole
    direction: RelationshipDirection
    temporal: P4E1Temporal | None = None
    evidence: tuple[P4E1EvidenceRef, ...] = ()
    qualification: StrictStr | None = None


class P4E1RelationshipOutput(StrictModel):
    relationships: tuple[P4E1Relationship, ...]


class P4E1BundledOutput(StrictModel):
    compact: CompactKnowledgeOutputV02
    relationships: P4E1RelationshipOutput


P4E1_COMPACT_SCHEMA = CompactKnowledgeOutputV02.model_json_schema()
P4E1_RELATIONSHIP_SCHEMA = P4E1RelationshipOutput.model_json_schema()
P4E1_BUNDLED_SCHEMA = P4E1BundledOutput.model_json_schema()


def _strictify(value):
    if isinstance(value, dict):
        value.pop("default", None)
        if value.get("type") == "object" and "properties" in value:
            value["required"] = list(value["properties"])
        for child in value.values():
            _strictify(child)
    elif isinstance(value, list):
        for child in value:
            _strictify(child)


for _schema in (P4E1_COMPACT_SCHEMA, P4E1_RELATIONSHIP_SCHEMA, P4E1_BUNDLED_SCHEMA):
    _strictify(_schema)


__all__ = [
    "P4E1EvidenceRef", "P4E1Temporal", "P4E1Relationship",
    "P4E1RelationshipOutput", "P4E1BundledOutput", "P4E1_COMPACT_SCHEMA",
    "P4E1_RELATIONSHIP_SCHEMA", "P4E1_BUNDLED_SCHEMA",
]
