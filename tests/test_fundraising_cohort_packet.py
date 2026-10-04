from datetime import date

import pytest
from pydantic import ValidationError

from charitygraph.fundraising_cohort_packet import (
    FundraisingCohortPacket, build_cohort_packet_ledger,
)


def source():
    return {"source_id": "report:one", "source_role": "annual_report", "source_locator": "p. 12, row 3", "source_native_wording": "Fundraising costs", "rights_disposition": "rights_cleared_for_review_retention"}


def assertion(kind="practice", **changes):
    value = {"assertion_id": "assertion:one", "kind": kind, "source_id": "report:one", "subject_binding_basis": "report identifies the charity", "scope": "organisation", "production_method": "direct_source_claim", "review_status": "independently_adjudicated", "coverage_status": "observed", "disposition": "retained"}
    value.update(changes)
    return value


def packet(**changes):
    value = {"packet_id": "packet:one", "packet_status": "ready_for_independent_review", "source_backed": True, "fixture_only": False, "cases": [{"case_id": "case:one", "subject_id": "charity:one", "identity_adjudication": "confirmed", "sources": [source()], "assertions": [assertion(), assertion("f2f_currentness", assertion_id="assertion:two", disposition="refused", coverage_status="not_found_in_scoped_source", error_class="scoped_silence")]}]}
    value.update(changes)
    return FundraisingCohortPacket(**value)


def test_empty_template_is_explicitly_not_processed_not_evidence():
    template = FundraisingCohortPacket(packet_id="template:one", packet_status="not_processed", source_backed=False, fixture_only=False)
    ledger = build_cohort_packet_ledger(template)
    assert ledger.case_denominator == 0
    assert not ledger.is_external_quality_measurement


def test_packet_ledger_keeps_case_and_assertion_denominators_separate():
    ledger = build_cohort_packet_ledger(packet())
    assert ledger.case_denominator == 1
    assert ledger.assertion_denominators == {"practice": 1, "f2f_currentness": 1}
    assert ledger.error_classes == {"scoped_silence": 1}
    assert ledger.dispositions == {"retained": 1, "refused": 1}


def test_packet_refuses_fixture_only_or_incomplete_source_and_binding_evidence():
    with pytest.raises(ValidationError, match="cannot be fixture-only"):
        packet(fixture_only=True)
    with pytest.raises(ValidationError, match="retained source metadata"):
        packet(cases=[{**packet().cases[0].model_dump(), "sources": []}])
    with pytest.raises(ValidationError, match="assertion source_id"):
        packet(cases=[{**packet().cases[0].model_dump(), "assertions": [assertion(source_id="other")]}])
    with pytest.raises(ValidationError, match="source_locator"):
        packet(cases=[{**packet().cases[0].model_dump(), "sources": [{**source(), "source_locator": ""}]}])
    with pytest.raises(ValidationError, match="rights cleared"):
        packet(cases=[{**packet().cases[0].model_dump(), "sources": [{**source(), "rights_disposition": "blocked_by_rights"}]}])
    with pytest.raises(ValidationError, match="non-observed assertion cannot be retained"):
        packet(cases=[{**packet().cases[0].model_dump(), "assertions": [assertion(coverage_status="unavailable")]}])
    with pytest.raises(ValidationError, match="independently adjudicated"):
        packet(cases=[{**packet().cases[0].model_dump(), "assertions": [assertion(review_status="reviewed")]}])


def test_finance_and_linkage_assertions_fail_closed():
    case = packet().cases[0].model_dump()
    with pytest.raises(ValidationError, match="entity, period and basis"):
        packet(cases=[{**case, "assertions": [assertion("finance_compatibility")]}])
    finance = assertion("finance_compatibility", finance_entity_id="charity:one", finance_period_start=date(2024, 7, 1), finance_period_end=date(2025, 6, 30), finance_basis="accrual")
    linkage = assertion("money_linkage", assertion_id="link:one", same_source_exact_grain=False, disposition="refused", coverage_status="unavailable", error_class="exact_grain_linkage")
    ledger = build_cohort_packet_ledger(packet(cases=[{**case, "assertions": [finance, linkage]}]))
    assert ledger.error_classes == {"exact_grain_linkage": 1}
