"""Private, read-only composition of the Gate 4 E2B answer projection.

This module does not read the manifest, source representations, catalogue, or
runtime state.  It consumes the already validated E2B ``AnswerProjection``
and composes a comparison-friendly derivative while retaining the E2B answer
records as the citation-bearing source of truth for this derivative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .phase5_t4b_source_answer_projection import (
    AnswerProjection,
    AnswerRecord,
    QUESTION_ACTIVITY,
    QUESTION_CURRENTNESS,
    QUESTION_SCALE,
)


class BriefCompositionError(ValueError):
    """Raised when an E2B projection is not safe to compose."""


@dataclass(frozen=True)
class CitedValue:
    """A mechanically selected or counted value with its complete citation."""

    value: Any
    subject_id: str
    scope_id: str
    source_family: str
    source_record_id: str
    representation_sha256: str
    source_date: str | None
    reporting_period: Mapping[str, str] | None
    fact_vs_source_statement_vs_inference: str
    field_basis: tuple[str, ...]

    @classmethod
    def from_record(cls, record: AnswerRecord, value: Any, field_basis: Sequence[str]) -> "CitedValue":
        if not field_basis or not set(field_basis).issubset(set(record.field_basis)):
            raise BriefCompositionError("derived value uses a field basis absent from its E2B record")
        return cls(
            value=value,
            subject_id=record.subject_id,
            scope_id=record.scope_id,
            source_family=record.source_family,
            source_record_id=record.source_record_id,
            representation_sha256=record.representation_sha256,
            source_date=record.source_date,
            reporting_period=None if record.reporting_period is None else dict(record.reporting_period),
            fact_vs_source_statement_vs_inference=record.fact_vs_source_statement_vs_inference,
            field_basis=tuple(field_basis),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "source_record_id": self.source_record_id,
            "representation_sha256": self.representation_sha256,
            "source_date": self.source_date,
            "reporting_period": None if self.reporting_period is None else dict(self.reporting_period),
            "fact_vs_source_statement_vs_inference": self.fact_vs_source_statement_vs_inference,
            "field_basis": list(self.field_basis),
        }


@dataclass(frozen=True)
class ComparisonRow:
    """One subject's mechanically comparable, source-native measures."""

    subject_id: str
    scope_id: str
    display_name: str
    program_count: CitedValue
    operating_in_states: CitedValue
    countries: CitedValue
    beneficiaries: CitedValue
    reporting_period: CitedValue
    accounting_basis: CitedValue
    receipts: CitedValue
    expenses: CitedValue
    net_surplus_deficit: CitedValue
    full_time_employees: CitedValue
    part_time_employees: CitedValue
    casual_employees: CitedValue
    unpaid_volunteers: CitedValue

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "display_name": self.display_name,
            "program_count": self.program_count.as_dict(),
            "operating_in_states": self.operating_in_states.as_dict(),
            "countries": self.countries.as_dict(),
            "beneficiaries": self.beneficiaries.as_dict(),
            "reporting_period": self.reporting_period.as_dict(),
            "accounting_basis": self.accounting_basis.as_dict(),
            "receipts": self.receipts.as_dict(),
            "expenses": self.expenses.as_dict(),
            "net_surplus_deficit": self.net_surplus_deficit.as_dict(),
            "full_time_employees": self.full_time_employees.as_dict(),
            "part_time_employees": self.part_time_employees.as_dict(),
            "casual_employees": self.casual_employees.as_dict(),
            "unpaid_volunteers": self.unpaid_volunteers.as_dict(),
        }


@dataclass(frozen=True)
class NorthStarCoverage:
    """Coverage metadata, deliberately separate from answer knowledge."""

    section_id: int
    title: str
    code: str
    status: str
    status_by_subject: Mapping[str, str]
    basis: str
    missingness: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "code": self.code,
            "status": self.status,
            "status_by_subject": dict(self.status_by_subject),
            "basis": self.basis,
            "missingness": list(self.missingness),
        }


@dataclass(frozen=True)
class SubjectBrief:
    subject_id: str
    scope_id: str
    display_name: str
    activity: AnswerRecord
    scale: AnswerRecord
    currentness: AnswerRecord
    comparison: ComparisonRow

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "display_name": self.display_name,
            "activity": self.activity.as_dict(),
            "scale": self.scale.as_dict(),
            "currentness": self.currentness.as_dict(),
            "comparison": self.comparison.as_dict(),
        }


@dataclass(frozen=True)
class PrivateAnswerBrief:
    """The private E3 derivative and its explicit coverage boundary."""

    subjects: tuple[SubjectBrief, ...]
    answer_slots: tuple[AnswerRecord, ...]
    source_hash_bindings: tuple[tuple[str, str], ...]
    north_star_coverage: tuple[NorthStarCoverage, ...]
    side_effects: Mapping[str, int]

    @property
    def document(self) -> dict[str, Any]:
        return {
            "schema": "charitygraph.gate4.e3.private-answer-brief/v1",
            "answer_state_vocabulary": ["supported", "unanswered"],
            "subjects": [subject.as_dict() for subject in self.subjects],
            "answer_slots": [record.as_dict() for record in self.answer_slots],
            "source_hash_bindings": [
                {"source_record_id": source_record_id, "representation_sha256": digest}
                for source_record_id, digest in self.source_hash_bindings
            ],
            "north_star_coverage": [entry.as_dict() for entry in self.north_star_coverage],
            "side_effects": dict(self.side_effects),
        }


_ACTIVITY_BASIS = {
    "programs": "$.Programs[].Name",
    "operating_in_states": "$.OperatingInStates[].Name",
    "countries": "$.Countries[].Name",
    "beneficiaries": "$.Beneficiaries[].Name",
}
_SCALE_BASIS = {
    "from": "$.FinReportFrom",
    "to": "$.FinReportTo",
    "accounting_basis": "$.FinReportingType",
    "receipts": "$.IncomeTotalReceipts",
    "expenses": "$.ExpenseTotal",
    "net_surplus_deficit": "$.NetSurplusDeficit",
    "full_time_employees": "$.HrFullTimeEmployees",
    "part_time_employees": "$.HrPartTimeEmployees",
    "casual_employees": "$.HrCasualEmployees",
    "unpaid_volunteers": "$.HrUnpainVolunteers",
}

_NORTH_STAR_SECTIONS = (
    (1, "Identity / regulatory", "subject and scope identifiers are preserved; identity attributes are outside E2B", ("identity_attributes",)),
    (2, "Purpose / cause", "E2B selects no purpose narrative", ("purpose_detail",)),
    (3, "Programs / services", "source-native program names are retained when activity is supported", ("currentness", "delivery_party", "access_route")),
    (4, "Activities / SDGs", "source-native program classifications are retained; no SDG interpretation", ("sdg_proposition", "independent_activity_assessment")),
    (5, "Geography / beneficiaries", "source-native named states, countries and beneficiaries are retained", ("served_or_reached_status",)),
    (6, "Participation", "no participation proposition is present in E2B", ("participation",)),
    (7, "Direct service / capacity", "current capacity and availability remain unanswered", ("current_service_capacity", "eligibility", "throughput", "waitlist")),
    (8, "Fundraising", "no current giving terms or fundraising offer is present in E2B", ("current_giving_terms",)),
    (9, "Governance / leadership", "no governance or appointment proposition is present in E2B", ("governance",)),
    (10, "People / workforce", "source-native AIS workforce counts are retained when scale is supported", ("role_and_capability_detail",)),
    (11, "Scale / capability", "selected source-native scale measures are retained; capability is not assessed", ("independent_capability_assessment", "constraints")),
    (12, "Relationships", "no governed relationship edge is present in E2B", ("relationships",)),
    (13, "Finances", "source-native AIS period, basis, receipts, expenses and result are retained", ("independent_reconciliation",)),
    (14, "Funding / dependencies", "no funder concentration, dependency or conditionality assessment is present", ("funding_dependency",)),
    (15, "Ethos / values", "no ethos or values assessment is present in E2B", ("values_assessment",)),
    (16, "Conduct / adverse", "not assessed; silence is not a clean record", ("conduct_or_adverse_history",)),
    (17, "Notable history", "no historical review is present in E2B", ("notable_history",)),
    (18, "Evaluation / outcomes", "no evaluation, outcome or effectiveness evidence is present", ("outcomes_or_effectiveness",)),
    (19, "Classification / search / AI discovery", "source-native program classifications are retained; no discovery decision", ("classification_decision",)),
    (20, "Evidence / coverage / freshness / corrections", "exact answer-slot citations, hashes and missingness are retained", ("reviewed_universe", "freshness", "corrections")),
)


def _record_map(projection: AnswerProjection) -> dict[str, dict[str, AnswerRecord]]:
    if len(projection.records) != 15:
        raise BriefCompositionError("E2B projection must contain exactly fifteen answer slots")
    if any(value != 0 for value in projection.side_effects.values()):
        raise BriefCompositionError("E2B projection reports a non-zero operational side effect")
    grouped: dict[str, dict[str, AnswerRecord]] = {}
    source_bindings: dict[str, str] = {}
    for record in projection.records:
        if record.question_id not in {QUESTION_ACTIVITY, QUESTION_SCALE, QUESTION_CURRENTNESS}:
            raise BriefCompositionError("E2B projection contains an unsupported answer question")
        subject = grouped.setdefault(record.subject_id, {})
        if record.question_id in subject:
            raise BriefCompositionError("E2B projection contains a duplicate answer slot")
        subject[record.question_id] = record
        if record.source_record_id in source_bindings and source_bindings[record.source_record_id] != record.representation_sha256:
            raise BriefCompositionError("one source record is bound to multiple representation hashes")
        source_bindings[record.source_record_id] = record.representation_sha256
        if not record.source_references:
            raise BriefCompositionError("E2B answer slot has no source reference")
        envelope_keys = ("subject_id", "scope_id", "source_family", "source_record_id", "representation_sha256")
        if not any(
            all(getattr(record, key) == getattr(citation, key) for key in envelope_keys)
            for citation in record.source_references
        ):
            raise BriefCompositionError("E2B answer envelope does not match a source citation")
    if len(grouped) != 5 or any(set(records) != {QUESTION_ACTIVITY, QUESTION_SCALE, QUESTION_CURRENTNESS} for records in grouped.values()):
        raise BriefCompositionError("E2B projection must contain three slots for each of five subjects")
    if len(source_bindings) != 10:
        raise BriefCompositionError("E2B projection must retain ten source-record/hash bindings")
    if set(projection.representation_hashes) != set(source_bindings.values()) or len(projection.representation_hashes) != 10:
        raise BriefCompositionError("E2B representation hash inventory does not match answer citations")
    return grouped


def _cited(record: AnswerRecord, value: Any, *basis: str) -> CitedValue:
    exact_basis: list[str] = []
    for path in basis:
        candidates = (path, "$.data." + path[2:]) if path.startswith("$.") else (path,)
        try:
            exact_basis.append(next(candidate for candidate in candidates if candidate in record.field_basis))
        except StopIteration as exc:
            raise BriefCompositionError("derived value uses a field basis absent from its E2B record") from exc
    return CitedValue.from_record(record, value, exact_basis)


def _comparison(activity: AnswerRecord, scale: AnswerRecord, display_name: str) -> ComparisonRow:
    if activity.answer_state != "supported" or scale.answer_state != "supported" or not isinstance(activity.answer, Mapping) or not isinstance(scale.answer, Mapping):
        raise BriefCompositionError("the five-subject comparison requires supported activity and scale slots")
    programs = activity.answer.get("programs")
    states = activity.answer.get("operating_in_states")
    countries = activity.answer.get("countries")
    beneficiaries = activity.answer.get("beneficiaries")
    financial = scale.answer.get("financial_measures")
    workforce = scale.answer.get("workforce")
    if not all(isinstance(value, list) for value in (programs, states, countries, beneficiaries)):
        raise BriefCompositionError("activity answer has an invalid source-native list")
    if not isinstance(financial, Mapping) or not isinstance(workforce, Mapping):
        raise BriefCompositionError("scale answer has invalid source-native measures")
    period = scale.answer.get("reporting_period")
    if not isinstance(period, Mapping):
        raise BriefCompositionError("scale answer has no reporting period")
    scope_id = activity.scope_id
    if scope_id != scale.scope_id:
        raise BriefCompositionError("activity and scale slots have different scopes")
    return ComparisonRow(
        subject_id=activity.subject_id,
        scope_id=scope_id,
        display_name=display_name,
        program_count=_cited(activity, len(programs), _ACTIVITY_BASIS["programs"]),
        operating_in_states=_cited(activity, states, _ACTIVITY_BASIS["operating_in_states"]),
        countries=_cited(activity, countries, _ACTIVITY_BASIS["countries"]),
        beneficiaries=_cited(activity, beneficiaries, _ACTIVITY_BASIS["beneficiaries"]),
        reporting_period=_cited(scale, dict(period), _SCALE_BASIS["from"], _SCALE_BASIS["to"]),
        accounting_basis=_cited(scale, scale.answer["accounting_basis"], _SCALE_BASIS["accounting_basis"]),
        receipts=_cited(scale, financial["receipts"], _SCALE_BASIS["receipts"]),
        expenses=_cited(scale, financial["expenses"], _SCALE_BASIS["expenses"]),
        net_surplus_deficit=_cited(scale, financial["net_surplus_deficit"], _SCALE_BASIS["net_surplus_deficit"]),
        full_time_employees=_cited(scale, workforce["full_time_employees"], _SCALE_BASIS["full_time_employees"]),
        part_time_employees=_cited(scale, workforce["part_time_employees"], _SCALE_BASIS["part_time_employees"]),
        casual_employees=_cited(scale, workforce["casual_employees"], _SCALE_BASIS["casual_employees"]),
        unpaid_volunteers=_cited(scale, workforce["unpaid_volunteers"], _SCALE_BASIS["unpaid_volunteers"]),
    )


def _coverage(subject_ids: Sequence[str], *, activity_supported: bool, scale_supported: bool) -> tuple[NorthStarCoverage, ...]:
    entries: list[NorthStarCoverage] = []
    for section_id, title, basis, missingness in _NORTH_STAR_SECTIONS:
        if section_id == 1:
            code, status = "P", "partial"
        elif section_id in {3, 4, 5, 19}:
            code, status = ("P", "partial") if activity_supported else ("M", "unassessed")
        elif section_id in {10, 13}:
            code, status = ("S", "supported") if scale_supported else ("M", "unassessed")
        elif section_id == 11:
            code, status = ("P", "partial") if activity_supported or scale_supported else ("M", "unassessed")
        elif section_id == 20:
            code, status = "S", "supported"
        else:
            code, status = "M", "unassessed"
        entries.append(
            NorthStarCoverage(
                section_id=section_id,
                title=title,
                code=code,
                status=status,
                status_by_subject={subject_id: code for subject_id in subject_ids},
                basis=basis,
                missingness=tuple(missingness),
            )
        )
    return tuple(entries)


def compose_private_answer_brief(
    projection: AnswerProjection,
    *,
    subject_labels: Mapping[str, str] | None = None,
) -> PrivateAnswerBrief:
    """Compose the private E3 brief from an already-built E2B projection.

    ``subject_labels`` is display metadata only.  It is never used for
    grouping, identity, binding, source selection, or validation.  When it is
    absent, durable subject IDs remain the display labels.
    """

    grouped = _record_map(projection)
    labels = {} if subject_labels is None else {str(key): str(value) for key, value in subject_labels.items()}
    unknown_labels = set(labels) - set(grouped)
    if unknown_labels:
        raise BriefCompositionError("subject_labels contains an unknown subject")

    subjects: list[SubjectBrief] = []
    for subject_id in sorted(grouped):
        records = grouped[subject_id]
        activity = records[QUESTION_ACTIVITY]
        scale = records[QUESTION_SCALE]
        currentness = records[QUESTION_CURRENTNESS]
        if currentness.answer_state != "unanswered" or currentness.answer is not None:
            raise BriefCompositionError("currentness slot must remain explicitly unanswered")
        if activity.scope_id != scale.scope_id or scale.scope_id != currentness.scope_id:
            raise BriefCompositionError("the three E2B slots do not share a scope")
        display_name = labels.get(subject_id, subject_id)
        subjects.append(
            SubjectBrief(
                subject_id=subject_id,
                scope_id=activity.scope_id,
                display_name=display_name,
                activity=activity,
                scale=scale,
                currentness=currentness,
                comparison=_comparison(activity, scale, display_name),
            )
        )

    ordered_slots = tuple(
        record
        for subject in subjects
        for record in (subject.activity, subject.scale, subject.currentness)
    )
    source_hash_bindings = tuple(
        sorted({(record.source_record_id, record.representation_sha256) for record in ordered_slots})
    )
    side_effects = dict(projection.side_effects)
    side_effects.setdefault("provider_calls", 0)
    side_effects.setdefault("transport_requests", 0)
    side_effects.setdefault("budget_reservations", 0)
    side_effects.setdefault("source_acquisitions", 0)
    side_effects.setdefault("publications", 0)
    side_effects.setdefault("sqlite_opens", 0)
    return PrivateAnswerBrief(
        subjects=tuple(subjects),
        answer_slots=ordered_slots,
        source_hash_bindings=source_hash_bindings,
        north_star_coverage=_coverage(
            tuple(subject.subject_id for subject in subjects),
            activity_supported=all(subject.activity.answer_state == "supported" for subject in subjects),
            scale_supported=all(subject.scale.answer_state == "supported" for subject in subjects),
        ),
        side_effects=side_effects,
    )


__all__ = [
    "BriefCompositionError",
    "CitedValue",
    "ComparisonRow",
    "NorthStarCoverage",
    "PrivateAnswerBrief",
    "SubjectBrief",
    "compose_private_answer_brief",
]
