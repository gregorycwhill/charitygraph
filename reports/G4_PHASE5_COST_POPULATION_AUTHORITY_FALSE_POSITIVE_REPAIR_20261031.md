# G4 Phase-5 cost population authority false-positive repair

Date: 2026-10-31 (Australia/Sydney)  
HEAD checked: `33cf117c69fbe8785e6803cda108fc08d4651838`  
Fence supplied: v87, SHA-256 `a4e6dd6629831658d6505118c72cb6090dd2fc18f48ecae065f15562b1f0a05c`

## Outcome

The two reported false positives are repaired fail-closed.

- A complete local schema-29 run comparison no longer establishes a trusted
  project-wide population. `project_wide=True` does not inspect `runs` to
  invent expected historical runs; absent an independently attested
  source-owned manifest, the population is `unknown` with
  `MISSING_TRUSTED_RUN_INVENTORY`.
- A structured source-owned manifest must carry unique run IDs, explicit
  `scope`, `provenance`, and `completeness` evidence. A bounded manifest can
  make population diagnostics complete, but cannot make the cumulative
  project-wide total authoritative.
- Any blocker or unreconciled accounting record vetoes authority, including an
  ambiguous provider crossing in a mixed run. The known receipt-linked amount
  remains available as `observed_actual_subtotal`; authoritative total and
  remaining spend remain null.

## Regression evidence

The focused suite covers ambiguous crossing without a cost row, mixed-run
unknown receipt cost, missing inventory, omitted local history, untrusted
caller inventory, bounded complete two-run output, duplicate/conflicting
receipts, missing pricing/FX, stale schema 27, reservation/release and retry
cases, deterministic ordering, and raw-payload exclusion.

Commands were local-only, cache-free and bytecode-disabled, with basetemp
outside the repository:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp <outside-repository> tests/test_phase5_project_cost_reconciliation.py
27 passed

PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp <outside-repository> [focused plus related operator-health/accounting tests]
135 passed (27 focused + 108 related)
```

No provider/model call, source acquisition, Drive, watcher, GitHub, release,
publication, gate closure, or follow-on dispatch occurred. No private runtime,
payload, credential, cache, or generated projection was written.

## Exact bounded diff

Only the allowlisted paths changed:

- `src/charitygraph/phase5_project_cost_reconciliation.py` — removed local
  SQLite run-population inference; added manifest validation and blocker /
  unreconciled authority vetoes. SHA-256:
  `9b196782d08bc3686a0630633caa97e60519b7d84319fab6efc4cd67a9967b48`
- `tests/test_phase5_project_cost_reconciliation.py` — updated the obsolete
  authority-positive expectation and added negative regressions. SHA-256:
  `0c0a7b8631daa1cd5b032478af18e9d6a84228b4e0beb9538aafce746903faf2`
- `reports/G4_PHASE5_COST_POPULATION_AUTHORITY_FALSE_POSITIVE_REPAIR_20261031.md`
  — this report.

The repository contains no verified independent cumulative run-inventory
artifact for the real project. Therefore the approved cumulative AUD 10
remainder remains unknown, not zero, and no project-wide authoritative spend
claim is made by this repair.
