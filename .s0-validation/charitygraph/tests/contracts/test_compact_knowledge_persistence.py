from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from charitygraph.compact_knowledge import CompactKnowledgeOutputV02, COMPACT_V02_SCHEMA
from charitygraph.compact_knowledge_persistence import adapt_compact_v02

SUBJECT = "subject:" + "a" * 32
WHEN = datetime(2026, 9, 2, tzinfo=timezone.utc)
MAP = {("S001", "L0001"): "evidence:" + "b" * 32}
SRC = {"S001": "srcrec:" + "c" * 32}


def atom(**overrides):
    value = {"proposition": "A supported fact", "scope_kind": "subject", "scope_label": None, "effective_from": None, "effective_to": None, "reporting_period": None, "epistemic_status": "supported", "evidence": ({"source": "S001", "locator": "L0001", "role": "supporting"},), "qualifications": ()}
    value.update(overrides)
    return value


def test_v02_temporal_forms_and_scopes_map_to_existing_observation():
    output = CompactKnowledgeOutputV02(atoms=(atom(), atom(scope_kind="named_program_or_service", scope_label="Program", effective_from="2024-01-01"), atom(effective_from="2024-01-01", effective_to="2024-12-31"), atom(reporting_period="year ended 30 June 2025"), atom(epistemic_status="explicit_absence")))
    scopes, observations = adapt_compact_v02(output, subject_id=SUBJECT, observed_at=WHEN, model_result_id="modelresult:" + "d" * 32, task_id="modeltask:" + "e" * 32, evidence_locator_map=MAP, source_record_map=SRC)
    assert len(scopes) == 1 and len(observations) == 5
    assert observations[1].observation_time.effective_from
    assert observations[2].observation_time.effective_to
    assert observations[3].observation_time.reporting_period
    assert observations[4].value["epistemic_status"] == "explicit_absence"


def test_malformed_iso_temporal_value_is_rejected_without_repair():
    with pytest.raises(ValueError):
        adapt_compact_v02({"atoms": [atom(effective_from="2013-12-31 onward")]}, subject_id=SUBJECT, observed_at=WHEN, model_result_id="modelresult:" + "d" * 32, task_id="modeltask:" + "e" * 32, evidence_locator_map=MAP, source_record_map=SRC)


def test_evidence_and_lineage_are_preserved_and_replay_is_deterministic():
    kwargs = dict(subject_id=SUBJECT, observed_at=WHEN, model_result_id="modelresult:" + "d" * 32, task_id="modeltask:" + "e" * 32, evidence_locator_map=MAP, source_record_map=SRC)
    first = adapt_compact_v02({"atoms": [atom()]}, **kwargs)
    second = adapt_compact_v02({"atoms": [atom()]}, **kwargs)
    assert first[1][0].record_id == second[1][0].record_id
    assert first[1][0].evidence_locator_ids == (MAP[("S001", "L0001")],)
    assert {edge.target_artifact_id for edge in first[1][0].lineage} == {kwargs["model_result_id"], kwargs["task_id"]}


def test_v02_schema_has_temporal_fields():
    props = COMPACT_V02_SCHEMA["$defs"]["CompactAtomV02"]["properties"]
    assert set(("effective_from", "effective_to", "reporting_period")) <= set(props)

def test_v02_schema_enforces_exact_calendar_dates_but_periods_remain_coarse():
    CompactKnowledgeOutputV02(atoms=(atom(effective_from="2020-11-30"), atom(reporting_period="2020"), atom(reporting_period="2020-11")))
    for value in ("2020", "2020-11", "2020-02-31", "2020-11-30 onward"):
        with pytest.raises(ValueError):
            CompactKnowledgeOutputV02(atoms=(atom(effective_from=value),))
    assert "pattern" in COMPACT_V02_SCHEMA["$defs"]["CompactAtomV02"]["properties"]["effective_from"]["anyOf"][0]
