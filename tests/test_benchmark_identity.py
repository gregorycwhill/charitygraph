from charitygraph.benchmark_identity import bootstrap_benchmark_subjects


def test_benchmark_binding_rejects_duplicate_lookup_inputs(tmp_path):
    try:
        bootstrap_benchmark_subjects(catalog_path=tmp_path / "x.sqlite", runtime_root=tmp_path, bindings=[
            {"binding_key":"a", "abn":"123", "label":"A"}, {"binding_key":"b", "abn":"123", "label":"B"},
        ])
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate ABN must fail before transport")
