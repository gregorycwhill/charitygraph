from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_native_induction_v3_gardener import ATTACH_SCHEMA, DISC_SCHEMA, TEND_SCHEMA, apply_operations, strict_schema_errors


def _concept(identifier: str, parent: str | None = None) -> dict:
    return {"concept_id": identifier, "preferred_label": identifier, "definition": identifier, "inclusion_boundary": identifier, "exclusion_boundary": identifier, "parent_concept_id": parent, "supporting_observation_ids": ["o1"], "organisations": ["org"], "active": True, "lineage": []}


def _operation(action: str, predecessors: list[str], successors: list[str] | None = None, **changes: object) -> dict:
    result = {"action": action, "predecessor_concept_ids": predecessors, "successor_concept_ids": successors or [], "rationale": "test", "new_preferred_label": None, "new_definition": None, "new_inclusion_boundary": None, "new_exclusion_boundary": None, "new_parent_concept_id": None, "successor_concept_specs": [], "supporting_observation_ids": ["o1"]}
    result.update(changes)
    return result


def test_v3_strict_schemas_are_provider_shape_complete() -> None:
    assert strict_schema_errors(TEND_SCHEMA) == []
    assert strict_schema_errors(ATTACH_SCHEMA) == []
    assert strict_schema_errors(DISC_SCHEMA) == []


def test_apply_rename_and_quarantine_conflicting_operation() -> None:
    catalogue = {"a": _concept("a")}
    first = _operation("rename", ["a"], new_preferred_label="renamed")
    conflicting = _operation("redefine", ["a"], new_definition="different")
    result, bad, counts = apply_operations(catalogue, [first, conflicting], {"o1"}, "test")
    assert result["a"]["preferred_label"] == "renamed"
    assert result["a"]["definition"] == "a"
    assert counts["rename"] == 1
    assert bad[0]["reason"] == "conflicting_duplicate_operation"


def test_apply_split_preserves_predecessor_lineage() -> None:
    catalogue = {"a": _concept("a")}
    specs = [{"concept_id": "b", "preferred_label": "b", "definition": "b", "inclusion_boundary": "b", "exclusion_boundary": "b", "parent_concept_id": None, "supporting_observation_ids": ["o1"]}, {"concept_id": "c", "preferred_label": "c", "definition": "c", "inclusion_boundary": "c", "exclusion_boundary": "c", "parent_concept_id": None, "supporting_observation_ids": ["o1"]}]
    operation = _operation("split", ["a"], ["b", "c"], successor_concept_specs=specs)
    result, bad, counts = apply_operations(catalogue, [operation], {"o1"}, "test")
    assert not bad and counts["split"] == 1
    assert result["a"]["active"] is False
    assert result["a"]["deprecated_by"] == ["b", "c"]
    assert result["b"]["active"] is True and result["c"]["active"] is True


def test_merge_keeps_existing_successor_active_and_reparents_direct_children() -> None:
    catalogue = {"a": _concept("a"), "b": _concept("b"), "child": _concept("child", "b")}
    operation = _operation("merge", ["a", "b"], ["a"])
    result, bad, counts = apply_operations(catalogue, [operation], {"o1"}, "test")
    assert not bad and counts["merge"] == 1
    assert result["a"]["active"] is True
    assert result["b"]["active"] is False
    assert result["child"]["parent_concept_id"] == "a"


def test_parent_cycle_is_quarantined() -> None:
    catalogue = {"a": _concept("a"), "b": _concept("b", "a")}
    operation = _operation("reparent", ["a"], new_parent_concept_id="b")
    result, bad, counts = apply_operations(catalogue, [operation], {"o1"}, "test")
    assert result["a"]["parent_concept_id"] is None
    assert counts == {}
    assert bad[0]["reason"] == "parent_cycle"
