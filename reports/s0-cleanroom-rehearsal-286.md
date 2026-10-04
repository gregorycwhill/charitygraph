# S0 clean-room provider-free rehearsal 286

Date: 2026-10-04 (Australia/Sydney)

## Inputs and isolation

- Builder canonical base: `2221d4e1c252451dbea3e4e98ae0d535cd36e6d1`.
- Builder intended local recovery base: `cd3e025812f41b32bb95450e3a99e45521dd0fc4`.
- Data canonical base supplied by campaign: `1513648ec358645c23ff49a34769ae91365bf47e`.
- Data intended local successor package: `191f6140cfd65cc74e70f854e40918e76026cbee`.
- Fresh Builder worktree: `C:\CharityGraph-runtime\cg-s0-cleanroom-286-builder`.
- Fresh Data worktree: `C:\CharityGraph-runtime\cg-s0-cleanroom-286-data`.
- Fresh runtime and test temp root: `C:\CharityGraph-runtime\cg-s0-cleanroom-286-runtime`.

The test process explicitly set `CHARITYGRAPH_S0_DATA_PACKAGE` to the fresh
Data worktree, set `TEMP` and `TMP` to the fresh runtime root, and removed
`OPENAI_API_KEY` from its process environment.

## Result

`scripts/validate_s0_lineage.py` completed against the fresh Data worktree.
It reported the Attempt 21 structured-authority hash
`93d57a7cc84776926ea6cf34ab6ec853ab5c553916b84ab87b0eddcee2eb31d1` and
validated 24 package artifacts.

The production CLI rehearsal in
`tests/runtime/test_s0_live_cli_rehearsal.py` reached the provider boundary
with structured authority and no A3 record. It verified that the run remained
provider-free: zero provider calls, reservations, and sends. Negative paths
covered malformed authority, authority-hash mismatch, stale attestation, an
incomplete A3 tuple, and replay/idempotency behaviour.

Test results:

- `test_s0_live_cli_rehearsal.py`: 3 passed.
- Structured-authority, locator lifecycle, and identity-lineage focus: 39 passed.
- All runtime S0 tests: 99 passed.
- All top-level S0 tests: 107 passed.
- Total S0 suite: 206 passed.

## Repairs

The legacy opaque-A3 CLI negative test had depended on a hard-coded Drive
pricing capture. It now creates and hashes a governed local fixture inside
`tmp_path`. The authorisation-package copy helper had copied unrelated source
archives and could exceed Windows path limits in a fresh temporary root; it
now copies only the governed `SCALE_S0_*` authority material and `policies`
tree, preserving repeat-copy behaviour.

No authenticated GitHub actions, provider/source calls, reset-credit actions,
reservations, physical sends, or credential reads were performed.

## End state

Local Builder branch `cg-s0-cleanroom-reproducibility-286` contains this
record and the repairs. Publication remains a guarded host action if desired:
publish its local clean-room commit for review; no publication is required for
the provider-free certification result.

The sole live-execution boundary remains a fresh human A3 attestation together
with independently authorised provider credentials and canonical live
authority. No new Attempt was allocated.
