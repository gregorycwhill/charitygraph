"""Strict wire contract for independent semantic scope resolution."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ScopeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    atom_index: int = Field(ge=0)
    resolved_scope_kind: Literal["subject", "named_program_or_service", "other_named_scope", "reporting_group", "uncertain"]
    resolved_scope_label: str | None = None
    scope_status: Literal["resolved", "uncertain"]
    supporting_evidence_indices: tuple[int, ...] = ()

    @classmethod
    def validate_for_atom(cls, decision: "ScopeDecision", evidence_count: int) -> "ScopeDecision":
        if any(i < 0 or i >= evidence_count for i in decision.supporting_evidence_indices):
            raise ValueError("supporting_evidence_indices out of range")
        if decision.resolved_scope_kind in {"subject", "uncertain"} and decision.resolved_scope_label is not None:
            raise ValueError("subject and uncertain scopes must not carry labels")
        if decision.resolved_scope_kind not in {"subject", "uncertain"} and not decision.resolved_scope_label:
            raise ValueError("lower scopes require a label")
        return decision

class ScopeResolutionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    decisions: tuple[ScopeDecision, ...]

SCOPE_RESOLUTION_SCHEMA = ScopeResolutionOutput.model_json_schema()
def _strict(node):
    if isinstance(node, dict):
        if node.get("type") == "object": node["required"] = list(node.get("properties", {}))
        node.pop("default", None)
        for v in node.values(): _strict(v)
    elif isinstance(node, list):
        for v in node: _strict(v)
_strict(SCOPE_RESOLUTION_SCHEMA)
