# G4 T4A9b SQLite accounting contract successor

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD: `b3e01793100b9c92e992559187a3177db650662b`  
Fence: `v58` / `9ca4ce44dc90eeb11640b3456e08d997d9be469d78590ad82e6f8c415b6567c6`

## Result

Implemented one distinct pure contract in the three allowlisted new paths:

- `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py`
- `tests/test_phase5_t4a9_sqlite_accounting_contract.py`
- this report

The validator accepts only caller-supplied immutable mapping views aligned to
migration 29. It checks the explicit `cost_entries` → `task_attempts` →
logical task / physical attempt chain and the explicit request-item → receipt
and provider-attempt links. It rejects orphaned, duplicate, contradictory,
unpriced, non-AUD-mismatched, unresolved and uncovered states. It never opens
SQLite, reads or writes files, creates a ledger, contacts a provider, infers
empty-view completeness, computes a positive ledger total, or issues a send
ticket. A valid result is only `CANDIDATE_NOT_ATTESTED`, with
`independent_trust=NOT_SUPPLIED` and `request_ticket=None`.

No source-owned factual export, project-wide accounting assertion, provider
route, spend, reservation, publication, release or gate closure follows from
this task. The two T4A9 partial forensic files were read-only evidence and
remain byte-preserved and untouched.

## Verification

Exactly two focused pytest invocations were permitted and run, each against
only the new test file with bytecode and pytest cache disabled and a unique
external basetemp:

1. `C:\CharityGraph-runtime\g4-t4a9b-contract-20261030-01` — exit 1,
   7 passed, 1 failed. The failure exposed that duplicate provider-attempt
   physical IDs were indexed before their migration-13 uniqueness diagnostic;
   the validator was corrected within the same new path set.
2. `C:\CharityGraph-runtime\g4-t4a9b-contract-20261030-02` — exit 0,
   8 passed, 0 failed (`0.50s`).

Command form:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp <unique-external-dir> tests/test_phase5_t4a9_sqlite_accounting_contract.py
```

## Material diff and hashes

The material diff is the new validator, its eight focused fixture-only tests,
and this report. No pre-existing dirty path was absorbed or changed by this
task. Hashes below were collected after the final test run; the report hash is
reported externally because embedding it would change the report bytes.

| path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py` | `03c67fa6f4caef27d52d17839520408925bd4754620b75add99b9d8ad750f995` |
| `tests/test_phase5_t4a9_sqlite_accounting_contract.py` | `a8e5216dd687814f66c431515a3a600fec0831ae6d19efe4c85d5bd7a830c840` |
| `reports/G4_T4A9_SQLITE_ACCOUNTING_CONTRACT_SUCCESSOR_20261030.md` | `<collected-externally>` |

No provider/model/network/credential call, source acquisition, budget
reservation, runtime database access, Drive/GitHub mutation, watcher/process
action, staging, commit, merge, release, publication or follow-on dispatch
occurred.
