# Gate 4 P3 — durable artifact-rights Factory preflight

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free local engineering task  
Scope: bounded implementation only; no Gate 4 closure or supervisory acceptance

## Control and preservation

- Branch: `gate3-cg406-remediation`
- HEAD unchanged: `8b7018f7507d52928d3e306bbf6f9d863f245937`
- HEAD tree: `514867d5cdfdb28ac81cc80815baae83ca91d02c`
- Active fence v26 SHA-256: `ce0d91b3b4584e87d0ce9f23c0525edfb93dc7cbc7b8a9646ac4c727bf01c97a`
- P2c report preflight SHA-256 matched the supplied value: `7f38f9bd764de63610cb7fcea329495fa2d3d7c5c384fb47fb997e590a760008`
- Required report was absent before this task. Existing dirty/untracked bridge, P1, P2 and P2c paths were preserved; no staging, commit, reset, checkout, watcher, bridge, GitHub, provider or source-acquisition action was used.

## Implementation

The existing governed path remains the single route: durable source/evidence/representation checks → `preflight_governed_references` → `FactoryPlan` → `ReferenceFactory` → SQLite catalogue.

- `SQLiteCatalog` now retains immutable, idempotent `ArtifactRightsDecision` records with decision version, exact source and representation artifacts/hashes, source record/origin/role, acquisition receipt lineage, rights and provider policy versions, transmission status, assessment authority/date, optional expiry, and supersession status. A separate event trail and durable rights-diagnostic table preserve traceability.
- Governed preflight requires referenced durable decisions, resolves current supersession deterministically, rejects missing/contradictory/denied/revoked/mismatched decisions, checks exact representation/hash, source role, acquisition lineage, source origin, policy identity/version and assessment authority, and treats absent expiry as valid. A supplied expiry blocks only when the planned processing date is later; equality is allowed.
- Caller-supplied `rights_role` and `rights_policy_id` are never permission. They are checked against durable source/decision bindings. No universal role allowlist or new acquisition family was added.
- Blocked references emit durable rights diagnostics and are omitted from the Factory plan, so they create no tasks, physical attempts, reservations, receipts or costs. Accepted peers continue independently. The Factory and transport/bridge code were not changed.

## Verification

Baseline before edits: `tests/test_source_rights.py`, `tests/test_phase5_governed_factory_integration.py`, and `tests/runtime/test_task_state.py` — **46 passed**.

Final command, with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`, `pytest -p no:cacheprovider`, and a fresh `C:\CharityGraph-runtime\g4-p3-final-*` basetemp — **66 passed**:

`tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py`

The new rights suite contributed **12 passed**. It covers exact hash/artifact binding, representation mismatch, source role, acquisition lineage, provider/right-policy mismatch, missing and duplicate current decisions, explicit deny/revocation with supersession, absent expiry, inclusive expiry boundary, expired blocking, restart idempotency, independent accepted peer, zero work/cost on blocked input, and reconciled fake cost on the approved path. `git diff --check` passed; only pre-existing line-ending warnings were emitted for unrelated dirty files.

Positive synthetic Factory row assertions: `tasks=1`, `physical_attempts=1`, `provider_receipts=1`, `budget_reservations=1`, `cost_entries=2`; actual fake cost was AUD `0.002000`, and restart added no rows. Blocked cases asserted zero rows in all work/cost tables and zero actual spend. Rights decisions, decision events and diagnostics remained catalogue-only metadata; no provider response or real transmission was created.

Final allowlisted hashes:

```text
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py
9c69e04a50f56ec7a9a6b1364aa7c36f4e7d9d3ad087e886bc3636ea3286fb89  src/charitygraph/phase5_governed_factory_integration.py
8bc8f51d68eed498db2d631764976c8d1d5ae7d16d7126c33b2faed16175600c  src/charitygraph/source_rights.py
fa85b7fdf949e58a0e0819634e97d1265e27e97a90ac4ca867874ab6ab5683b7  tests/runtime/test_task_state.py
933177298b63d03a7bd51a2defa37f2a94780d9a5581cc72979b1debbd22274c  tests/test_source_rights.py
9c71f762bcae0363cff34552f68e0fe9a18c5fdd2c472f2edadf1c0eede0c01d  tests/test_phase5_governed_factory_integration.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py
```

## Limits and unresolved policy

This is a provider-free synthetic demonstration. It does not authorise a provider call, spend, source acquisition, external transmission, publication, release, GitHub mutation or gate closure. The SQLite catalogue remains rebuildable operational state, not the evidence authority. The adapter records the canonical source-role/policy facts supplied by durable records but does not decide legal rights or invent proposition-specific authority. The allowlist prohibited changing `migrations.py`; therefore the new catalogue tables are created idempotently by the regular `SQLiteCatalog` lifecycle, while each decision carries an explicit adapter version and immutable material hash. No public schema or compatibility identifier changed.
