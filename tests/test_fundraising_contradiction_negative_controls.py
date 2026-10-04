"""Adversarial fundraising controls for non-inference and money compatibility.

These are deliberately source-shaped fixtures rather than an English keyword
detector: the production compiler receives the already governed source claim.
Their purpose is to ensure tempting adjacent evidence remains blocked, unknown,
or reviewable at the relevant boundary.
"""
from datetime import date

import pytest
from pydantic import ValidationError

from charitygraph.finance_measurement import FundraisingMoneyMeasurement, decide_addition_compatibility
from charitygraph.fundraising_evidence_roles import EvidenceScope, FundraisingEvidence, assess_fundraising_evidence
from charitygraph.fundraising_inference import NativeFundraisingClaim, compile_fundraising_candidates
from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink


def evidence(identifier: str, *, role="first_party_practice_page", binding="confirmed", facets=("practice",)):
    return FundraisingEvidence(
        evidence_id=identifier, source_id=f"source:{identifier}", source_role=role,
        locator=f"/source/{identifier}", source_wording="Source-native assertion retained for review.",
        subject_binding=binding, binding_basis="durable organisation identifier", observed_at=date(2026, 10, 5),
        scope=EvidenceScope(kind="organisation", identifier="cb:one"), production_method="governed_semantic_inference",
        review_status="reviewed", coverage="observed", asserted_facets=facets,
    )


def claim(identifier: str, evidence_id: str, *, assertion="present", lifecycle="unknown"):
    return NativeFundraisingClaim(
        claim_id=identifier, evidence_id=evidence_id, source_phrase="face-to-face fundraising",
        inference_method="governed_semantic_mapping", canonical_term_id="fundraising.face_to_face",
        mapping_predicate="close_match", assertion=assertion, lifecycle=lifecycle,
    )


def money(identifier: str, **changes):
    values = dict(
        observation_id=f"obs:{identifier}", amount={"source_amount": "100", "source_unit_scale": 1, "normalised_amount": "100"},
        measure_kind="gross_proceeds", source_wording="Campaign gross proceeds: $100.", evidence_ids=[f"ev:{identifier}"],
        period={"period_start": date(2025, 7, 1), "period_end": date(2026, 6, 30), "period_length_days": 365},
        reporting_scope="subject", reporting_subject_causebase_id="cb:one", recognition_basis="accrual",
        gross_net_basis="gross", gst_treatment="exclusive", pass_through_treatment="excluded",
        allocation_method="not_applicable", amount_is_approximate=False, source_role="audited_financial_statement",
        assurance="audited", fundraising_activity_id="campaign:winter", aggregation_set_id="note:7", component_is_disjoint=True,
    )
    values.update(changes)
    return FundraisingMoneyMeasurement(**values)


def test_permission_and_membership_records_cannot_be_recast_as_actual_f2f_use():
    for role, wording in (("regulator_registration", "Permitted methods include door-to-door collections."),
                          ("pfra_membership", "Charity One is a PFRA member.")):
        record = evidence(role, role=role, facets=()).model_copy(update={"source_wording": wording})
        assert assess_fundraising_evidence(record).promotion == "blocked"
        with pytest.raises(ValidationError, match="cannot support facets"):
            FundraisingEvidence(**(record.model_dump() | {"asserted_facets": ("practice",)}))


def test_stale_agency_case_after_cessation_does_not_become_current():
    base = evidence("agency-2019", role="agency_provider_case_evidence")
    agency = FundraisingEvidence(**(base.model_dump() | {
        "source_wording": "We delivered face-to-face fundraising in 2019; the engagement ended in 2020.",
        "valid_from": date(2019, 1, 1), "valid_to": date(2020, 12, 31), "asserted_facets": ("practice", "currentness"),
    }))
    result = compile_fundraising_candidates((agency,), (claim("old-case", "agency-2019", lifecycle="discontinued"),))
    assert result.candidates[0].lifecycle == "discontinued"


def test_generic_donate_page_and_annual_expense_do_not_create_method_attribution():
    donate = evidence("donate", facets=("channel",)).model_copy(update={"source_wording": "Donate online today."})
    web = NativeFundraisingClaim(claim_id="donate-web", evidence_id="donate", source_phrase="Donate online today.",
                                 inference_method="governed_semantic_mapping", canonical_term_id="fundraising.website_donation",
                                 mapping_predicate="close_match")
    assert compile_fundraising_candidates((donate,), (web,)).candidates[0].canonical_term_id == "fundraising.website_donation"
    expense = FundraisingMoneyScopeLink(measurement=money("annual-cost", measure_kind="total_fundraising_cost", gross_net_basis="not_applicable", source_wording="Annual fundraising expense: $100."), linkage_status="unknown")
    assert (expense.attributed_scope_kind, expense.attributed_scope_id) == ("organisation", None)


def test_campaign_gross_provider_raised_and_audited_revenue_are_not_interchangeable():
    campaign_gross = money("campaign-gross")
    audited_donations = money("audited-donations", measure_kind="donations_received", source_wording="Donations received: $100.")
    provider_raised = money("provider-raised", measure_kind="amount_raised", source_role="platform_report", assurance="unaudited", source_wording="Platform reports $100 raised.")
    assert "different_measure_kind" in decide_addition_compatibility(campaign_gross, audited_donations).reasons
    assert "different_measure_kind" in decide_addition_compatibility(provider_raised, audited_donations).reasons


def test_gross_net_group_and_entity_mismatches_fail_closed():
    base = money("base")
    for other in (
        money("net", gross_net_basis="net"),
        money("group", reporting_scope="consolidated_group", reporting_subject_causebase_id=None, consolidation_scope_id="group:one"),
        money("other-entity", reporting_subject_causebase_id="cb:two"),
    ):
        assert not decide_addition_compatibility(base, other).safe_to_add


def test_duplicate_name_or_domain_is_not_an_identity_bridge_for_money_links():
    measurement = money("same-name")
    with pytest.raises(ValidationError, match="retain the measurement reporting entity"):
        FundraisingMoneyScopeLink(
            measurement=measurement, linkage_status="explicit", attributed_scope_kind="campaign",
            attributed_scope_id="campaign:other-charity-winter", reporting_entity_causebase_id="cb:other",
            linkage_evidence_ids=["ev:link"], linkage_source_wording="Winter Appeal",
        )


def test_present_and_explicit_absence_remain_linked_contradictions_not_resolution():
    result = compile_fundraising_candidates((evidence("present"), evidence("ceased")), (
        claim("present", "present"), claim("ceased", "ceased", assertion="explicitly_absent"),
    ))
    assert len(result.candidates) == 2
    assert all(candidate.contradiction_candidate_ids for candidate in result.candidates)
