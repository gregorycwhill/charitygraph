# G4-O1C P4-E currency and sensitive-field provenance remediation

Date: 2026-10-27 (Australia/Sydney)
Target: `gate3-cg406-remediation` HEAD `e995da27b72b88badbe9feba01af8f88f0584c20`
Fence: v39
Status: **local offline PARTIAL; Gate 4 OPEN**

## Verified fixes

- Added `accounting_currency` to the explicit `cost_entries` provenance
  allowlist. A fixture mutation changing only one ledger currency changes that
  row digest, the cost-entry group digest and aggregate digest; other groups
  remain unchanged. The ledger amount remains the exact Decimal string
  `0.125000`.
- Added a fixture-backed sentinel test for persisted prompt/source material,
  response/raw references, usage JSON, redacted errors, authorization/credential
  text and transport metadata. The returned provenance manifest contains none
  of the injected values or forbidden field names, including after JSON
  serialization. Existing reopen/replay and snapshot-hash assertions remain
  exercised.
- Removed only the three trailing-space Markdown hard-break violations from
  `G4_P4_D_DURABLE_OBSERVATION_ROW_PROVENANCE_20261027.md`.

## Test results

- Target module: **9 passed** in 9.71s.
- Provider-free regression suite: **115 passed** in 26.57s, with
  `PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled, and an isolated runtime
  basetemp.
- Exact `git archive HEAD` plus only the allowlisted source/test overlay:
  **9 passed** in 9.99s.
- `git diff --check`: passed for the allowlisted source, test and P4-D report
  paths. The worker diff is limited to the allowlisted paths and this report;
  pre-existing unrelated worktree changes were preserved. No Git index or
  commit operation was performed.

## Remaining offline limitations

These tests use temporary local SQLite fixtures and a synthetic FakeProvider.
They do not establish provider-side exactly-once effects, historical
production persistence, live authorization or readiness, multiworker/SLO
health, rights acceptance, publication/release compatibility, Viewer behaviour,
or Gate 4 acceptance/closure. No provider, model, network, source acquisition
or spend occurred. P4 therefore remains offline partial pending separately
authorised operational evidence.
