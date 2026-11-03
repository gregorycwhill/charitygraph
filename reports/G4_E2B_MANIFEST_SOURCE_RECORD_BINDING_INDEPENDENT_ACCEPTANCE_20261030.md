# Gate 4 E2B independent acceptance — manifest/source-record binding

Date: 2026-10-30 (Australia/Sydney)  
Disposition: **PARTIAL** — the bounded repair passes technically; independent
acceptance is limited by local fence/worktree evidence. This is not gate closure.

## Scope and authority

Reviewed branch `gate3-cg406-remediation`, exact HEAD
`6442e9abdc39d40d55b1653a1b98b24dfa78821b`, parent
`c3fc30c4e81e0a862d6b75bb78344b1ce7efa86c`, and supplied fence `v63`, SHA-256
`a5d598ab2d3509c2a95506a4d225d2a4f3d0f661d7ae4e91dca5d64290f99095`.
Grounding included local `AGENTS.md`, Builder architecture/machinery, sibling
Data authority/current-state/plans, North Star v0.3, T3 source/rights reports,
the E1/E2 reports, the E2 independent PARTIAL report, and the E2B implementation
report. The governing epistemic boundary is consistent with
`NORTH_STAR_TARGET_CARD_V0_3.md:18-36`: retain subject/scope, evidence,
provenance, field basis and explicit missingness; do not infer currentness.

## Evidence and checks

- `git diff c3fc30c..6442e9ab` is exactly three paths: the E2B repair report,
  `src/charitygraph/phase5_t4b_source_answer_projection.py`, and its focused
  test file. `git diff --check` for the direct-child commit is clean. No
  unrelated path is in the commit.
- The local worktree was already dirty before review: 11 tracked paths plus
  many untracked evidence/report/runtime paths. It was not cleaned or changed;
  the only worker output is this requested report. Therefore a clean-worktree
  claim is not available.
- Using the actual repository algorithm
  `src/charitygraph/contracts/canonical.py:77-87`, the manifest core
  recomputes to `5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a`.
  Independently, the JSON file-byte SHA is
  `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`, and
  `selected_manifest_sha256` is the distinct governed identity
  `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`
  (`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json:4`).
- The manifest has 10 rows, 5 unique subjects, both admitted families, 10
  unique source-record IDs and 10 unique rights-record IDs. Comparing every
  ordinal's subject/source-record/representation-SHA tuple with the T3
  reconciliation table gives **10/10 matches**
  (`reports/G4_T3_MANIFEST_FENCE_PROVENANCE_RECONCILIATION_20261029.md:20-39`).
  The exact scope, family, representation-SHA and rights-ID tuple is then
  fail-closed by `phase5_t4b_source_answer_projection.py:293-347`, rather than
  by name or an `srcrec:` prefix.
- All ten retained runtime representation files were accessible. Direct
  SHA-256 rehashing matched each manifest representation/source hash, with
  expected ABN and source type. Register `LastReported` and AIS
  `FinReportFrom`/`FinReportTo` values were present. The loader repeats the
  byte hash, JSON, ABN and source-family checks at
  `phase5_t4b_source_answer_projection.py:350-383`.
- The focused command
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py -q`
  returned **12 passed in 2.23s**. The projection independently returned 15
  records for 5 subjects and 10 representation hashes: 10 supported source-
  native records, 5 unanswered currentness records, exact reporting periods,
  source field bases, and missingness dimensions with
  `source_silence_is_not_absence: true`
  (`phase5_t4b_source_answer_projection.py:387-531`).
- Disposable adversarial probes rejected all seven cases: selected-manifest
  identity, canonical self-identity, source-record substitution, rights-ID
  substitution, subject drift, scope drift and representation-byte tampering.
  The corresponding committed tests are at
  `tests/test_phase5_t4b_source_answer_projection.py:84-160`.
- Code/diff inspection found no regex, lexical semantic heuristic, SQLite/WAL,
  provider/model/network, acquisition, budget, publication, release, watcher
  or subprocess side effect. The projection declares zero counters for those
  operational effects at `phase5_t4b_source_answer_projection.py:534-579`.

## Residual limitation and next bounded improvement

The supplied v63 fence SHA was not found in the local repository, so its
external fence provenance cannot be independently reproduced from local
evidence. The pre-existing dirty worktree also prevents a clean-baseline
assertion, although the direct-child commit and all targeted checks are exact.
No functional defect was found in the fixed ten-row cohort.

The next bounded improvement is to keep this provider-free and add a local,
versioned T3 binding/rights authority reload (or a hash-anchored evidence
record) so the exact tuple is reloaded from governed records rather than
duplicated in `_EXPECTED_T3_SOURCE_BINDINGS` (`phase5_t4b_source_answer_projection.py:70-151`).
That work must preserve fail-closed tamper tests and must not broaden the source
universe or introduce semantic heuristics.

No source acquisition, provider/model/network call, Drive/GitHub action, budget
spend, publication, release, gate closure, watcher control, runtime DB change,
or follow-on dispatch was performed.
