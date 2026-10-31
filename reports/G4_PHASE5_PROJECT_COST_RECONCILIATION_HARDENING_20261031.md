# G4 Phase-5 project-cost reconciliation hardening

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **bounded local hardening complete; independent acceptance remains required**

## Implementation

The existing read-only diagnostic now preserves and evaluates all safe-exported request, delivery-attempt, physical-attempt and receipt rows. It no longer selects the first request, attempt or physical receipt. Exact source-native request/attempt/receipt identities may disambiguate a historical row; otherwise it emits `AMBIGUOUS_LINKAGE` or `INCOMPLETE_ATTEMPT_HISTORY`. Contradictory request, attempt, physical and receipt identities emit `CONTRADICTORY_RUNTIME_IDENTITIES` and the affected actual charge is excluded from a known actual total.

Reservation rows are identity-deduplicated and amount/currency conflicts fail closed. Persisted release entries are reconciled separately into gross, active-status reserved, released and net reservation-exposure records. `remaining_spend` is always `unknown`: the migration-29 export has no authority for a current remaining budget. Actual charges, reservations and estimates remain separate Decimal-based projections.

The diagnostic remains read-only and deterministic: safe identifiers and provenance only, stable ordering and SHA-256 canonical output, no raw provider payloads/prompts/credentials, no schema or database change, and no provider/model/source access.

## What the export can and cannot prove

It can prove bounded arithmetic over the selected safe catalogue rows, exact persisted identities, supported-schema/run-selection state, receipt-linked charge candidates, explicit reservation/release rows, and deterministic missingness or contradiction blockers. It cannot prove provider-side exactly-once effects, invoice truth, pricing or FX authority validity, unpersisted charges, project-wide completeness without an authenticated complete boundary, cumulative AUD10 spend, or remaining spend authority. Source and snapshot hashes are lineage, not independent accounting authority.

## Evidence

Cache-free, bytecode-free, local-only and provider-free:

```text
python -m pytest -p no:cacheprovider tests/test_phase5_project_cost_reconciliation.py
15 passed in 1.71s

python -m pytest -p no:cacheprovider tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_t4a9_sqlite_accounting_contract.py tests/test_phase5_t4a8_durable_accounting_export.py tests/runtime/test_currency_accounting.py
55 passed in 3.40s

python -m py_compile src/charitygraph/phase5_project_cost_reconciliation.py
passed
```

The new fixtures cover multiple requests, multiple delivery attempts, contradictory receipt IDs, multiple physical receipts, replay/idempotence, reservation release and unknown release state, partial actuals without silent undercounting, stable hashing, unchanged SQLite bytes, and raw-payload exclusion. No test failures remain in the executed selections.

## Remaining gaps and bounded next step

Provider-route authority, source-owned pricing/FX snapshots, authenticated project ledger coverage, external invoice/effect reconciliation, and cumulative budget authority remain unresolved. This change does not activate a provider route or make the diagnostic pre-send authority.

The bounded next step is an independently authenticated, source-owned ledger export and acceptance fixture that supplies exact project/run coverage, provider contract identity, pricing/FX snapshots, reservation/release semantics, and receipt identity across historical attempts. Any external acquisition or provider work remains separately authorised.

## North Star impact

Directly advances North Star v0.3 sections **13 Finances**, **14 Funding / dependencies**, and **20 Evidence / coverage / freshness / corrections** through better scoped operational cost evidence and explicit missingness. Adjacent reusable evidence touches **11 Scale / capability** and **19 Classification / search / AI discovery** through runtime-task economics and provenance. This is private Builder operational telemetry, not charity expenditure knowledge or a public release projection; it earns no Gate 4 closure or scorecard progress.

No private source material, runtime databases, caches, prompts, model responses, credentials, logs, raw provider bodies or public projections were added or modified. Existing unrelated dirty work, including the four unadopted CGDOC1 ingress paths, was preserved.
