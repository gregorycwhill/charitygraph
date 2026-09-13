"""Artifact-bound source-rights decisions for private provider processing.

This is deliberately a small gate, not a legal expert system.  A decision is
made outside the runner under a named policy, bound to one exact transmitted
representation, and retained with the evidence that supports it.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .contracts.common import Sha256, StrictModel, require_nonblank


RightsBasis = Literal[
    "explicit_open_license", "explicit_terms_permission", "direct_permission",
    "statutory_exception", "public_facts_only", "unknown", "prohibited",
]


class ArtifactRightsDecision(StrictModel):
    """One append-only decision for a source artefact and its sent rendering."""

    decision_id: str
    source_artifact_id: str
    transmitted_representation_sha256: Sha256
    rights_policy_id: str
    provider_processing_policy_id: str
    rights_basis: RightsBasis
    evidence_locator: str
    evidence_sha256: Sha256
    assessed_on: date
    assessment_scope: str
    attribution: str | None = None
    licence_identifier: str | None = None
    licence_or_terms_url: str | None = None
    restrictions: str | None = None
    assessment_notes: str | None = None
    local_retention_allowed: bool
    provider_transmission_allowed: bool
    public_redistribution_allowed: bool
    factual_representation_only: bool = False

    @model_validator(mode="after")
    def _fail_closed(self) -> "ArtifactRightsDecision":
        for field in ("decision_id", "source_artifact_id", "rights_policy_id", "provider_processing_policy_id", "evidence_locator", "assessment_scope"):
            require_nonblank(str(getattr(self, field)), field)
        if self.rights_basis in {"unknown", "prohibited", "statutory_exception"} and self.provider_transmission_allowed:
            raise ValueError("this rights basis cannot authorize provider transmission")
        if self.rights_basis == "public_facts_only" and self.provider_transmission_allowed and not self.factual_representation_only:
            raise ValueError("public_facts_only requires an explicitly factual transmitted representation")
        if self.provider_transmission_allowed and self.rights_basis not in {
            "explicit_open_license", "explicit_terms_permission", "direct_permission", "public_facts_only",
        }:
            raise ValueError("provider transmission requires an affirmative rights basis")
        return self


def require_provider_rights(decisions: list[ArtifactRightsDecision], sources: list[dict]) -> list[str]:
    """Return deterministic blockers for the exact frozen source representations."""
    by_pair = {(item.source_artifact_id, str(item.transmitted_representation_sha256)): item for item in decisions}
    blockers: list[str] = []
    for source in sources:
        artifact_id = source.get("source_artifact_id") or source.get("artifact_id") or source.get("source_record_id")
        representation = source.get("exact_transmitted_representation")
        if not isinstance(artifact_id, str) or not isinstance(representation, str):
            blockers.append("source identity or frozen representation is absent")
            continue
        import hashlib
        decision = by_pair.get((artifact_id, hashlib.sha256(representation.encode("utf-8")).hexdigest()))
        if decision is None:
            blockers.append(f"{artifact_id}: no artifact-bound rights decision")
        elif not decision.provider_transmission_allowed:
            blockers.append(f"{artifact_id}: provider transmission is not permitted")
    return blockers
