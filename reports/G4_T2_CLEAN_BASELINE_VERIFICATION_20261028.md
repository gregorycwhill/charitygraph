# G4-O1C T2 clean-baseline verification

Date: 2026-10-28 (Australia/Sydney)  
Mode: local, read-only verification; no source/provider/network/model work  
Target: `gate3-cg406-remediation@700cfe1f4e576e00471155a6bfedbcc40fc36cab`  
HEAD tree: `739e7da9515eb2a0435d6632d6bb8b2ad3d29767`  
Fence: v43

## Decision: STOP

There is no genuinely clean T2 execution path in this checkout. The two
requested fresh candidate names are absent from both HEAD and the live tree,
but the clean T1B module imports dirty tracked modules when imported from the
live worktree. A bounded code task could create the fresh names only in a
separately provisioned pristine HEAD execution surface. It must not be started
against this worktree and must not touch the quarantined T2 files.

## Baseline and path inventory

The checkout was already dirty: 10 modified tracked paths and 80 untracked
status entries (90 total). Existing bytes were preserved. Relevant modified
tracked paths include `phase5_factory.py`,
`phase5_governed_factory_integration.py`, `runtime/catalog.py`,
`source_rights.py`, and their related tests. The target report was absent
before this write.

| Path | HEAD | Live tree | Finding |
|---|---:|---:|---|
| `src/charitygraph/phase5_governed_cohort_rehearsal.py` | absent | absent | safe fresh name in principle |
| `tests/test_phase5_governed_cohort_rehearsal.py` | absent | absent | safe fresh name in principle |
| `reports/G4_T2_CLEAN_RECONSTRUCTION_20261028.md` | absent | absent | safe future report name |
| `src/charitygraph/phase5_offline_cohort_rehearsal.py` | absent | present | quarantined; unchanged; SHA-256 `9dd267a84f856069c6ea3ac0d14d0b36df49318ed1906c9d5800695047e0beaa` |
| `tests/test_phase5_offline_cohort_rehearsal.py` | absent | present | quarantined; unchanged; SHA-256 `56bb3da80e18209ebac09cd64a95ac941564d803c70215902607cc20788da70f` |
| `reports/G4_T2_EVIDENCE_BACKED_FACTORY_REHEARSAL_20261028.md` | absent | present | prior T2 result; quarantined; unchanged; SHA-256 `e15bf805943cade7b66b50aa1560fd4d5363dca10417636c227cbad9572e6e62` |

The prior T2 result is explicitly bounded offline evidence and says real
evidence was not proven. Its two live rehearsal tests skipped at the dirty
seam. The supervisory T2/T3/T4 plan directs this exact report-only check and
says not to issue a T2 code-change instruction against this checkout. No
separately named `T2R` report is present in the repository; recovery/replay
claims in the prior T2 material do not repair the current import boundary.

## Clean HEAD seam verified

The clean HEAD blobs are present for the accepted T1B chain:

- `runtime/rights_governance_record.py` (`afd7f77176adc9ec38d1b5d8ca37b073c277c385`): `RightsGovernanceStore` is the private content-addressed authority.
- `runtime/migrations.py` (`9dac65cb45f6e4408fb65a9bfa0e92c352aed91`): numbered v29 `rights_projection_records`, `rights_projection_events`, and `rights_projection_current` tables.
- `runtime/rights_governance_projection.py` (`9700b2307ad9478134b677058f870808a612964a`): transactional rebuild and current-row lookup.
- `phase5_governed_rights_preflight.py` (`0335567dd58f7fd0220ee89f71297f768bedaf1f`): reloads the authoritative record by content hash, verifies the v29 current row and exact subject/scope/source/receipt/representation lineage, then delegates accepted material to clean governed-reference preflight and `FactoryPlan`.
- `phase5_factory.py` (`d89c937c544f4939d2eb06b3a8aa47161275192`): clean `FactoryPlan` and `ReferenceFactory` seed/run lifecycle with the provider-free fake seam.
- `phase5_run_diagnostics_catalog.py` (`b68f029ddbabd131b73f0931e182004198e6998d`): read-only immutable SQLite diagnostic projection; `phase5_run_diagnostics.py` supplies stable canonical diagnostic bytes and SHA.

The exact intended chain is therefore:

`RightsGovernanceStore` record bytes → v29 projection rebuild/current lookup →
clean rights preflight → `FactoryPlan` → `ReferenceFactory`/SQLite task,
attempt, receipt, reservation and cost lifecycle → immutable SQLite diagnostics
projection.

This chain is synthetic/provider-free control-plane machinery. It is not source
evidence, provider-side exactly-once proof, human promotion, publication or
Gate 4 closure.

## Dirty import and test behavior

The read-only Python import probe used `PYTHONDONTWRITEBYTECODE=1` and
`PYTHONPATH=src`. `phase5_governed_rights_preflight` resolved to the live
checkout, but so did its imports of the dirty
`phase5_governed_factory_integration`, `phase5_factory`, and `runtime.catalog`.
The live `GovernedReference` has `rights_decision_ids`, and live
`SQLiteCatalog` exposes `get_artifact_rights_decisions`; these are the dirty
`artifact_rights_*` prototype seam, not the clean v29 projection seam.

Both the clean T1B test and the quarantined T2 test contain a guard that skips
when `rights_decision_ids` is present. Collection-only verification collected
five relevant tests (three T1B and two quarantined T2) with no cache provider
and no bytecode; no fixture tests were executed because they create local
SQLite/test artefacts, which this report-only task does not authorise. The
current worktree therefore cannot produce a zero-skip T2-focused execution.

## Safe future allowlist and tests

After a separate pristine checkout/worktree is supplied at the target HEAD,
the only fresh repository paths that may be considered are:

1. `src/charitygraph/phase5_governed_cohort_rehearsal.py`
2. `tests/test_phase5_governed_cohort_rehearsal.py`
3. `reports/G4_T2_CLEAN_RECONSTRUCTION_20261028.md`

The quarantined offline module/test/prior report and all current dirty tracked
paths remain outside the allowlist. The focused offline tests should use only
explicitly labelled TEST FIXTURE subjects and must produce zero T2-focused
skips. They should verify:

- exact T1B rights-record/v29 lowering and deterministic task identity;
- denied or mismatched authority produces a diagnostic and zero tasks,
  attempts, reservations, receipts and cost entries;
- standard item failure isolation;
- batch request planning without a batch send;
- ambiguous crossing held for explicit reconciliation without resend;
- replay with zero new fake calls and unchanged diagnostic SHA; and
- reservation → actual → release reconciliation with observable persisted
  attempt, receipt, request, cost and diagnostic identities.

A safe execution environment is a pristine target-HEAD checkout with
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, pytest cache disabled
(`-p no:cacheprovider`), and any test basetemp outside the repository. Before
running, assert that the imported governed integration has no
`rights_decision_ids` and that no `artifact_rights_*` table/helper is used.
The current dirty worktree is not such an environment.

## T2 versus T3 evidence boundary

T2 may establish only local synthetic control-plane receipts, attempts,
diagnostics, failure isolation, replay and accounting. It must not use the
local 36-charity inventory as if it were a governed T3 cohort, and it must not
claim source rights, real subject binding, provider readiness or production
industrialisation.

T3 is a separate no-send evidence task. It requires one immutable selected
manifest plus exact durable subject/scope bindings, admitted source family,
source record and artifact, representation bytes/hash, acquisition receipt
lineage, authoritative `RightsGovernanceRecord`, and matching current v29 row
for every selected task. Missing, stale, revoked, superseded, contradictory,
unbound or mismatched material remains an explicit diagnostic/coverage state;
it is not repaired by discovery or synthetic rights decisions.

## Stop criteria and smallest remedy

Stop without implementation approval if any of the following remains true:

- clean imports resolve to dirty tracked modules or a focused test skips;
- a quarantined T2 path, dirty `artifact_rights_*` seam or copied rights field
  is imported as authority;
- a test requires source/provider/network/model work, spend, semantic
  heuristics, new discovery/source families, or a database/cache in the
  checkout;
- exact rights, subject/scope, receipt, representation or diagnostic identity
  is absent or unstable; or
- any existing dirty/untracked byte would be edited, overwritten, staged,
  deleted or reset.

Smallest non-destructive remedy: provide a separate pristine execution
surface at `700cfe1f4e576e00471155a6bfedbcc40fc36cab` (leaving this checkout
untouched), rerun this baseline verification there, and only then consider a
fresh-path T2 code task under the three-path allowlist. This report authorises
no implementation, T3 binding, T4 crossing, spend, adoption, publication,
release or Gate 4 closure.

## Boundary receipt

Only this report was written. No product code, test, quarantined path, source
material, database, cache, archive, credential, log, Git index, GitHub state,
watcher/fence state, publication or release was changed. Existing dirty and
untracked bytes remain preserved.
