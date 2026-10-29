# G4 T4A9c linkage completeness repair

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD at start: `24569165f7b14693ea43d054224864f5b773db64`  
Fence: `v59` / `4608d1b7a4b788ed5d5fd058aeeb9ac3178a679c9fcb4850441fd65885a35cd8`

## Result

Completed the four bounded T4A9b repairs in the pure mapping validator. The
result remains `CANDIDATE_NOT_ATTESTED` only for a complete valid fixture;
`independent_trust` remains `NOT_SUPPLIED`, and no project-wide total or send
ticket is produced.

- Added caller-supplied `delivery_jobs` coverage and migration-13 job/run,
  provider and route identity checks across request items and attempts.
- Added reverse completeness for every terminal physical attempt: exactly one
  request item, provider attempt and receipt is required independently of cost
  rows. Pending, unknown and ambiguous states fail closed.
- Added migration-10 receipt `physical_attempt_id` uniqueness checking before
  receipt indexing.
- Actual cost rows now require provider amount and currency, retain pricing/FX
  identity checks, and reject conflicting AUD accounting money.

The implementation uses only migration-29 columns from the pinned local
migration source (`75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c`).
The validator remains mapping-only: no SQLite, filesystem, socket, provider,
model, network or credential surface.

## Focused validation

Both permitted invocations targeted only the T4A9c test module, disabled
bytecode/cache writes, and used external runtime basetemp directories.

1. `g4-t4a9c-repair-20261030-01`: exit `1`, **12 passed, 1 failed**. The
   failure identified a repair regression treating `held` as acceptable; it
   was corrected so only explicit terminal physical/provider statuses pass.
2. `g4-t4a9c-repair-20261030-02`: exit `0`, **13 passed, 0 failed**.

The final post-test cleanup removed only unused constants; it does not change
runtime behaviour. Final source and test files parse successfully with Python
AST parsing. Tests cover positive linkage, all four adversarial defects,
empty/partial coverage, deterministic replay and the no-I/O guard.

## Final target hashes

| path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py` | `0774def89df1e1fdba73dd317ad347fa7eaed5ed71b2863a95914f42f1150d9b` |
| `tests/test_phase5_t4a9_sqlite_accounting_contract.py` | `1dbe75a10d9e37c6ce3764ae2c068d10a5993eb39e78b21a3efabb2c23dd324f` |

## Boundary

Only the source, focused test and this report are task paths. The pre-existing
dirty runtime/catalogue, T4A2/T4A8 paths, evidence directories and both T4A9
partial export files were not imported, changed, copied, staged or absorbed.
No source acquisition, provider/model call, spend, reservation, database
export, publication, GitHub/Drive mutation, watcher action or gate closure
occurred. The result does not verify caller completeness or source authority.

The requested exact-three-path local commit was attempted after an explicit
path-list check but could not be created: Git was denied creation of
`.git/index.lock`. The failed `git add` staged nothing; no commit or other Git
mutation was made.
