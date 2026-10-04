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

Starting and ending worktree identity were both:

```
C:\CharityGraph-runtime\terra-s0-a3-endtoend-repair-284
cg-s0-structured-a3-endtoend-repair-284
71c00f421bbf4f1f2ade2b180eac5f677dba3fda
```

Focused provider-free suite (89 collected, passed):

```
python -m pytest tests/runtime/test_s0_accounting.py tests/runtime/test_currency_accounting.py tests/runtime/test_s0_execution_attempt_identity.py tests/runtime/test_s0_identity_checkpoint.py tests/runtime/test_s0_locator_search_lifecycle.py tests/runtime/test_s0_structured_authority.py tests/runtime/test_s0_pricing_boundary.py tests/runtime/test_s0_historical_terminals.py tests/runtime/test_s0_orchestration.py tests/runtime/test_scale_s0_durability.py tests/runtime/test_scale_s0_halts.py -q --basetemp=C:\CharityGraph-runtime\pytest-s0-reservation-accounting-286
```

Complete runtime suite (201 collected, passed):

```
python -m pytest tests/runtime -q --basetemp=C:\CharityGraph-runtime\pytest-s0-reservation-accounting-286-all
```

The first focused invocation exposed a host-owned default pytest temp path
permission denial before test bodies ran.  Re-running with the explicitly
isolated writable `--basetemp` above resolved that environment condition;
there was no product failure.

## Disposition

No code repair was necessary.  This report is the only task change.  The
worktree is otherwise clean.  Publication, if desired, requires the guarded
host action to commit and publish the local report; no human A3 or external
authentication is required for further provider-free local work.  A real
reservation/send remains blocked pending separately authorised fresh human A3
and canonical live authority.
