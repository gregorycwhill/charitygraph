from charitygraph.phase5_factory_chaos import scenario_for, scenario_ledger

def test_chaos_selection_is_deterministic_and_bounded() -> None:
    ids=[f"physical:{i}" for i in range(1000)]
    assert [scenario_for(x) for x in ids] == [scenario_for(x) for x in ids]
    assert all(s is None or s.startswith("C") for s in map(scenario_for,ids))

def test_scenario_ledger_is_stable() -> None:
    assert scenario_ledger(["physical:b","physical:a"]) == scenario_ledger(["physical:a","physical:b"])
