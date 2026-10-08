"""Executable CG-344 certification checks over the frozen 342 corpus."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.ethos_history import (EthosObservation, NotableEvent,
    notable_event_candidate_id, project_ethos_observation, project_notable_event,
    v03_missingness)

ROOT = Path(__file__).parents[2]
CORPUS = json.loads((ROOT / "tests/fixtures/reality_corpus_ethos_notability_v1.json").read_text())
MATRIX = json.loads((ROOT / "certification/ethos-notability-v1-certification-matrix.json").read_text())
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
S, SC, R, L = "subject:" + "a" * 64, "scope:" + "b" * 64, "srcrec:" + "c" * 64, "lineage:" + "d" * 64

def _ethos(case):
    return EthosObservation(subject_id=S, scope_id=SC, epistemic_role=case.get("role", "self_described"),
        descriptor=case.get("descriptor", "Source-faithful bounded descriptor"), source_role="supporting",
        evidence_locator_ids=("[corpus]",), source_record_ids=(R,), lineage_ids=(L,),
        observation_time=ObservationTime(observed_at=NOW), qualification=case.get("qualification"))

def _event(case):
    values = dict(subject_id=S, scope_id=SC, event_family=case.get("family", "institutional_milestone"),
        statement=case.get("statement", "Source-faithful bounded event"), event_date=date(2020, 1, 1),
        source_roles=tuple(case.get("source_roles", ["supporting"])), evidence_locator_ids=("[corpus]",),
        source_record_ids=(R,), lineage_ids=(L,), observation_time=ObservationTime(observed_at=NOW),
        related_subject_id=case.get("related_subject_id"), relationship_kind=case.get("relationship_kind"),
        procedural_status=case.get("procedural_status"))
    values["candidate_id"] = notable_event_candidate_id(subject_id=S, scope_id=SC,
        event_family=values["event_family"], event_date=values["event_date"],
        statement=values["statement"], related_subject_id=values["related_subject_id"])
    return NotableEvent(**values)

def test_frozen_identity_and_matrix_agree():
    # The exact frozen-byte hash belongs to the Data Git blob (not this Builder
    # adapter fixture, whose formatting is intentionally independent).
    assert MATRIX["corpus_sha256"] == "f49735791652d3a65ab627138662653c76a615496f0f154a325bf8729d662c1b"
    assert MATRIX["corpus_id"] == CORPUS["corpus_id"]
    assert MATRIX["corpus_version"] == CORPUS["version"]
    assert [row["case_id"] for row in MATRIX["cases"]] == [case["id"] for case in CORPUS["cases"]]

@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["id"])
def test_each_gold_outcome_is_observed_through_actual_adapter(case):
    if case["outcome"] == "missing":
        observed = v03_missingness(subject_id=S, section_id=17, state="not_found")
        assert (observed.state, observed.basis) == ("NOT_FOUND", "unknown_history")
    elif case["outcome"] == "rejected":
        # A prohibited inference is not an EthosObservation field: strict parsing rejects it.
        payload = _ethos(case).model_dump()
        payload[case["forbidden"]] = "prohibited"
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            EthosObservation.model_validate(payload)
    elif case["section"] == 15:
        observed = project_ethos_observation(_ethos(case), record_id="observation:" + "e" * 64,
            created_at=NOW, producer={"kind": "code", "producer_id": "cg-344"})
        assert observed.value["epistemic_role"] == case["role"]
    else:
        item = _event(case)
        observed = project_notable_event(item, record_id="observation:" + "e" * 64,
            created_at=NOW, producer={"kind": "code", "producer_id": "cg-344"})
        assert observed.value["candidate_id"] == item.candidate_id

def test_certified_dedupe_and_section_boundary_guards():
    milestone = next(c for c in CORPUS["cases"] if c["id"] == "RC-14")
    assert _event(milestone).candidate_id == _event({**milestone, "source_roles": ["supporting"]}).candidate_id
    inquiry = project_notable_event(_event(next(c for c in CORPUS["cases"] if c["id"] == "RC-13")),
        record_id="observation:" + "f" * 64, created_at=NOW, producer={"kind": "code", "producer_id": "cg-344"})
    assert inquiry.value["procedural_status"] == "reported"
    assert "adverse_finding" not in inquiry.value
