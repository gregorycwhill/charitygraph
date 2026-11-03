# G4 T4E timeout / dirty-overlay independent reconciliation

Date: 2026-10-31 (Australia/Sydney)
Worker: bounded G4-O1C, report-only, provider-free
Branch/HEAD: `gate3-cg406-remediation` / `d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`
Fence: v68 / `e06d652988383909e72cf59367c8d4e290c9a9778407e72c644bae4a8c103ea3`

## Verdict

**PARTIAL reconciliation; not product acceptance and not Gate 4 closure.** The
final attested dirty source/test bytes are internally reproducible. The exact
current T3 rights records and projection remain unavailable, so exact-rights
authority is still fail-closed and blocked.

## Hash provenance and root cause

The live bytes match the bridge attestation:

| Path | Current SHA-256 | Raw diff versus HEAD |
|---|---|---:|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` | 69 added lines |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7` | 165 added, 2 removed |

The timeout report records test hash `f0a0ca3d0f18d6817c37d64f02edadfdfbf467ededc74d409a7e450d4e50a0bc`.
The prior execution log establishes the precise sequence: the worker first
ran 31 focused tests with that 731-line test snapshot, then added the
37-line `test_adapter_blocks_mixed_scope_plan_before_any_catalogue_seed`
adapter-path assertion (current line 546), producing the final 768-line
`38f8...` snapshot, and timed out while rerunning. The report therefore describes
the intermediate snapshot, not the final attested bytes. The report itself is
`cd8170ae6c3cd63c1b301325e1565e9e526227fb1b12c7683c0fee8f87f65bbd`.

## Independent clean-overlay tests

I created a fresh `git archive` of the exact HEAD, overlaid only the current
attested source/test files, disabled bytecode and pytest cache, and used
disposable basetemp/SQLite state under `C:\CharityGraph-runtime`.

- Final focused file: **32 passed in 125.30s**. The prior 31-test claim does
  not cover the final test bytes.
- Exact reported regression command (T4B/T4C/Factory/governed Factory/
  governed rights preflight): **50 passed in 10.70s** against the final
  attested overlay.

Acceptance matrix:

| Boundary | Result | Evidence |
|---|---|---|
| Scope guard | **PASS** | Mixed-scope package rejection, adapter rejection before catalogue seed, and same-scope distinct-source acceptance all pass. |
| 20 coverage statuses / five `source_silent` records | **PASS** | Final focused suite preserves and asserts all 20 `north-star-v0.3` entries and five currentness records with `missingness.status=source_silent`. This is bounded fixture/carriage evidence, not an upgrade of production missingness. |
| Exact T3 rights fail-closed | **PARTIAL** | Exact manifest rows remain `bound_not_task_eligible` with provider `blocked_provider_contract_not_bound`; an empty rights store yields ten bounded blocked diagnostics and zero tasks. No current ten-record rights store/projection was available to prove authority resolution. |
| Provenance / lineage | **PARTIAL** | Mechanical subject/scope/source/representation/hash and durable-lineage checks pass; exact current T3 authority remains unavailable. |
| Replay / idempotence | **PASS** | Synthetic deterministic seed/run/replay assertions pass with zero replay work. |
| Zero side effects | **PASS** | Tests assert zero provider calls, reservations and cost entries. This task made no provider/network/acquisition/spend/publication/Drive/process action. |
| Dirty-baseline integrity | **PASS** | Runs were isolated in the archive overlay; no pre-existing repository path was edited or staged. HEAD stayed `d41fd766...`; only this required report is new from this task. |
| Test reproducibility | **PASS** | The final hashes were checked in both worktree and overlay; final focused and 50-test regression results reproduce independently. |

## Bridge and recovery boundary

The T4E result is `CODEX_EXECUTION_TIMEOUT` at 03:07:02Z, with no commit,
zero provider calls, no source acquisition, `publication=false`, and
`semantic_product_work=NOT_PERFORMED`. The Sol protocol states that a tracked
file already dirty at launch cannot be absorbed into a local commit; its
pre-existing edit must remain protected. Therefore bridge policy prevents
committing these already-dirty two files from this checkout. No workaround,
staging, clobbering, replay, or direct bridge operation was used.

The smallest safe distinct recovery task is a fresh, separately authorized
bridge run from a clean worktree at this exact HEAD that reconstructs only the
evidence-backed two-file patch, reruns the 32/50 evidence, and lets the bridge
commit only those clean-worktree paths. It must not replay the timed-out
instruction or stage/absorb the current dirty checkout; exact T3 authority
inspection remains a separate prerequisite for full acceptance.

No raw/private evidence, prompts, model responses, credentials, runtime state,
cache, SQLite database or logs were added to Git. This report is the only
workspace output of this task.
