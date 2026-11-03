# G4 P4-D independent offline acceptance review

Date: 2026-10-27 (Australia/Sydney)  
Mode: independent, local, read-only, provider-free  
Target: `gate3-cg406-remediation` HEAD `e995da27b72b88badbe9feba01af8f88f0584c20`  
Parent: `7fffe4197681feba3d6c1607504076a742628481`  
Fence: v39

## Decision

**P4-D: ACCEPT_BOUNDED_OFFLINE_BASELINE.** The committed diagnostic hardening
meets its bounded local contract with one small provenance-coverage remediation
recommended below. This is not product, provider, or production acceptance.

**P4 remains PARTIAL and Gate 4 remains OPEN.** The persisted run is a
synthetic FakeProvider fixture, not historical/provider exact-once evidence.

## Independent scope and repository proof

I read the repository `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`,
the P4-C report, the P3c-B/P4-C independent review, the clean-catalogue/source-
rights archaeology, and the committed P4-D report. The sibling Data governance
files named by the task are not present in this configured workspace; external
access is prohibited, so I relied on the local Builder authority and the local
reports' recorded Data-authority findings.

`e995da2` is the direct child of `7fffe419` and changes exactly three paths:

```text
A reports/G4_P4_D_DURABLE_OBSERVATION_ROW_PROVENANCE_20261027.md
M src/charitygraph/phase5_run_diagnostics_catalog.py
M tests/runtime/test_phase5_run_diagnostics_catalog.py
```

The checkout was already materially dirty. At the end of review it still had
10 pre-existing modified tracked paths and 73 pre-existing untracked entries;
the target implementation/test/report paths were not dirty before this report.
No staging, commit, reset, checkout, watcher, Git metadata, provider, model,
network, source acquisition, spend, production database, or publication action
occurred.

## Findings

Passed bounded properties:

- Durable timestamps are parsed as timezone-aware values and normalized to UTC;
  malformed or timezone-ambiguous values fail closed. If all durable timestamps
  are absent, `snapshot_observed_at` uses the stable
  `evidence:<snapshot_hash>` token. Reopen/replay preserves snapshot,
  projection, and manifest hashes.
- Thirteen operational groups have run-scoped per-row digests, group digests,
  canonical ordering, and an aggregate digest. The allowlists exclude payloads,
  prompts, evidence/source material, response bodies, usage JSON, raw result
  references, redacted error messages, credentials, and private rights data.
  A task-field mutation changed both the task-group and aggregate digests.
- Existing joins and state checks remain fail closed for missing, duplicate,
  orphan, ambiguous, malformed-state, inconsistent-receipt, and cost/currency
  ambiguity cases. Read-only immutable SQLite access and uncheckpointed-WAL
  rejection remain intact.

One narrow blind spot remains: `cost_entries.accounting_currency` is used by
validation and returned ledger output but is absent from the cost-entry
provenance allowlist. A currency-only mutation therefore changes the aggregate
snapshot hash but not that row/group provenance digest. Smallest remediation:
add this field to the explicit cost-entry allowlist and add one mutation test.

The focused tests assert prohibited field names are absent, but do not inject
sentinel prompt/source/response/usage/raw-reference/error values into persisted
rows and assert their values are absent from the returned manifest. Smallest
test-only hardening: add one adversarial sentinel test across those columns.
`error_class` and `failure_class` are included as operational classes; this is
safe only while they remain controlled classes rather than free-form messages.

Commit-level `git diff --check` also reports three Markdown hard-break lines in
the committed P4-D report. This is documentation hygiene, not a code failure.

## Test evidence and limits

All runs were provider-free, used `PYTHONDONTWRITEBYTECODE=1`, disabled the
pytest cache, and used basetemps under `C:\CharityGraph-runtime`:

```text
dirty worktree focused regression: 113 passed in 25.33s
exact e995da2 clean git archive:   105 passed in 19.88s
clean-archive adapter module:        7 passed in 10.13s
```

The clean archive did not include the unrelated dirty test changes. These are
separate proofs, not an additive claim of 225 tests. The evidence establishes
an offline bridge/diagnostic baseline only. It does not attest provider-side
exactly-once acceptance, historical production persistence, provider
authorization, live readiness, multiworker/SLO health, rights acceptance,
public contract compatibility, publication, release, or Gate 4 closure.

The clean archive and temporary test fixtures were created outside the
repository; the original checkout and Git metadata were left unchanged. This
report is the only repository write made by this review.
