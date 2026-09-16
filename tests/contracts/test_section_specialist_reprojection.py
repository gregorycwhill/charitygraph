from datetime import datetime, timezone
import pytest
from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.section_specialist_reprojection import SpecialistInput, project_specialist_observation, specialist_card_evidence

NOW=datetime(2026,9,17,tzinfo=timezone.utc); S="subject:"+"a"*64; C="scope:"+"b"*64; R="srcrec:"+"c"*64; L="evidence:"+"d"*64
def item(predicate="activity_observed", **kw):
    values=dict(predicate=predicate,subject_id=S,scope_id=C,coverage_state="supported",source_role="supporting",epistemic_basis="source_fact",evidence_locator_ids=("[x:p1]",),source_record_ids=(R,),lineage_ids=(L,),observation_time=ObservationTime(observed_at=NOW),detail="bounded retained fact")
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
def test_card_evidence_fails_closed_on_scope_and_lineage():
    value=item(); o=obs(value)
    with pytest.raises(ValueError,match="matching projected"):
        specialist_card_evidence(value,o.model_copy(update={"scope_id":"scope:"+"9"*64}))
    with pytest.raises(ValueError,match="matching lineage"):
        specialist_card_evidence(value,o.model_copy(update={"lineage":()}))
