# G4-O1C P4 provider-free run diagnostics — 26 October 2026

Status: **implemented and verified offline only**. This is additive product
progress, not Gate 4 closure and not acceptance of the quarantined P3b2
attempt (`CODEX_EXECUTION_FAILED_UNEXPECTED_CHANGES`). No provider, source,
network, spend, publication, watcher, bridge, GitHub or external state was
used.

## Control and preservation

- Workspace: `C:\CharityGraph-clean\charitygraph`
- Branch: `gate3-cg406-remediation`
- HEAD: `4b3fbcaeaace5170994da57a4fe502e6f450ba29`
- HEAD tree: `627fafae46e097d4d4f8d67b57a385c374b0ab84`
- The three allowlisted paths were absent before work. No other path was
  written, staged, committed, reset, checked out or deleted.
- Normalized `git status --porcelain=v1 --untracked-files=all` baseline before
  writes: 281 records, SHA-256
  `f05e2ab0228e36e1f1d8903ea5929a5c895b78450dbe46f81441fd5bf228307f`.
  This is the full baseline stream (all dirty and untracked paths), with the
  known inaccessible temporary-prefix warnings omitted by stderr capture.
- After writes: 284 records, SHA-256
  `1c1e6a5b2959fd2642c4901e1fcee097d07fb535d1909350d00c14fbe67875c8` (10 pre-existing modified tracked records and
  274 untracked records, plus exactly the three new allowlisted records).
- No local commit was created; the three new files remain uncommitted for
  independent supervisor verification.

## Product change

`src/charitygraph/phase5_run_diagnostics.py` implements the pure,
versioned projection `charitygraph.phase5.run-diagnostics/v1`. It accepts
caller-supplied existing run results and durable ledger rows only, canonicalises
unordered input, and returns canonical JSON bytes plus their SHA-256. It
derives status counts, stop classification, unattempted work, configured and
observed concurrency, provider posts, restart/no-resend evidence,
subject/scope-separated outcomes, attempts, receipts, reservations, exact
decimal actuals/releases and reconciliation discrepancies.

Missing identity/provenance, conflicting summaries, duplicate accounting keys,
unsupported accounting, binary floats, cross-currency aggregation and
observed concurrency above the configured cap fail closed. Incomplete
reservation accounting is emitted as `INCOMPLETE_OR_DISCREPANT`; unavailable
operational measurements are `NOT_OBSERVED`. The projection excludes prompts,
source text, credentials and response bodies. It has no scheduler, persistence,
rights authority, source discovery, semantic inference or cost allocation.

Deterministic sample projection SHA-256:
`6ed21f8a3e5da684c9e72b3d58a39ee1ce1dbe69d861cef9ca31258512e3e09`.

## Tests

Focused command (fresh basetemp outside checkout):

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-run-diagnostics-focused-final-20261026-01 tests/test_phase5_run_diagnostics.py
```

Result: **7 passed in 0.74s**.

Regression command (fresh basetemp outside checkout):

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-run-diagnostics-final-20261026-01 tests/test_phase5_run_diagnostics.py tests/test_phase5_standard_transport.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/runtime/test_task_state.py
```

Result: **108 passed in 13.36s**. The new tests cover canonical identity/hash,
summary correctness, fake-Standard concurrency and peer progress, saved-response
restart with zero new posts, ambiguous/systemic distinction, file-backed SQLite
exact accounting and duplicate/discrepant accounting, and fail-closed
malformed/omitted/conflicting input with unchanged input records.

## Hashes

New files after verification:

```text
9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372  src/charitygraph/phase5_run_diagnostics.py
869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325  tests/test_phase5_run_diagnostics.py
The report's final self-hash is supplied in the handoff below; embedding a
file's own SHA-256 would make the recorded content self-referential.
```

Known read-only dependencies inspected:

```text
195d15c3ce0a1f4452984cabb71c5c6ab84efd1a898ea542fbe3dc0866396c5b  src/charitygraph/phase5_standard_transport.py
7370a7be3080e4923a6b75c1c5596f053441c00da1d83d80dac164313fb09eea  tests/test_phase5_standard_transport.py
ee91b164e4ce658eda70d29134ebfaaa2d3e9636ca1754921d242b8bbcd15516  src/charitygraph/phase5_preflight.py
a24eaa07db4b439e0caa76b0ecb033e4e4cc71d981fe3278692884d9ed27fce5  src/charitygraph/phase5_delivery.py
dc7f335873789c31f016351c9dccd20f04f7ed002689d0e6dd36b981ab100dfe  src/charitygraph/phase5_factory.py
503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224  src/charitygraph/phase5_governed_factory_integration.py
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py
72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc  src/charitygraph/source_rights.py
fa85b7fdf949e58a0e081963e4e97d1265e27e97a90ac4ca867874ab6ab5683b7  tests/runtime/test_task_state.py
```

The sibling Data authority files were read locally: `DOCUMENT_AUTHORITY.md`,
`CURRENT_STATE.md`, `ROADMAP.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`,
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md` and
`SEMANTIC_HEURISTIC_APPROVALS.md`.

## Remaining evidence and authority gaps

Acceptance is **OFFLINE ONLY**. Remaining work includes the P3c versioned
rights migration and durable external governance record/revalidation, a
separately authorised P4 real-provider cohort, production multiworker SLO and
alert evidence, current source and cost authorization, and complete Gate 4
closing evidence. This projection does not establish provider-side exactly
once, live scheduling, rights acceptance, production health, publication
readiness or Gate 4 closure. The historical P3b2 result remains quarantined
and was neither replayed nor upgraded.
