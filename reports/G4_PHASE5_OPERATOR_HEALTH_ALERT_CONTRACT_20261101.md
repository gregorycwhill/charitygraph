# G4 Phase-5 operator-health alert contract

Status: PARTIAL structural monitor; implementation and focused verification complete.

Scope delivered: `src/charitygraph/phase5_operator_health_alert_contract.py` adds a pure alert projection over the existing Phase-5 operator-health/runtime export seam. It preserves source, subject, scope, run and task provenance; treats missing evidence as unknown/unverified; generates deterministic event identities; accepts a versioned threshold policy; and emits no monitoring side effect, restart, requeue, duplicate dispatch, provider call or spend.

Actual APIs used: `project_phase5_operator_health_alerts` / `project_operator_health_alerts`, `AlertThresholdPolicy`, `canonical_operator_health_alert_json`, and `operator_health_alert_sha256`. Input is the existing `charitygraph.phase5.operator-health-runtime-contract/v1` document (`operator_health` plus its allowlisted `persisted_representation.records`), with support for the existing catalogue projection object. Archaeology/read: `phase5_operator_health.py`, `phase5_operator_health_catalogue.py`, `phase5_operator_health_runtime_contract.py`, `phase5_run_diagnostics_catalog.py`, and `phase5_provider_history_evidence_adapter.py`, plus focused tests. Existing dirty files are outside this task and remain untouched.

Projection families:

- Ambiguous or terminal post-crossing events: `CRITICAL/HIGH`, `STOP_RESEND`.
- Missing or ambiguous provider usage and unverified authoritative budget: `HIGH` (or `UNKNOWN` without a bounded run), `PREVENT_SPEND_ASSUMPTION`.
- Failed, retryable or stalled task records: bounded `ISOLATE_TASK`; staleness is `UNVERIFIED/REVIEW_UNVERIFIED` unless explicit trusted/durable clock provenance and a supplied threshold exist.
- Unsupported schema, malformed flags, absent records and zero/unknown denominators remain explicit diagnostics/nulls; no missing-event-as-zero or no-failure claim is made. No charity/service SLO is emitted.

Concrete synthetic operator-visible example: a runtime-contract export with `request:amb` in `flags.ambiguous`, `run:1`, `task:1`, `subject:1`, `scope:1`, and a durable request row with `status=send_ambiguous` yields event `alert-event:aafb0945b42dda6ff4525b4f0c88d793ccbeeccf38ec7cb4c6ad22b63885b4d7`, family `provider_crossing_ambiguous`, severity `CRITICAL`, disposition `STOP_RESEND`, and an allowlisted evidence reference to `requests/request:amb` with `source:runtime` / `source:v1`.

Verification (cache-free):

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_operator_health_alert_contract.py tests/test_phase5_operator_health.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_provider_history_evidence_adapter.py tests/test_phase5_run_diagnostics.py --basetemp C:\CharityGraph-runtime\g4-o1c-alert-contract-pytest-6`

Result: 77 passed in 1.14s. New tests cover healthy, terminal and ambiguous crossing, pre-send retry isolation, missing usage/receipts and budget, caller-clock staleness, trusted-clock staleness, mixed subject/scope, duplicate and reordered events with stable SHA, private nested-field exclusion, and zero/unknown denominator plus unsupported input.

Remaining gaps: this is not live host monitoring, a scheduler, a restart/requeue authority, a second ledger, a provider-history completeness verifier, or a project-wide authoritative budget/SLO measurement. Live staleness requires a future trusted clock/heartbeat provenance seam; authoritative spend prevention still depends on the governed budget/ledger authority; Gate4 monitoring/scheduling/concurrency/recovery industrialisation and the 65k plan remain outside this task. No provider/model calls, spend, acquisition, publication, release or scorecard mutation occurred.
