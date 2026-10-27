import sys

sys.path.insert(0, "scripts")
import run_native_v4_faceted as v4


def test_all_provider_schemas_are_strict_and_explicit():
    for schema in (v4.DISP_SCHEMA, v4.AUDIT_SCHEMA, v4.DISC_SCHEMA, v4.OP_SCHEMA, v4.ATT_SCHEMA):
        assert v4.strict(schema) == []


def test_representation_families_and_facets_are_explicit():
    assert "native_candidate" in v4.FAMILIES
    assert None not in v4.FAMILIES
    assert "other_native_residual" in v4.FACETS


def test_v4_is_lab_only_and_does_not_persist_production_native():
    assert v4.ROOT.name == "native-induction-v4-faceted-disposition"
    assert v4.CAP == v4.Decimal("1.50")

