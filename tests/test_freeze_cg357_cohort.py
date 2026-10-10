import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "freeze_cg357_cohort.py"
SPEC = importlib.util.spec_from_file_location("freeze_cg357_cohort", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_cg357_selection_is_exactly_fifteen_and_uses_only_governed_map_rows():
    rows = [{"rank": rank, "subject_id": f"subject:{rank}", "abn": str(rank), "display_name": f"Org {rank}"}
            for rank in range(1, 101)]
    cohort = MODULE.build({"identity_map_hash": "55dc192a4d226fc3769f8408d5fdf6467f11710b9687f8f72c3f2a0ba10024aa", "rows": rows})
    assert len(cohort["cases"]) == 15
    assert [case["rank"] for case in cohort["cases"]] == list(MODULE.SELECTED_RANKS)
    assert sum(case["arm"] == "challenge" for case in cohort["cases"]) == 10
    assert sum(case["arm"] == "blind" for case in cohort["cases"]) == 5
    assert MODULE.build({"identity_map_hash": "55dc192a4d226fc3769f8408d5fdf6467f11710b9687f8f72c3f2a0ba10024aa", "rows": rows})["cohort_sha256"] == cohort["cohort_sha256"]
