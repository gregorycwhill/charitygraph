# G4 Phase-5 project-cost population completeness

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C local engineering task  
HEAD: `0a3a2e8f85703798aed95ee27287de3a06b5714c`  
Immutable v86 fence: `2df394dd800618725bbb47aec6460ba4715e7e0d87e8052a0a19c7acac58640f`

## Result

Implemented a provider-free, read-only `project_wide=True` diagnostic in
`phase5_project_cost_reconciliation.py`. It discovers the complete persisted
`schema29` `runs.run_id` population through an immutable/query-only SQLite
read, then passes those exact IDs to the existing catalogue adapter for the
typed run, task-attempt, request, delivery-attempt, physical-attempt, receipt,
reservation and cost export.

The diagnostic now reports, per run, missing run/task-attempt/delivery-attempt/
physical-attempt/receipt/cost records and deterministic population state. It
adds an observed actual subtotal that remains useful for a bounded partial
export. A project-wide `authoritative_total` is emitted only when the
source-owned schema29 run population and all receipt-linked actual cost rows
reconcile; otherwise the status is `NOT_AUTHORITATIVE` and both
`authoritative_total` and `remaining_spend` are null. No approved AUD10
remaining-spend value is calculated or implied.

Stale schema27, empty source state, missing records, duplicate/conflicting
receipts, contradictory runtime identities, missing pricing/FX, retries and
reservation release cases remain fail-closed. Existing identity guards were
preserved. No public contract or existing bounded-call shape was removed;
the new population and authority fields are additive.

## Verification

- Focused: `22 passed`
- Related operator-health/accounting regressions: `62 passed`
- Commands used `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`, and
  basetemp directories under `C:\CharityGraph-runtime`.
- Tests cover complete two-run schema29 population, missing run/attempt/receipt/
  cost evidence, stale schema27, empty source state, duplicate and conflicting
  receipts, contradictory identities, missing pricing/FX, retry and release
  handling, stable ordering and unchanged source fixture bytes.
- No provider, model, external source or Drive call occurred. Disposable test
  SQLite files were created only under the runtime basetemp; no database,
  cache, raw payload, prompt, result body, credential or private evidence was
  added to the repository.

This is a local persisted-cost completeness diagnostic, not provider-side
exactly-once, invoice, pricing/FX or release authority. It makes no Gate 4
closure or scorecard claim.
