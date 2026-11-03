# G4 Builder operator-health dedup independent acceptance

Date: 2026-10-31 (Australia/Sydney)
Decision: **PARTIAL acceptance of the bounded repair; Gate 4 remains open.**

This was a local, provider-free acceptance of
`gate3-cg406-remediation@a058df5cc97787947cb4de0629162729c4f9da72`, whose
exact parent is `3b9a6e22651452344997425ddd089ffe534f6352`. The supplied v79
immutable fence is `cf8e4d5bcd3347f2edb775dcebb2d39a703f72e7fb86eefb15fb2a66e969495f`.
I read the repository authority/machinery documents, the sibling Data authority,
current state and plans, the prior implementation and acceptance reports, and
the bounded repair instruction and terminal result.

## Commit and boundary

The exact direct-child commit changes only these three paths:

1. `src/charitygraph/phase5_operator_health.py`
2. `tests/test_phase5_operator_health.py`
3. `reports/G4_BUILDER_OPERATOR_HEALTH_DEDUP_REPAIR_20261031.md`

`git diff --check` was clean for the exact three-path diff. The current target
files match `HEAD` and have SHA-256 values:

- source: `ca37b363936dc920456e34cc95a1e97d98dfc407e08c12a05ae40fc239e64a4c`
- tests: `106a61f31738e5b49b57429ebcc325274330d7fc89dd1cdd5c2c8088416b71ba`
- repair report: `188caef50a316c71a3bc0a0ead27759b3414e5d76e9cdc06a6eab223c5a2f9c0`

The pre-existing dirty Factory/T4A/T4E and unrelated paths were not absorbed
or edited. The target paths were clean before this report was created; no
tracked or status-visible changes resulted from testing.

## Verification

All pytest invocations used a new external basetemp under
`C:\CharityGraph-runtime`, `PYTHONDONTWRITEBYTECODE=1`, and
`-p no:cacheprovider`:

| Area | Result |
|---|---:|
| operator-health focused suite | 21 passed |
| Phase-5 delivery | 14 passed |
| Phase-5 run diagnostics | 7 passed |
| persisted diagnostics catalogue | 9 passed |
| standard transport | 35 passed |
| budget ledger | 3 passed |
| **total** | **89 passed** |

No provider or external source was accessed. The engineering terminal result
records `provider_calls: 0`, `source_acquisition: false`, `publication: false`,
and `unexpected_paths: []`; this acceptance also made no provider call, source
acquisition, reservation, spend, bridge, watcher, GitHub, publication or
release action.

## Claim review

| Claim | Result | Evidence |
|---|---|---|
| Identical identified receipt replays do not double-count usage/tokens | **PASS, bounded** | `_deduplicate_rows` and usage projection at `phase5_operator_health.py:214-248,631-653,668`; tests `test_phase5_operator_health.py:141-165`. Probe result was one receipt and `10/4` tokens, with duplicate warnings. |
| Conflicting same-identity receipts fail closed for usage and actual cost | **PASS, bounded** | Receipt conflict path at `:238-248` and cost conflict path at `:467-478,527-534`; tests `:154-165,211-220`. Usage became `ambiguous` with zero totals; actual cost became non-observed/ambiguous. |
| Identical receipt-linked actual costs count once | **PASS, bounded** | Receipt-key actual-cost aggregation at `:438-484`; existing duplicate-cost regression `:120-138` and conflict regression `:211-220`. This is evidence aggregation, not provider-side exactly-once effect. |
| Identical reservation IDs count once; conflicting IDs fail closed | **PASS** | Reservation deduplication and validation at `:485-510`; tests `:168-187`. Probe produced reserved `2`/one entry for an identical replay and an ambiguous null total for a conflicting `2` versus `3`. |
| Explicit zero release differs from absent release evidence | **PASS** | Release row counting and state selection at `:440-442,479-483,537-543`; tests `:190-208`. Absent rows produced `missing`/null and `MISSING`; an explicit `0.00` row produced observed `0` and `RECONCILED`. |
| Missing, incomplete and stale project ledgers fail closed | **PASS, bounded** | `_ledger_health` at `:398-418` and cost states at `:516-543`; tests `:304-318`. Probes produced `missing`, `unknown`, and `stale` states with null monetary amounts, not inferred project totals. |
| Canonical JSON and SHA are stable under row ordering | **PASS** | Canonical serialization at `:674-675`; test `:363-378`; independent probe SHA was `8b44ac82bc4120a80314f322801e8641b372a5a612570a89727c7085e6d6b2ac` for both orderings. |
| Nested float-bearing adapters are rejected | **PASS** | Recursive guard at `:117-133`; test `:350-360`; probe rejected `snapshot.receipts[0].usage.input_tokens`. |
| Decimal arithmetic and FX/pricing provenance are not overstated | **PARTIAL** | Decimal/currency/provenance checks at `:387-395,449-464,541-543`; test `:253-264`. Decimal values and required non-empty pricing/FX IDs are retained, but IDs/rates are not independently verified and do not establish an external FX rate. |
| No provider-processing permission or project-wide completeness is inferred | **PASS, bounded** | Provider-free/read-only module contract at `phase5_operator_health.py:1-7`, limitations at `:672`, and ledger completeness gate at `:409-418`. This remains a diagnostic over supplied rows, not live runtime or project completeness authority. |

## Residual limitations and live-runtime boundary

The repair still appends receipt rows with no `provider_receipt_id` or
`receipt_id` to the usage set (`:227-248`). An adversarial probe with two
identical no-identity rows therefore reported two receipts and `20/8` tokens.
That is **FAIL for deduplication of unidentifiable receipt replays**, and is
why the overall result is PARTIAL: the evidence contract must provide a stable
receipt identity before exactly-once-like local aggregation can be claimed.
The actual-cost path likewise falls back to an entry identity when no receipt
identity exists (`:465`), so it must not be read as a universal replay guard.

The module remains a pure supplied-snapshot diagnostic. The tests establish
deterministic local semantics and provider-free integration with persisted-row
shapes; they do not establish current live catalogue wiring, provider-side
effects, provider permissions, project-wide cost completeness, external FX-rate
validity, or release authority. Gate 4 is not closed. The canonical 65k
scorecard remains Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned.

No private source material, prompts, model responses, credentials, runtime
state, caches or logs were added to Git.
