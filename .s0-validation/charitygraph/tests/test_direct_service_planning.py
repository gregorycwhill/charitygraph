import json

from charitygraph.direct_service_planning import SECTIONS, plan_section_tasks


def _packet():
    return {"subject_id": "subject:" + "1" * 32, "scopes": [{"scope_id": "scope:" + "2" * 32, "scope_kind": "organisation", "label": "Example"}], "evidence": ["[S001:L0001] example"]}


def test_section_planning_is_independent_and_not_authorized():
    report = plan_section_tasks(_packet())
    assert report["provider_calls"] == 0
    assert report["authorization_state"] == "not_authorized"
    assert [row["section_number"] for row in report["tasks"]] == ["6", "11", "13"]
    assert len({row["task_id"] for row in report["tasks"]}) == 3
    assert len({row["run_id"] for row in report["tasks"]}) == 3
    assert len({row["task_run_id"] for row in report["tasks"]}) == 3
    assert all(row["physical_max_attempts"] == 1 for row in report["tasks"])
    assert all(len(row["ceiling_comparison"]) == 4 for row in report["tasks"])


def test_section_planning_uses_one_wire_schema_and_expected_types():
    report = plan_section_tasks(_packet())
    assert len({row["wire_schema_sha"] for row in report["tasks"]}) == 1
    for row in report["tasks"]:
        assert tuple(row["allowed_proposition_types"]) == SECTIONS[row["section_number"]][1]
        assert row["packet_sha"] == report["packet_sha"]
