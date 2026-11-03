# G4 cost hardening independent review recovery

Date: 2026-10-31 (Australia/Sydney)  
Branch/HEAD: `gate3-cg406-remediation` / `4fbd894f607e11eff03307a5fc75d1955ce69c39`  
Parent: `a9aa4ccc4b97be7cad80a69aedd59d80314a0ba9`  
Supplied v85 fence: `a6ce616ba5832c69687bf6c31cc91d41180a896aac72d3cdc38c9f7e2057a3ea`

## Disposition

- Code semantics: **PARTIAL**.
- Report-only isolation: **PASS**.

## Recovery diagnosis

The pre-existing `reports/G4_PHASE5_PROJECT_COST_RECONCILIATION_HARDENING_20261031.md` was modified in the worktree before this task. Read-only evidence:

- `git diff --numstat -- <path>`: `87` added, `30` deleted; the diff is a complete rewrite from the committed 45-line hardening report to a 102-line independent-acceptance report.
- HEAD blob: `9ed6c7a0008865e55eff63695112628b38b1f4c6`; worktree `git hash-object`: `c3fced7f3f1482162215034cc52eb9a69862c3dc`; worktree SHA-256: `f4b2c07c430c3e6f4a49aace62d14f2961b7e3115d2f71de6b1e78d6122e7268`.
- No source, test, bridge or script reference to that report path was found; the focused tests contain no report writes. This makes the previous worker’s report edit the most consistent explanation, but authorship is not provable from the local evidence. The dirty report was not changed by this task.

## Commit and isolated verification

`git diff-tree --no-commit-id --name-status -r 4fbd894f...` shows exactly the three direct-child paths: the Phase-5 source, its focused test, and the hardening report. `git diff --check <parent> <HEAD>` reports only the committed report’s intentional Markdown trailing-space line 3. No unrelated dirty path was absorbed.

The exact commit was archived outside the repository at `C:\CharityGraph-runtime\g4-cost-hardening-review-4fbd894f` and tested with bytecode disabled, `-p no:cacheprovider`, and disposable basetemp:

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-cost-hardening-review-basetemp-4fbd894f tests/test_phase5_project_cost_reconciliation.py
15 passed in 2.13s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-cost-hardening-review-basetemp-support-4fbd894f tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py tests/runtime/test_currency_accounting.py
34 passed in 3.48s
```

The historical 55-test command was not replayable in the exact archive because `tests/test_phase5_t4a8_durable_accounting_export.py` is absent from this three-file commit; the attempted command stopped at collection with “file or directory not found” and ran no tests.

## Semantic review

The committed code correctly exercises multi-request/multi-attempt grouping and exact-ID disambiguation, contradiction blocking for the identities it compares, receipt replay de-duplication/conflict exclusion, reservation identity and release reconciliation, explicit unknown `remaining_spend`, non-negative `Decimal` arithmetic, schema-29 gating through the catalogue adapter, and safe projection without raw payload/result fields. The focused fixtures cover these paths.

Two bounded gaps were reproduced in the disposable overlay with inline SQLite mutations:

1. Moving `receipt:one` to a second same-run physical attempt still produced a known `cost:one` charge and no contradiction blocker. The linkage at source lines 469–498 selects a declared receipt by receipt ID but does not compare that receipt’s `physical_attempt_id` with the selected physical ID.
2. Changing `task_attempts.provider_request_id` to a value different from the request/attempt/receipt still produced a known charge. The provider-request contradiction set at source lines 500–509 omits the task-attempt declaration.

These are fail-closed contradiction gaps, so this is not a full semantic PASS. No provider, source, model, spend, watcher, process, Drive, GitHub, publication, release, gate closure or successor dispatch was used.

## Safe next action

Add focused overlay-only tests and a bounded code repair for the two identity comparisons above, then rerun the exact-commit isolation review. Do not alter the dirty hardening report or use provider work; Gate 1 remains CLOSED, Gate 2 ACTIVE, 12% earned, with no scorecard credit claimed.
