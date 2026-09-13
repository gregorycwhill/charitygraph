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
RepresentationClass = Literal[
    "bounded_excerpt", "structured_factual", "complete_or_near_complete_work", "unclear",
]
FAIR_DEALING_POLICY_ID = "AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1"
OPENAI_PROVIDER_POLICY_ID = "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1"
RIGHTS_POLICY_REGISTRY = {
    FAIR_DEALING_POLICY_ID: {
        "version": "1.0.0",
        "basis": "statutory_exception",
        "scope": "bounded private analytical processing of lawfully accessible public material",
        "public_redistribution": False,
        "complete_or_near_complete_work": False,
    },
    "CC_BY_3_0_AU_V1": {"version": "1.0.0", "basis": "explicit_open_license"},
    "CC_BY_4_0_V1": {"version": "1.0.0", "basis": "explicit_open_license"},
    "PUBLIC_FACTS_ONLY_V1": {"version": "1.0.0", "basis": "public_facts_only"},
}
_ANALYTICAL_PURPOSES = {
    "charitygraph_research", "semantic_analysis", "classification", "extraction",
    "evaluation", "evidence_grounded_knowledge_construction",
}


class ArtifactRightsDecision(StrictModel):
    """One append-only decision for a source artefact and its sent rendering."""

    decision_id: str
    source_artifact_id: str
    source_record_id: str
    source_origin_url: str
    source_role: str
    acquisition_lineage_ids: tuple[str, ...]
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
    representation_class: RepresentationClass = "unclear"
    publicly_accessible_without_circumvention: bool | None = None
    access_controls_bypassed: bool | None = None
    lawfully_acquired: bool | None = None
    analytical_purpose: str | None = None
    explicit_prohibition_found: bool = False
    provider_no_training_default: bool = False
    provider_data_sharing_opt_in: bool | None = None

    @model_validator(mode="after")
    def _fail_closed(self) -> "ArtifactRightsDecision":
        for field in ("decision_id", "source_artifact_id", "source_record_id", "source_origin_url", "source_role", "rights_policy_id", "provider_processing_policy_id", "evidence_locator", "assessment_scope"):
            require_nonblank(str(getattr(self, field)), field)
        if not self.acquisition_lineage_ids or any(not item.strip() for item in self.acquisition_lineage_ids):
            raise ValueError("provider rights require acquisition lineage")
        if self.rights_basis in {"unknown", "prohibited"} and self.provider_transmission_allowed:
            raise ValueError("this rights basis cannot authorize provider transmission")
        if self.explicit_prohibition_found and self.provider_transmission_allowed:
            raise ValueError("explicit prohibitory terms block provider transmission")
        if self.rights_basis == "public_facts_only" and self.provider_transmission_allowed:
            if (
                RIGHTS_POLICY_REGISTRY.get(self.rights_policy_id, {}).get("basis") != "public_facts_only"
                or not self.factual_representation_only
                or self.representation_class != "structured_factual"
            ):
                raise ValueError("public_facts_only requires an explicitly factual structured representation")
        if self.rights_basis == "explicit_open_license" and self.provider_transmission_allowed:
            policy = RIGHTS_POLICY_REGISTRY.get(self.rights_policy_id)
            if policy is None or policy.get("basis") != "explicit_open_license" or not self.licence_identifier or not self.licence_or_terms_url:
                raise ValueError("explicit open licence requires a matching versioned policy and licence evidence")
        if self.rights_policy_id == FAIR_DEALING_POLICY_ID:
            if self.public_redistribution_allowed:
                raise ValueError("Fair Dealing V1 does not authorize redistribution")
            if self.local_retention_allowed:
                raise ValueError("Fair Dealing V1 does not authorize local retention")
        if self.rights_basis == "statutory_exception" and self.provider_transmission_allowed:
            required = (
                self.rights_policy_id == FAIR_DEALING_POLICY_ID,
                self.provider_processing_policy_id == OPENAI_PROVIDER_POLICY_ID,
                self.provider_no_training_default,
                self.provider_data_sharing_opt_in is False,
                self.publicly_accessible_without_circumvention is True,
                self.access_controls_bypassed is False,
                self.lawfully_acquired is True,
                self.analytical_purpose in _ANALYTICAL_PURPOSES,
                self.representation_class in {"bounded_excerpt", "structured_factual"},
                not self.explicit_prohibition_found,
            )
            if not all(required):
                raise ValueError("Fair Dealing V1 predicates are not all satisfied")
        if self.provider_transmission_allowed and self.rights_basis not in {
            "explicit_open_license", "explicit_terms_permission", "direct_permission", "public_facts_only", "statutory_exception",
        }:
            raise ValueError("provider transmission requires an affirmative rights basis")
        return self


def require_provider_rights(decisions: list[ArtifactRightsDecision], sources: list[dict]) -> list[str]:
    """Return deterministic blockers for the exact frozen source representations."""
    by_pair = {}
    for item in decisions:
        key = (item.source_artifact_id, str(item.transmitted_representation_sha256))
        if key in by_pair:
            raise ValueError("duplicate artifact/representation rights decisions are ambiguous")
        by_pair[key] = item
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
        elif (
            decision.source_record_id != source.get("source_record_id")
            or decision.source_origin_url != source.get("source_locator")
            or decision.source_role != source.get("source_role")
            or not decision.acquisition_lineage_ids
        ):
            blockers.append(f"{artifact_id}: source identity, role, origin, or acquisition lineage mismatch")
        elif not decision.provider_transmission_allowed:
            blockers.append(f"{artifact_id}: provider transmission is not permitted")
    return blockers
