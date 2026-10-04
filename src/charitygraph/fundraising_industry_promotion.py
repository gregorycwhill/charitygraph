"""Conservative, review-only promotion of fundraising-industry source records.

This is deliberately a candidate boundary.  It gives reviewers typed, scoped
observations without treating directory membership, awards, or benchmark
figures as canonical CharityGraph claims.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from .models import (
    EvidenceRef, FundraisingCampaignObservation, FundraisingObservationScope,
    FundraisingPracticeObservation, FundraisingProviderRelationship,
    MoneyObservation, SubjectRelationship,
)


CandidateKind = Literal["practice", "campaign", "provider_relationship", "source_metric"]
ReviewState = Literal["review_required", "identity_blocked", "unsupported"]


class SourceNativeMetric(BaseModel):
    """A benchmark value, never AIS income or fundraising expenditure."""

    metric_label: str
    source_raw_value: str
    reporting_year: int | None = None
    caveat: str | None = None
    money: MoneyObservation | None = None


class IndustryPromotionCandidate(BaseModel):
    candidate_id: str
    candidate_kind: CandidateKind
    review_state: ReviewState = "review_required"
    review_reason: str
    source_record_id: str
    source_family: str
    source_role: str
    identity_status: Literal["resolved", "candidate", "ambiguous", "unresolved"]
    subject_id: str | None = None
    evidence: EvidenceRef
    source_native_category: str | None = None
    source_native_metrics: list[SourceNativeMetric] = Field(default_factory=list)
    practice: FundraisingPracticeObservation | None = None
    campaign: FundraisingCampaignObservation | None = None
    provider_relationship: FundraisingProviderRelationship | None = None


def _id(prefix: str, record: dict) -> str:
    raw = f"{prefix}|{record.get('source_record_id')}|{record.get('source_url')}"
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _evidence(record: dict, observed_at: date) -> EvidenceRef:
    text = str(record.get("source_text") or "")
    return EvidenceRef(
        evidence_id=_id("ev_industry", record), source_type="independent_reference",
        title=f"Fundraising industry source: {record.get('source_record_id')}",
        url=record.get("source_url"), observed_at=observed_at,
        section=str(record.get("source_location") or "unknown"),
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )


def _scope(subject_id: str, observed_at: date) -> FundraisingObservationScope:
    return FundraisingObservationScope(scope_kind="subject", scope_subject_causebase_id=subject_id, observed_at=observed_at)


def _facets(text: str) -> tuple[str, ...]:
    low = text.casefold()
    result = []
    if "face-to-face" in low or "face to face" in low:
        result.append("fundraising.face_to_face")
    if "peer-to-peer" in low or "peer to peer" in low or re.search(r"\bp2p\b", low):
        result.append("fundraising.peer_to_peer")
    if "event" in low:
        result.append("fundraising.events")
    return tuple(result)


def _money(raw: str, year: int | None, caveat: str | None) -> SourceNativeMetric:
    cleaned = raw.upper().replace("AUD", "").replace("$", "").replace(",", "").strip()
    scale = Decimal("1000000") if cleaned.endswith("M") else Decimal("1000") if cleaned.endswith("K") else Decimal("1")
    cleaned = cleaned[:-1].strip() if cleaned.endswith(("M", "K")) else cleaned
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return SourceNativeMetric(metric_label="source_reported_amount", source_raw_value=raw, reporting_year=year, caveat=caveat)
    return SourceNativeMetric(
        metric_label="source_reported_amount", source_raw_value=raw, reporting_year=year, caveat=caveat,
        money=MoneyObservation(source_amount=amount, source_currency="AUD", source_unit_scale=scale,
                               normalised_amount=amount * scale, normalised_currency="AUD", source_raw_value=raw),
    )


def promote_industry_record(
    record: dict, *, subject_id: str | None, identity_status: Literal["resolved", "candidate", "ambiguous", "unresolved"],
    observed_at: date, provider_subject_id: str | None = None, provider_evidence_ids: list[str] | None = None,
) -> list[IndustryPromotionCandidate]:
    """Return review candidates; only exact binding produces typed observations.

    ``provider_subject_id`` is intentionally separate: PFRA/FIA text does not
    turn a provider name into a governed relationship or a setting assertion.
    """
    evidence = _evidence(record, observed_at)
    base = dict(source_record_id=str(record.get("source_record_id")), source_family=str(record.get("source_family") or "fundraising_industry"), source_role=str(record.get("source_role") or "industry_context"), identity_status=identity_status, subject_id=subject_id, evidence=evidence)
    if identity_status != "resolved" or not subject_id:
        return [IndustryPromotionCandidate(candidate_id=_id("fic", record), candidate_kind="campaign", review_state="identity_blocked", review_reason="Exact governed subject binding is required before a typed observation can be proposed.", **base)]

    text = str(record.get("source_text") or record.get("campaign_event_name") or "")
    scope = _scope(subject_id, observed_at)
    output: list[IndustryPromotionCandidate] = []
    if record.get("record_type") in {"membership_semantics", "current_charity_membership"} and "face" in text.casefold():
        practice = FundraisingPracticeObservation(observation_id=_id("fp", record), source_native_phrase=text, canonical_facets=_facets(text), scope=scope, lifecycle="unknown", source_role="industry_context", evidence_ids=[evidence.evidence_id], uncertainty_note="PFRA-scoped industry evidence; it does not establish setting, delivery party, compensation, regular giving, or current use.")
        output.append(IndustryPromotionCandidate(candidate_id=_id("ficp", record), candidate_kind="practice", review_reason="PFRA F2F candidate requires human review of scope and currentness.", practice=practice, **base))
    if record.get("record_type") in {"top30_campaign", "fia_award_record"}:
        name = str(record.get("campaign_event_name") or record.get("campaign_project") or text).strip()
        campaign = FundraisingCampaignObservation(observation_id=_id("fc", record), campaign_name=name, source_native_phrase=text or name, canonical_facets=_facets(text), scope=scope, lifecycle="unknown", source_role="industry_context", evidence_ids=[evidence.evidence_id], uncertainty_note="Industry/award record; not an effectiveness rating or accounting allocation.")
        metrics = [_money(str(record[key]), record.get("reporting_year") or record.get("year"), record.get("offline_revenue_caveat") or record.get("caveat")) for key in ("reported_amount_2023", "reported_amount_2024") if record.get(key) is not None]
        output.append(IndustryPromotionCandidate(candidate_id=_id("ficc", record), candidate_kind="campaign", review_reason="Campaign and source-native metrics require review; amounts are not AIS donations or fundraising expense.", campaign=campaign, source_native_category=record.get("source_native_award_category"), source_native_metrics=metrics, **base))
    if provider_subject_id and provider_evidence_ids and (record.get("nominated_by") or record.get("consultant_service_provider")):
        relation = FundraisingProviderRelationship(relationship_id=_id("fpr", record), relationship=SubjectRelationship(relationship_type="fundraising_service_provider", target_causebase_id=provider_subject_id, evidence_ids=provider_evidence_ids), subject_role="client", provider_role="fundraising_service_provider", scope=scope, lifecycle="unknown", source_role="industry_context", evidence_ids=provider_evidence_ids)
        output.append(IndustryPromotionCandidate(candidate_id=_id("ficr", record), candidate_kind="provider_relationship", review_reason="Provider relationship has separate exact provider binding and evidence; review still required.", provider_relationship=relation, **base))
    return output or [IndustryPromotionCandidate(candidate_id=_id("fic", record), candidate_kind="campaign", review_state="unsupported", review_reason="This source record does not support a typed fundraising candidate without adding unsupported semantics.", **base)]
