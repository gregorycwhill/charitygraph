# G4 T4E recovery-authority repair — independent acceptance

Date: 2026-10-31 (Australia/Sydney)

## Verdicts

| Surface | Verdict | Boundary |
|---|---|---|
| Dormant validator | **ACCEPT** | Bounded structural validation only; no authority or execution eligibility |
| Live bridge integration | **NOT AUTHORISED** | No integration is present or accepted; no bridge/adoption action was run |

## Exact review identity

Reviewed `gate3-cg406-remediation` at HEAD
`354619c30b5fe85c2a4d513b111315c432524fc6`, parent
`6c88e7da57d85bd4eaf86961b54547668c3eabfd`, subject
`bridge: commit gate4:engineering:20261031-g4-t4e-recovery-authority-repair-v72-sol-0428-8ee2ac`.
The commit changes exactly three paths: the repair report, the validator and
its focused test. The reviewed working-tree bytes are unchanged from HEAD;
SHA-256 values are:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/g4_clean_target_recovery_authority.py` | `8ba4ac3a7c036fdd6c1ca934dbe5a67eea3ef98243974ff645d409a622f464ae` |
| `tests/test_g4_clean_target_recovery_authority.py` | `f6692d5581533f3c870f69cb346a0f8782366ad1e024ad42e5657e0982909543` |
| `reports/G4_T4E_RECOVERY_AUTHORITY_REPAIR_20261031.md` | `f8e2327f0fe19f10eb900e7b4510ffdd3a6e762648c101e445e442b3f85eeb4` |

The pre-existing dirty baseline was preserved: 14 tracked modified paths and
123 untracked paths. None is one of the three reviewed commit paths.

## Acceptance evidence

The repair removes the historical fixed HEAD/fence gate and adds a distinct
`POLICY_PROVENANCE_EPOCH` plus an `ActiveBridgeExecutionContext`. Envelope,
pins and active context must agree on repository, workspace, branch, HEAD and
fence; stale/current mismatch returns `BLOCKED` with `action: NONE`.

The formerly positive path now returns
`STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED` with `action: NONE`.
It carries `host_authentication_required: true`, keeps T3, provider, rights
and ordinary-dirty adoption limits blocked, and treats timeout as evidence
only. A caller-created `TrustedRecoveryPins`, context, or fake
`RecoveryHostReadback` cannot produce `DRY_RUN_ELIGIBLE`, adoption, or bridge
permission: supplied readback is explicitly rejected as
`host_authentication_integration_unavailable`.

The v72 and v73 tests use different dynamic HEAD/fence values and confirm the
same structural-only result. They do not silently assert that either value is
an independently authenticated live fence. No authenticated v73 host
readback is available in this dormant module.

The previous independent REJECT findings are therefore addressed for the
dormant contract: the stale v71/old-HEAD constants are gone, policy epoch and
active context are separate, and caller-supplied values cannot become
actionable. Cryptographic/independent-origin verification remains deliberately
outside this pure validator and is still required before any host integration.

## Tests and boundary review

Executed in a disposable runtime with `PYTHONDONTWRITEBYTECODE=1`, `python -B`,
pytest cache disabled, and basetemp outside the repository:

```text
28 passed, 0 failed
tests/test_g4_clean_target_recovery_authority.py
```

An additional provider-free probe passed 8/8 checks: v72 and v73 structural
only results, forged pins, forged active-context HEAD/fence mismatches, fake
readback rejection, timeout-semantic rejection, and v72/v73 non-silent
distinction. The historical 32 focused / 50 regression counts are validated
as envelope claims by the dormant tests; those full suites were not rerun in
this acceptance and are not treated as fresh evidence. Source/test
`git diff --check` was clean.

Static bridge review found zero references to this validator or
`RecoveryHostReadback` in `bridge/`. The existing bridge remains the separate
host-owned transport and exact-fence/dirty-baseline/commit boundary. No live
bridge integration, adoption, watcher, Git metadata, provider/source,
credential, Drive, publication, release, or gate action occurred.

## Smallest next safe step

Keep the validator dormant. Any future work must be a separately authorised
host-owned integration that authenticates the active context and independently
verifies status, fence, result, report and source/test/artifact bytes before
calling this structural validator. Repeat independent acceptance then; do not
infer bridge permission or Gate 4 closure from this report.

Only this private acceptance report was written.
