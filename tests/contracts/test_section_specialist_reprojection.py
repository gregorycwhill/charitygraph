from datetime import datetime, timezone
import pytest
from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.section_specialist_reprojection import SpecialistInput, project_specialist_observation, specialist_card_evidence

NOW=datetime(2026,9,17,tzinfo=timezone.utc); S="subject:"+"a"*64; C="scope:"+"b"*64; R="srcrec:"+"c"*64; L="evidence:"+"d"*64
def item(predicate="activity_observed", **kw):
    values=dict(predicate=predicate,subject_id=S,scope_id=C,coverage_state="supported",source_role="supporting",epistemic_basis="source_fact",evidence_locator_ids=("[x:p1]",),source_record_ids=(R,),lineage_ids=(L,),observation_time=ObservationTime(observed_at=NOW),detail="bounded retained fact")
    if predicate in {"commitment_stated_observed", "claimed_implementation_observed", "observed_practice_observed", "verified_completion_observed"}:
        values.update(action="deliver service", object_or_result="the stated community program")
    values.update(kw); return SpecialistInput(**values)
def obs(value): return project_specialist_observation(value,record_id="observation:"+"f"*64,created_at=NOW,producer={"kind":"code","producer_id":"test"})
def test_activity_and_taxonomy_are_independent_and_v02_only():
    a=obs(item()); t=obs(item("assessed_classification_observed",epistemic_basis="governed_event",taxonomy_id="un-sdg",taxonomy_version="2015",concept_id="sdg:4",assignment_status="accepted",method="retained-review"))
    assert a.predicate.startswith("north_star_v02.section4") and t.predicate.startswith("north_star_v02.section19")
    assert "taxonomy_id" not in a.value and "activity" not in t.value
def test_source_reported_and_assessed_classification_do_not_collapse():
    with pytest.raises(ValueError,match="source_fact"):
        item("source_reported_classification_observed",epistemic_basis="governed_event",taxonomy_id="sdg",taxonomy_version="1",concept_id="1",assignment_status="accepted",method="source")
    with pytest.raises(ValueError,match="taxonomy fields"):
        item(taxonomy_id="sdg")
def test_commitment_is_not_implementation_or_completion():
    c=obs(item("commitment_stated_observed",epistemic_basis="source_interpretation")); i=obs(item("claimed_implementation_observed",epistemic_basis="source_interpretation")); v=obs(item("verified_completion_observed"))
    assert len({c.predicate,i.predicate,v.predicate})==3
def test_fundraising_practice_and_campaign_are_distinct_from_finance_and_dependency():
    practice=obs(item("fundraising_practice_observed")); campaign=obs(item("fundraising_campaign_observed"))
    assert practice.predicate.startswith("north_star_v02.section8")
    assert campaign.predicate.startswith("north_star_v02.section8")
    assert "finance" not in practice.value and "dependency" not in campaign.value
def test_card_evidence_fails_closed_on_scope_and_lineage():
    value=item(); o=obs(value)
    with pytest.raises(ValueError,match="matching projected"):
        specialist_card_evidence(value,o.model_copy(update={"scope_id":"scope:"+"9"*64}))
    with pytest.raises(ValueError,match="matching lineage"):
        specialist_card_evidence(value,o.model_copy(update={"lineage":()}))


@pytest.mark.parametrize("predicate,basis", [
    ("activity_observed", "source_fact"),
    ("fundraising_practice_observed", "source_fact"),
    ("fundraising_campaign_observed", "source_fact"),
    ("ethos_self_description_observed", "source_interpretation"),
    ("ethos_affiliation_observed", "source_fact"),
    ("commitment_stated_observed", "source_interpretation"),
    ("claimed_implementation_observed", "source_interpretation"),
    ("observed_practice_observed", "source_fact"),
    ("verified_completion_observed", "source_fact"),
])
def test_supported_specialist_positive_requires_substantive_what(predicate,basis):
    with pytest.raises(ValueError, match="substantive detail"):
        item(predicate, epistemic_basis=basis, detail=None)


@pytest.mark.parametrize("status", ["candidate", "rejected", "abstained", "superseded"])
def test_non_effective_taxonomy_history_stays_traceable_but_cannot_be_card_content(status):
    value=item("assessed_classification_observed",epistemic_basis="governed_event",taxonomy_id="un-sdg",taxonomy_version="2015",concept_id="sdg:4",assignment_status=status,method="retained-review")
    observed=obs(value)
    assert observed.outcome_state == "unknown"
    assert observed.value["effective_assignment"] is False
    with pytest.raises(ValueError,match="non-effective"):
        specialist_card_evidence(value,observed)


def test_accepted_and_narrowed_taxonomy_assignments_are_effective_only_at_stated_concept_scope():
    for status, concept in (("accepted", "sdg:4"), ("narrowed", "sdg:4.1")):
        value=item("assessed_classification_observed",epistemic_basis="governed_event",taxonomy_id="un-sdg",taxonomy_version="2015",concept_id=concept,assignment_status=status,method="retained-review")
        observed=obs(value)
        assert observed.outcome_state == "supported"
        assert observed.value["effective_assignment"] is True
        assert specialist_card_evidence(value,observed).section_ids == (19,)


def test_discovery_signal_is_derived_and_never_card_evidence():
    value=item("discovery_signal_observed",epistemic_basis="derived_signal",method="embedding-v1",signal_type="similarity",query_or_profile="sdg-profile-v1",upstream_artifact_ids=("document:retained",))
    observed=obs(value)
    assert observed.outcome_state == "unknown"
    assert observed.value["epistemic_basis"] == "derived_signal"
    with pytest.raises(ValueError,match="retrieval inputs"):
        specialist_card_evidence(value,observed)
    with pytest.raises(ValueError,match="derived_signal"):
        item("discovery_signal_observed",epistemic_basis="source_fact",method="embedding-v1",signal_type="similarity",query_or_profile="sdg-profile-v1",upstream_artifact_ids=("document:retained",))


def test_created_at_cannot_be_used_as_specialist_observation_time():
    value=item(coverage_state="unknown",observation_time=None)
    with pytest.raises(ValueError,match="created_at"):
        obs(value)


@pytest.mark.parametrize("predicate,basis", [
    ("commitment_stated_observed", "source_interpretation"),
    ("claimed_implementation_observed", "source_interpretation"),
    ("observed_practice_observed", "source_fact"),
    ("verified_completion_observed", "source_fact"),
])
def test_commitment_lifecycle_requires_typed_action_and_object(predicate,basis):
    with pytest.raises(ValueError, match="action and object_or_result"):
        item(predicate, epistemic_basis=basis, action=None)
    with pytest.raises(ValueError, match="action and object_or_result"):
        item(predicate, epistemic_basis=basis, object_or_result=None)
