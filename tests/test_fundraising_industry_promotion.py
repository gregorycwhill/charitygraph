from datetime import date

from charitygraph.fundraising_industry_promotion import promote_industry_record


TODAY = date(2026, 10, 4)


PFRA_F2F = {
    "source_record_id": "pfra:fixture:f2f", "source_url": "https://pfra.example/member",
    "source_location": "member:1", "source_text": "Example Charity", "record_type": "membership_semantics",
    "source_family": "fundraising_industry_pfra", "source_role": "industry_context",
    "source_supported_facets": ["fundraising.face_to_face"],
}


def test_pfra_f2f_is_scoped_review_candidate_without_invented_axes():
    candidates = promote_industry_record(PFRA_F2F, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    practice = candidates[0].practice
    assert candidates[0].candidate_kind == "practice"
    assert practice.scope.scope_subject_causebase_id == "cb_example"
    assert practice.canonical_facets == ("fundraising.face_to_face",)
    assert practice.lifecycle == "unknown"
    assert "setting" in practice.uncertainty_note and "delivery party" in practice.uncertainty_note
    assert candidates[0].review_state == "review_required"
    assert candidates[0].evidence.content_hash and candidates[0].source_role == "industry_context"


def test_pfra_does_not_create_provider_or_setting_without_separate_evidence():
    candidates = promote_industry_record(PFRA_F2F, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    assert all(item.provider_relationship is None for item in candidates)
    assert "fundraising.external_agency" not in candidates[0].practice.canonical_facets
    assert "fundraising.private_site" not in candidates[0].practice.canonical_facets


def test_ambiguous_binding_is_explicitly_blocked_not_promoted():
    candidates = promote_industry_record(PFRA_F2F, subject_id=None, identity_status="ambiguous", observed_at=TODAY)
    assert candidates[0].review_state == "identity_blocked"
    assert candidates[0].practice is None and candidates[0].campaign is None


def test_p2p_campaign_retains_native_metrics_without_accounting_rewrite():
    record = {"source_record_id": "p2p:fixture:1", "source_url": "https://benchmark.example/2024", "source_text": "Harbour P2P Walk", "record_type": "top30_campaign", "campaign_event_name": "Harbour P2P Walk", "reporting_year": 2024, "reported_amount_2023": "$10,000", "reported_amount_2024": "$12,000", "source_supported_facets": ["fundraising.peer_to_peer"], "offline_revenue_caveat": "Public revenue may omit offline funds."}
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    campaign = candidates[0]
    assert campaign.campaign.canonical_facets == ("fundraising.peer_to_peer",)
    assert [m.source_raw_value for m in campaign.source_native_metrics] == ["$10,000", "$12,000"]
    assert "not AIS donations" in campaign.review_reason


def test_fia_campaign_is_source_native_and_provider_needs_separate_binding_evidence():
    record = {"source_record_id": "fia:fixture:1", "source_url": "https://fia.example/awards", "source_text": "Example Charity — Flood Appeal", "record_type": "fia_award_record", "campaign_project": "Flood Appeal", "source_native_award_category": "CAMPAIGN", "nominated_by": "Example Agency"}
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    assert len(candidates) == 1 and candidates[0].campaign is not None
    assert candidates[0].source_native_category == "CAMPAIGN"
    linked = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY, provider_subject_id="cb_agency", provider_identity_status="resolved", provider_evidence_ids=["ev_separate_provider_proof"])
    relationship = next(item.provider_relationship for item in linked if item.provider_relationship)
    assert relationship.relationship.target_causebase_id == "cb_agency"


def test_unsupported_attribution_is_not_a_candidate():
    record = {"source_record_id": "pfra:empty", "source_url": "https://pfra.example", "source_text": "Membership listing", "record_type": "current_charity_membership"}
    candidate = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)[0]
    assert candidate.review_state == "unsupported"
    assert candidate.practice is None and candidate.campaign is None


def test_unscoped_money_and_ambiguous_provider_remain_unpromoted():
    aggregate = {"source_record_id": "p2p:aggregate", "source_url": "https://benchmark.example", "source_text": "Portfolio total $10,000", "record_type": "benchmark_total", "reported_amount_2024": "$10,000"}
    candidate = promote_industry_record(aggregate, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)[0]
    assert candidate.review_state == "unsupported"
    fia = {"source_record_id": "fia:ambiguous-provider", "source_url": "https://fia.example", "source_text": "Appeal", "record_type": "fia_award_record", "campaign_project": "Appeal", "nominated_by": "Same Name Agency"}
    candidates = promote_industry_record(fia, subject_id="cb_example", identity_status="resolved", observed_at=TODAY, provider_subject_id="cb_agency", provider_identity_status="ambiguous", provider_evidence_ids=["ev_provider"])
    assert all(item.provider_relationship is None for item in candidates)
