# G4 T4A9c linkage completeness — independent acceptance

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD: `a850f8104cf3e3f9150df27c4671ab084ba0453e`  
Parent: `24569165f7b14693ea43d054224864f5b773db64`  
Fence: `v60` / `849f55679e1609e06d9e7e49b9226d72ecbd0b218f803a5a0358d9f7f7f73715`

## Independent result

The pinned HEAD is the exact direct child of the requested parent. Its commit
diff is exactly these three paths, with no fourth path:

- `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py`
- `tests/test_phase5_t4a9_sqlite_accounting_contract.py`
- `reports/G4_T4A9C_LINKAGE_COMPLETENESS_REPAIR_20261030.md`

The two code/test paths are clean at HEAD and match the repair report's hashes:

| path | SHA-256 |
|---|---|
| source | `0774def89df1e1fdba73dd317ad347fa7eaed5ed71b2863a95914f42f1150d9b` |
| focused test | `1dbe75a10d9e37c6ce3764ae2c068d10a5993eb39e78b21a3efabb2c23dd324f` |

The migration source is `src/charitygraph/runtime/migrations.py`, version 29,
SHA-256 `75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c`.
The local Builder/Data authority, North Star v0.3 and current-state/planning
documents were read before review. The contract remains a pure caller-bound
mapping validator; it does not open SQLite or create a source-owned ledger.

## Focused validation

One fresh independent run was made with an external basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a9c-independent-acceptance-20261030-01 tests/test_phase5_t4a9_sqlite_accounting_contract.py
```

Exit `0`: **13 passed, 0 failed**. The repair report records the worker's
earlier sequence as **12 passed, 1 failed**, followed by **13 passed, 0
failed**; only this fresh run is independent acceptance evidence.

## Mechanical assessment

- Migration-13 `delivery_job_id` coverage is caller-required. The validator
  joins each request item to the job's `run_id`, `provider_id` and
  `model_route`, and each provider attempt to the item/job identity.
- Every terminal physical attempt (`receipt_persisted`, `validated` or
  `failed`) must have exactly one reverse-linked request item, provider
  attempt and receipt, even when no cost row refers to it.
- Receipt `physical_attempt_id` duplication is diagnosed before receipt
  indexing; the reverse-link check also rejects the resulting ambiguity.
- Actual costs require both `provider_amount` and `provider_currency`, retain
  pricing/FX identity checks, and reject a provider amount conflicting with
  persisted AUD accounting money. No conversion authority is invented.
- The fixture suite covers positive linkage, job/route contradiction, reverse
  incompleteness, receipt duplication, held physical status, missing caller
  coverage, canonical replay, AUD conflict and the no-I/O guard. Physical and
  provider pending/unknown statuses are rejected by the terminal-status
  branches; duplicate links are rejected fail closed.

Residual assurance boundary: there is no separate test for every pending,
held or unknown combination on delivery jobs and request items. Delivery-job
status is checked for membership in the known schema set, not required to be
terminal, and request-item status is not independently terminal-validated.
Those are untested broader status-semantics edges, not evidence of a live
ledger or route. They prevent upgrading this pure validator into a complete
status-aware factual ledger authority.

## Dirty baseline and exclusions

HEAD and branch remained exact. The pre-existing dirty T4A2, T4A8 and T4A9
partial paths remained present and untouched; the named T4A9 partial hashes
remain source `ae44e25a1eb7aa123da2151dd32f136aca14d04287631dec1e2a7e416e35a8a8`
and test `db395f8d6ae7c005f3c98570cb9e1ee355ffeb964899b861c810916a4dc71a1d`.
The focused test introduced no repository path, staged change, bytecode or
pytest cache. After the report write, the only new path is this required
report; all other dirty entries remain the observed baseline.

## Dispositions

| Boundary | Status |
|---|---|
| Bounded four-defect pure repair | **ACCEPT** |
| Complete status-aware migration-29 ledger/linkage authority | **PARTIAL** |
| Live factual project ledger | **NOT ACCEPTED** |
| Independent source pin and caller coverage truth | **NOT ACCEPTED** |
| Pricing/FX authority | **NOT ACCEPTED** — migration 29 carries IDs, not authority records |
| Selected provider project/route | **NOT ACCEPTED** |
| Cumulative AUD10 position | **NOT ACCEPTED** |
| Real-send authority | **NOT ACCEPTED** |
| Gate 4 closure | **NOT ACCEPTED** |

The positive result is only `CANDIDATE_NOT_ATTESTED`; independent trust remains
`NOT_SUPPLIED`, with no total and no send ticket.

## One factual next task (recommendation only)

Within 600 seconds, perform one read-only reconciliation against the already
authorised local source-owned runtime authority: pin its exact migration-29
snapshot hash, project-wide coverage declaration, delivery job/item/attempt/
receipt joins, and any available pricing/FX and selected provider-route
authority. Return a factual authority/no-authority result. Do not iterate on
fixtures, call a provider, reserve spend, or dispatch this task here.

No provider, model, network, credential, Drive/GitHub, source-acquisition,
publication, release, watcher/process or gate action occurred. No private
material was added to the report or repository.
