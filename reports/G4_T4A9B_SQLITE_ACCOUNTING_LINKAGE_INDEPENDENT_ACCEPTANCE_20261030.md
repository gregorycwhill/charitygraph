# G4 T4A9b SQLite accounting linkage — independent acceptance

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free, report-only  
Branch: `gate3-cg406-remediation`  
HEAD: `24569165f7b14693ea43d054224864f5b773db64`  
Parent: `b3e01793100b9c92e992559187a3177db650662b`  
Fence supplied: `v59` / `4608d1b7a4b788ed5d5fd058aeeb9ac3178a679c9fcb4850441fd65885a35cd8`

## Result

The pinned HEAD is one direct-child commit of the requested parent. Its diff is
exactly these three paths: the T4A9b contract source, its focused test, and the
successor worker report. The target paths are clean in the worktree and there
are no staged changes. The implementation and tests match the worker report:

| path | SHA-256 | Git blob |
|---|---|---|
| `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py` | `03c67fa6f4caef27d52d17839520408925bd4754620b75add99b9d8ad750f995` | `cd31ad75755e7190f13b8daa8c980828a51c3b44` |
| `tests/test_phase5_t4a9_sqlite_accounting_contract.py` | `a8e5216dd687814f66c431515a3a600fec0831ae6d19efe4c85d5bd7a830c840` | `a4a8ee00467e79981f12deacc1b3cec085cb90f4` |

The one independent focused run was:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a9b-independent-acceptance-20261030-01 tests/test_phase5_t4a9_sqlite_accounting_contract.py
```

Exit `0`: **8 passed, 0 failed**. The worker's earlier 7-pass/1-fail and
8-pass history was not counted as this acceptance.

## Independent assessment

Migration source is version 29, SHA-256
`75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c`.
The contract checks the supplied `cost_entries → task_attempts → tasks →
physical_attempts` identity and the request-item/attempt/receipt links. The
duplicate `provider_request_attempts.physical_attempt_id` check is correctly
performed before the provider-attempt index, so the migration-13 uniqueness
diagnostic is retained. It also rejects tested orphan, missing, ambiguous,
unpriced, contradictory, non-AUD, coverage and authority cases; canonical
replay is deterministic; and the result remains `CANDIDATE_NOT_ATTESTED` with
no total, trust assertion or send ticket. The source has no SQLite, filesystem,
socket, provider or network surface.

The narrow migration-29 linkage claim is nevertheless **PARTIAL**, not fully
accepted. Actual defects beyond the worker report are:

1. `delivery_jobs` is not an input view, so the required migration-13
   `delivery_job_id`/run/provider-route identity is never checked. Runs,
   cohorts and reservation joins are also outside the contract.
2. Checks are mostly child-to-parent. A terminal physical attempt with no
   request item, provider attempt or receipt can pass when no cost row points
   at it; coverage flags do not prove reverse completeness.
3. Receipt identity is indexed only by `provider_receipt_id`; the validator
   does not reject two receipt rows sharing one `physical_attempt_id`, despite
   the migration-10 uniqueness constraint.
4. An actual cost row may omit both `provider_amount` and `provider_currency`
   while retaining pricing/FX IDs. Only missing pricing/FX IDs are classified
   as unpriced, so provider-price completeness is not fail-closed.

The T4A9 partials remain byte-preserved: source SHA
`ae44e25a1eb7aa123da2151dd32f136aca14d04287631dec1e2a7e416e35a8a8` and test
SHA `db395f8d6ae7c005f3c98570cb9e1ee355ffeb964899b861c810916a4dc71a1d`.
The pre-existing T4A8/T4A2 dirty paths remain present and were not absorbed,
edited, staged or cleaned.

## Separate dispositions

| Boundary | Disposition |
|---|---|
| Pure provider-free candidate validator | **ACCEPT** |
| Narrow migration-29 cost/request/receipt linkage contract | **PARTIAL** |
| Current factual project-wide ledger | **REJECT** — no source-owned live export or completeness proof |
| Independently trusted source pin | **REJECT** — authority and content hash are caller assertions |
| Pricing/FX authority | **REJECT** — migration 29 has IDs but no pricing/FX authority tables |
| Current provider route | **REJECT** — no route is established by this contract; no crossing occurred |
| Cumulative AUD10 position | **REJECT** — not evidenced |
| Real-send authority | **REJECT** — no ticket or authorization is produced |
| Gate 4 closure | **REJECT** |

## Small next task

One distinct task within 600 seconds: extend only the clean T4A9b pure mapping
contract and its fixtures to include minimal `delivery_jobs` identity,
receipt-per-physical uniqueness, reverse completeness, and provider amount /
currency presence checks. Do not open a database, attempt a full-schema export,
use or change either T4A9 partial, call a provider, reserve budget, or alter
the route.

No code/test edits, provider/model/network/credential calls, acquisition,
spend, publication, GitHub/Drive mutation, watcher/process action, commit,
release or follow-on dispatch occurred. No private source material was added.
