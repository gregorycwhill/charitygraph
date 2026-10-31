# G4 T4E recovery-authority repair

Date: 2026-10-31 (Australia/Sydney)  
Target: `gate3-cg406-remediation` / `6c88e7da57d85bd4eaf86961b54547668c3eabfd`

## Result

Repaired the dormant validator fail-closed. Historical build-time HEAD/fence
constants were removed. `ActiveBridgeExecutionContext` now carries the exact
dynamic repository, workspace, branch, current HEAD, fence identity and the
separate immutable policy-provenance epoch. v72 and later v73-shaped contexts
are structurally checked against the candidate and evidence pins; mismatches
remain `BLOCKED`.

The positive structural result is now
`STRUCTURE_VERIFIED_BUT_HOST_AUTHENTICATION_REQUIRED` with `action: NONE`.
Caller-constructed candidates, pins, contexts, and fake readback objects can
never produce execution eligibility. `RecoveryHostReadback` is only a narrow
future bridge seam for host-read status/fence/result/report bytes and
independently trusted SHA pins; supplying it to this pure validator is blocked
until a separately reviewed authenticated host integration exists.

The exact two-file artifact allowlist, historical 32 focused / 50 regression
labels, timeout-source semantics, T3 rights block, and existing scope limits
remain unchanged.

## Verification

Cache-free focused run:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider tests/test_g4_clean_target_recovery_authority.py
28 passed
```

Coverage includes dynamic v72/v73 structural validation, non-actionability,
malicious caller inputs, active-context mismatches, duplicate/extra paths,
dirty/staged/untracked/ignored paths, missing evidence, timeout semantics and
the exact artifact/hash and test-count boundaries.

No provider, network, source acquisition, Drive, bridge, watcher, process,
Git, publication, release, or gate action occurred. Existing unrelated dirty
and untracked paths were preserved. No private evidence, raw source, cache,
credential, runtime state or log was added.
