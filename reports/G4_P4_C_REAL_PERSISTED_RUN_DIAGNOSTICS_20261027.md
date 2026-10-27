# G4 P4-C persisted-run diagnostics — 27 October 2026

## Result

**PARTIAL — local offline read-only persisted-run diagnostic integration is implemented and tested.**

This does not accept Gate 4, establish production readiness, prove provider
exactly-once effects, or authorize publication/release/follow-on work.

## Boundary and classification

- Workspace: `C:\CharityGraph-clean\charitygraph`
- Branch: `gate3-cg406-remediation`
- Requested clean HEAD: `0d88635f334dedc42bc3cecb29909597f10bc818`
- No provider, model, network, source acquisition, spend, production database,
  Git staging/commit, watcher, bridge, GitHub, publication, release, or gate
  action occurred.
- The worktree was already dirty. Existing changes in `runtime/catalog.py`,
  `source_rights.py`, Factory files, tests, evidence, and reports were
  preserved byte-for-byte and not used as implementation inputs.
- Local sibling Data authority was read from
  `C:\CharityGraph-clean\charitygraph-data`, including `DOCUMENT_AUTHORITY.md`,
  `CURRENT_STATE.md`, `IMPLEMENTATION_PLAN.md`, the LLM economics policy,
  integrated model, source/publication governance, taxonomy governance, and
  `TEST_PLAN.md`. The applicable boundary remains SQLite as rebuildable
  operational catalogue/ledger state, exact accounting, explicit provenance,
  and fake/recorded provider-free persistence tests.

## Clean-HEAD persistence classification

Clean HEAD migration v29 provides the operational paths used here:

`runs` → `tasks` → `task_attempts`; Standard delivery uses
`provider_request_items` → `provider_request_attempts` → `physical_attempts`,
`standard_transport_traces`, and `provider_receipts`; economics uses
`budget_reservations` → `reservation_tasks` and `cost_entries`. Migration v20
adds the exact `accounting_amount`/`accounting_currency` and
`reserved_amount`/`accounting_currency` fields. The clean HEAD API names used
to generate the fixture are the existing `SQLiteCatalog`/Standard seams:
`register_task`, `begin_task_attempt`, `create_provider_request_item`,
`create_provider_request_attempt`, `prepare_physical_attempt`, Standard
transport completion/failure, `record_accounting_actual`, and
`release_reservation`. The adapter itself imports no `SQLiteCatalog` and does
not call any dirty-only helper; it reads the committed schema directly.

The pre-existing dirty `runtime/catalog.py` diff contains unrelated P3/P2c
additions. No migration, catalog, Factory, or existing diagnostics file was
changed by this task.

## Implementation

Added only:

- `src/charitygraph/phase5_run_diagnostics_catalog.py`
- `tests/runtime/test_phase5_run_diagnostics_catalog.py`
- this report

The adapter:

- opens the selected database with SQLite `mode=ro&immutable=1`, sets
  `query_only`, and rejects a non-empty uncheckpointed WAL rather than risk a
  sidecar or incomplete snapshot;
- verifies the contiguous clean migration state ends at v29 and requires the
  committed run/task/attempt/receipt/reservation/ledger/Standard tables;
- joins one requested run by durable identity, validates task, delivery,
  physical-attempt, receipt, reservation, membership, trace and cost joins,
  and rejects missing/duplicate/orphan/ambiguous rows and unknown states;
- carries exact decimal accounting rows into the pure canonical projection,
  including actuals, releases, and explicitly directed adjustments;
- binds the projection references to the resolved database path, run ID,
  stable record snapshot hash, record counts, and a stable stored observation
  time/version. Reopening and repeating the same read produces the same
  snapshot and projection hash;
- supports restart evidence by comparing a prior immutable snapshot with the
  post-restart snapshot. A changed durable snapshot fails closed before
  marking `restart_no_resend` true.

## Evidence and tests

The new fixture is a genuinely file-backed Standard run using the existing
provider-free `FakeProvider`. It persists two tasks, task attempts, Standard
delivery attempts, physical attempts, receipts, two AUD reservations, two
exact `0.125000` actuals and two exact `0.875000` releases. A second Standard
invocation returns `replayed_terminal`, adds zero provider posts, leaves the
provider post count at two, and produces the same snapshot/projection hash.

The adapter tests also cover distinct ambiguous and systemic stop
classifications, missing run, orphan task attempt, inconsistent receipt,
repeated task attempt, unknown state, and cost-to-reservation mismatch.

Commands, all provider-free and with pytest cache disabled:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-catalog-focused-20261027-r4 tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_run_diagnostics.py
11 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-catalog-regression-20261027 tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_run_diagnostics.py tests/test_phase5_standard_transport.py tests/test_standard_delivery_job.py tests/runtime/test_task_state.py tests/runtime/test_migrations.py tests/runtime/test_budget_ledger.py tests/runtime/test_currency_accounting.py
69 passed

git diff --check
passed; only pre-existing line-ending warnings and inaccessible unrelated runtime directories were reported
```

All pytest basetemps were under `C:\CharityGraph-runtime`; no runtime fixture,
database, response body, cache, credential, prompt, source text, or private
evidence was added to the repository.

## Honest limitations

This is an offline local observer only. It does not prove provider-side
exactly-once acceptance, live provider reconciliation, multiworker behavior,
SLOs, production health, alerts, rights acceptance, source authorization,
public contract compatibility, Viewer behavior, immutable release bytes, or
publication. It intentionally fails closed on a live uncheckpointed WAL and
on repeated delivery/task attempts rather than widening the current contract.

No Product Owner acceptance or Gate 4 closure is claimed.
