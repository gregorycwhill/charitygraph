# G4 Builder operator-health independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Decision: **PARTIAL acceptance of the bounded module; Gate 4 remains open.**

This is an independent, provider-free review of
`gate3-cg406-remediation@3b9a6e22651452344997425ddd089ffe534f6352`, whose exact
parent is `3eb28abf4647136132e7fe558900d091c21d814b`. The v78 immutable fence
was `5e2837f451c225e284921bac1251baa3372cb766f2d93ab065860445e3502b40`.
The direct-child commit contains exactly these three added paths and no other
committed changes:

1. `src/charitygraph/phase5_operator_health.py`
2. `tests/test_phase5_operator_health.py`
3. `reports/G4_BUILDER_OPERATOR_HEALTH_IMPLEMENTATION_20261031.md`

The commit tree hashes were `3ada50a4734978d2c6ba2b0f2ac778b22a00e818`
(child) and `4441dc5427225f958fbd5dbc7dcbbeb2f60c31c3` (parent). The three
committed file SHA-256 values are respectively
`4592cdf01eaecb5108f9a262b378594eeca54a4c47a3483544e140fb7da3dd5d`,
`64c0220783a5b4dc5fd0ea6b36163abffb440f892b7212d92cc6b5ad33c72d44`, and
`b6c2f71cb0ebbf65649737316b8309c17c13d8edc84f7a2d2e91dba86dc63e73`.

## Verification

The clean, cache-free run used an external basetemp and passed **81 tests**:

| Area | Result |
| --- | ---: |
| operator-health tests | 14 passed |
| Phase-5 delivery | 14 passed |
| Phase-5 run diagnostics | 7 passed |
| persisted-run diagnostics catalogue | 8 passed |
| standard transport | 35 passed |
| budget ledger | 3 passed |

Independent probes also confirmed order-independent canonical bytes and hash,
empty-catalog window preservation, conflicting receipt fail-closed behaviour,
and no file opening. The order-invariance probe produced SHA
`e23c4fa0570e88ce661426ab8fc2cb2dc63fe31442b273b9c4cd1920a491d1c1`.

## Capability classification

| Claimed capability | Result | Evidence and boundary |
| --- | --- | --- |
| Deterministic serialization and SHA identity | PASS | `phase5_operator_health.py:552-566`; tests `test_phase5_operator_health.py:71-87,251-257`; adversarial row/key reordering was byte-stable. |
| Exact status denominators, reporting windows and observed-time throughput | PASS, bounded | `:278-310`; tests `:103-118,170-180`. Unknown/zero windows do not divide. With zero observed rows, the metric-level elapsed denominator is `null` even when the document window is known. |
| Stalled, failed, ambiguous, retry/recovery, latency and scheduling diagnostics | PASS, bounded | `:313-326,462-501`; tests `:89-139,197-220`. Only explicit timestamp pairs are measured; provider-side effects remain unobserved. |
| Per-run subject/scope/source provenance and as-of scoping | PASS | `:504-512,538-550`; tests `:153-167`. This is provenance of supplied rows, not project-wide completeness. |
| Decimal costs, currency/FX provenance and reservation reconciliation | PARTIAL | `:359-459`; tests `:183-249`. Decimal and missing/stale-ledger fail-closed paths work, but FX is represented by required IDs rather than independently validated rates, provider-currency validation is loose, and a ledger with no release rows projects release amount `0`. |
| No double-counting retries, duplicate receipts or bundles | FAIL for the full claim | Cost actuals deduplicate same receipts at `:402-412`, and retries/recovery are flagged. However provider usage sums raw receipt rows at `:546`; a duplicate receipt probe reported count `2` and tokens `20`. Reservation rows are also summed without reservation-ID deduplication at `:418-429`; duplicate ID rows produced reserved amount `4` from two `2` rows. |
| Missing/stale/incomplete project ledger fails closed | PASS | `:336-356,434-449`; tests `:234-249`. No project total is treated as zero when ledger evidence is absent, stale or incomplete. |
| No implicit provider permission, model promotion or external side effect | PASS | Module has no HTTP/provider/file-write/model-promotion path; tests `:251-259` reject file opening and assert provider-free limits. The diagnostic is read-only over caller-supplied rows. An object adapter can bypass the float guard because `_no_float` does not traverse arbitrary object attributes (`:210-227`); callers should use mappings or `OperatorHealthSnapshot`. |

## Baseline, ledger and boundary

The pre-existing dirty worktree was preserved; no tracked dirty file was edited
and no source, cache, provider, bridge, watcher, publication or GitHub action was
performed. The original engineering result at
`runtime/.../gate4-operator-health-v77-sol-0750-1bd22a.json` records
`provider_calls: 0`, `source_acquisition: false`, `publication: false`, the
exact three-path commit, and `unexpected_paths: []`. This acceptance made no
provider call, reservation or spend. Its cost-ledger conclusion is limited to
the supplied snapshot contract and the fail-closed tests above; it is not a
live project ledger or spend assertion.

No standalone local canonical Builder-to-65k plan artifact was available in the
workspace; no external source was accessed.

The bounded module advances the Gate 4 monitoring/cost-throughput criterion by
providing deterministic offline evidence over structured runtime snapshots. It
does not establish live monitoring, provider exactly-once effects, source or
project completeness, rights/route authority, or Gate 4 closure. The canonical
65k scorecard remains Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned; this bounded
acceptance does not change that state.
