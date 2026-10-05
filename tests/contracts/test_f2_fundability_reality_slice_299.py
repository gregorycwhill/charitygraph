"""Regression guard for the review-only, official-source F2 reality slice.

The companion packet is retained as canonical review evidence in the Data product
documentation.  These
atoms preserve the reviewed source statements; they do not drive payment, discovery,
or a public projection.
"""
from datetime import datetime, timezone

from charitygraph.contracts.common import ProducerRef
from charitygraph.contracts.fundability import FundabilityEvidenceRef, FundabilityProposition, FundabilityV1, project_observation
from charitygraph.contracts.knowledge import ObservationTime


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
OXFAM = "subject:" + "9" * 32
RED_CROSS = "subject:" + "8" * 32
CANCER_COUNCIL = "subject:" + "7" * 32
OXFAM_APPEAL = "scope:" + "6" * 32


def evidence(key: str, url: str, role: str = "first_party") -> FundabilityEvidenceRef:
    return FundabilityEvidenceRef(locator=url, source_record_id=f"src:299:{key}", source_role=role, lineage_id=f"lineage:299:{key}")


def test_f2_current_disaster_offer_resolves_scope_without_legal_or_allocation_conflation():
    appeal = "https://www.oxfam.org.au/ways-to-donate/our-appeals/gaza-palestinian-crisis/"
    offer = FundabilityProposition(
        predicate="designation_available_observed", giving_context_id="giving:299:OX-01",
        accepting_subject_id=OXFAM, destination_source_label="Oxfam Middle East crisis response",
        destination_scope_id=OXFAM_APPEAL, destination_resolution="resolved", audience="public",
        instrument="donation", commitment_pattern="once_or_regular", designation_type="source_stated_designation",
        status="current", endpoint_type="first_party_form", endpoint_url=appeal, coverage_state="supported",
        observation_time=ObservationTime(observed_at=NOW), evidence=(evidence("OX-01", appeal),),
        detail="Appeal funds support the Middle East crisis response including Gaza, West Bank and Lebanon; not a legal restriction or allocation guarantee.",
    )
    redirection = offer.model_copy(update={
        "predicate": "redirection_terms_observed", "detail": "Excess or unusable appeal funds are directed to Oxfam's International Crisis Fund."
    })
    costs_url = "https://www.oxfam.org.au/our-impact/where-the-money-goes/"
    shared_costs = offer.model_copy(update={
        "predicate": "shared_cost_terms_observed", "endpoint_type": None, "endpoint_url": None,
        "evidence": (evidence("OX-02", costs_url),),
        "detail": "At least 90% of emergency appeal funds go to program and humanitarian work; stated remaining costs are not marginal allocation."
    })
    packet = FundabilityV1(propositions=(offer, redirection, shared_costs))
    assert {item.predicate for item in packet.propositions} == {"designation_available_observed", "redirection_terms_observed", "shared_cost_terms_observed"}
    projected = project_observation(offer, record_id="observation:" + "5" * 64, subject_id=OXFAM, created_at=NOW, producer=ProducerRef(kind="code", producer_id="f2-packet-299"))
    assert projected.scope_id == OXFAM_APPEAL
    assert "allocation" not in projected.value and projected.value["designation_type"] == "source_stated_designation"


def test_f2_unresolved_offer_blocks_scope_join_and_major_gift_is_audience_labelled():
    arc = FundabilityProposition(
        predicate="giving_offer_observed", giving_context_id="giving:299:ARC-01", accepting_subject_id=RED_CROSS,
        destination_source_label="Middle East Crisis Appeal", destination_resolution="candidate", audience="public",
        instrument="donation", designation_type="source_stated_designation", status="current", coverage_state="supported",
        observation_time=ObservationTime(observed_at=NOW), evidence=(evidence("ARC-01", "https://www.redcross.org.au/middleeastcrisisappeal/"),),
        detail="Current public appeal; scope remains a candidate and cannot join finance.",
    )
    major = FundabilityProposition(
        predicate="giving_offer_observed", giving_context_id="giving:299:CC-02", accepting_subject_id=CANCER_COUNCIL,
        destination_source_label="Cancer Research", destination_resolution="unresolved", audience="major_donor",
        instrument="major_gift", designation_type="negotiated", status="current", endpoint_type="contact_route",
        endpoint_url="https://give.cancercouncil.com.au/eofy", coverage_state="supported",
        observation_time=ObservationTime(observed_at=NOW), evidence=(evidence("CC-02", "https://give.cancercouncil.com.au/eofy"),),
        detail="Pillar choice is stated only for gifts over $5,000; excluded from default retail results.",
    )
    not_found = FundabilityProposition(
        predicate="designation_available_observed", giving_context_id="giving:299:CC-RETAIL", accepting_subject_id=CANCER_COUNCIL,
        destination_source_label="Cancer Research", destination_resolution="unresolved", audience="public",
        designation_type="unknown", status="current", coverage_state="not_found_in_reviewed_public_giving_channels",
        observation_time=ObservationTime(observed_at=NOW), detail="No retail selector was observed; this is not explicit unavailability.",
    )
    assert arc.destination_scope_id is None and major.audience == "major_donor"
    assert not_found.coverage_state != "explicitly_unavailable"
