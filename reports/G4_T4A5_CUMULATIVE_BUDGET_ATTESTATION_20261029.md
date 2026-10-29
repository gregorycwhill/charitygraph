# G4 T4A5 cumulative budget attestation

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free  
Branch: `gate3-cg406-remediation`  
Target HEAD: `5edcb38c6b101284782f2e5edcb146f32f972314`  
Fence: `v54`

## Disposition

Implemented one pure, deterministic, fail-closed verifier for an externally
supplied versioned project-wide AUD ledger snapshot. A positive result is only
`BUDGET_EVIDENCE_VERIFIED_NON_SEND`; it contains no request ticket and fixes
`send_authorization` to `not_authorized_for_send`.

The verifier checks canonical UTF-8 JSON bytes, duplicate keys, an independent
trusted SHA-256 pin, exact project identity, timestamp freshness, AUD currency,
finite nonnegative decimal amounts, the fixed cumulative AUD10 cap, complete
project-wide actual/reservation/physical-attempt coverage, unresolved physical
attempts, and headroom after a caller-proposed maximum one-request reservation.
It performs no filesystem, network, provider, credential, catalogue, cost or
reservation operation.

## Factual authority boundary

The current project-wide cumulative actual-spend and outstanding-reservation
snapshot remains **MISSING**. Packet-local zeroes, synthetic fixtures,
historical CG406/development ledgers and local task tests were not treated as
project-wide evidence. The existing runtime catalogue exposes reusable
cohort-scoped reservation/actual reconciliation (`budget_position` and
`accounting_budget_position`) but no safely reconciled project-wide read-only
projection for this task; no second ledger or transaction path was added.

Source-owned factual authorities still missing for any real send include the
current cumulative ledger, current pricing snapshot, FX authority where
applicable, and exact project/service/endpoint/model route authority. This task
does not guess prices, FX, provider contract values or route defaults. It also
does not establish send readiness.

## Focused verification

Two focused invocations were used, within the task limit: the first exposed a
test-fixture construction error before the verifier ran; the corrected second
invocation passed with bytecode and pytest cache disabled and an external
basetemp:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_budget_attestation.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a5-budget-attestation-20261029 -ra`

Result of the corrected invocation: **16 passed, 0 failed**. No provider/model/network/credential access,
source acquisition, spend, reservation, actual-ledger mutation, publication,
GitHub/Drive action, watcher/process management or existing-file modification
occurred.

## Exact new-file hashes

Filled after the passing focused test:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_budget_attestation.py` | `da1b9f5da5f1b90b30493396ce646e386d3c06c5365e14aaa5da388cbdc25c6c` |
| `tests/test_phase5_t4a_budget_attestation.py` | `497c7eaaa1be3822cc345c1e70841e80e697003fe2469aa59d39b331b8efeb7c` |

The report is the attestation record itself; its worktree digest is not
embedded in its own content because that would change the digest.

## Next bounded step

Obtain an independently trusted, canonical, project-wide AUD ledger snapshot
with explicit coverage and the current source-owned pricing/FX/route
authorities. Re-run this provider-free verifier against those bytes. Until
that evidence exists, the truthful state remains budget evidence unresolved;
no reservation or provider crossing is authorized by this artifact.
