"""Evidence-bounded, multi-period history for a fundraising method.

This module receives already-governed structured observations.  It does not
read source prose, infer a method, or turn elapsed time into an expiry rule.
Its job is deliberately smaller: retain the full dated sequence, say when a
method was last evidenced, and route conflicting source assertions to review.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fundraising_evidence_roles import EvidenceScope, FundraisingEvidence


MethodStatus = Literal[
    "current", "recent", "historical", "discontinued", "unknown",
    "not_found_in_scoped_source",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MethodHistoryInput(_Strict):
    """One source-native temporal assertion about one canonical method.

    ``evidence`` remains the provenance authority. ``status`` is supplied by
    the applicable source adapter or governed semantic process, never guessed
    from the age of ``observed_at``.  A cessation date is retained as an end
    marker; it does not erase earlier observations.
    """

    method_id: str = Field(min_length=1)
    evidence: FundraisingEvidence
    status: MethodStatus = "unknown"
    cessation_date: date | None = None

    @model_validator(mode="after")
    def status_has_supported_shape(self):
        if self.status == "not_found_in_scoped_source":
            if self.evidence.coverage != "not_found_in_scoped_source":
                raise ValueError("scoped non-finding status requires scoped non-finding coverage")
        elif self.evidence.coverage != "observed":
            raise ValueError("a method status other than scoped non-finding requires observed coverage")
        if self.status in {"current", "recent", "discontinued"} and "currentness" not in self.evidence.asserted_facets:
            raise ValueError("current, recent and discontinued statuses require a currentness facet")
        if self.status == "discontinued" and self.cessation_date is None:
            raise ValueError("discontinued status requires an explicit cessation_date")
        if self.cessation_date and self.cessation_date < self.evidence.observed_at and self.status != "discontinued":
            raise ValueError("only a discontinuation observation may carry an earlier cessation_date")
        return self


class MethodHistoryEvent(_Strict):
    method_id: str
    evidence_id: str
    source_id: str
    source_role: str
    locator: str
    source_wording: str
    subject_binding: str
    binding_basis: str
    observed_at: date
    valid_from: date | None = None
    valid_to: date | None = None
    cessation_date: date | None = None
    scope: EvidenceScope
    production_method: str
    review_status: str
    coverage: str
    coverage_description: str | None = None
    status: MethodStatus
    practice_observed: bool | None


class MethodHistoryContradiction(_Strict):
    first_evidence_id: str
    second_evidence_id: str
    reason: str


class FundraisingMethodHistory(_Strict):
    """A review projection, not a timeless status assertion."""

    contract_version: Literal["fundraising-method-history-v1-review"] = "fundraising-method-history-v1-review"
    method_id: str
    scope: EvidenceScope
    events: tuple[MethodHistoryEvent, ...] = Field(min_length=1)
    last_evidenced_at: date | None = None
    last_evidenced_event_id: str | None = None
    explicit_cessation_dates: tuple[date, ...] = ()
    contradictions: tuple[MethodHistoryContradiction, ...] = ()
    review_required: bool
    summary_basis: str


def _scope_key(scope: EvidenceScope) -> tuple[object, ...]:
    return (scope.kind, scope.identifier, scope.geography, scope.description)


def _event(item: MethodHistoryInput) -> MethodHistoryEvent:
    evidence = item.evidence
    return MethodHistoryEvent(
        method_id=item.method_id, evidence_id=evidence.evidence_id, source_id=evidence.source_id,
        source_role=evidence.source_role, locator=evidence.locator, source_wording=evidence.source_wording,
        subject_binding=evidence.subject_binding, binding_basis=evidence.binding_basis,
        observed_at=evidence.observed_at, valid_from=evidence.valid_from, valid_to=evidence.valid_to,
        cessation_date=item.cessation_date, scope=evidence.scope, production_method=evidence.production_method,
        review_status=evidence.review_status, coverage=evidence.coverage,
        coverage_description=evidence.coverage_description, status=item.status,
        practice_observed=True if item.status in {"current", "recent", "historical", "discontinued"}
        and evidence.subject_binding == "confirmed" else None,
    )


def _contradictions(events: tuple[MethodHistoryEvent, ...]) -> tuple[MethodHistoryContradiction, ...]:
    """Find direct post-cessation conflicts without deciding which source wins."""
    found: list[MethodHistoryContradiction] = []
    cessations = [event for event in events if event.status == "discontinued" and event.cessation_date]
    for cessation in cessations:
        for event in events:
            if event.evidence_id == cessation.evidence_id or event.status not in {"current", "recent"}:
                continue
            # A source assertion of current/recent practice observed or stated
            # as valid after an explicit cessation is a review conflict.  No
            # reverse inference is made when the dates do not establish this.
            asserted_after = event.valid_from or event.observed_at
            if asserted_after >= cessation.cessation_date:
                found.append(MethodHistoryContradiction(
                    first_evidence_id=cessation.evidence_id, second_evidence_id=event.evidence_id,
                    reason="current/recent source assertion is dated on or after an explicit cessation date",
                ))
    return tuple(sorted(found, key=lambda value: (value.first_evidence_id, value.second_evidence_id)))


def compile_fundraising_method_histories(
    inputs: tuple[MethodHistoryInput, ...],
) -> tuple[FundraisingMethodHistory, ...]:
    """Compile repeated observations by exact method and scope.

    The returned ``last_evidenced_*`` fields are provenance facts only.  They
    never imply that a method is still active, stale, or discontinued.
    """
    if len({item.evidence.evidence_id for item in inputs}) != len(inputs):
        raise ValueError("history evidence IDs must be unique")
    grouped: dict[tuple[object, ...], list[MethodHistoryEvent]] = {}
    for item in inputs:
        key = (item.method_id, *_scope_key(item.evidence.scope))
        grouped.setdefault(key, []).append(_event(item))

    histories: list[FundraisingMethodHistory] = []
    for key, raw_events in sorted(grouped.items(), key=lambda pair: str(pair[0])):
        events = tuple(sorted(raw_events, key=lambda event: (event.observed_at, event.evidence_id)))
        observed = [event for event in events if event.practice_observed is True]
        latest = max(observed, key=lambda event: (event.observed_at, event.evidence_id)) if observed else None
        contradictions = _contradictions(events)
        histories.append(FundraisingMethodHistory(
            method_id=key[0], scope=events[0].scope, events=events,
            last_evidenced_at=latest.observed_at if latest else None,
            last_evidenced_event_id=latest.evidence_id if latest else None,
            explicit_cessation_dates=tuple(sorted({event.cessation_date for event in events if event.cessation_date})),
            contradictions=contradictions, review_required=bool(contradictions),
            summary_basis="last evidenced is the latest confirmed positive source observation; no freshness or continuity is inferred",
        ))
    return tuple(histories)
