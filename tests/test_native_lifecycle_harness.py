import json
import pytest
from charitygraph.native_lifecycle_harness import *

def cat(f="operational_activity"):
    c=Catalogue(f,{"O1","O2"}); c.add("P01","one",["O1"]); c.add("P02","two",["O2"]); return c
def test_five_strict_schemas(): assert set(schemas())=={"quality","discovery","gardener","attachment","extraction"} and all(not validate_schema_shapes(x) for x in schemas().values())
def test_recursive_schema_guard(): assert validate_schema_shapes({"type":"object","required":[],"properties":[]})
def test_discovery_processor_requires_local_key():
    with pytest.raises(ValueError): process_discovery_response({"concepts":[{"preferred_label":"x"}]},schemas()["discovery"])
def test_duplicate_local_key_rejected():
    with pytest.raises(ValueError): process_discovery_response({"concepts":[{"local_key":"P","preferred_label":"x"},{"local_key":"P","preferred_label":"y"}]},schemas()["discovery"])
def test_gardener_processor_requires_operations():
    with pytest.raises(ValueError): process_gardener_response({"operations":[{"local_key":"P"}]},schemas()["gardener"])
def test_extraction_processor_requires_reviews():
    with pytest.raises(ValueError): process_extraction_response({"local_key":"x"},schemas()["extraction"])
def test_local_keys_global_ids(): assert cat().active_ids().isdisjoint(cat("participation").active_ids())
def test_repeated_local_keys_across_calls():
    r={}; a=Catalogue("operational_activity",{"O1"},r); b=Catalogue("operational_activity",{"O1"},r); a.add("P01","a",["O1"]); b.add("P02","b",["O1"]); assert len(r)==2
def test_unknown_support_rejected():
    with pytest.raises(ValueError): Catalogue("operational_activity",{"O1"}).add("P","x",["O2"])
def test_rename_returned_semantics():
    c=cat(); c.mutate("rename",["P01"],[{"preferred_label":"returned","support_overlay_keys":["O1"]}]); assert c.items["P01"]["preferred_label"]=="returned"
def test_redefine_returned_semantics():
    c=cat(); c.mutate("redefine",["P01"],[{"preferred_label":"one","definition":"new","inclusion_boundary":"i","exclusion_boundary":"e","support_overlay_keys":["O1"]}]); assert c.items["P01"]["definition"]=="new"
def test_self_parent_rejected():
    with pytest.raises(ValueError): cat().mutate("reparent",["P01"],parent_mode="set",parent="P01")
def test_indirect_cycle_rejected():
    c=cat(); c.add("A","A",["O1"]); c.add("B","B",["O1"],"A"); c.add("C","C",["O1"],"B")
    with pytest.raises(ValueError): c.mutate("reparent",["A"],parent_mode="set",parent="C")
def test_cross_facet_parent_rejected():
    c=cat(); c2=cat("participation"); c2.items["P01"]["parent"]=c.items["P01"]["id"]; assert not c2.validate({"O1","O2"})
def test_remove_parent(): c=cat(); c.mutate("reparent",["P02"],parent_mode="remove"); assert c.items["P02"]["parent"] is None
def test_merge_unknown_support_rejected():
    with pytest.raises(ValueError): cat().mutate("merge",["P01","P02"],[{"preferred_label":"m","support_overlay_keys":["O9"]}])
def test_two_successor_operations_have_unique_ids():
    c=cat(); c.mutate("split",["P01"],[{"preferred_label":"a","definition":"d","inclusion_boundary":"i","exclusion_boundary":"e","support_overlay_keys":["O1"]},{"preferred_label":"b","definition":"d","inclusion_boundary":"i","exclusion_boundary":"e","support_overlay_keys":["O1"]}]); ids=[v["id"] for v in c.items.values()]; assert len(ids)==len(set(ids))
def test_lineage_backlinks_validate():
    c=cat(); c.mutate("merge",["P01","P02"],[{"preferred_label":"m","definition":"d","inclusion_boundary":"i","exclusion_boundary":"e","support_overlay_keys":["O1"]}]); child=next(k for k,v in c.items.items() if v["predecessors"]); c.items[child]["predecessors"]=[]; assert not c.validate({"O1","O2"})
def test_duplicate_attachment_rejected():
    with pytest.raises(ValueError): validate_attachments(["O1"],{"C"},[{"overlay_key":"O1","concept_ids":["C","C"]}])
def test_unknown_attachment_rejected():
    with pytest.raises(ValueError): validate_attachments(["O1"],{"C"},[{"overlay_key":"O1","concept_ids":["X"]}])
def test_inactive_attachment_rejected():
    c=cat(); c.mutate("deprecate",["P01"])
    with pytest.raises(ValueError): validate_attachments(["O1"],c.active_ids(),[{"overlay_key":"O1","concept_ids":[c.items["P01"]["id"]]}])
def test_salted_split_order_independent():
    ids={"O1","O2","O3","O4"}; assert split_overlay_ids(list(ids),"s")==split_overlay_ids(list(reversed(list(ids))),"s")
def test_holdout_guard(): assert not holdout_guard([{"object_ids":["H"],"overlay_ids":[]}],{"H"},set())
def test_holdout_allowed_after_freeze(): assert holdout_guard([{"object_ids":["H"],"overlay_ids":[]}],{"H"},set(),frozen=True)
def test_fake_provider_roundtrips():
    p=FakeProvider(); s=schemas(); assert process_quality_response(p.request("quality",{"overlay_keys":["O1"],"facet":FACETS[0]},s["quality"]),s["quality"])
def test_synthetic_30_assertions():
    r=run_synthetic_lifecycle(); assert r["passed"]==30 and r["total"]==30 and all(r["assertions"].values())
