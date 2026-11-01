# Gate 4 Phase 5 integrated offline recovery rehearsal

Status: COMPLETE (provider-free local rehearsal; not a Gate 4 closure)

## Bounded seam

This tranche integrates the existing governed task manifest, `ReferenceFactory`
and read-only operator-health catalogue projection in one small offline
rehearsal. It exercises deterministic scheduling/replay, task-local terminal
failure, retryable pre-send recovery, an ambiguous send boundary that remains
fail-closed, unrelated-task completion, idempotence, and explicit missingness.
It does not add acquisition, semantic interpretation, a provider transport, or a
second orchestrator.

## Evidence boundary

All evidence produced here is simulated/offline fixture evidence. The fake
provider is a local receipt generator only; no provider/model call, source
acquisition, authenticated provider-data claim, or production/65k result is
made. Fake receipt usage and cost rows are rehearsal accounting, not
authoritative provider usage or cost authority. Failed and ambiguous logical
tasks retain explicit `NOT_OBSERVED` result/usage missingness.

## Implementation and verification

The reusable coordinator calls the existing `GovernedFactoryPreflight` plan,
`ReferenceFactory.seed`, `ReferenceFactory.run`, durable `SQLiteCatalog`
registration/transition/reopen APIs, and the read-only
`project_operator_health_catalogue` projection. It does not implement a second
orchestrator or transport.

The focused suite passed **3 tests**. The narrow related regressions passed
**44 tests**: `test_phase5_factory.py` (8), `test_phase5_factory_chaos.py`
(2), `test_phase5_governed_factory_integration.py` (5), and
`test_phase5_operator_health.py` (29). All runs used a separate basetemp,
`PYTHONDONTWRITEBYTECODE=1`, and `pytest -p no:cacheprovider`.

The four-task rehearsal produced four deterministic physical packages and four
fake provider calls: three initial receipt-generating calls plus one recovered
retry after restart. The
healthy task completed. The terminal task became `failed_terminal` with no
accepted logical result. The retryable pre-send task had no send on its first
pass, then completed once after catalogue close/reopen. The ambiguous task
remained `send_started` without a receipt and was never resent; its result and
usage remain `NOT_OBSERVED`. Reversed input produced the same manifest hash,
schedule, event trace, fake-call IDs, and operator-health SHA. No accepted
logical effect was duplicated and no physical package crossed subjects or
scopes.

The operator-health projection reported one held run, two succeeded tasks, one
terminal failure, and one leased ambiguous task. It observed usage only for
three fake receipt rows (`3` input and `3` output tokens); the ambiguous task
has no usage evidence. Cost reconciliation is explicitly `AMBIGUOUS` because
the project ledger is not attested and the rehearsal cost rows lack provider
receipt linkage. This is the intended honest missingness, not cost authority.

Only these new allowlisted paths changed:

- `src/charitygraph/phase5_integrated_offline_recovery_rehearsal.py`
- `tests/test_phase5_integrated_offline_recovery_rehearsal.py`
- `reports/G4_PHASE5_INTEGRATED_OFFLINE_RECOVERY_REHEARSAL_20261101.md`

No raw/private source material, source snapshots, prompts, model responses,
runtime database, cache, credentials, or debug artefacts were added to Git.

## Residual boundary

This rehearsal cannot prove live provider exactly-once effects, provider
receipt reconciliation, 65k scheduling economics, source coverage, semantic
quality, or Gate 4 exit. The next substantive tranche, if separately assigned,
would need independently accepted provider-owned complete run/receipt
inventory and authority, then a separately approved bounded live or recorded
standard-transport recovery exercise that binds actual cost to receipt identity.
No such work was performed or authorised by this tranche.
