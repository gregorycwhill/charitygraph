"""Frozen adversarial corpus exercised through the real v0.3 adapters."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.ethos_history import EthosObservation, NotableEvent, notable_event_candidate_id, project_ethos_observation, project_notable_event, v03_missingness

CORPUS = json.loads((Path(__file__).parents[1] / "fixtures" / "reality_corpus_ethos_notability_v1.json").read_text())
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
S, SC, R, L = "subject:" + "a" * 64, "scope:" + "b" * 64, "srcrec:" + "c" * 64, "lineage:" + "d" * 64

def _ethos(case):
    return EthosObservation(subject_id=S, scope_id=SC, epistemic_role=case.get("role", "self_described"), descriptor="Source-faithful corpus descriptor", source_role="supporting", evidence_locator_ids=("[corpus]",), source_record_ids=(R,), lineage_ids=(L,), observation_time=ObservationTime(observed_at=NOW))

def _event(case):
    values = dict(subject_id=S, scope_id=SC, event_family=case.get("family", "institutional_milestone"), statement="Source-faithful corpus event", event_date=date(2020, 1, 1), source_roles=tuple(case.get("source_roles", ["supporting"])), evidence_locator_ids=("[corpus]",), source_record_ids=(R,), lineage_ids=(L,), observation_time=ObservationTime(observed_at=NOW), related_subject_id=case.get("related_subject_id"), relationship_kind=case.get("relationship_kind"), procedural_status=case.get("procedural_status"))
    values["candidate_id"] = notable_event_candidate_id(subject_id=S, scope_id=SC, event_family=values["event_family"], event_date=values["event_date"], statement=values["statement"], related_subject_id=values["related_subject_id"])
    return NotableEvent(**values)

def test_frozen_corpus_shape_and_real_synthetic_split():
    cases = CORPUS["cases"]
    assert CORPUS["version"] == "1.0.0" and len(cases) == 14
    assert sum(c["kind"] == "real" for c in cases) == 3
    assert sum(c["kind"] == "synthetic" for c in cases) == 11
    assert {c["id"] for c in cases} == {f"RC-{n:02d}" for n in range(1, 15)}

@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["id"])
def test_corpus_gold_outcomes_use_actual_contracts(case):
    if case["outcome"] == "missing":
        missing = v03_missingness(subject_id=S, section_id=17, state="not_found")
        assert missing.state == "NOT_FOUND" and missing.basis == "unknown_history"
    elif case["outcome"] == "rejected":
        payload = _ethos(case).model_dump()
        payload[case["forbidden"]] = "prohibited corpus inference"
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            EthosObservation.model_validate(payload)
    elif case["section"] == 15:
        item = _ethos(case)
        projected = project_ethos_observation(item, record_id="observation:" + "e" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"reality-corpus"})
        assert projected.value["epistemic_role"] == case["role"]
    else:
        item = _event(case)
        projected = project_notable_event(item, record_id="observation:" + "e" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"reality-corpus"})
        assert projected.value["candidate_id"] == item.candidate_id

def test_multisource_event_deduplication_and_section_boundaries_are_executable():
    case = next(c for c in CORPUS["cases"] if c["id"] == "RC-14")
    one, two = _event(case), _event({**case, "source_roles": ["supporting"]})
    assert one.candidate_id == two.candidate_id
    inquiry = _event(next(c for c in CORPUS["cases"] if c["id"] == "RC-13"))
    assert inquiry.value if False else inquiry.procedural_status == "reported"
    assert "adverse_finding" not in project_notable_event(inquiry, record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind":"code", "producer_id":"reality-corpus"}).value
