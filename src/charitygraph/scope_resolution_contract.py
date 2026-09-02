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
    evidence_refs: tuple[str, ...] = ()

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
