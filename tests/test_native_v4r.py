import sys
sys.path.insert(0, "scripts")
import run_native_v4r as v4

def test_corrected_schemas_are_strict():
    for schema in (v4.DISP_SCHEMA, v4.AUD_SCHEMA, v4.DISC_SCHEMA, v4.OP_SCHEMA, v4.ATT_SCHEMA):
        assert v4.strict(schema) == []

def test_stage_a_requires_exact_local_key_shape_and_nonempty_objects():
    item=v4.DISP_SCHEMA["properties"]["dispositions"]["items"]
    assert item["properties"]["local_key"]["pattern"] == "^O[0-9]{2}$"
    assert item["properties"]["objects"]["minItems"] == 1

def test_edit_grammar_has_required_actions_and_parent_modes():
    assert {"retain","rename","redefine","merge","split","reparent","deprecate","dispose_non_native"} == set(v4.OPF["action"]["enum"])
    assert {"unchanged","set","remove"} == set(v4.OPF["parent_mode"]["enum"])
