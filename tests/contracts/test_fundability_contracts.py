from datetime import datetime, timezone
import pytest
from charitygraph.contracts.common import ProducerRef
from charitygraph.contracts.fundability import FundabilityEvidenceRef, FundabilityProposition, project_observation
from charitygraph.contracts.knowledge import ObservationTime, ScopeRecord

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
SUBJECT = "subject:" + "a" * 32
SCOPE = "scope:" + "b" * 32
EVIDENCE = FundabilityEvidenceRef(locator="retained:donate#program-x", source_record_id="srcrec:donate-x", source_role="first_party", lineage_id="evidence:donate-x")
def p(predicate="designation_available_observed", **kw):
    values=dict(predicate=predicate, giving_context_id="giving:x-2026", accepting_subject_id=SUBJECT, destination_source_label="Program X", destination_scope_id=SCOPE, destination_resolution="resolved", audience="public", designation_type="source_stated_designation", status="current", coverage_state="supported", observation_time=ObservationTime(observed_at=NOW), evidence=(EVIDENCE,), detail="retained statement")
    values.update(kw); return FundabilityProposition(**values)
def test_program_is_not_an_offer_and_positive_requires_evidence():
    assert p().destination_scope_id == SCOPE
    with pytest.raises(ValueError): p(evidence=())
def test_not_found_is_not_explicit_unavailability():
    assert p(destination_scope_id=None, destination_resolution="unresolved", coverage_state="not_found_in_reviewed_public_giving_channels", evidence=()).coverage_state == "not_found_in_reviewed_public_giving_channels"
    with pytest.raises(ValueError): p(predicate="designation_explicitly_unavailable_observed", coverage_state="not_found_in_reviewed_public_giving_channels")
def test_third_party_endpoint_requires_official_provenance():
    with pytest.raises(ValueError): p(predicate="action_endpoint_observed", endpoint_type="official_third_party_form", endpoint_url="https://third.example", detail="route")
    third=EVIDENCE.model_copy(update={"source_role":"officially_linked_third_party"})
    assert p(predicate="action_endpoint_observed", endpoint_type="official_third_party_form", endpoint_url="https://third.example", evidence=(third,), detail="route").endpoint_type == "official_third_party_form"
def test_unresolved_destination_cannot_join_scope_or_finance():
    with pytest.raises(ValueError): p(destination_resolution="unresolved")
def test_historical_offer_and_current_program_are_distinct_and_no_finance_is_created():
    observed=project_observation(p(status="historical"), record_id="observation:"+"c"*64, subject_id=SUBJECT, created_at=NOW, producer=ProducerRef(kind="code", producer_id="test"))
    assert observed.predicate == "fundability.designation_available_observed" and "allocation" not in observed.value
def test_one_form_can_share_a_group_without_inheriting_destination_terms():
    assert p(giving_offer_group_id="form:annual-giving").giving_offer_group_id == "form:annual-giving"
def test_scope_vnext_supports_fund_and_appeal_without_subject_promotion():
    common=dict(subject_id=SUBJECT, created_at=NOW, producer=ProducerRef(kind="code", producer_id="test"))
    assert ScopeRecord(record_id="scope:"+"d"*32, scope_kind="fund", **common).scope_kind == "fund"
    assert ScopeRecord(record_id="scope:"+"e"*32, scope_kind="appeal", **common).scope_kind == "appeal"
