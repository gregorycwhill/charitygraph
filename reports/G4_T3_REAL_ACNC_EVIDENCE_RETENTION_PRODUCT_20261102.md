# Gate 4 T3 — ACNC real-evidence retention

Date: 2026-11-02  
Scope: bounded local implementation only; no provider calls, external retrieval, publication or Gate 4 closure.

## Delivered

- Added deterministic intake for one exact durable subject and organisation scope for `acnc_register` and `acnc_ais_bundle`.
- Retains exact source bytes in memory/JSON-safe base64 output with SHA-256 identity, source URL, UTC receipt, source record, evidence locator and acquisition receipt.
- Materialises a separate structured representation and independently hashes it; source and representation hash substitution is rejected.
- Records local retention under the existing bounded policy and explicitly reports provider processing as `blocked` and public redistribution as `not_assessed` until exact authority records are supplied.
- Added a callable adapter into the existing T3 binder without modifying that binder.

## Verification

Focused offline tests passed: **14 passed** (5 new retention tests and 9 existing T3 binder tests). Tests used `-p no:cacheprovider` and basetemp outside the repository.

The new tests cover positive local retention, exact base64 round-trip, source/representation distinctness, wrong subject/scope, missing receipt, and missing rights. Only offline authoritative-shape fixtures were used.

## Actual retained data and remaining gaps

No real ACNC bytes were acquired or durably retained in `evidence/gate4-t3-five-subject-v1/`; the task safety boundary prohibited external-source access. The test fixtures are in-memory only and are not evidence. The selected five-charity cohort therefore remains **0 BOUND / 10 MISSING** for real retained evidence. Gate 4 still needs governed acquisition of each selected register/AIS object, durable private storage outside Git, and real authority records for provider processing/public redistribution before any row can bind.

Existing dirty Factory, authority, overlay, bridge, watcher, fence and evidence paths were not modified.

The optional local-only commit was not created: Git could not create
`.git/index.lock` (`Permission denied`). The lock/fence was not removed or
bypassed.
