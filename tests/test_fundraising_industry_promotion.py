from datetime import date

from charitygraph.fundraising_industry_promotion import promote_industry_record
from charitygraph.semantic_benchmark import DonorRepublicFunraisinAdapter, FIAAwardsAdapter, PFRAAdapter


TODAY = date(2026, 10, 4)


def test_pfra_f2f_is_scoped_review_candidate_without_invented_axes():
    record = PFRAAdapter().enumerate_records("Face-to-face fundraising member")[0]
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    practice = candidates[0].practice
    assert candidates[0].candidate_kind == "practice"
    assert practice.scope.scope_subject_causebase_id == "cb_example"
    assert practice.canonical_facets == ("fundraising.face_to_face",)
    assert practice.lifecycle == "unknown"
    assert "setting" in practice.uncertainty_note and "delivery party" in practice.uncertainty_note


def test_pfra_does_not_create_provider_or_setting_without_separate_evidence():
    record = PFRAAdapter().enumerate_records("Face-to-face fundraising agency")[0]
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    assert all(item.provider_relationship is None for item in candidates)
    assert "fundraising.external_agency" not in candidates[0].practice.canonical_facets
    assert "fundraising.private_site" not in candidates[0].practice.canonical_facets


def test_ambiguous_binding_is_explicitly_blocked_not_promoted():
    record = PFRAAdapter().enumerate_records("Face-to-face fundraising member")[0]
    candidates = promote_industry_record(record, subject_id=None, identity_status="ambiguous", observed_at=TODAY)
    assert candidates[0].review_state == "identity_blocked"
    assert candidates[0].practice is None and candidates[0].campaign is None


def test_p2p_campaign_retains_native_metrics_without_accounting_rewrite():
    record = DonorRepublicFunraisinAdapter().enumerate_top30_rows("1 | Harbour P2P Walk | Example Charity | walk | $10,000 | $12,000 | +20%")[0]
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    campaign = candidates[0]
    assert campaign.campaign.canonical_facets == ("fundraising.peer_to_peer",)
    assert [m.source_raw_value for m in campaign.source_native_metrics] == ["$10,000", "$12,000"]
    assert "not AIS donations" in campaign.review_reason


def test_fia_campaign_is_source_native_and_provider_needs_separate_binding_evidence():
    record = FIAAwardsAdapter().enumerate_records("CAMPAIGN\nExample Charity\nFlood Appeal\nNominated by: Example Agency")[0]
    candidates = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)
    assert len(candidates) == 1 and candidates[0].campaign is not None
    assert candidates[0].source_native_category == "CAMPAIGN"
    linked = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY, provider_subject_id="cb_agency", provider_evidence_ids=["ev_separate_provider_proof"])
    relationship = next(item.provider_relationship for item in linked if item.provider_relationship)
    assert relationship.relationship.target_causebase_id == "cb_agency"


def test_unsupported_attribution_is_not_a_candidate():
    record = {"source_record_id": "pfra:empty", "source_url": "https://pfra.example", "source_text": "Membership listing", "record_type": "current_charity_membership"}
    candidate = promote_industry_record(record, subject_id="cb_example", identity_status="resolved", observed_at=TODAY)[0]
    assert candidate.review_state == "unsupported"
    assert candidate.practice is None and candidate.campaign is None
