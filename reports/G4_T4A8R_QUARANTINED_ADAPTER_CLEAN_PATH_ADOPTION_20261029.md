# G4 T4A8R quarantined adapter clean-path adoption

Date: 2026-10-29 (Australia/Sydney)
Worker: bounded G4-O1C, provider-free
Branch: `gate3-cg406-remediation`
Starting HEAD: `aeca5ce1bc57f381a0612f7b302c83db1680569b`
Fence: `v57` / `546fd536da2fa28c91bcf78583323146525090d453794d06718e85d5e70ce3b`

## Disposition

Ported the quarantined T4A8 adapter and focused tests into the exact clean
allowlisted names:

- `src/charitygraph/phase5_t4a_durable_accounting_export.py`
- `tests/test_phase5_t4a_durable_accounting_export.py`
- this report

The implementation remains a caller-bound, read-only adapter over already-open
views. It does not open the SQLite catalogue, read or write files, mutate
state, contact a provider, reserve budget, or issue a send ticket. The only
code correction was the clean module import in the copied focused test; no
semantic heuristic, discovery path, or new acquisition path was introduced.

## Evidence and schema assessment

The two quarantined forensic files were verified before adoption and remain
untouched:

| Quarantined file | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a8_durable_accounting_export.py` | `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0` |
| `tests/test_phase5_t4a8_durable_accounting_export.py` | `321c1061ccd5f93cbdcf62c27b5d7cb4e0f4bfd11191436d925d3cfc2e327bf5` |

The adapter’s inventories and reconciliation inputs match the existing durable
catalogue schema: cohorts, runs, tasks, task attempts, budget reservations,
cost entries, physical attempts, physical-attempt members, and provider
request attempts. Accounting amounts/currency and pricing/FX identity fields
are existing schema fields; no second ledger or database view was added.
Inspected schema hash: `src/charitygraph/runtime/migrations.py` =
`75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c`.

The T4A6 candidate builder remains the reused contract (hash
`ac202755d4a42ed812a03b80688f239abb1763f110fa2bc684132b499a37e24f`).
This result is evidence-only: the candidate is not a factual project-wide
ledger, no live durable view was opened, and no independently trusted pin was
supplied. Empty or missing evidence is not treated as zero. Missing
provider/FX/pricing/coverage authority remains `NOT_ATTESTABLE` or
`BLOCKED` as applicable. `independent_trust` remains
`NOT_SUPPLIED`; there is no request ticket and
`send_authorization` remains `not_authorized_for_send`.

## Verification

Static AST parsing passed for both clean target files.
Per-target `git diff --no-index --check` checks against `/dev/null`
reported no whitespace errors; exit 1 was the expected untracked-file
difference from `/dev/null`. Final hashes were independently recomputed.

Exactly one permitted focused pytest invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' tests/test_phase5_t4a_durable_accounting_export.py --basetemp C:\CharityGraph-runtime\g4-t4a8r-clean-path-adoption-20261029`

Result: **exit 0; 8 passed, 0 failed**.

The tests cover multi-cohort/retry reconciliation without physical
double-counting, duplicate records, ambiguous/unpriced/unknown physical
states, incomplete coverage, missing or unauthorised retention identity,
canonical bytes, deterministic replay, no independent pin, no send
authorization, and filesystem/network side-effect absence.

Clean target hashes after verification:

| New file | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_durable_accounting_export.py` | `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0` |
| `tests/test_phase5_t4a_durable_accounting_export.py` | `4fe08b92a178498990d210dbe05a1ac8a9aea76399d59246549ae8195da899a1` |

No provider/model/network/credential call, acquisition, budget reservation,
spend, publication, GitHub/Drive mutation, watcher/process action, release,
gate closure, or follow-on dispatch occurred. The pre-existing dirty
catalogue/runtime, T4A2/T4A2A, other reports/evidence, quarantined files, and
original T4A8 report were not edited or absorbed.

## Commit boundary

The required exact-three-path local commit could not be created. Explicit

`git add -- src/charitygraph/phase5_t4a_durable_accounting_export.py tests/test_phase5_t4a_durable_accounting_export.py reports/G4_T4A8R_QUARANTINED_ADAPTER_CLEAN_PATH_ADOPTION_20261029.md`

failed with exit **128**:

`fatal: Unable to create 'C:/CharityGraph-clean/charitygraph/.git/index.lock': Permission denied`

No path was staged and no commit was created. No permission workaround,
watcher/process action, reset, checkout, deletion or unrelated-path mutation
was attempted.
