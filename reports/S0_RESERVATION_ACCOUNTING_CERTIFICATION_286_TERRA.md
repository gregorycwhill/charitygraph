# S0 reservation and accounting certification 286 (Terra)

## Scope and result

This provider-free certification audited the current S0 path from durable
Attempt 21 authority and structured A3 checkpoint material through frozen
locator packet preparation, reservation binding, accounting reconciliation,
and the durable send boundary.  It made no provider call, live reservation,
authenticated GitHub mutation, or reset-credit action.

The implementation is fail-closed at the relevant crossings.  A locator
packet must be attempt-owned, checkpoint-bound, A3-bound, and carry the
frozen pricing snapshot before a reservation lifecycle can be prepared.
The send gate rechecks the durable lifecycle and A3 immediately before it
records `send_started`.  A restarted gate cannot begin a second request.
Accounting accepts only durable receipt-matching usage and governed pricing
evidence; it records the actual and releases remaining reserved exposure
idempotently.  Ambiguous or malformed post-crossing evidence remains held.

## Checks exercised

- Authority, checkpoint, structured-A3 material/hash, attempt, project, and
  frozen packet binding.
- Per-request and aggregate economic caps, pricing/currency identity,
  retained exposure, exact-zero/exhausted capacity, and governed FX handling.
- Physical-bundle and provider-request identity, request idempotency,
  restart-after-send-started, actual-before-release crash recovery, and
  duplicate terminal re-entry.
- Post-response schema failure, missing/partial/mismatched usage, model
  mismatch, unreconciled response identity, and held ambiguous crossings.
- Provider-free dry-run/CLI paths and current Attempt 21 lineage; no Attempt
  20 value is used as current execution authority.

## Reproducible evidence

This closure audit used the current consolidated successor worktree:

```
C:\CharityGraph-runtime\terra-s0-a3-endtoend-repair-286-consolidated
cg-s0-structured-a3-endtoend-repair-286-consolidated
cd3e025812f41b32bb95450e3a99e45521dd0fc4
```

It binds the immutable current Attempt 21 package explicitly, rather than
using the removed historical host worktree path:

```
$env:CHARITYGRAPH_S0_DATA_PACKAGE='C:\CharityGraph-runtime\s0-attempt21-successor-data'
```

Focused provider-free suite (100 collected, passed):

```
python -m pytest tests/runtime/test_s0_live_cli_rehearsal.py tests/runtime/test_s0_locator_search_lifecycle.py tests/runtime/test_s0_orchestration.py tests/runtime/test_s0_structured_authority.py tests/test_s0_identity_lineage.py tests/runtime/test_s0_accounting.py tests/runtime/test_currency_accounting.py tests/runtime/test_s0_execution_attempt_identity.py tests/runtime/test_s0_identity_checkpoint.py tests/runtime/test_s0_pricing_boundary.py tests/runtime/test_s0_historical_terminals.py tests/runtime/test_scale_s0_durability.py tests/runtime/test_scale_s0_halts.py -q --basetemp=C:\CharityGraph-runtime\pytest-s0-closure-286-focused-bound
```

Complete runtime suite (202 collected, passed), run in two disjoint batches
because the host command runner has a 30-second foreground cap:

```
python -m pytest tests/runtime/test_s0_execution_attempt_identity.py tests/runtime/test_s0_historical_terminals.py tests/runtime/test_s0_identity_checkpoint.py tests/runtime/test_s0_live_cli_rehearsal.py tests/runtime/test_s0_locator_search_lifecycle.py tests/runtime/test_s0_model_d_integrated_restart.py tests/runtime/test_s0_orchestration.py tests/runtime/test_s0_pricing_boundary.py tests/runtime/test_s0_project_binding.py tests/runtime/test_s0_source_authority_runtime.py tests/runtime/test_s0_structured_authority.py tests/runtime/test_scale_s0_durability.py tests/runtime/test_scale_s0_halts.py tests/test_s0_acquisition_bridge.py -q --basetemp=C:\CharityGraph-runtime\pytest-s0-closure-286-runtime-a
python -m pytest tests/runtime/test_bitemporal_knowledge.py tests/runtime/test_budget_ledger.py tests/runtime/test_cache_and_artifacts.py tests/runtime/test_correction_invariants.py tests/runtime/test_currency_accounting.py tests/runtime/test_direct_service_persistence.py tests/runtime/test_knowledge_persistence.py tests/runtime/test_legacy_cost_entry.py tests/runtime/test_migrations.py tests/runtime/test_model_execution_safety.py tests/runtime/test_s0_accounting.py tests/runtime/test_section16_subjects.py tests/runtime/test_semantic_result_lineage.py tests/runtime/test_source_evidence.py tests/runtime/test_task_state.py -q --basetemp=C:\CharityGraph-runtime\pytest-s0-closure-286-runtime-b
```

An initial unbound focused invocation found seven identity-lineage failures:
the test's legacy default points to `C:\CharityGraph-runtime\.s0-policy-data`,
which no longer contains the immutable lineage registry.  Binding the current
Attempt 21 Data worktree above made all 100 focused tests pass.  This is local
test-environment configuration drift, not an S0 execution-path defect.  All
commands use isolated writable `--basetemp` locations.

## Disposition

No production code repair was necessary.  This corrected report is the only
closure-audit change.  A real reservation/send remains blocked pending a
separately authorised fresh human A3 and canonical live authority.  The
provider-free readiness path itself is certified at the SHA above; publication
of this local evidence remains a guarded authenticated-host action.
