# G4 Phase-5 project cost reconciliation implementation

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, local-only and provider-free

## Result

Implemented one new read-only diagnostic in
`src/charitygraph/phase5_project_cost_reconciliation.py` and its cache-free
SQLite fixture tests in `tests/test_phase5_project_cost_reconciliation.py`.
The required report is the only report path changed. The documented dirty
bridge paths and unrelated historical work were not touched.

The diagnostic consumes the existing
`Phase5OperatorHealthCatalogueAdapter` export. It accepts an explicit set of
run IDs, so multiple runs and cohorts are reconciled in one deterministic
projection. Cost rows are mechanically linked through the existing
task-attempt/request-item/physical-attempt/provider-receipt records because
the current persisted `cost_entries` schema has no direct receipt column.
No database, schema, provider, source, model, watcher, Drive or runtime state
was changed.

## Behaviour and boundary

- Uses `Decimal`; reports only auditable known AUD actual charges.
- Keeps actual charges, reservations and explicit estimates/forecasts in
  separate totals.
- Deduplicates identical receipt-linked actuals, blocks conflicting duplicate
  receipts, marks replayed attempts, and reports ambiguous provider crossings.
- Reports explicit blockers for missing pricing, FX, usage, runtime linkage,
  unsupported/stale schema, unknown cost entries, missing runs and absent or
  unauthenticated project-wide coverage.
- Preserves run, cohort, task, attempt, request, provider, model, subject,
  scope, physical-attempt, receipt and provenance identifiers where the
  existing export provides them.
- Excludes raw provider payloads, response bodies, prompts, credentials and
  transport errors.
- Project-wide completeness is **not proven** without an authenticated,
  complete boundary whose run set matches the selected persisted runs.

## Verification

Focused command:

```text
python -m pytest -p no:cacheprovider tests/test_phase5_project_cost_reconciliation.py
```

Result: **8 passed**. The existing Phase-5 catalogue/runtime-contract
regression plus this suite passed **22 tests** together.

The tests cover multi-run/multi-cohort Decimal totals; idempotent and
conflicting duplicate receipts; missing pricing, FX and usage; stale schema;
ambiguous crossings; unknown costs; empty data; authenticated-boundary
requirements; replayed attempts; stable canonical ordering/hash; read-only
fixture use; and raw-payload exclusion. No live project-wide accounting
completeness is claimed. The smallest subsequent integration test is an
independently supplied authenticated project-ledger fixture with exact
selected-run coverage, followed by a read-only adapter integration assertion
against the current source-bearing catalogue.

North Star v0.3 direct domains: section 13 Finances, section 14 Funding /
dependencies, and section 20 Evidence / coverage / freshness / corrections.
Adjacent domains: section 19 Classification / search / AI discovery (model
task economics and provenance) and section 11 Scale / capability (operational
scale telemetry). This is internal operational evidence, not public release
knowledge and not expenditure evidence about charities.

No private material, runtime database, cache, model response, prompt,
credential, raw source or generated public projection was added to Git.
