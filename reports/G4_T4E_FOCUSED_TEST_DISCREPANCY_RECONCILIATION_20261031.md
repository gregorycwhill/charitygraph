# G4 T4E focused-test discrepancy reconciliation

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Target: `gate3-cg406-remediation` / `6c88e7da57d85bd4eaf86961b54547668c3eabfd`  
Fence: v72 / `53d899916a6f9437f6b5d7dd44c876db4533e45a92d405e51b4babaec010bf30`

## Verdict

**PASS for root-cause reconciliation; PARTIAL for product acceptance.** The three
reported failures are not T4E adapter defects. They require the dirty
`phase5_factory.py` and related dirty regression implementation/test files that
were present in the earlier “clean” overlay. Fresh clean archives of both
requested revisions pass the three nodes. Exact T3 rights authority remains
fail-closed and unavailable for promotion, as required.

## Attested inputs and clean overlays

The live dirty T4E files match the requested hashes exactly:

| File | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7` |

I created new disposable `git archive` directories, then overlaid only those
two files:

- A: `d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`
- B: `6c88e7da57d85bd4eaf86961b54547668c3eabfd`

Both overlays reproduced both attested hashes. Runs used external basetemp
directories under `C:\CharityGraph-runtime`, `PYTHONDONTWRITEBYTECODE=1`,
`python -B`, `PYTHONPATH=src`, and `-p no:cacheprovider`; no live repository
SQLite/source state was used.

## Reproduction and traces

Exact minimal command, run once in each archive (A and B):

```text
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python -B -m pytest -vv --tb=long -p no:cacheprovider --basetemp <external-basetemp> `
  tests/test_phase5_t4d_e3_factory_handoff.py::test_synthetic_authorized_internal_policy_fixture_lowers_to_ten_children_and_replays `
  tests/test_phase5_t4d_e3_factory_handoff.py::test_mixed_scope_physical_package_is_rejected_with_zero_seedable_work `
  tests/test_phase5_t4d_e3_factory_handoff.py::test_adapter_blocks_mixed_scope_plan_before_any_catalogue_seed
```

Result: **3 passed in A; 3 passed in B**. The file collects **32** focused
tests in each clean archive. The exact T3 missing-rights node was also run in
each archive and passed (**1/1** in A and B):
`test_exact_committed_t3_rights_authority_is_explicitly_blocked_without_records`.

The prior failing run’s recorded full traceback was:

```text
tests/.../test_phase5_t4d_e3_factory_handoff.py:402
    assert not first.diagnostics
E   AssertionError: assert not (PreflightDiagnostic(... state='rights_missing', reason='provider rights decision references are absent', details=()), ...)

tests/.../test_phase5_t4d_e3_factory_handoff.py:539
    assert diagnostic is not None
E   assert None is not None

tests/.../test_phase5_t4d_e3_factory_handoff.py:574
    assert result.accepted_count == 0
E   AssertionError: assert 2 == 0
E   + where 2 = E3FactoryHandoff(tasks=(...), diagnostics=(), factory_plan=FactoryPlan(...)).accepted_count
```

Those assertions map to the current test at lines 402, 539 and 574. In the
clean archives, T4D reaches the scope check at
`phase5_t4d_e3_factory_handoff.py:430-461`; no source change is needed to make
these three nodes pass.

## Evidence-backed root cause

The previous failing overlay’s T4E source/test hashes were correct, but its
dependencies were not clean archive bytes:

| Dependency | Clean A/B archive | Previous failing overlay (also live dirty) |
|---|---|---|
| `src/charitygraph/phase5_factory.py` | `3560ba44becba1c0b4bde1b22974e99394ba130c0f42cda22bb7c0781ab4f69a` | `dc7f335873789c31f016351c9dccd20f04f7ed002689d0e6dd36b981ab100dfe` |
| `src/charitygraph/phase5_governed_factory_integration.py` | `9d29301417a092125cea34dac04c337b690b718bfebeb78566dcf6849e6362ab` | `503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224` |

The prior run used `New-Item -Force` for the archive destination without an
empty-destination assertion. Its recorded failing overlay contains the live
dirty `FactoryPlan` implementation. The clean committed implementation groups
physical packages by `(subject_id, kind, delivery_mode)`; the dirty version
groups by `(subject_id, scope_id, kind, delivery_mode)` at
`phase5_factory.py:40-44`. Therefore the T4D adapter’s deliberate mixed-scope
guard at `phase5_t4d_e3_factory_handoff.py:248-268` sees two separate packages
in the dirty overlay and returns no diagnostic, causing lines 539 and 574 to
fail.

The dirty governed-factory implementation also added provider-rights decision
enforcement at `phase5_governed_factory_integration.py:341-353` and calls it
from `:522-553`. The T4E synthetic fixture does not provide those new
`rights_decision_ids`, so it correctly receives `rights_missing` in that
contaminated overlay, causing line 402. This is a stale/mixed dependency
fixture context, not a T4E adapter defect.

## Regression count reconciliation

The clean regression command was the five-file selection from the prior report:

```text
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='src'
python -B -m pytest -q -rA -p no:cacheprovider --basetemp <external-basetemp> `
  tests/test_phase5_t4b_source_answer_projection.py `
  tests/test_phase5_t4c_private_answer_brief.py `
  tests/test_phase5_factory.py `
  tests/test_phase5_governed_factory_integration.py `
  tests/test_phase5_governed_rights_preflight.py
```

Result: **50 passed, 0 skipped** in both clean A and B archives. The prior
**51 passed, 1 skipped** run used dirty regression files: the dirty Factory
test adds `test_factory_plan_keeps_distinct_scopes...` at
`tests/test_phase5_factory.py:20`; the dirty governed-factory test adds
`test_governed_factory_isolates_scopes_and_subjects_in_durable_physical_work`
at `tests/test_phase5_governed_factory_integration.py:279`; and the dirty
rights test explicitly skips the old seam at
`tests/test_phase5_governed_rights_preflight.py:224-228` when the dirty rights
prototype is present. Thus 51/1 is a different dirty test universe, not a
regression failure and not evidence against the clean 50-test result.

## Disposition and allowlist

No T4E product or test fix is required by this reconciliation. Do not weaken
the current T3 missing-rights fail-closed behavior, promote synthetic rights,
or change the 20 North Star/five `source_silent` carriage.

If a future verification run is separately authorised, its only required
procedure correction is to create a guaranteed-empty archive destination (or
fail closed if non-empty) and verify all imported dependency hashes, not only
the two dirty T4E files. No product-file allowlist expansion is justified by
this task. Exact current T3 rights authority remains a separate acceptance
boundary.

No provider/model/network/credential/source-acquisition/spend/publication/
release/Drive/GitHub/process action occurred. No Git edit, stage, commit,
reset, checkout, or historical-work deletion occurred. The only repository
output is this report; all disposable archives, basetemp and SQLite test state
remain outside the repository.
