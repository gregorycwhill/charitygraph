# G4 T4A7 budget verifier edge-case repair

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
Branch: `gate3-cg406-remediation`  
Starting HEAD: `59d982d0862c76d7af5bcefd8ba1e138e31af637`  
Fence: `v56` / `e9996da194468a768b680cead3a4b72df20b9281c62dede47fc1c41e2f23b7fb`

## Result

Implemented the one bounded T4A5 repair. `_parse_amount` now accepts a copied,
finite, nonnegative `Decimal` caller value while retaining string handling and
rejecting float, bool, NaN, Infinity, negative and unknown values. No ledger,
provider route, source acquisition or send path was added or changed.

Focused tests now directly cover valid/invalid Decimal proposals, nested and
root duplicate JSON keys, naive/future/stale `as_of`, independent exact SHA
pin versus snapshot provenance, incomplete coverage, pending/ambiguous
physical attempts, deterministic replay, and filesystem/network/provider-free
execution. The positive result remains exactly
`BUDGET_EVIDENCE_VERIFIED_NON_SEND`, with no ticket or send authorization.

## Allowlisted diff and hashes

Only these three paths are changed by this task:

- `src/charitygraph/phase5_t4a_budget_attestation.py`: Decimal parser repair.
- `tests/test_phase5_t4a_budget_attestation.py`: 31 focused contract and edge-case tests.
- This report.

Worktree SHA-256 before commit:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_budget_attestation.py` | `14324f22ba94aa374adae6c82402c4cb0d40610213a9522de523bb05b3e436fc` |
| `tests/test_phase5_t4a_budget_attestation.py` | `356514864fd86b23e256e3257b61d1fc1fa5b35aaef7def5e74a9fd200c4ca80` |

The repository had unrelated dirty tracked and untracked paths at the starting
HEAD. None was staged, edited, or absorbed; prior reports and runtime state
remain untouched. This report does not embed its own hash.

## Verification

Both permitted focused invocations were used:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a7-budget-verifier-edgecase-20261029 tests/test_phase5_t4a_budget_attestation.py`

Exit code: **0**. Result: **31 passed, 0 failed**.

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a7-budget-verifier-edgecase-repair-final-20261029 tests/test_phase5_t4a_budget_attestation.py`

Exit code: **0**. Result: **31 passed, 0 failed**. No provider/model/network,
credential, source, spend, reservation, ledger mutation, publication or
filesystem side effect occurred. Static `ast.parse` checks passed for both
changed Python files. The unrelated pre-existing worktree whitespace warning
is outside the allowlist.

The required direct-child commit could not be created: `git add` failed with
`Permission denied` creating `.git/index.lock`; read-only inspection confirmed
no stale lock and a platform read-only `.git` boundary. No paths were staged,
and no escalation or unrelated permission change was attempted.

## Bounded limitations and next separate task

This repair does not establish the truth, provenance or completeness of a
current project-wide accounting export; the verifier still validates only
caller-supplied canonical bytes and an independently supplied trusted pin.
It does not establish pricing, FX, route, credentials, real-send readiness,
authorization or Gate 4 closure. The factual positive state remains
evidence-only and non-send.

The next separate source-owned task is to produce a current, independently
trusted canonical project-wide accounting export covering every paid logical
task, retry, physical attempt, reservation, actual, pricing/FX identity and
ambiguous or unknown attempt, then feed that export through this verifier.
That task must remain read-only and must not reserve, send, infer zero, or
treat a candidate hash as an attestation.
