from datetime import date, datetime, timezone

import pytest

from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.ethos_history import (
    EthosObservation, NotableEvent, notable_event_candidate_id, project_ethos_observation,
    project_notable_event, v03_card_evidence, v03_missingness,
)
from charitygraph.integrated_card import NORTH_STAR_PROJECTION_V0_2, NORTH_STAR_PROJECTION_V0_3

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
S, OTHER, SCOPE = "subject:" + "a" * 64, "subject:" + "b" * 64, "scope:" + "c" * 64
R, L = "srcrec:" + "d" * 64, "evidence:" + "e" * 64


def ethos(role="self_described", **changes):
    item = dict(subject_id=S, scope_id=SCOPE, epistemic_role=role, descriptor="Source-faithful institutional statement", source_role="supporting", evidence_locator_ids=("[page:1]",), source_record_ids=(R,), lineage_ids=(L,), observation_time=ObservationTime(observed_at=NOW))
    item.update(changes)
    return EthosObservation(**item)


def event(family="founding", **changes):
    values = dict(subject_id=S, scope_id=SCOPE, event_family=family, statement="Organisation was founded in 1982", event_date=date(1982, 1, 1), source_roles=("supporting",), evidence_locator_ids=("[page:2]",), source_record_ids=(R,), lineage_ids=(L,), observation_time=ObservationTime(observed_at=NOW))
    values.update(changes)
    values["candidate_id"] = notable_event_candidate_id(subject_id=values["subject_id"], scope_id=values["scope_id"], event_family=values["event_family"], event_date=values.get("event_date"), statement=values["statement"], related_subject_id=values.get("related_subject_id"))
    return NotableEvent(**values)


def test_v02_and_v03_are_explicit_distinct_projection_identities():
    assert NORTH_STAR_PROJECTION_V0_2.projection_contract_id == "north-star-v0.2"
    assert NORTH_STAR_PROJECTION_V0_3.projection_contract_id == "north-star-v0.3"
    assert NORTH_STAR_PROJECTION_V0_2.section_titles[15] == NORTH_STAR_PROJECTION_V0_3.section_titles[15]
    assert NORTH_STAR_PROJECTION_V0_2 is not NORTH_STAR_PROJECTION_V0_3


@pytest.mark.parametrize("role", ["self_described", "formal_affiliation", "external_characterisation", "historical_orientation"])
def test_ethos_roles_are_first_class_and_source_faithful(role):
    observed = project_ethos_observation(ethos(role), record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind": "code", "producer_id": "test"})
    assert observed.value["epistemic_role"] == role
    assert observed.predicate.startswith("north_star_v03.section15")
    assert v03_card_evidence(observed, section_id=15).projection_contract_id == "north-star-v0.3"


def test_event_contract_carries_dates_sources_scope_lineage_and_deduplicates():
    first, repeated = event(), event(source_roles=("discovery", "supporting"))
    assert first.candidate_id == repeated.candidate_id
    observed = project_notable_event(first, record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind": "code", "producer_id": "test"})
    assert observed.value["event_date"] == date(1982, 1, 1)
    assert observed.value["candidate_id"] == first.candidate_id
    assert v03_card_evidence(observed, section_id=17).section_ids == (17,)


def test_lineage_and_inquiry_are_explicit_not_transferred_or_adverse_findings():
    with pytest.raises(ValueError, match="related subject"):
        event("succession")
    succession = event("succession", statement="Former body succeeded by current body", related_subject_id=OTHER, relationship_kind="predecessor")
    assert succession.related_subject_id == OTHER
    with pytest.raises(ValueError, match="procedural_status"):
        event("public_inquiry_or_review")
    inquiry = event("public_inquiry_or_review", statement="Public review occurred", procedural_status="reported")
    assert inquiry.procedural_status == "reported"


@pytest.mark.parametrize("forbidden, model, injected", [
    ("beneficiary identity does not establish ethos", EthosObservation, "beneficiary_identity"),
    ("parent/network ethos does not transfer to affiliate", EthosObservation, "parent_ethos"),
    ("historical founding does not establish current affiliation", EthosObservation, "current_affiliation"),
    ("commitment does not establish practice", EthosObservation, "observed_practice"),
    ("ethos does not imply service participation rules", EthosObservation, "participation_rule"),
    ("Wikimedia absence does not imply no notable history", NotableEvent, "wikimedia_absence"),
    ("award does not imply quality", NotableEvent, "quality"),
    ("inquiry occurrence does not imply adverse finding", NotableEvent, "adverse_finding"),
    ("allegation does not imply finding", NotableEvent, "finding"),
    ("predecessor history does not automatically transfer to successor", NotableEvent, "transferred_to_successor"),
    ("parent controversy does not transfer to affiliate", NotableEvent, "parent_controversy"),
    ("missing evidence does not imply secular neutral or good reputation", EthosObservation, "reputation"),
])
def test_forbidden_inferences_have_no_adapter_path(forbidden, model, injected):
    # Strict models reject each attempted cross-section/quality/reputation inference.
    exemplar = ethos().model_dump() if model is EthosObservation else event().model_dump()
    exemplar[injected] = forbidden
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        model.model_validate(exemplar)


def test_positive_controls_and_missingness_are_scoped_not_absence():
    assert ethos("formal_affiliation").epistemic_role == "formal_affiliation"
    assert ethos("historical_orientation").epistemic_role == "historical_orientation"
    assert event("institutional_milestone").event_family == "institutional_milestone"
    unknown = v03_missingness(subject_id=S, section_id=17, state="not_found")
    assert unknown.state == "NOT_FOUND" and unknown.basis == "unknown_history"
