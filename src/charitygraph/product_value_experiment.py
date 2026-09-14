"""Small, private contracts for the bounded product-value experiment.

These records are deliberately separate from canonical knowledge and public
release models.  They perform no persistence, provider work or promotion.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalObject, Sha256, StrictModel, require_nonblank, utc_datetime


AdjudicationDisposition = Literal[
    "ACCEPT", "ACCEPT_MINOR_CORRECTION", "REJECT_UNSUPPORTED", "REJECT_INCORRECT",
    "REJECT_SCOPE", "REJECT_EPISTEMIC_CLASS", "REJECT_MISSINGNESS",
    "MECHANICALLY_UNRESOLVED", "CRITICAL",
]
CoverageState = Literal[
    "evidence_present", "not_found_in_reviewed_sources", "source_silent", "not_processed",
    "source_unavailable", "not_acquired", "processing_failed", "unknown", "not_applicable",
]


class ExperimentCandidate(StrictModel):
    candidate_id: str
    candidate_content_sha256: Sha256
    subject_id: str
    scope_id: str
    scope_kind: Literal["organisation", "program", "service"]
    source_artifact_id: str
    source_record_id: str
    representation_sha256: Sha256
    retention_decision_id: str
    proposition_type: str
    proposition: CanonicalObject
    evidence_locator_ids: tuple[str, ...]
    source_carrier_role: str
    epistemic_status: str
    reviewed_evidence_universe_id: str
    coverage_state: CoverageState | None = None
    source_period_start: date | None = None
    source_period_end: date | None = None
    candidate_producer_id: str
    provider_request_id: str | None = None

    @field_validator(
        "candidate_id", "subject_id", "scope_id", "proposition_type", "source_carrier_role",
        "source_artifact_id", "source_record_id", "retention_decision_id", "epistemic_status",
        "reviewed_evidence_universe_id", "candidate_producer_id",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @model_validator(mode="after")
    def _evidence_and_period(self) -> "ExperimentCandidate":
        if not self.proposition:
            raise ValueError("candidate proposition must be a nonempty typed payload")
        if len(set(self.evidence_locator_ids)) != len(self.evidence_locator_ids):
            raise ValueError("evidence locator IDs must be unique")
        if self.coverage_state in {"evidence_present", "not_found_in_reviewed_sources", "source_silent"} and not self.reviewed_evidence_universe_id:
            raise ValueError("evidence and reviewed-source missingness require a named reviewed universe")
        if self.coverage_state == "evidence_present" and not self.evidence_locator_ids:
            raise ValueError("positive coverage requires at least one evidence locator")
        if self.source_period_start and self.source_period_end and self.source_period_end < self.source_period_start:
            raise ValueError("source period end cannot precede its start")
        return self


class PropositionAdjudication(StrictModel):
    adjudication_id: str
    candidate_id: str
    candidate_content_sha256: Sha256
    disposition: AdjudicationDisposition
    adjudicator_id: str
    adjudicator_role: Literal["independent_human_proposition_adjudicator"]
    adjudicated_at: datetime
    adjudication_version: str
    rationale: str
    corrected_governed_representation: CanonicalObject | None = None
    corrected_governed_representations: tuple[CanonicalObject, ...] = ()
    reviewer_id: str | None = None
    reviewer_role: Literal["MODEL_ASSISTED_REVIEWER"] | None = None
    independent_of_candidate_producer: bool

    @field_validator("adjudication_id", "candidate_id", "adjudicator_id", "adjudication_version", "rationale")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("adjudicated_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return utc_datetime(value)

    @model_validator(mode="after")
    def _disposition_shape(self) -> "PropositionAdjudication":
        if not self.independent_of_candidate_producer:
            raise ValueError("experiment governance requires independent proposition-level human adjudication")
        if self.reviewer_id is not None:
            require_nonblank(self.reviewer_id, "reviewer_id")
        if self.reviewer_id == self.adjudicator_id:
            raise ValueError("model-assisted reviewer cannot satisfy the human adjudicator role")
        if self.corrected_governed_representation is not None and self.corrected_governed_representations:
            raise ValueError("use either the legacy single corrected representation or the plural form")
        corrections = self.corrected_governed_representations or (
            (self.corrected_governed_representation,) if self.corrected_governed_representation else ()
        )
        if self.disposition == "ACCEPT_MINOR_CORRECTION" and not corrections:
            raise ValueError("minor correction requires a preserved corrected governed representation")
        if self.disposition != "ACCEPT_MINOR_CORRECTION" and corrections:
            raise ValueError("corrected representation is only valid for ACCEPT_MINOR_CORRECTION")
        if any(not correction for correction in corrections):
            raise ValueError("corrected governed representations cannot be empty")
        return self


class ExperimentGovernedItem(StrictModel):
    namespace_id: Literal["product_value_experiment_2026_09_14"]
    item_id: str
    item_kind: Literal["proposition", "coverage_state"]
    candidate_id: str
    candidate_content_sha256: Sha256
    adjudication_id: str
    subject_id: str
    scope_id: str
    scope_kind: Literal["organisation", "program", "service"]
    source_artifact_id: str
    source_record_id: str
    representation_sha256: Sha256
    retention_decision_id: str
    proposition_type: str
    governed_proposition_type: str
    governed_representation: CanonicalObject
    evidence_locator_ids: tuple[str, ...]
    source_carrier_role: str
    epistemic_status: str
    reviewed_evidence_universe_id: str
    coverage_state: CoverageState | None
    source_period_start: date | None
    source_period_end: date | None
    adjudication_disposition: Literal["ACCEPT", "ACCEPT_MINOR_CORRECTION"]
    adjudicator_id: str
    adjudicator_role: Literal["independent_human_proposition_adjudicator"]
    adjudicated_at: datetime
    adjudication_version: str
    corrected_atom_index: int | None = None
    reviewer_id: str | None = None
    reviewer_role: Literal["MODEL_ASSISTED_REVIEWER"] | None = None
    provider_request_id: str | None = None
    canonical_public: Literal[False] = False

    @model_validator(mode="after")
    def _governed_item_shape(self) -> "ExperimentGovernedItem":
        for name in (
            "item_id", "candidate_id", "adjudication_id", "subject_id", "scope_id",
            "source_artifact_id", "source_record_id", "retention_decision_id",
            "proposition_type", "governed_proposition_type", "source_carrier_role", "epistemic_status",
            "reviewed_evidence_universe_id", "adjudicator_id", "adjudication_version",
        ):
            require_nonblank(getattr(self, name), name)
        if not self.governed_representation:
            raise ValueError("governed representation cannot be empty")
        if len(set(self.evidence_locator_ids)) != len(self.evidence_locator_ids):
            raise ValueError("governed evidence locator IDs must be unique")
        if self.coverage_state == "evidence_present" and not self.evidence_locator_ids:
            raise ValueError("positive governed coverage requires an evidence locator")
        if self.adjudication_disposition == "ACCEPT_MINOR_CORRECTION":
            if self.corrected_atom_index is None or self.corrected_atom_index < 1:
                raise ValueError("corrected governed atoms require a positive atom index")
        elif self.corrected_atom_index is not None:
            raise ValueError("only corrected governed atoms may carry an atom index")
        if self.reviewer_id is not None:
            require_nonblank(self.reviewer_id, "reviewer_id")
        if self.reviewer_id == self.adjudicator_id:
            raise ValueError("model-assisted reviewer cannot satisfy the human adjudicator role")
        if self.source_period_start and self.source_period_end and self.source_period_end < self.source_period_start:
            raise ValueError("source period end cannot precede its start")
        return self


def create_experiment_governed_item(
    candidate: ExperimentCandidate, adjudication: PropositionAdjudication
) -> ExperimentGovernedItem | None:
    """Compatibility wrapper for one accepted item; use the plural API for corrections."""
    items = create_experiment_governed_items(candidate, adjudication)
    if not items:
        return None
    if len(items) != 1:
        raise ValueError("adjudication creates multiple atoms; use create_experiment_governed_items")
    return items[0]


def create_experiment_governed_items(
    candidate: ExperimentCandidate, adjudication: PropositionAdjudication
) -> tuple[ExperimentGovernedItem, ...]:
    """Create one or more governed atoms from one exact candidate and human decision."""
    if adjudication.candidate_id != candidate.candidate_id or adjudication.candidate_content_sha256 != candidate.candidate_content_sha256:
        raise ValueError("adjudication must bind the exact immutable candidate identity and hash")
    if adjudication.adjudicator_id == candidate.candidate_producer_id:
        raise ValueError("candidate producer cannot adjudicate their own candidate")
    if adjudication.disposition not in {"ACCEPT", "ACCEPT_MINOR_CORRECTION"}:
        return ()
    if adjudication.disposition == "ACCEPT_MINOR_CORRECTION":
        representations = adjudication.corrected_governed_representations or (
            (adjudication.corrected_governed_representation,)
            if adjudication.corrected_governed_representation else ()
        )
    else:
        representations = (candidate.proposition,)
    kind = "coverage_state" if candidate.coverage_state is not None else "proposition"
    result = []
    for index, representation in enumerate(representations, start=1):
        if representation is None:
            raise ValueError("minor correction requires a preserved corrected governed representation")
        base_item_id = f"expitem:{candidate.candidate_id.removeprefix('candidate:')}"
        atom_index = index if adjudication.disposition == "ACCEPT_MINOR_CORRECTION" else None
        item_id = f"{base_item_id}:atom-{index:02d}" if atom_index is not None else base_item_id
        result.append(ExperimentGovernedItem(
            namespace_id="product_value_experiment_2026_09_14",
            item_id=item_id,
            item_kind=kind,
            candidate_id=candidate.candidate_id,
            candidate_content_sha256=candidate.candidate_content_sha256,
            adjudication_id=adjudication.adjudication_id,
            subject_id=candidate.subject_id,
            scope_id=candidate.scope_id,
            scope_kind=candidate.scope_kind,
            source_artifact_id=candidate.source_artifact_id,
            source_record_id=candidate.source_record_id,
            representation_sha256=candidate.representation_sha256,
            retention_decision_id=candidate.retention_decision_id,
            proposition_type=candidate.proposition_type,
            governed_proposition_type=str(representation.get("proposition_type", candidate.proposition_type)),
            governed_representation=representation,
            evidence_locator_ids=candidate.evidence_locator_ids,
            source_carrier_role=candidate.source_carrier_role,
            epistemic_status=candidate.epistemic_status,
            reviewed_evidence_universe_id=candidate.reviewed_evidence_universe_id,
            coverage_state=candidate.coverage_state,
            source_period_start=candidate.source_period_start,
            source_period_end=candidate.source_period_end,
            adjudication_disposition=adjudication.disposition,
            adjudicator_id=adjudication.adjudicator_id,
            adjudicator_role=adjudication.adjudicator_role,
            adjudicated_at=adjudication.adjudicated_at,
            adjudication_version=adjudication.adjudication_version,
            corrected_atom_index=atom_index,
            reviewer_id=adjudication.reviewer_id,
            reviewer_role=adjudication.reviewer_role,
            provider_request_id=candidate.provider_request_id,
        ))
    return tuple(result)


class ExperimentProjection(StrictModel):
    namespace_id: Literal["product_value_experiment_2026_09_14"]
    items: tuple[ExperimentGovernedItem, ...]

    @model_validator(mode="after")
    def _private_items_only(self) -> "ExperimentProjection":
        if any(item.namespace_id != self.namespace_id or item.canonical_public for item in self.items):
            raise ValueError("projection can contain only private items from its experiment namespace")
        return self


def project_experiment_items(items: tuple[ExperimentGovernedItem, ...]) -> ExperimentProjection:
    """Projection accepts governed items only; raw candidates are not an input type."""
    return ExperimentProjection(namespace_id="product_value_experiment_2026_09_14", items=items)


def verify_candidate_bytes(candidate: ExperimentCandidate, exact_candidate_bytes: bytes) -> None:
    """Bind the typed candidate to the immutable, exact candidate artifact bytes."""
    if sha256(exact_candidate_bytes).hexdigest() != candidate.candidate_content_sha256:
        raise ValueError("candidate bytes do not match the immutable candidate content hash")
