from dataclasses import replace

import pytest

from charitygraph.s0_structured_authority import (
    FrozenLocatorQueries, GovernedLocatorBinding, LocatorAuthorityMaterial,
    compile_locator_authority, frozen_locator_material_sha256, validate_live_bindings,
)
from charitygraph.scale_s0 import ScalePreflightError


def _subjects():
    return tuple(FrozenLocatorQueries(GovernedLocatorBinding(f"subject:{n}", "ABN", f"{n}" * 11),
                                      (f'"Charity {n}"', f'"Charity {n}" ABN')) for n in "123")


def _authority(subjects=None):
    subjects = subjects or _subjects()
    return LocatorAuthorityMaterial("CG-S0-PO-ATTEMPT19-2026-09-26", "attempt:s0:19", "run:s0:attempt-19",
        "a" * 40, "b" * 40, "proj_vnAuU8uxocL0Rosg3SulgmRI", frozen_locator_material_sha256(subjects),
        tuple(x.binding for x in subjects), 3, "0.10", "0.30")


def test_three_subject_two_candidate_authority_compiles_exactly_three_slots_and_alternates():
    compiled = compile_locator_authority(_authority(), _subjects())
    assert compiled.max_physical_calls == 3
    assert str(compiled.max_new_exposure_usd) == "0.30"
    assert [len(x.alternate_queries) for x in compiled.slots] == [1, 1, 1]
    assert all(x.executable_query_index == 0 and x.alternate_status.startswith("non_executable") for x in compiled.slots)


@pytest.mark.parametrize("mutation", ["budget", "data", "builder", "subject", "frozen"])
def test_structured_authority_rejects_budget_and_binding_substitution(mutation):
    subjects = _subjects(); authority = _authority(subjects)
    if mutation == "budget": authority = replace(authority, max_physical_calls=4)
    elif mutation == "data": authority = replace(authority, data_merge_sha="c" * 40)
    elif mutation == "builder": authority = replace(authority, builder_commit_sha="c" * 40)
    elif mutation == "subject": subjects = tuple(reversed(subjects))
    else: subjects = subjects[:-1] + (FrozenLocatorQueries(subjects[-1].binding, ("mutated", "alternate")),)
    if mutation in {"budget", "subject", "frozen"}:
        with pytest.raises(ScalePreflightError): compile_locator_authority(authority, subjects)
    else:
        with pytest.raises(ScalePreflightError):
            validate_live_bindings(authority, attempt_id="attempt:s0:19", run_id="run:s0:attempt-19",
                                   builder_commit_sha="a" * 40, data_merge_sha="b" * 40,
                                   provider_project="proj_vnAuU8uxocL0Rosg3SulgmRI")


def test_abn_alias_cannot_be_a_governed_subject():
    bad = FrozenLocatorQueries(GovernedLocatorBinding("ABN:11111111111", "ABN", "11111111111"), ("one", "two"))
    with pytest.raises(ScalePreflightError): _authority((bad,)).validate()
