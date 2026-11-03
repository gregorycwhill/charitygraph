# Gate 4 P3c-B / P4-C independent Product Lead acceptance review

Date: 2026-10-27 (Australia/Sydney)  
Mode: independent, local, read-only, provider-free  
Target: branch `gate3-cg406-remediation`, HEAD `7fffe4197681feba3d6c1607504076a742628481`, fence v38 (task-supplied)

## Decision

| Tranche | Disposition | Bounded meaning |
|---|---|---|
| P3c-A provider policy authority | **BLOCKED** | The clean source-owned authority exposes the provider policy ID but no exact provider ID/version registry. The record layer therefore fails closed for provider authorization. |
| P3c-B versioned SQLite projection | **ACCEPT_BOUNDED_OFFLINE_BASELINE** | The private content-addressed store is projected transactionally into v29 safe metadata with deterministic rebuild and fail-closed tests. This is not provider or production acceptance. |
| P4-C persisted-run diagnostics | **PARTIAL** | The read-only adapter and file-backed Standard/FakeProvider diagnostic fixture work offline. The run is test-generated, not a historical production run; provider-side exactly-once and production operations remain unproved. |
| Gate 4 | **OPEN / NOT ACCEPTED** | This report is evidence only and does not close a gate, authorize publication or establish live readiness. |

## Controls and repository proof

I read `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the local Data
repository `DOCUMENT_AUTHORITY.md`, `INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md`,
`TEST_PLAN.md`, and the coverage/economics policy. I also read the latest
post-adoption/P3c-A reports and the P3c-B/P4-C reports.

The requested commits are direct children with exact narrow path sets:

```text
0d88635 parent 006f635  4 paths:
  reports/G4_P3C_B_VERSIONED_SQLITE_PROJECTION_REBUILD_20261027.md
  src/charitygraph/runtime/migrations.py
  src/charitygraph/runtime/rights_governance_projection.py
  tests/runtime/test_rights_governance_projection.py

7fffe41 parent 0d88635  3 paths:
  reports/G4_P4_C_REAL_PERSISTED_RUN_DIAGNOSTICS_20261027.md
  src/charitygraph/phase5_run_diagnostics_catalog.py
  tests/runtime/test_phase5_run_diagnostics_catalog.py
```

`git diff-tree --check` is clean for P3c-B. P4-C has one hygiene finding:
`tests/runtime/test_phase5_run_diagnostics_catalog.py` ends with a blank line.
No committed P3c-B/P4-C path is dirty at the target HEAD. The pre-existing
dirty `runtime/catalog.py` and `source_rights.py` were not absorbed:

```text
catalog.py      HEAD blob 5954ce82   worktree raw SHA 3e1a4cea
source_rights.py HEAD blob bab1f855   worktree raw SHA 72f0cc0b
```

The worktree had a material pre-existing dirty/untracked baseline (10 tracked
paths and 296 total porcelain status entries at review). No reset, checkout,
staging, commit, database, provider, source, network, GitHub, watcher or
publication action was performed. This report is the only repository write.

## P3c-B findings

Passed bounded properties:

- Migration v29 is numbered after v28, checksum-recorded, reopenable and
  upgrade-tested. `rights_projection_records`, `rights_projection_events` and
  `rights_projection_current` contain IDs, hashes, lifecycle and safe metadata,
  not private bodies or `material_json`.
- `RightsGovernanceStore` remains the private content-addressed authority.
  Rebuild restores and validates those records/events, checks content hashes
  and event targets, resolves the deterministic current frontier, and inserts
  predecessor records before successors.
- Rebuild is transactional (`BEGIN IMMEDIATE`); an injected failure preserves
  the prior projection. Repeating the same rebuild yields the same snapshot
  hash. The unique current-row key and foreign keys enforce projection-side
  uniqueness and lifecycle references.
- Corruption, missing event targets, duplicate eligible current records,
  cross-binding links, cycles, expiry, review-due and revoked states fail
  closed or are omitted as appropriate. Provider/public axes are not inferred
  from one another; an unsupported provider authorization is rejected.

Independent rerun, with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`
and an external basetemp:

```text
tests/runtime/test_migrations.py
tests/runtime/test_rights_governance_projection.py
tests/runtime/test_rights_governance_record.py
tests/test_source_rights.py
60 passed
```

Schema integration remains bounded. Clean HEAD `catalog.py` has no rights
tables; the dirty worktree catalog side-installs separate `artifact_rights_*`
tables through `_ensure_artifact_rights_tables()`. P3c-B uses distinct
`rights_projection_*` names and did not edit `catalog.py`, so no name collision
or dirty DDL absorption was observed. However, the rerun necessarily imported
the dirty worktree catalog; a clean-catalog integration/rebuild proof is still
required before treating this as an integrated catalogue capability.

P3c-A remains a hard boundary. Clean HEAD `source_rights.py` contains
`OPENAI_PROVIDER_POLICY_ID` but no `PROVIDER_POLICY_REGISTRY`. The committed
rights record explicitly rejects provider authorization when that exact
source-owned mapping is absent. The dirty helper in `source_rights.py` does not
provide the missing registry and is not authority. Therefore no provider
transmission, live rights revalidation, Factory integration or provider
readiness may be claimed. Public-axis checks are only offline registry and
capability checks; they do not authorize publication.

## P4-C findings

The adapter reads the selected SQLite file using `mode=ro&immutable=1`,
`query_only`, a contiguous clean-v29 migration check, and required-table
allowlisting. It rejects a non-empty WAL rather than observing an unstable
snapshot. It joins run, task, task-attempt, request-item, delivery-attempt,
physical-attempt, membership, receipt, reservation, reservation-task, trace and
cost rows; orphan, duplicate, missing, inconsistent and unknown-state cases
fail closed.

The file-backed fixture persisted two tasks and attempts, Standard delivery and
physical attempts, receipts, two AUD reservations, two exact `0.125000` actuals
and two exact `0.875000` releases. Decimal parsing rejects floats and checks
currency consistency. A replay after closing/reopening produced
`replayed_terminal`, zero new provider posts, and identical snapshot and
diagnostic hashes. Provenance includes the resolved database path, run ID,
schema version, record counts, snapshot hash and observation reference. The
pure diagnostic module excludes prompts, source text, credentials and response
bodies.

Independent rerun, with bytecode/cache disabled and an external basetemp:

```text
tests/runtime/test_phase5_run_diagnostics_catalog.py
tests/test_phase5_run_diagnostics.py
tests/test_phase5_standard_transport.py
tests/test_standard_delivery_job.py
tests/runtime/test_task_state.py
tests/runtime/test_migrations.py
tests/runtime/test_budget_ledger.py
tests/runtime/test_currency_accounting.py
69 passed
```

The evidence is a test-generated local SQLite run made by the provider-free
`FakeProvider` fixture. It is not a historical production run, does not cross
a live provider, and does not establish provider-side exactly-once effects,
billing reconciliation, multiworker behavior, SLOs, alerts or production
health. The adapter itself does not import the dirty catalog, but its test
fixture does use the current dirty `SQLiteCatalog` to create the database; this
is why the result is `PARTIAL` rather than production integration acceptance.

Adversarial code-review notes: restart evidence is local replay against an
unchanged immutable snapshot, not proof of a real process/provider restart;
the timestamp fallback uses wall-clock time when all source timestamps are
absent, which can undermine repeatability; and the adapter carries an
aggregate snapshot hash rather than independently content-addressing every
ledger row. These are bounded-test limitations, not evidence of failure in the
fixture used here.

## Ranked mandatory next work

1. **Source-owned provider authority (P3c-A blocker).** Add and propagate an
   exact versioned provider-policy registry in the clean source-rights
   authority, with negative/positive tests and immediate pre-provider
   revalidation. Until then provider status remains `BLOCKED`; do not use the
   dirty helper as a substitute.
2. **Clean catalogue integration and provenance.** Supply a clean promoted
   `catalog.py` baseline, remove the side-installed rights-authority seam from
   the integration path, and prove v29 migration, import, rebuild, current
   frontier, record/event provenance and restart from the clean catalogue.
   SQLite must remain a rebuildable projection, not the rights authority.
3. **P4 operational evidence.** Add a clean-catalogue fixture or approved
   historical persisted run, make observation time fail closed when not
   durable, and retain per-record/task/attempt/receipt/reservation/cost hashes
   sufficient for restart and ledger audit. Separately authorised real-provider
   evidence is required for any live-readiness claim.
4. **Hygiene and final acceptance.** Remove the P4 test trailing blank line,
   rerun the clean-head focused suite, then obtain Product Owner/Data authority
   acceptance. None of these steps is authorized by this review.

## Explicit non-claims

This review does not claim provider-side exactly-once, production SLOs, live
provider readiness, historical production-run evidence, public publication,
immutable release compatibility, Viewer acceptance, Product Owner acceptance
or Gate 4 closure. No private evidence, database, cache, prompt, model output,
credential or runtime artifact was added to Git.
