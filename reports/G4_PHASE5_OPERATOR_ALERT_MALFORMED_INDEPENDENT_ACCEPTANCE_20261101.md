# Gate4 Phase 5 operator-health alert malformed-input independent acceptance

Status: PASS for bounded local semantic acceptance; PARTIAL for live operational evidence

Scope: independent local semantic acceptance of commit
`4eaa7eccb38a722a88797483ecae7bfd26492b4b` on `gate3-cg406-remediation`,
using fence v96 SHA-256
`b19206c9803b86e7bcf5bb0de014a5c03030a5f105b3817b4595f38dbc7f54ce`.
No providers, models, external sources, Drive, GitHub, publication, release,
watchers, spend, or automatic actions are used.

## Acceptance result

The repaired malformed-input path is independently accepted locally. Missing or
malformed health/flags now fail closed with typed `UNKNOWN` diagnostics; absent
or malformed schema is `UNKNOWN`, unsupported schema is `UNSUPPORTED`, and no
unhandled `AttributeError` or `TypeError` was observed. This is not live
provider, monitoring, SLO, scale, release, or Gate4-closure evidence.

## Exact diff reviewed

HEAD is the stated direct child of `0ed05055b847371ef02616565ec8d473680dc50a`.
The parent-to-HEAD diff is exactly:

- `src/charitygraph/phase5_operator_health_alert_contract.py`: five invalid
  `ObservationState.UNOBSERVED` references replaced by existing typed
  `ObservationState.UNKNOWN`; public schemas and projection policy unchanged.
- `tests/test_phase5_operator_health_alert_contract.py`: 27 focused regression
  cases for malformed shapes, missingness, timestamps, denominator, lineage,
  determinism and private-field exclusion.
- `reports/G4_PHASE5_OPERATOR_ALERT_UNOBSERVED_REPAIR_20261101.md`: repair
  report.

No `ObservationState.UNOBSERVED` enum reference remains in the implementation.

## Independent adversarial evidence

An in-memory provider-free probe passed **23 checks**, covering:

- missing/null/list/scalar `operator_health`, flags and flag entries;
- absent/malformed schema and unsupported schema;
- empty persisted records, unknown usage/cost, unknown denominator and no
  fabricated zero rate/tokens/amounts;
- missing, caller-created, invalid and untrusted timestamps as `UNVERIFIED`;
- post-send ambiguous/terminal crossings as `STOP_RESEND`, and pre-send retry
  isolation without dispatch, requeue, restart or resend advice;
- mixed subject/scope lineage isolation, nested private-field omission, and
  deterministic event IDs/canonical SHA under reversed input.

The focused alert assertions also confirm unknown usage and budget remain
unverified and that unsupported input produces no alerts.

## Test evidence

Command (cache-free, bytecode-disabled, external basetemp):

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_operator_health_alert_contract.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_operator_health.py tests/test_phase5_integrated_offline_recovery_rehearsal.py --basetemp C:\CharityGraph-runtime\g4-phase5-alert-malformed-independent-20261101 -q`

Result: **65 passed** — alert contract **27**, runtime contract **6**,
operator health **29**, integrated offline recovery **3**. Each file also
passed independently with the same cache-free settings. The repair diff passed
`git diff --check`.

## Worktree and boundary

Branch and HEAD remained `gate3-cg406-remediation` and
`4eaa7eccb38a722a88797483ecae7bfd26492b4b`; the supplied v96 fence is recorded
above. The pre-existing dirty tracked and untracked worktree paths remain
unchanged. This worker added/edited only this required report. No provider,
model, source, Drive, GitHub, publication, release, watcher, spend, cache,
runtime state, raw evidence, credentials or private payload was used or added.

## Remaining evidence gap

Operational status remains **PARTIAL**: live provider receipt/usage and
authoritative budget reconciliation, deployment/scheduler and trusted host/run
heartbeat evidence, production monitoring and alert delivery, explicit
denominator/threshold evidence for any SLO, and project-wide **65k** scale
evidence are absent. Independent Product Supervision is unchanged; this report
does not grant scorecard credit, close Gate4, or trigger any automatic action.
