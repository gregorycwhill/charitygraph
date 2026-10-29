# G4 T4A11 immutable catalogue snapshot

Date: 2026-10-30 (Australia/Sydney)  
Branch: `gate3-cg406-remediation`  
HEAD: `a850f8104cf3e3f9150df27c4671ab084ba0453e`  
Fence: `v60` / `849f55679e1609e06d9e7e49b9226d72ecbd0b218f803a5a0358d9f7f7f73715`

## Result

Implemented one provider-free, read-only preflight in exactly these new paths:

- `src/charitygraph/phase5_t4a11_immutable_catalogue_snapshot.py`
- `tests/test_phase5_t4a11_immutable_catalogue_snapshot.py`
- `reports/G4_T4A11_IMMUTABLE_CATALOGUE_SNAPSHOT_20261030.md`

The result is `CANDIDATE_NOT_ATTESTED` only for a caller-pinned immutable main
file. It returns source identity, SQLite header, migration schema version,
enumerated table/view row counts and mechanical diagnostics. Project
completeness, pricing, FX, route authority and AUD spend are always explicit
`NOT_ATTESTED`; missing tables and empty views are never treated as zero.

The preflight rejects missing or non-regular files, invalid SQLite headers,
hash or source-identity mismatch, missing schema-migration authority,
pre-existing or newly created `-wal`, `-shm` and journal sidecars, WAL journal
mode, active/mutable source declarations, and any main-file hash change.
SQLite is opened only through a URI containing `mode=ro&immutable=1`; the
connection enables and verifies `PRAGMA query_only = ON`; bytes and sidecar
absence are checked again after close.

## Verification

Tests: 7 focused tests, run provider-free with:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a11_immutable_catalogue_snapshot.py --basetemp=<external-runtime-temp> --cache-clear -o addopts=
```

The test fixtures are disposable synthetic SQLite files under the external
basetemp. No runtime database was opened, and no existing sidecar was touched.
The final source SHA-256 values are recorded after verification:

| New path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a11_immutable_catalogue_snapshot.py` | `6d813dc01e6c2499b6f9e1ae6dfa56e7921c8077f34a0d4ec86bd05b9bdb9901` |
| `tests/test_phase5_t4a11_immutable_catalogue_snapshot.py` | `0f8cc7cb7d91b5c3b05ca2bd5d2a30294cda79b85ed54e45ac90c93d239c54e9` |

The report is the audit record being written and therefore does not embed a
self-referential file hash. The two implementation hashes above are direct
SHA-256 hashes of the final files.

Exact diff boundary: three untracked allowlisted paths only; no existing path
was edited. `git diff --check` is clean for the allowlisted paths.

## Boundaries and practical limits

This is not a database, catalogue migration, accounting ledger, source
authority, project manifest, pricing/FX registry, route authority or release
path. `immutable=1` prevents SQLite from consulting WAL/SHM state; it does not
make a concurrently changing main file safe. The before/after hash and
sidecar checks therefore fail closed, but cannot make an external writer stop.
A WAL-mode source is rejected even when its sidecar is absent because the main
file may not contain the complete current view. A trusted source owner must
first provide a closed, immutable main-file snapshot and its exact SHA-256.

T4A10's five read-only inspections that materialised zero-byte WAL and 32-KiB
SHM sidecars remain runtime artefacts; this task did not open, remove or alter
them. The practical next action is for the runtime owner to supply one
independently pinned closed snapshot with project/coverage, pricing, FX and
route authority before any accounting completeness claim is attempted.

No network/provider/model call, source acquisition, reservation/spend,
publication, GitHub/Drive mutation, watcher/process management, commit or gate
closure occurred. Pre-existing dirty and untracked paths were preserved.
