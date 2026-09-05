import json
import pytest

from charitygraph.native_lifecycle_harness import (
    ACTIONS, FACETS, Catalogue, digest, run_synthetic_lifecycle,
    schemas, validate_attachments, validate_schema_shapes,
)


def test_all_five_schemas_are_strict():
    assert set(schemas()) == {"quality", "discovery", "gardener", "attachment", "extraction"}
    assert all(not validate_schema_shapes(v) for v in schemas().values())


def test_recursive_schema_rejects_missing_additional_properties_guard():
    bad = {"type": "object", "required": [], "properties": {}}
    assert validate_schema_shapes(bad) == [":additionalProperties"]


def test_catalogue_rejects_unknown_support():
    c = Catalogue(FACETS[0], {"OVL-1"})
    with pytest.raises(ValueError): c.add("P1", "x", ["OVL-2"])


def test_catalogue_rejects_duplicate_concept():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"])
    with pytest.raises(ValueError): c.add("P1", "y", ["OVL-1"])


def test_retain_is_append_only():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"]); before = digest(c.items)
    c.mutate("retain", ["P1"]); assert digest(c.items) == before


def test_rename_and_redefine_change_semantics():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"]); c.mutate("rename", ["P1"])
    assert c.items["P1"]["label"].endswith("renamed"); c.mutate("redefine", ["P1"])
    assert c.items["P1"]["definition"] == "redefined"


def test_reparent_remove():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"]); c.add("P2", "y", ["OVL-1"], "P1")
    c.mutate("reparent", ["P2"], parent_mode="remove"); assert c.items["P2"]["parent"] is None


def test_reparent_rejects_self():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"])
    with pytest.raises(ValueError): c.mutate("reparent", ["P1"], parent_mode="set", parent="P1")


def test_reparent_rejects_cross_facet():
    a = Catalogue(FACETS[0], {"OVL-1"}); b = Catalogue(FACETS[1], {"OVL-1"})
    a.add("P1", "x", ["OVL-1"]); b.add("P2", "y", ["OVL-1"])
    with pytest.raises(ValueError): b.mutate("reparent", ["P2"], parent_mode="set", parent="P1")


def test_merge_deprecates_predecessors_and_records_lineage():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"]); c.add("P2", "y", ["OVL-1"])
    c.mutate("merge", ["P1", "P2"], ({"label":"m", "definition":"d", "support":[]},))
    assert not c.items["P1"]["active"] and any(v["predecessors"] == ["P1", "P2"] for v in c.items.values())


def test_split_records_predecessor_lineage():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"])
    c.mutate("split", ["P1"], ({"label":"a", "definition":"d", "support":[]}, {"label":"b", "definition":"d", "support":[]}))
    assert sum(1 for v in c.items.values() if v["predecessors"]) == 2


def test_deprecate_and_dispose_preserve_history():
    c = Catalogue(FACETS[0], {"OVL-1"}); c.add("P1", "x", ["OVL-1"]); c.mutate("deprecate", ["P1"]); c.mutate("dispose_non_native", ["P1"])
    assert not c.items["P1"]["active"] and c.items["P1"]["history"] == ["deprecate", "dispose_non_native"]


def test_attachment_exact_coverage_and_zero_one_multi():
    assert validate_attachments(["O1", "O2", "O3"], {"P1"}, [
        {"overlay_key":"O1", "concept_keys":[]}, {"overlay_key":"O2", "concept_keys":["P1"]}, {"overlay_key":"O3", "concept_keys":["P1", "P1"]}]) == [0, 1, 2]


def test_attachment_rejects_missing_overlay():
    with pytest.raises(ValueError): validate_attachments(["O1"], set(), [])


def test_attachment_rejects_unknown_concept():
    with pytest.raises(ValueError): validate_attachments(["O1"], set(), [{"overlay_key":"O1", "concept_keys":["P9"]}])


def test_durable_ids_are_not_local_keys():
    r = run_synthetic_lifecycle(); assert r["catalogue_hashes"]["round1"] != r["catalogue_hashes"]["final"]


def test_synthetic_harness_has_thirty_passing_assertions():
    r = run_synthetic_lifecycle(); assert r["passed"] == 30; assert r["total"] == 30; assert all(r["assertions"].values())


def test_synthetic_report_is_json_serializable(tmp_path):
    r = run_synthetic_lifecycle(tmp_path); data = json.loads((tmp_path / "synthetic-lifecycle-verification.json").read_text())
    assert data["passed"] == r["passed"]


def test_unknown_operation_rejected():
    c = Catalogue(FACETS[0], set()); c.add("P1", "x", [])
    with pytest.raises(ValueError): c.mutate("unknown", ["P1"])


def test_unknown_predecessor_rejected():
    c = Catalogue(FACETS[0], set())
    with pytest.raises(ValueError): c.mutate("retain", ["P9"])


def test_catalogue_validation_checks_support_and_parent():
    c = Catalogue(FACETS[0], {"O1"}); c.add("P1", "x", ["O1"]); assert c.validate({"O1"})
    c.items["P1"]["parent"] = "missing"; assert not c.validate({"O1"})


def test_all_actions_are_declared():
    assert set(ACTIONS) == {"retain", "rename", "redefine", "merge", "split", "reparent", "deprecate", "dispose_non_native"}
