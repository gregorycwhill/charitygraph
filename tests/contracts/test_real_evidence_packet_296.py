"""Regression proof for the bounded, official-source packet 296.

The companion adjudication packet is retained as review evidence in the Data product
documentation.  These are
atomic source claims, not a scraper or a payment-form test.
"""
from datetime import datetime, timezone

from charitygraph.contracts.common import ProducerRef
from charitygraph.contracts.fundability import FundabilityEvidenceRef, FundabilityProposition, FundabilityV1, project_observation
from charitygraph.contracts.knowledge import ObservationTime


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
WV = "subject:" + "1" * 32
CC = "subject:" + "2" * 32


def evidence(key: str, url: str) -> FundabilityEvidenceRef:
    return FundabilityEvidenceRef(locator=url, source_record_id=f"src:296:{key}", source_role="first_party", lineage_id=f"lineage:296:{key}")


def atom(predicate: str, subject: str, key: str, url: str, **values) -> FundabilityProposition:
    base = dict(predicate=predicate, giving_context_id=f"giving:296:{key}", accepting_subject_id=subject,
        destination_resolution="unresolved", status="current", coverage_state="supported",
        observation_time=ObservationTime(observed_at=NOW), evidence=(evidence(key, url),))
    base.update(values)
    return FundabilityProposition(**base)


def test_real_packet_keeps_pooled_sponsorship_parent_giving_and_negotiation_distinct():
    wv_url = "https://www.worldvision.com.au/child-sponsorship-faqs#how-does-child-sponsorship-work"
    cc_url = "https://give.cancercouncil.com.au/eofy#become-a-major-donor"
    propositions = (
        atom("giving_offer_observed", WV, "WV-01", wv_url, destination_source_label="Child Sponsorship", audience="public", instrument="sponsorship", commitment_pattern="recurring", designation_type="source_stated_preference", detail="Donations are pooled for community projects; named child is not allocation evidence."),
        atom("shared_cost_terms_observed", WV, "WV-01", wv_url, destination_source_label="Child Sponsorship", audience="public", detail="Pooled community-focused arrangement."),
        atom("giving_offer_observed", WV, "WV-01", wv_url, destination_source_label="Where it’s most needed", audience="public", instrument="donation", designation_type="unrestricted", endpoint_type="contact_route", endpoint_url="https://www.worldvision.com.au/child-sponsorship-faqs", detail="Phone/chat setup described."),
        atom("giving_offer_observed", CC, "CC-01", "https://www.cancercouncil.com.au/ways-to-donate/", destination_source_label="Cancer Council NSW general donation", audience="public", instrument="donation", commitment_pattern="once_or_regular", designation_type="unrestricted", detail="General giving covers multiple activities; no retail selector asserted."),
        atom("giving_offer_observed", CC, "CC-02", cc_url, destination_source_label="Cancer Research Awards 2025", audience="public", instrument="donation", designation_type="unknown", detail="Appeal label does not establish a legal restriction."),
        atom("giving_offer_observed", CC, "CC-02", cc_url, destination_source_label="Cancer Research", audience="major_donor", instrument="major_gift", designation_type="negotiated", endpoint_type="contact_route", endpoint_url="https://give.cancercouncil.com.au/eofy", detail="Choice of one of three pillars stated for gifts over $5,000."),
        FundabilityProposition(predicate="designation_available_observed", giving_context_id="giving:296:CC-01", accepting_subject_id=CC, destination_source_label="Cancer Research", destination_resolution="unresolved", audience="public", designation_type="unknown", status="current", coverage_state="not_found_in_reviewed_public_giving_channels", observation_time=ObservationTime(observed_at=NOW)),
        FundabilityProposition(predicate="giving_offer_observed", giving_context_id="giving:296:CC-04", accepting_subject_id=CC, destination_source_label="2016/17 Breakthrough", destination_resolution="unresolved", audience="public", status="historical", coverage_state="stale", observation_time=ObservationTime(observed_at=NOW), evidence=(evidence("CC-04", "https://www.cancercouncil.com.au/wp-content/uploads/2023/06/Annual-Report-2016-2017-Cancer-Council-NSW.pdf"),)),
    )
    packet = FundabilityV1(propositions=propositions)
    assert {p.audience for p in packet.propositions} == {"public", "major_donor"}
    assert next(p for p in packet.propositions if p.destination_source_label == "Cancer Research" and p.audience == "public").coverage_state == "not_found_in_reviewed_public_giving_channels"
    assert next(p for p in packet.propositions if p.destination_source_label == "2016/17 Breakthrough").status == "historical"
    projected = project_observation(packet.propositions[0], record_id="observation:" + "3" * 64, subject_id=WV, created_at=NOW, producer=ProducerRef(kind="code", producer_id="packet-296"))
    assert projected.scope_id is None and "allocation" not in projected.value
