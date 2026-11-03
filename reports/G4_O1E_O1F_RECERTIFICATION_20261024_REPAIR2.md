# G4-O1E/O1F final repair recertification — 2026-10-24

## Conclusion

**REPAIRS PROVEN; RECERTIFICATION REJECTED pending fence reconciliation.** The two requested code repairs are independently verified. A separate future code-change certification is conditionally justified after a separately authorised active fence targets `f6b78d2be8ad699829169cc611d2f60a6ad573a4` and claim/worker evidence is re-established. This report does not activate that route.

This was read-only and provider-free. No source acquisition, provider call, publication, Git mutation, process management, production SQLite mutation, legacy replay, gate action or spending occurred.

## Identity and exact diff

- Branch: `gate3-cg406-remediation`.
- HEAD: `f6b78d2be8ad699829169cc611d2f60a6ad573a4`.
- `git diff --check HEAD^ HEAD`: passed.
- HEAD changes are limited to the repair set: `bridge/bridge.py`, `src/charitygraph/bounded_authority.py`, `src/charitygraph/mission_ledger.py`, `tests/test_bridge_cutover.py`, and `tests/test_double_loop_harness.py`.
- `MissionLedger.dispatch()` (`src/charitygraph/mission_ledger.py:549-559`) now loads the latest durable `supervisor_review_recorded` event and rejects a selected decision whose ID is not that latest review.
- `CutoverWatcher._validate_engineering()` (`bridge/bridge.py:415-419`) now routes `report_only` through `report_only_execution()`. The helper (`src/charitygraph/bounded_authority.py:186-194`) requires exactly `mode`, `change_policy`, `model`, `report_path`, and `timeout_seconds`, with `change_policy=report_only`.

## Independent verification

The focused command was:

```text
$env:PYTHONPATH=(Join-Path (Get-Location) 'src'); python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_double_loop_harness.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4_o1e_o1f_recertification_20261024_repair2_run1
```

Result: **31 passed, 2 skipped**. The skipped cases are the existing real-Codex opt-in and Windows symlink-dependent cases. The targeted superseded-review and missing-timeout tests also passed independently: **2 passed**.

The superseded-review fixture used temporary SQLite state: an older `ACCEPTED` review was followed by a newer `ACCEPTED` review at the same frontier; dispatch of the old decision raised `DecisionNotDispatchable` with `superseded`, while dispatch of the new decision succeeded. The report-only fixture omitted `timeout_seconds` and was rejected before execution/result creation.

## Boundary and historical checks

- `CODE_CHANGE_ROUTE_ACTIVE` remains `False` in both enforcing modules: `bridge/bridge.py:61` and `src/charitygraph/bounded_authority.py:17`.
- The repository contains no v13 dormant fence. The highest local active fence is `runtime/g4-o1d-dormant-state-fence-20261020-v12.json`, whose target is the superseded `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2`, not this HEAD. Therefore the required active-v13 identity is **not proven**, and no fence was changed.
- That v12 record preserves the historical exclusions: technical specification `007` is execution-ineligible with zero exact claims and no consumed marker; campaign `403` is execution-ineligible; historical deletion and modification counts are zero. These exclusions are preserved, but they do not cure the stale/missing active-v13 fence.
- The repo-local managed status is `READY`, with one recorded launcher PID and one watcher instance, and the last recorded instruction is terminal. Read-only process inventory showed the corresponding two Python processes and no additional managed Python worker. No process was started or stopped.
- No active or ambiguous claim marker was found in the inspected repo-local status/evidence. A production ledger database was not available under the repository workspace, so this is not a fresh ledger-row proof; no claim was altered or reconciled.

## Disposition

| Finding | Result |
|---|---|
| Superseded prior `ACCEPTED` decision rejected | **PROVEN** |
| Exact `report_only` schema including `timeout_seconds` | **PROVEN** |
| Active v13 fence matching this HEAD | **FAILED / NOT FOUND** |
| Historical `007`/`403` exclusion and inactive code-change route | **PARTIAL** — exclusions and `False` route are present, but the active fence identity is stale |
| No duplicate worker / no active or ambiguous claim evidence | **PARTIAL** — repo-local status/process evidence only |

The semantic conclusion is **REJECTED for supervisory recertification** until the active fence and claim/worker evidence are separately reconciled. The repaired code itself is ready for that future, separately authorised certification; this report grants no code-change authority.

