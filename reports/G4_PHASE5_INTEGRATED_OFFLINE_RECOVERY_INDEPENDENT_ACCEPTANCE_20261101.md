# Gate 4 Phase 5 integrated offline recovery — independent acceptance

Status: PASS for the bounded provider-free rehearsal; not live-provider or Gate 4 closure acceptance.

## Independent evidence

- Exact HEAD and branch matched the instruction: `2af1d063595d68adbbd4826937023230bc6ef8a2` on `gate3-cg406-remediation`; parent `3114fce5dff4fde3ce6bce01b740e4d49d77a4cc`.
- A disposable `git archive` overlay outside the checkout showed exactly three added paths and 655 insertions: the rehearsal module (450 lines), focused test (131), and prior rehearsal report (74). `git diff --check` was clean.
- Static review found the new code calls the existing `GovernedFactoryPreflight` plan, `ReferenceFactory.seed/run`, `SQLiteCatalog` registration/transition/close/reopen APIs, and read-only `project_operator_health_catalogue`. Its only provider is a counting subclass of the existing `RehearsalFakeProvider`; no second semantic/provider orchestrator was introduced.
- Focused command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider --basetemp <C:\CharityGraph-runtime\...> tests/test_phase5_integrated_offline_recovery_rehearsal.py` — **3 passed**.
- Related command over the bounded factory/chaos/governed-integration/operator-health suites — **44 passed**: 8 + 2 + 5 + 29.
- An additional independent provider-free run, with forward and reversed input, passed all assertions: 4 same-subject/same-scope packages; equal manifest, schedule/event trace and health SHA; 4 unique fake provider calls; 3 unique accepted fake receipts; 1 provider call added after catalogue reopen for the pre-send retry; 0 added on idempotent replay; one unrelated healthy task completed.

The failure boundaries held: the terminal task had `result_state=NOT_OBSERVED` despite its retained fake receipt; the pre-send task succeeded exactly once after reopen; the ambiguous task remained without a receipt and with `usage_state=NOT_OBSERVED`; no accepted logical effect duplicated; and source-record, subject and scope provenance remained present and isolated. Operator health reported fake receipt usage as observed, explicitly based on deduplicated local receipts only. Cost reconciliation remained `AMBIGUOUS` because the supplied ledger was not complete/attested; no authoritative project cost was inferred.

## Limitations and next tranche

This proves only deterministic local catalogue/factory behaviour. It does not observe provider-side exactly-once effects, real provider invocation, receipt reconciliation, live cost authority, 65k economics, source coverage, semantic quality, or release/Gate 4 exit. The next highest-value Gate 4 tranche is an independently accepted provider-owned complete run/receipt inventory and authority, followed—only under separate approval—by a bounded recovery exercise binding actual cost to receipt identity.

No provider/model request, paid spend, source acquisition, private evidence, runtime database, cache, credential, GitHub/publication/release action, watcher/process change, or gate closure was performed. The pre-existing dirty checkout was preserved; this new report is the only task-scope checkout addition.

