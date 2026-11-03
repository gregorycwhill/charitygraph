# G4-O1C P4-E independent offline acceptance review

Date: 2026-10-28 (Australia/Sydney)  
Target: `gate3-cg406-remediation` HEAD `4bf112726f289b191c9f765e0c3bfc3f0d0cd021`  
Fence: v40  
Verdict: **ACCEPT_BOUNDED_OFFLINE_BASELINE** — Gate 4 remains OPEN.

## Scope and commit boundary

I read the Builder instructions, architecture, machinery map, available
CharityGraph Data authority/model/source-governance/economics/plan/test-plan
documents, P4-D independent review, and the P4-E remediation report.

- `HEAD^` is exactly `e995da27b72b88badbe9feba01af8f88f0584c20`; HEAD is its
  direct child.
- The committed diff contains exactly four paths: the P4-D report amendment,
  the P4-E report, `src/charitygraph/phase5_run_diagnostics_catalog.py`, and
  `tests/runtime/test_phase5_run_diagnostics_catalog.py`.
- `git diff-tree --check e995da2 HEAD` passed. The parent P4-D report had three
  trailing-space lines (3–5); HEAD has zero.
- No staged paths exist. Before this report was written, the ambient worktree
  had 10 modified tracked files and 289 untracked files (239 under
  `evidence/`, 47 under `reports/`, and 3 under `tests/`); these pre-existing
  unrelated changes were not absorbed, edited, staged, or deleted. The commit
  itself contains no data/archive/database path.

## Independent implementation audit

Passed bounded properties:

- `accounting_currency` is in the explicit `cost_entries` provenance allowlist.
  The fixture mutation changing one currency to `NZD` changes exactly the
  affected cost-row digest, the cost-entry group digest, and aggregate digest;
  all other group digests remain stable.
- The returned cost row preserves exact Decimal text: `0.125000`; currency
  shape and amount validation fail closed for invalid values.
- Stable identity/reopen assertions preserve snapshot, projection, and
  provenance hashes.
- The fixture-backed sentinel test injected 9 prohibited values (prompt,
  source, response, usage, error, result-reference, transport, and
  authorization/credential values) and found none in the returned manifest or
  its JSON serialization. It also found none of 12 prohibited field names.
- `error_class` and `failure_class` are operational classifications, not
  message fields, and are safe for the current controlled classification
  contract. Residual risk: the adapter does not independently enum-validate
  those strings, so a manually corrupted database containing sensitive
  free-form class text is outside this bounded proof.

## Test evidence

All runs were provider/model/network-free, used
`PYTHONDONTWRITEBYTECODE=1`, disabled the pytest cache provider, and used
basetemp directories under `C:\CharityGraph-runtime`:

- Focused worktree module: **9 passed**.
- Same focused module from a fresh clean `git archive HEAD`: **9 passed**.
- Full clean-archive suite: **1,224 passed, 33 failed, 4 skipped**. The
  failures are outside P4-E and are attributable to absent sibling Data
  fixtures/metadata, historical version expectations, or tests requiring Git
  metadata in the archive. They are not used as a claim of full-suite health.

The checkout already contained 380 `.pyc` files; they were not touched or
removed. No pytest cache was present, and the review created no repository
cache/bytecode or source/provider artefacts.

## Non-claims and limitations

This is an offline baseline only. It does not establish production-provider
exactly-once effects, live authorization/readiness, multiworker/SLO health,
P3c provider-policy-registry readiness, rights acceptance, publication,
release compatibility, Viewer behaviour, or Gate 4 acceptance/closure.
The local `FakeProvider` and temporary SQLite fixtures are not production
evidence. No provider, model, source, network, spend, GitHub, publication,
release, watcher, fence, or follow-on action occurred.
