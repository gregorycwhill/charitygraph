"""Artifact-bound source-rights decisions for private provider processing.

This is deliberately a small gate, not a legal expert system.  A decision is
made outside the runner under a named policy, bound to one exact transmitted
representation, and retained with the evidence that supports it.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, StrictInt, model_validator

from .contracts.common import Sha256, StrictModel, require_nonblank


RightsBasis = Literal[
    "explicit_open_license", "explicit_terms_permission", "direct_permission",
    "statutory_exception", "public_facts_only", "public_source_private_processing",
    "unknown", "prohibited",
]
RepresentationClass = Literal[
    "bounded_excerpt", "structured_factual", "complete_or_near_complete_work", "unclear",
]
FAIR_DEALING_POLICY_ID = "AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1"
PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID = "CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1"
OPENAI_PROVIDER_POLICY_ID = "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1"
PUBLIC_FACTS_ONLY_POLICY_ID = "PUBLIC_FACTS_ONLY_V1"
RIGHTS_POLICY_REGISTRY = {
    FAIR_DEALING_POLICY_ID: {
        "version": "1.0.0",
        "basis": "statutory_exception",
        "scope": "bounded private analytical processing of lawfully accessible public material",
        "public_redistribution": False,
        "complete_or_near_complete_work": False,
    },
    PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID: {
        "version": "1.0.0",
        "basis": "public_source_private_processing",
        "scope": "full or partial governed public PDF/XLSX material for private analytical processing",
        "public_redistribution": False,
        "complete_or_near_complete_work": True,
        "payload_caps_are_rights_conditions": False,
    },
    "CC_BY_3_0_AU_V1": {"version": "1.0.0", "basis": "explicit_open_license"},
    "CC_BY_4_0_V1": {"version": "1.0.0", "basis": "explicit_open_license"},
    PUBLIC_FACTS_ONLY_POLICY_ID: {"version": "1.0.0", "basis": "public_facts_only"},
}
_ANALYTICAL_PURPOSES = {
    "charitygraph_research", "semantic_analysis", "classification", "extraction",
    "evaluation", "evidence_grounded_knowledge_construction",
}


def governed_rights_policy(
    policy_id: str,
    policy_version: str | None,
    *,
    rights_basis: str | None = None,
) -> dict[str, object] | None:
    """Resolve one exact, in-repository governed rights-policy identity."""
    policy = RIGHTS_POLICY_REGISTRY.get(policy_id)
    if policy is None or policy.get("version") != policy_version:
        return None
    if rights_basis is not None and policy.get("basis") != rights_basis:
        return None
    return policy


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
    decision_version: str = "1"
    representation_artifact_id: str | None = None
    rights_policy_version: str | None = None
    provider_processing_policy_version: str | None = None
    assessment_authority: str | None = None
    expires_on: date | None = None
    status: Literal["authorized", "blocked", "revoked", "superseded"] = "authorized"
    supersedes_decision_id: str | None = None

    @model_validator(mode="after")
    def _fail_closed(self) -> "ArtifactRightsDecision":
        for field in ("decision_id", "source_artifact_id", "source_record_id", "source_origin_url", "source_role", "rights_policy_id", "provider_processing_policy_id", "evidence_locator", "assessment_scope"):
            require_nonblank(str(getattr(self, field)), field)
        for field in (
            "decision_version", "representation_artifact_id", "rights_policy_version",
            "provider_processing_policy_version", "assessment_authority",
            "supersedes_decision_id",
        ):
            value = getattr(self, field)
            if value is not None:
                require_nonblank(str(value), field)
        if not self.acquisition_lineage_ids or any(not item.strip() for item in self.acquisition_lineage_ids):
            raise ValueError("provider rights require acquisition lineage")
        if self.rights_basis in {"unknown", "prohibited"} and self.provider_transmission_allowed:
            raise ValueError("this rights basis cannot authorize provider transmission")
        if self.provider_transmission_allowed and self.status != "authorized":
            raise ValueError("non-authorized decision status cannot authorize provider transmission")
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
        if self.rights_basis == "public_source_private_processing" and self.provider_transmission_allowed:
            required = (
                self.rights_policy_id == PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
                self.provider_processing_policy_id == OPENAI_PROVIDER_POLICY_ID,
                self.provider_no_training_default,
                self.provider_data_sharing_opt_in is False,
                self.publicly_accessible_without_circumvention is True,
                self.access_controls_bypassed is False,
                self.lawfully_acquired is True,
                self.analytical_purpose in _ANALYTICAL_PURPOSES,
                self.representation_class in {"bounded_excerpt", "structured_factual", "complete_or_near_complete_work"},
                not self.explicit_prohibition_found,
            )
            if not all(required):
                raise ValueError("public-source private-provider predicates are not all satisfied")
        if self.provider_transmission_allowed and self.rights_basis not in {
            "explicit_open_license", "explicit_terms_permission", "direct_permission", "public_facts_only", "statutory_exception", "public_source_private_processing",
        }:
            raise ValueError("provider transmission requires an affirmative rights basis")
        return self


# Local analytical retention is a separate, versioned decision.  Keeping it
# separate from ArtifactRightsDecision preserves V1.0's frozen meaning and
# makes it impossible to infer retention from provider permission.
LOCAL_RETENTION_POLICY_ID = "CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1"
LOCAL_RETENTION_POLICY_VERSION = "1.0.0"


class BoundedLocalRetentionDecision(StrictModel):
    """Fail-closed, exact-representation authorization for private retention."""

    decision_id: str
    source_artifact_id: str
    source_record_id: str
    source_role: str
    acquisition_lineage_ids: tuple[str, ...]
    representation_sha256: Sha256
    rights_policy_id: str = LOCAL_RETENTION_POLICY_ID
    rights_policy_version: str = LOCAL_RETENTION_POLICY_VERSION
    rights_basis: Literal["statutory_exception", "explicit_open_license", "explicit_terms_permission", "direct_permission"]
    representation_class: Literal["bounded_excerpt", "structured_factual"]
    purpose: Literal[
        "research", "semantic_analysis", "adjudication", "provenance",
        "governed_evidence_construction", "bounded_experiment_reproducibility",
        "governed_proposition_audit",
    ]
    scope: str
    selected_page_count: StrictInt | None = None
    source_page_count: StrictInt | None = None
    one_source_native_entity_record: bool = False
    lawful_access_confirmed: bool
    circumvention_used: bool
    explicit_prohibition_found: bool
    retention_status: Literal["authorized", "blocked", "unknown"]
    lifecycle_status: Literal["active_until_review", "review_due", "deleted", "blocked"]
    review_due_on: date
    provider_transmission_decision_id: str | None = None
    provider_transmission_status: Literal["authorized", "blocked", "unknown", "not_assessed"]
    public_redistribution_status: Literal["not_authorized", "authorized_under_separate_basis"] = "not_authorized"
    public_redistribution_decision_id: str | None = None

    @model_validator(mode="after")
    def _fail_closed(self) -> "BoundedLocalRetentionDecision":
        for name in ("decision_id", "source_artifact_id", "source_record_id", "source_role", "scope"):
            require_nonblank(getattr(self, name), name)
        if not self.acquisition_lineage_ids or any(not item.strip() for item in self.acquisition_lineage_ids):
            raise ValueError("local retention requires recorded acquisition lineage")
        if self.rights_policy_id != LOCAL_RETENTION_POLICY_ID or self.rights_policy_version != LOCAL_RETENTION_POLICY_VERSION:
            raise ValueError("local retention requires the approved, versioned CharityGraph policy")
        if self.retention_status == "authorized":
            if not self.lawful_access_confirmed or self.circumvention_used or self.explicit_prohibition_found:
                raise ValueError("retention authorization requires lawful access, no circumvention, and no explicit prohibition")
            if self.lifecycle_status not in {"active_until_review", "review_due"}:
                raise ValueError("authorized retention requires an auditable active review lifecycle")
            if self.representation_class == "bounded_excerpt":
                if (
                    self.selected_page_count is None or self.source_page_count is None
                    or self.selected_page_count < 1 or self.selected_page_count > 5
                    or self.source_page_count < 1
                    or self.selected_page_count / self.source_page_count > 0.20
                ):
                    raise ValueError("bounded report retention must be at most five selected pages and 20 percent of the source")
            elif not self.one_source_native_entity_record:
                raise ValueError("structured factual retention is limited to one source-native entity record")
        if self.provider_transmission_status == "authorized" and not self.provider_transmission_decision_id:
            raise ValueError("provider authorization requires its separate provider-rights decision ID")
        if self.provider_transmission_status != "authorized" and self.provider_transmission_decision_id:
            raise ValueError("provider decision ID may appear only when provider transmission is separately authorized")
        if self.public_redistribution_status == "authorized_under_separate_basis" and not self.public_redistribution_decision_id:
            raise ValueError("public redistribution requires its own separate rights decision ID")
        if self.public_redistribution_status == "not_authorized" and self.public_redistribution_decision_id:
            raise ValueError("public rights decision ID is valid only when separate redistribution is authorized")
        return self


def require_provider_rights(
    decisions: list[ArtifactRightsDecision],
    sources: list[dict],
    *,
    planned_processing_at: date | None = None,
) -> list[str]:
    """Return deterministic blockers for the exact frozen source representations."""
    by_pair = {}
    for item in decisions:
        key = (
            item.source_artifact_id,
            item.representation_artifact_id,
            str(item.transmitted_representation_sha256),
        )
        if key in by_pair:
            raise ValueError("duplicate artifact/representation rights decisions are ambiguous")
        by_pair[key] = item
    blockers: list[str] = []
    for source in sources:
        artifact_id = source.get("source_artifact_id") or source.get("artifact_id") or source.get("source_record_id")
        representation = source.get("exact_transmitted_representation")
        representation_hash = source.get("transmitted_representation_sha256")
        if representation_hash is None and isinstance(representation, str):
            import hashlib
            representation_hash = hashlib.sha256(representation.encode("utf-8")).hexdigest()
        if not isinstance(artifact_id, str) or not isinstance(representation_hash, str):
            blockers.append("source identity or frozen representation is absent")
            continue
        representation_artifact_id = source.get("representation_artifact_id")
        decision = by_pair.get((artifact_id, representation_artifact_id, representation_hash))
        if decision is None and representation_artifact_id is None:
            decision = by_pair.get((artifact_id, None, representation_hash))
        if decision is None:
            blockers.append(f"{artifact_id}: no artifact-bound rights decision")
        elif (
            decision.source_record_id != source.get("source_record_id")
            or decision.source_origin_url != source.get("source_locator", source.get("source_origin_url"))
            or decision.source_role != source.get("source_role")
            or not decision.acquisition_lineage_ids
            or source.get("acquisition_lineage_ids") is not None
            and set(decision.acquisition_lineage_ids) != set(source.get("acquisition_lineage_ids") or ())
            or source.get("rights_policy_id") is not None
            and decision.rights_policy_id != source.get("rights_policy_id")
            or source.get("rights_policy_version") is not None
            and decision.rights_policy_version != source.get("rights_policy_version")
            or source.get("provider_processing_policy_id") is not None
            and decision.provider_processing_policy_id != source.get("provider_processing_policy_id")
            or source.get("provider_processing_policy_version") is not None
            and decision.provider_processing_policy_version != source.get("provider_processing_policy_version")
        ):
            blockers.append(f"{artifact_id}: source identity, role, origin, or acquisition lineage mismatch")
        elif decision.status in {"blocked", "revoked", "superseded"} or not decision.provider_transmission_allowed:
            blockers.append(f"{artifact_id}: provider transmission is not permitted")
        elif decision.expires_on is not None and planned_processing_at is not None and planned_processing_at > decision.expires_on:
            blockers.append(f"{artifact_id}: provider rights decision is expired")
        elif governed_rights_policy(
            decision.rights_policy_id,
            decision.rights_policy_version,
            rights_basis=decision.rights_basis,
        ) is None:
            blockers.append(f"{artifact_id}: rights policy identity is unknown or version-mismatched")
        elif decision.provider_transmission_allowed and (
            not decision.representation_artifact_id
            or not decision.rights_policy_version
            or not decision.provider_processing_policy_version
            or not decision.assessment_authority
        ):
            blockers.append(f"{artifact_id}: provider rights decision lacks durable version/authority binding")
    return blockers
