# G4-O1C Tranche 2 — evidence-backed Factory rehearsal

Date: 2026-10-28 (Australia/Sydney)  
Target: `gate3-cg406-remediation` HEAD `a699bf02e769271b9f9647c6c99155303de85d63`  
Fence: v41  
Mode: local, provider-free, no model, no network, no acquisition, no spend

## Result

**ACCEPT_BOUNDED_OFFLINE_REHEARSAL. REAL EVIDENCE NOT PROVEN.**

The clean T1B acceptance surface was independently rerun from a fresh
`git archive HEAD`: **29 passed**. It proves that current rights-record and
v29 projection identity are the input to FactoryPlan lowering, and that denied
rights paths create zero tasks, physical attempts, reservations, receipts or
cost entries.

The reusable Tranche 2 composition is
`src/charitygraph/phase5_offline_cohort_rehearsal.py`. It accepts only an
already-completed `preflight_governed_rights` result, uses the existing
`FactoryPlan`, `ReferenceFactory` seed/provider seam, durable SQLite Standard
catalogue lifecycle, and read-only P4 diagnostics projection. Batch is exposed
only as an offline reviewed planning projection; no Batch or Standard provider
boundary is crossed.

## Evidence inventory decision

Read-only inspection found the local G3 inventory at
`C:\CharityGraph-runtime\artifacts\g3-fresh-36-v15\source-universe`:

- `acquisition-ledger.json`: 182 rows, 36 each for `acnc_register`,
  `acnc_ais_bundle`, `annual_report`, `ato_abr_dgr` and `official_website`,
  plus one `pfra` and one `wikipedia_wikimedia`; `provider_calls` is zero.
- `representation-ledger.json`: 182 rows with content hashes; the local
  `source-objects` directory contains corresponding immutable bytes.

This is useful local real-data lineage evidence, but it is **not a qualifying
real cohort for this rehearsal**. The ledgers do not provide the exact
subject/scope-bound `RightsGovernanceRecord` and current v29 projection row
for each selected representation, nor a source-owned current provider-policy
registry/version. The representation ledger also does not itself carry the
durable acquisition-receipt and rights-decision binding required by the clean
preflight. No real source was promoted or transmitted.

## TEST FIXTURE rehearsal

The focused test creates five explicitly labelled TEST FIXTURE subjects,
scopes, source records, immutable source/representation bytes, acquisition
receipts and local-retention rights records. Provider transmission and public
redistribution remain blocked. Clean preflight accepts all five; the runtime
then records five isolated Standard physical attempts.

Observed fixture results:

- normal/error run: **5 tasks, 4 completed, 1 pre-send failure, 4 fake calls**;
  P4 catalogue projection is `RECONCILED` and has no active reservations;
- Batch planning: **5 request items, 1 deterministic Batch job**; no Batch
  send occurred;
- ambiguous run: **4 completed, 1 held after the send boundary, 5 fake calls**;
  one active reservation remains as the residual physical-attempt guard;
- replay: **zero new fake calls** and the diagnostic SHA is unchanged;
- the fixture harness is intentionally serial (`configured_concurrency=2`,
  `observed_concurrency=1`). Existing Standard FakeProvider tests in the same
  clean run prove the actual concurrency cap and peer progress under an
  isolated item failure.

## Test evidence

All clean runs used `PYTHONDONTWRITEBYTECODE=1`, disabled pytest cache
provider, and basetemp under `C:\CharityGraph-runtime`.

- focused exact-HEAD archive overlay: **87 passed**;
- full exact-HEAD archive overlay: **1,249 passed, 13 failed, 4 skipped**;
- safe live-worktree subset: **75 passed**;
- live new rehearsal tests: **2 skipped** because the pre-existing dirty
  governed-integration prototype adds provider-rights fields and is outside
  the clean T1/T2 seam.

The 13 full-suite failures are unrelated known archive/environment cases:
one historical rights compatibility expectation, one old migration-22 version
expectation, five Git-metadata-dependent bridge tests, and six tests requiring
external S0 policy-lineage files absent from the archive. They are not used as
T2 acceptance claims.

## Reuse and residual boundary

T3/T4 can reuse the new function and focused test after a real cohort has
source-bound rights records, exact current projection rows, durable receipts,
representation bytes and a governed scope for every task. The executable
provider-free check is:

```powershell
$env:PYTHONPATH = 'src'
python -B -m pytest -o addopts= -p no:cacheprovider `
  --basetemp=C:\CharityGraph-runtime\g4t2-future-basetemp `
  tests/test_phase5_offline_cohort_rehearsal.py
```

The current `source_rights` module still has no exact
`PROVIDER_POLICY_REGISTRY`; provider transmission therefore remains
fail-closed. No publication, release, GitHub, watcher, fence or follow-on
action occurred. No private source bytes, prompts, model responses, runtime
databases, caches, credentials or logs were added to Git. Existing dirty paths,
including `catalog.py`, `phase5_factory.py`, `source_rights.py` and governed
integration files, were not edited.
