from datetime import datetime, timezone
import pytest

from charitygraph.contracts.knowledge import ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import IntegratedGraph, NORTH_STAR_PROJECTION_V0_1, NORTH_STAR_PROJECTION_VNEXT, project_subject
from charitygraph.section_c5_reprojection import SectionC5Input, project_section_c5_observation, section_c5_card_evidence, section_c5_missingness

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
SUBJECT = "subject:" + "a" * 64
SCOPE = "scope:" + "b" * 64
SRC = "srcrec:" + "c" * 64
LINEAGE = "evidence:" + "d" * 64

def subject():
    return SubjectRecord(record_id="subjectrecord:" + "e" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"test"}, subject_id=SUBJECT, subject_kind="organisation", lifecycle_status="active", identity_authority_refs=({"artifact_id": SRC, "content_hash":"0" * 64, "schema":{"schema_id":"urn:charitygraph:builder:schema:test:1", "schema_version":"1"}},), identity_policy_id="test")

def scope():
    return ScopeRecord(record_id=SCOPE, created_at=NOW, producer={"kind":"code", "producer_id":"test"}, subject_id=SUBJECT, scope_kind="organisation")

def item(predicate="identity_role_observed", **updates):
    values = dict(predicate=predicate, subject_id=SUBJECT, scope_id=SCOPE, coverage_state="supported", source_role="supporting", epistemic_basis="source_fact", evidence_locator_ids=("[ARC:p2]",), source_record_ids=(SRC,), lineage_ids=(LINEAGE,), observation_time=ObservationTime(observed_at=NOW), identity_role="operating_unit")
    values.update(updates)
    return SectionC5Input(**values)

def graph(value):
    observed = project_section_c5_observation(value, record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"test"})
    return observed, IntegratedGraph(subjects=(subject(),), scopes=(scope(),), observations=(observed,), evidence=(section_c5_card_evidence(value, observed),))

@pytest.mark.parametrize("predicate,updates,section", [
    ("identity_role_observed", {"identity_role":"operating_unit"}, 1),
    ("population_role_observed", {"identity_role":None,"population_role":"served","value":2605}, 5),
    ("geography_role_observed", {"identity_role":None,"geography_role":"observed_reach","detail":"Victoria"}, 5),
    ("governance_role_observed", {"identity_role":None,"governance_role":"board_member"}, 9),
    ("workforce_measure_observed", {"identity_role":None,"workforce_role":"volunteer","workforce_measure":"headcount","value":30}, 10),
    ("historical_event_observed", {"identity_role":None,"event_type":"milestone","detail":"dated report event"}, 17),
    ("provenance_event_observed", {"identity_role":None,"provenance_event":"source_supersession","detail":"source explicitly supersedes prior edition"}, 20),
])
def test_atomic_roles_project_only_to_their_v02_section(predicate, updates, section):
    observed, value = graph(item(predicate, **updates))
    current = {x["section_id"]: x for x in project_subject(value, SUBJECT, projection_contract=NORTH_STAR_PROJECTION_VNEXT)["sections"]}
    old = {x["section_id"]: x for x in project_subject(value, SUBJECT, projection_contract=NORTH_STAR_PROJECTION_V0_1)["sections"]}
    assert current[section]["observation_ids"] == [observed.record_id]
    assert all(observed.record_id not in row["observation_ids"] for row in old.values())

def test_roles_cannot_collapse_or_leak():
    with pytest.raises(ValueError, match="limited"):
        item("identity_role_observed", identity_role="operating_unit", population_role="served")
    with pytest.raises(ValueError, match="limited"):
        item("workforce_measure_observed", identity_role=None, workforce_role="mixed", workforce_measure="headcount", value=20, geography_role="delivery")
    with pytest.raises(ValueError, match="limited"):
        item("population_role_observed", identity_role=None, population_role="served", geography_role="delivery")
    with pytest.raises(ValueError, match="limited"):
        item("geography_role_observed", identity_role=None, geography_role="delivery", population_role="served")

def test_coverage_preserves_unknown_and_rejects_duplicate_explicit_inputs():
    coverage = section_c5_missingness(subject_id=SUBJECT, section_id=16, coverage_state="not_reviewed")
    assert coverage.state == "NOT_REVIEWED"
    with pytest.raises(ValueError, match="non-positive"):
        section_c5_missingness(subject_id=SUBJECT, section_id=16, coverage_state="asserted_none")
    with pytest.raises(ValueError, match="one explicit coverage"):
        IntegratedGraph(subjects=(subject(),), scopes=(scope(),), observations=(), evidence=(), coverage_inputs=(coverage, coverage))

def test_newer_or_historical_fact_is_not_implicitly_correction_or_current_state():
    with pytest.raises(ValueError, match="requires"):
        item("provenance_event_observed", identity_role=None, provenance_event="source_correction", detail=None)
    historic = item("historical_event_observed", identity_role=None, event_type="crisis", detail="2020 cancellation")
    assert graph(historic)[0].value["event_type"] == "crisis"

def test_population_and_geography_are_independent_atomic_section5_observations():
    population = item("population_role_observed", identity_role=None, population_role="served", value=2605)
    geography = item("geography_role_observed", identity_role=None, geography_role="delivery", detail="Victoria")
    population_observation = project_section_c5_observation(population, record_id="observation:" + "1" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"test"})
    geography_observation = project_section_c5_observation(geography, record_id="observation:" + "2" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"test"})
    value = IntegratedGraph(subjects=(subject(),), scopes=(scope(),), observations=(population_observation, geography_observation), evidence=(section_c5_card_evidence(population, population_observation), section_c5_card_evidence(geography, geography_observation)))
    section = project_subject(value, SUBJECT, projection_contract=NORTH_STAR_PROJECTION_VNEXT)["sections"][4]
    assert set(section["observation_ids"]) == {population_observation.record_id, geography_observation.record_id}
    assert "geography_role" not in population_observation.value
    assert "population_role" not in geography_observation.value

@pytest.mark.parametrize("change,match", [
    ({"predicate":"north_star_v02.section1.other"}, "matching projected"),
    ({"source_record_ids": ("srcrec:" + "9" * 64,)}, "matching projected"),
    ({"evidence_locator_ids": ("[ARC:p99]",)}, "matching projected"),
    ({"observation_time": ObservationTime(observed_at=datetime(2026, 9, 15, tzinfo=timezone.utc))}, "matching projected"),
    ({"scope_id":"scope:" + "9" * 64}, "matching projected"),
    ({"lineage": ()}, "matching observation lineage"),
])
def test_card_evidence_fails_closed_for_every_bound_observation_field(change, match):
    value = item()
    observed = project_section_c5_observation(value, record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"test"})
    with pytest.raises(ValueError, match=match):
        section_c5_card_evidence(value, observed.model_copy(update=change))

def test_epistemic_basis_keeps_history_interpretation_distinct_from_event_fact():
    fact = item("historical_event_observed", identity_role=None, event_type="milestone", detail="Founded in 1984")
    interpretation = item("historical_interpretation_observed", identity_role=None, event_type="milestone", detail="The source retrospectively characterises this as a turning point", epistemic_basis="source_interpretation")
    assert graph(fact)[0].value["epistemic_basis"] == "source_fact"
    assert graph(interpretation)[0].value["epistemic_basis"] == "source_interpretation"
    with pytest.raises(ValueError, match="requires epistemic_basis source_interpretation"):
        item("historical_interpretation_observed", identity_role=None, event_type="milestone", detail="interpretation")
    with pytest.raises(ValueError, match="requires epistemic_basis governed_event"):
        item("provenance_event_observed", identity_role=None, provenance_event="charitygraph_correction", detail="decision", epistemic_basis="source_fact")
