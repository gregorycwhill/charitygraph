# G4 T4E recovery-authority validator independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Verdict: **REJECT** for current v72 integration; dormant mechanical validator only.

## Scope and identity

Reviewed branch `gate3-cg406-remediation`, HEAD
`6c88e7da57d85bd4eaf86961b54547668c3eabfd`, parent
`070c96a854e1a2ba8e674f21d06f3df602d86006`, and requested fence `v72`
(`53d899916a6f9437f6b5d7dd44c876db4533e45a92d405e51b4babaec010bf30`).
The HEAD commit is the exact three-path validator/report/test commit. The
checkout already had unrelated dirty and untracked paths; they were preserved.

The final T4E source/test bytes match the separately pinned values:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7` |

## Independent execution

The validator and its focused test were copied to a disposable runtime
directory. With `PYTHONDONTWRITEBYTECODE=1`, `python -B`,
`-p no:cacheprovider`, and an external pytest basetemp:

- Validator suite: **21 passed**, exit 0.
- The claimed T4E focused suite, run over an exact-HEAD archive with the final
  T4E source/test overlay: **29 passed, 3 failed**. The same three failures
  reproduced with the full current source/test overlay:
  `test_phase5_t4d_e3_factory_handoff.py:402`, `:539`, and `:574`.
  They concern missing rights decisions and mixed-scope rejection/adapter
  enforcement. Thus the current independent run does not confirm 32 focused
  passes.
- The related current regression selection was **51 passed, 1 skipped**; it
  does not independently reproduce the claimed 50-test count. The prior
  timeout-forensic report's 32/50 result remains historical evidence, not
  current acceptance of this v72 target.

## Critical findings

1. **The validator is pinned to the wrong execution context.**
   `EXPECTED_HEAD` is the old `070c...` at
   `src/charitygraph/g4_clean_target_recovery_authority.py:22`, and the
   build-time fence is v71 at `:23-24`. `_valid_pin_values` rejects any
   other HEAD/fence at `:167-170`. Supplying the requested HEAD/fence returns
   `BLOCKED` with `trusted_head_mismatch` and `trusted_fence_mismatch`.
   This also prevents future exact fences without a code rebuild.

2. **Separate input is not separate trust.** `TrustedRecoveryPins` is a
   caller-constructed frozen dataclass (`:66-116`); mapping construction only
   checks shape, and pin validation checks nonblank strings, hash syntax,
   fixed branch/HEAD/fence, and the fixed artifact allowlist (`:154-180`).
   There is no signature, supervisor-issued attestation, authenticated result
   record, or verification of the bytes named by the source/result/report/test
   hashes. A malicious caller able to supply both arguments can self-proclaim
   arbitrary provenance IDs/hashes and set reconciliation `independent=True`;
   the validator will accept them if they satisfy those syntactic checks.
   The tests prove candidate-vs-pin mismatch rejection, not independent origin.

3. **Policy provenance and active bridge context are conflated/absent.** The
   schema has no distinct policy-provenance epoch or active bridge execution
   context. `workspace` and identity are merely compared to the supplied pins
   (`:286-294`), and the eligible plan echoes those pins (`:203-249`). The
   module has no bridge/watchdog integration and performs no Git, Drive,
   provider, source, publication, or transaction operation.

## Boundary results

The mechanical fail-closed boundaries are present: timeout evidence must be
`CODEX_EXECUTION_TIMEOUT` with zero provider calls/acquisition/publication and
no semantic work (`:304-320`); dirty/staged/untracked/ignored target state is
blocked (`:379-383`); the returned action is `DRY_RUN_ONLY` (`:203-206`); and
the plan carries T3, provider, rights, and ordinary-dirty-adoption limits as
false/blocked (`:188-194`, `:242-249`). No raw material is returned; the
positive-plan test also checks that its serialisation contains no `bytes`
(`tests/test_g4_clean_target_recovery_authority.py:116-127`).

These controls do not cure the stale v71 constants or caller-controlled
"independent" pins. The implementation is therefore not independently
acceptable for bridge use.

## Smallest safe bridge implication

Keep this path dormant and dry-run-only. A bounded follow-up should make the
active HEAD/fence and policy-provenance epoch explicit inputs from an
immutable, supervisor-authenticated bridge record, verify the exact source,
result, reconciliation, attestation, and artifact bytes before constructing
trusted pins, and reject unverified/self-supplied pins. Then rerun the exact
32 focused and exact 50 regression suites in a clean target, reconcile their
attestations, and repeat independent acceptance. No provider/rights
promotion, bridge ingress, publication, Git/Drive action, or dirty-target
adoption is authorised by this report.

No raw/private evidence, credentials, caches, runtime state, SQLite database,
logs, provider/network calls, or Git/Drive effects were introduced. The only
repository output from this task is this report.
