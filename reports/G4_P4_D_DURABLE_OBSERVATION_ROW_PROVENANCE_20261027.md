# G4-O1C P4-D durable observation and row provenance

Date: 2026-10-27 (Australia/Sydney)
Branch: `gate3-cg406-remediation`
Clean target HEAD: `7fffe4197681feba3d6c1607504076a742628481` (fence v38)
Status: **local offline PARTIAL; Gate 4 OPEN**

## Scope and authority

This was one bounded, provider-free P4-D hardening task. Only these repository
paths were changed, plus this report:

- `src/charitygraph/phase5_run_diagnostics_catalog.py`
- `tests/runtime/test_phase5_run_diagnostics_catalog.py`
- `reports/G4_P4_D_DURABLE_OBSERVATION_ROW_PROVENANCE_20261027.md`

The clean architecture, Builder machinery, P4-C and independent P3c-B/P4-C
acceptance reports, provider-authority/catalogue archaeology, and the local
Data authority documents were read. The governing boundary remains that
SQLite is rebuildable operational state, observations retain provenance and
time, and this diagnostic adapter is not a source/right/provider authority.

The initial worktree already contained unrelated dirty tracked paths and many
untracked evidence/report paths. The target source and test files were clean
before this task; all unrelated dirty paths were preserved. No Git index,
commit, reset, checkout, watcher, provider, source, network, model, spend,
database outside temporary test fixtures, publication, release or Viewer
surface was touched.

## P4-D changes

The adapter now:

1. Parses all relevant persisted timestamp fields as timezone-aware durable
   values. Malformed or timezone-ambiguous timestamps fail closed. When all
   durable timestamps are absent, it uses the stable evidence-derived token
   `evidence:<snapshot_hash>` instead of wall-clock time.
2. Canonically orders persisted rows before hashing, retaining the existing
   aggregate `snapshot_hash` and idempotent reopen/replay behaviour.
3. Exposes a versioned `provenance_digests` manifest on the immutable snapshot.
   It is scoped by durable `run_id` and contains deterministic per-record
   digests and group digests for the run, tasks, task/delivery attempts,
   physical attempts, receipts, delivery jobs, transport traces, reservations,
   reservation bindings and cost entries, plus a safe aggregate digest.
4. Builds those digests only from explicit operational allowlists. Payloads,
   prompts, evidence, response bodies, usage JSON, raw result references,
   redacted error text, credentials and sensitive transport/authorisation
   metadata are excluded. The diagnostic remains local persisted-run evidence;
   the synthetic FakeProvider fixture is not production-provider evidence.

Existing join, duplicate, orphan, state, exact-Decimal and cost-reconciliation
validation remains fail closed. The pure diagnostics projection and public
contract were not changed.

## Verification

Final repository focused/provider-free regression command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4d-final-20261027-04 tests/runtime/test_phase5_run_diagnostics_catalog.py tests/runtime/test_migrations.py tests/runtime/test_rights_governance_projection.py tests/test_phase5_run_diagnostics.py tests/test_phase5_standard_transport.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/test_source_rights.py tests/runtime/test_task_state.py
```

Result: **113 passed** in 25.15s.

An out-of-repository `git archive HEAD` snapshot at
`C:\CharityGraph-runtime\g4-p4d-clean-archive-20261027-01` received only the
two allowlisted changed files as a test overlay. The clean archive regression
run passed **105 passed** in 20.14s before the final safe-field exclusion and
snapshot-manifest exposure refinements; the final overlay adapter run passed
**7 passed** in 8.43s afterward.

The new tests explicitly cover missing durable timestamps and delayed repeat
hash stability, timezone-ambiguous timestamps, safe per-group provenance,
mutation changing the relevant digest, and the existing missing/orphan,
duplicate, malformed-state, inconsistent-receipt and inconsistent-cost
fail-closed cases. `git diff --check` passed.

## Diff and non-claims

Final target SHA-256 values:

```text
6144757b2a6a469b223608eefb49c8d288b75acfc1c24548a17fcdda606330f8  src/charitygraph/phase5_run_diagnostics_catalog.py
f0e9df867510cb08e53484c8486e8f2446716efaadfa1b60de7e197a86e1830d  tests/runtime/test_phase5_run_diagnostics_catalog.py
```

The target diff is uncommitted and unstaged. No production persisted run,
provider-side exactly-once effect, provider authorization, live readiness,
multiworker/SLO health, source acquisition, public publication, release
compatibility, Gate 4 acceptance or closure is claimed. P4 remains local
offline PARTIAL pending separately authorised operational evidence.
