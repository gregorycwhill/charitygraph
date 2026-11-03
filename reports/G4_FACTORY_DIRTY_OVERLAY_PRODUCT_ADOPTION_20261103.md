# G4 Factory dirty-overlay product acceptance

Date: 2026-11-03 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free local acceptance

## Result

Accepted for bridge-owned local adoption. The current six-file dirty Factory/T4D
overlay contains real product repairs, not harness-only changes, and the focused
acceptance run passed **54 tests, 0 failed**.

The three previously failing tests were run independently: **3 passed, 29
deselected**. The four focused suites collected and passed as follows:

| Suite | Collected | Result |
| --- | ---: | --- |
| `test_phase5_t3_source_evidence_binding.py` | 9 | passed |
| `test_phase5_t4d_e3_factory_handoff.py` | 32 | passed |
| `test_phase5_factory.py` | 8 | passed |
| `test_phase5_governed_factory_integration.py` | 5 | passed |

Commands used `PYTHONDONTWRITEBYTECODE=1`, `python -B`, `-p no:cacheprovider`,
and basetemp under `C:\CharityGraph-runtime`.

## Product evidence

- `phase5_governed_factory_integration.py` now requires durable, exact
  representation-bound provider-rights decisions and records fail-closed
  diagnostics for missing, conflicting, mismatched or expired authority.
  Missing provider-rights authority produced no accepted work.
- `phase5_factory.py` exposes physical identities before scope-keyed execution
  grouping and preserves subject/scope boundaries. `phase5_t4d_e3_factory_handoff.py`
  rejects a mixed-scope physical package before catalogue seeding.
- The positive synthetic replay produced ten children, all 20 `north-star-v0.3`
  coverage entries, five `source_silent` currentness records, and zero provider
  calls, reservations or cost entries. Mixed physical scope produced zero
  accepted tasks and zero catalogue tasks.
- The matching tests exercise these outcomes and preserve valid same-scope
  bundling and the exact committed T3 authority's blocked state.

## Adoption boundary and evidence

Parent HEAD is `0a8f0413e94375e7d87049cf3cf27b846603183f`. The intended single
bridge-owned direct-child commit has exactly these paths:

1. `src/charitygraph/phase5_factory.py`
2. `src/charitygraph/phase5_governed_factory_integration.py`
3. `src/charitygraph/phase5_t4d_e3_factory_handoff.py`
4. `tests/test_phase5_factory.py`
5. `tests/test_phase5_governed_factory_integration.py`
6. `tests/test_phase5_t4d_e3_factory_handoff.py`
7. `reports/G4_FACTORY_DIRTY_OVERLAY_PRODUCT_ADOPTION_20261103.md`

The worker did not stage, commit, alter bridge/watch/fence/process state, or
touch `.git` metadata. The bridge adoption mechanism must perform the exact-path
`git commit --only`; unrelated dirty and untracked paths remain outside this
allowlist and are protected.

## Remaining gap and next substantive task

This acceptance is synthetic/provider-free and does not establish operation on
real retained-source material or a paid provider route. The remaining real-source
gap is an independently governed, already-admitted evidence run with current
provider-rights authority, cost reservation/reconciliation, and product review.
The next substantive task is that bounded real-data Factory acceptance after
bridge adoption; no source acquisition or provider call was performed here.

No private material, source bytes, runtime state, caches, credentials, logs or
generated public projections were added to Git.
