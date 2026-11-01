# Gate4 Phase 5 operator-health alert `UNOBSERVED` repair

Status: COMPLETE — bounded local repair verified locally

## Scope

This report records the approved local repair of the operator-health alert
projection's malformed/unobserved fail-closed paths. Work is confined to the
allowlisted alert module, its focused regression tests, and this report. No
provider, model, source, Drive, GitHub, publication, release, watcher, spend,
or runtime side effect is involved.

## Reproducer before repair

`ObservationState` permits only `OBSERVED`, `UNVERIFIED`, `UNKNOWN`, and
`UNSUPPORTED`, but the alert module referenced nonexistent
`ObservationState.UNOBSERVED` at lines 220, 239, 400, 412, and 416. Consequently
missing `operator_health`, missing schema, null/list/scalar flags, and malformed
flag entries could raise `AttributeError` instead of returning a typed
fail-closed diagnostic.

## Repair and verification plan

The repair will use existing typed states without changing the public schema,
canonicalisation, event hashing, STOP_RESEND behaviour, or private-field
allowlist. Regression probes will cover malformed input shapes, missing
records/timestamps and untrusted clocks, unknown usage/cost, mixed
subject/scope lineage, deterministic replay, and private-field omission. The
requested cache-free focused, runtime/operator-health, and integrated offline
rehearsal tests will be run with `PYTHONDONTWRITEBYTECODE=1` and a basetemp
outside the checkout.

## Current evidence

- Independent acceptance reproduced the defect; its 46-test local suite passed
  while missing the malformed branches.
- HEAD was verified as
  `0ed05055b847371ef02616565ec8d473680dc50a`.
- The worktree contains unrelated pre-existing dirty paths; they are preserved.

Final status, actual test counts, exact changed paths, and remaining operational
gaps are recorded below.

## Completed repair

The five invalid enum references now use `ObservationState.UNKNOWN` for missing
or malformed/uninterpretable observations. Existing `UNSUPPORTED` handling for
unsupported schemas and `UNVERIFIED` handling for observed-but-untrusted
staleness remain unchanged. No automatic retry, restart, dispatch, resend,
spend assumption, SLO claim, canonical hash rule, or private-field projection
was changed.

## Regression and suite evidence

Focused alert-contract run:

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_operator_health_alert_contract.py --basetemp C:\CharityGraph-runtime\g4-phase5-alert-unobserved-repair-focused-20261101 -q`

Result: **27 passed**.

Requested cache-free suite:

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_operator_health_alert_contract.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_operator_health.py tests/test_phase5_integrated_offline_recovery_rehearsal.py --basetemp C:\CharityGraph-runtime\g4-phase5-alert-unobserved-repair-20261101 -q`

Result: **65 passed** — 27 alert-contract, 6 runtime-contract, 29 existing
operator-health, and 3 integrated offline-recovery rehearsal tests. Collection
confirmed the same per-file counts. `git diff --check` passed and the invalid
`ObservationState.UNOBSERVED` reference is absent from the implementation.

The added probes cover absent/null/list/scalar operator health and flags,
malformed flag entries, missing schema, unsupported runtime version, missing
persisted records, missing or invalid timestamps under an untrusted clock,
unknown usage/cost, mixed subject/scope lineage, deterministic replay, and
private-field omission.

## Exact changed paths

- `src/charitygraph/phase5_operator_health_alert_contract.py`
- `tests/test_phase5_operator_health_alert_contract.py`
- `reports/G4_PHASE5_OPERATOR_ALERT_UNOBSERVED_REPAIR_20261101.md`

Unrelated pre-existing tracked and untracked worktree paths were preserved. No
raw evidence, credentials, runtime state, caches, logs, private payloads, or
provider/model material was added.

## Remaining real operational gaps

This local repair does not provide live deployment or scheduling evidence,
trusted host/run heartbeat delivery, production monitoring or alert delivery,
authoritative provider receipt/usage reconciliation, authoritative project-wide
budget completeness, or explicit denominator/threshold evidence for an SLO or
Gate4 credit. Independent semantic acceptance and all supervision/release
decisions remain separate.
