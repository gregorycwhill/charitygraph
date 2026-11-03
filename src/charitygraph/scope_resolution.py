"""Independent, evidence-led scope resolution for Compact atoms.

Producer scope fields are hints only.  This module never infers scope from
free-text; callers provide structured evidence candidates when a lower scope
is defensible.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

ScopeKind = Literal["subject", "named_program_or_service", "other_named_scope", "reporting_group", "uncertain"]

@dataclass(frozen=True)
class ScopeResolution:
    resolved_scope_kind: ScopeKind
    resolved_scope_label: str | None
    scope_status: Literal["resolved", "uncertain"]
    evidence_refs: tuple[str, ...] = ()

def resolve_scope(*, producer_scope_kind: str, producer_scope_label: str | None,
                  evidence_refs: tuple[str, ...] = (),
                  evidenced_scope_kind: ScopeKind | None = None,
                  evidenced_scope_label: str | None = None) -> ScopeResolution:
    """Resolve from structured caller evidence, never from proposition text.

    Without an explicit structured scope assertion, organisation-wide or
    generic material remains subject scope; a labelled producer hint alone is
    intentionally not enough to create a durable child scope.
    """
    if evidenced_scope_kind is not None:
        label = evidenced_scope_label or producer_scope_label
        if evidenced_scope_kind != "subject" and not label:
            return ScopeResolution("uncertain", None, "uncertain", evidence_refs)
        return ScopeResolution(evidenced_scope_kind, label if evidenced_scope_kind != "subject" else None, "resolved", evidence_refs)
    if producer_scope_kind == "subject" or not producer_scope_label:
        return ScopeResolution("subject", None, "resolved", evidence_refs)
    return ScopeResolution("uncertain", None, "uncertain", evidence_refs)
