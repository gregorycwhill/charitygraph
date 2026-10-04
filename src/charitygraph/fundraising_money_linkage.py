"""Evidence-bound links between fundraising money facts and activity scopes.

This contract is intentionally an attachment layer over
``FundraisingMoneyMeasurement``.  A measurement's reporting entity is not
silently converted into a campaign, practice, appeal, or provider amount.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .finance_measurement import (
    CompatibilityDecision,
    FundraisingMoneyMeasurement,
    decide_addition_compatibility,
)


LINKAGE_CONTRACT_VERSION = "1.0"
AttributedScopeKind = Literal[
    "organisation", "fundraising_portfolio", "practice", "campaign", "appeal",
    "provider_relationship",
]
LinkageStatus = Literal["explicit", "unknown"]


class FundraisingMoneyScopeLink(BaseModel):
    """The smallest source-supported scope for a single money measurement.

    ``unknown`` retains a financial fact without pretending that proximity to a
    practice or campaign establishes attribution.  It is anchored to the
    reporting organisation only so it remains discoverable without a guessed
    downstream target.
    """

    measurement: FundraisingMoneyMeasurement
    linkage_status: LinkageStatus
    attributed_scope_kind: AttributedScopeKind = "organisation"
    attributed_scope_id: str | None = None
    reporting_entity_causebase_id: str | None = None
    linkage_evidence_ids: list[str] = Field(default_factory=list)
    linkage_source_wording: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def enforce_evidenced_smallest_scope(self):
        reporting_entity = self.reporting_entity_causebase_id or self.measurement.reporting_subject_causebase_id
        if self.measurement.reporting_scope == "subject" and not reporting_entity:
            raise ValueError("subject measurement requires reporting entity identity")
        if self.linkage_status == "unknown":
            if self.attributed_scope_kind != "organisation" or self.attributed_scope_id is not None:
                raise ValueError("unknown linkage must remain at organisation level")
            if self.linkage_evidence_ids or self.linkage_source_wording:
                raise ValueError("unknown linkage cannot carry attribution evidence")
        else:
            if not self.linkage_evidence_ids or not self.linkage_source_wording:
                raise ValueError("explicit linkage requires evidence IDs and source wording")
            if self.attributed_scope_kind == "organisation":
                if self.attributed_scope_id is not None:
                    raise ValueError("organisation linkage uses reporting entity, not a separate scope ID")
            elif not self.attributed_scope_id:
                raise ValueError("non-organisation linkage requires attributed_scope_id")
        # A scope link can narrow a measurement to a campaign or practice, but
        # it cannot change who reported a subject-scoped measurement.  Without
        # this check a caller could attach an otherwise valid campaign link to
        # a same-named or same-domain charity by supplying a different
        # ``reporting_entity_causebase_id``.
        if self.measurement.reporting_scope == "subject":
            if reporting_entity != self.measurement.reporting_subject_causebase_id:
                raise ValueError("scope linkage must retain the measurement reporting entity")
        return self


class LinkedAdditionDecision(BaseModel):
    contract_version: str = LINKAGE_CONTRACT_VERSION
    status: Literal["compatible", "incompatible"]
    reasons: list[str] = Field(default_factory=list)
    measurement_decision: CompatibilityDecision

    @property
    def safe_to_add(self) -> bool:
        return self.status == "compatible"


def decide_linked_addition_compatibility(
    left: FundraisingMoneyScopeLink, right: FundraisingMoneyScopeLink
) -> LinkedAdditionDecision:
    """Allow addition only inside the exact same explicitly attributed scope."""
    measurement_decision = decide_addition_compatibility(left.measurement, right.measurement)
    reasons = list(measurement_decision.reasons)
    if left.linkage_status != "explicit" or right.linkage_status != "explicit":
        reasons.append("linkage_not_explicit")
    if left.attributed_scope_kind != right.attributed_scope_kind:
        reasons.append("different_attributed_scope_kind")
    if left.attributed_scope_id != right.attributed_scope_id:
        reasons.append("different_attributed_scope")
    if left.reporting_entity_causebase_id != right.reporting_entity_causebase_id:
        reasons.append("different_reporting_entity")
    return LinkedAdditionDecision(
        status="compatible" if not reasons else "incompatible",
        reasons=list(dict.fromkeys(reasons)),
        measurement_decision=measurement_decision,
    )
