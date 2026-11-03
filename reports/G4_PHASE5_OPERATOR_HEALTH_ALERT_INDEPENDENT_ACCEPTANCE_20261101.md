# Gate4 Phase 5 operator-health alert contract — independent acceptance

Status: PARTIAL — local contract evidence is mixed; live operational evidence is absent

## Scope and exact revision

- HEAD: `0ed05055b847371ef02616565ec8d473680dc50a`
- Branch: `gate3-cg406-remediation`
- Parent: `2b95eb320560d21b7336ca92b137b76cc79a86cc`
- Immutable fence supplied: v95, SHA256 `f58162d62028293fad6c07c413aa2f010c5068d2c6aa2fc495d1e5a15962c803`
- Review is limited to the direct-child contract commit, local semantics, independent probes and cache-free tests. No provider, model, source acquisition, operational side effect, publication, release or gate action was performed.

## Acceptance result

Local semantics: PARTIAL. The healthy, crossing, retry, missingness, determinism, provenance and privacy paths passed independent probes. The malformed/unobserved fail-closed path is a local FAIL: malformed flags and a runtime export missing `operator_health` raise `AttributeError` because the module references nonexistent `ObservationState.UNOBSERVED` (source lines 220, 239, 400, 412 and 416). No product-code repair was authorised in this report-only task.

Operational evidence: PARTIAL only. This review provides no live deployment, scheduler, host heartbeat, provider receipt/usage, authoritative cost-ledger, production monitoring, SLO or gate-credit evidence.

## Reviewed implementation and existing format

The direct-child commit contains exactly these three paths: `src/charitygraph/phase5_operator_health_alert_contract.py`, `tests/test_phase5_operator_health_alert_contract.py` and `reports/G4_PHASE5_OPERATOR_HEALTH_ALERT_CONTRACT_20261101.md`. The alert projection consumes the existing `charitygraph.phase5.operator-health-runtime-contract/v1` export and its `persisted_representation` safe-view records. The existing runtime contract and integrated offline Factory rehearsal were reviewed; the rehearsal is provider-free, fake-receipt based, restart/replay oriented, and deliberately holds an ambiguous send without retrying it.

## Independent probes

- PASS — healthy mixed subjects/scopes; no alerts; no inferred expenditure or SLO.
- PASS — event IDs/canonical bytes and SHA256 are stable when record input order is reversed.
- PASS — ambiguous crossing and terminal failure after crossing produce `STOP_RESEND` with run/task lineage.
- PASS — pre-send retry is isolated and does not suggest dispatch, requeue or restart.
- PASS — missing usage/receipts/cost remains unverified and prevents spend assumptions; no zero token/amount is invented.
- PASS — unknown denominator yields `rate: null`, not a zero rate or compliance claim.
- PASS — caller-created/corrupt timestamp context remains `UNVERIFIED`; durable trusted clock provenance permits the bounded observed staleness classification.
- PASS — nested synthetic private fields and unsupported-export private fields do not enter canonical bytes or diagnostics.
- PASS — unsupported schema fails closed with no alerts.
- FAIL — malformed flags and missing `operator_health` raise `AttributeError` rather than returning a diagnostic; this is the residual local defect.

The added module is read-only projection code: static review found no provider call, scheduling, catalogue/database access, requeue/restart, 65k scaling assumption or SLO-compliance claim. No provider/model/source call, spending or operational side effect occurred.

## Tests

Command:

`PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_phase5_operator_health_alert_contract.py tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_operator_health.py tests/test_phase5_integrated_offline_recovery_rehearsal.py --basetemp C:\CharityGraph-runtime\g4-phase5-alert-independent-acceptance-20261101 -q`

Result: **46 passed** (8 alert-contract, 6 runtime-contract, 29 existing operator-health, 3 integrated offline-recovery rehearsal tests). Pytest cache and bytecode were disabled; basetemp was outside the checkout.

## Changed paths and private-material boundary

The reviewed parent-to-HEAD diff is exactly the three direct-child paths above. This worker changed only this new acceptance report. The worktree was already dirty with unrelated tracked and untracked paths and was preserved. No raw evidence, credentials, runtime state, caches, logs or private payloads were added to the report or Git.

## Residual Gate4 exit requirements and next bounded tranche

Residual requirements are live deployment/scheduling evidence; trusted host/run clock provenance; production monitoring and alert delivery; authoritative provider receipt/usage reconciliation; authoritative budget/cost completeness; and explicit denominator/threshold evidence before any SLO or Gate4 credit. The next bounded local tranche is to repair the `UNOBSERVED` enum path, add regression tests for malformed flags, missing health and missing schema, and rerun this same cache-free suite. That repair is not performed here.

