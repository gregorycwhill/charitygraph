# Gate 4 P3 — independent supervisory acceptance

Date: 2026-10-26 (Australia/Sydney)  
Instruction: `20261026-g4-p3-independent-acceptance-v1`  
Mode: provider-free, local, `REPORT_ONLY`

## Disposition

**P3 bounded rights invariant: PARTIAL.** The governed reference → preflight →
`FactoryPlan` → `ReferenceFactory` → `SQLiteCatalog` path is fail-closed for
the exercised durable cases, but product acceptance is not established. Two
material implementation gaps remain: an unscoped source record can pass the
available-material check, and an arbitrary nonblank rights-policy version is
not checked against a governed policy registry/version binding. The new rights
tables and decision material are also stored only in rebuildable SQLite, with
no migration entry or content-addressed governance artefact authority.

**Provider-free continuation: CONDITIONAL YES.** It is safe to proceed only
with a subsequent provider-free Gate 4 concurrency/scheduling/monitoring
engineering tranche that preserves fake-only execution and treats these gaps
as open acceptance conditions. This evidence is not provider authority, spend
authority, source-acquisition authority, operational demonstration, Gate 4
closure, publication, release or supervisory acceptance.

## Control and preservation

- Workspace: `C:\CharityGraph-clean\charitygraph`.
- Branch: `gate3-cg406-remediation`.
- HEAD: `8b7018f7507d52928d3e306bbf6f9d863f245937`.
- HEAD tree: `514867d5cdfdb28ac81cc80815baae83ca91d02c`.
- Active v26 fence SHA-256 supplied and retained: `ce0d91b3b4584e87d0ce9f23c0525edfb93dc7cbc7b8a9646ac4c727bf01c97a`.
- Required report was absent before this task.
- P3 implementation report SHA-256 matched: `e3be6962d3335d1e632ceb799f14b8338ae799007f146ad0794d6e89160c85fc`.
- The P2c catalogue/physical-attempt report referenced by the P3 report matched
  `7f38f9bd764de63610cb7fcea329495fa2d3d7c5c384fb47fb997e590a760008`.
  The later P2c bridge-reconciliation report was also read; its current hash is
  `106f390e87041ed5370cf3e9ac3fdad4c7675db937d878014588a0929d31c46d`.

The pre-existing dirty/untracked baseline was preserved. Before this report
was written, visible `git status --porcelain=v1 --untracked-files=normal`
contained 59 records, with Git's known access-denied warnings for the two
synthetic pytest recovery prefixes. No status path was cleaned, staged,
committed, reset, checked out, or otherwise changed.

## Reviewed implementation and governance

The complete current P3 source/test diff relative to HEAD was reviewed,
including the earlier P1/P2/P2c dirty context. The meaningful P3 seams are:

- `src/charitygraph/source_rights.py:55-157,245-297` adds exact
  representation/artifact binding, decision version/status/supersession,
  assessment authority and optional expiry. `require_provider_rights()` treats
  absent expiry as valid and blocks only when a supplied expiry is earlier than
  the planned processing date.
- `src/charitygraph/runtime/catalog.py:77-124,2993-3123` persists immutable
  decision rows, decision events and diagnostics, validates durable source and
  representation artifacts, source role/origin and acquisition receipt
  lineage, and re-enters decisions idempotently by material hash.
- `src/charitygraph/phase5_governed_factory_integration.py:52-123,243-328,
  331-450,453-543` validates the real catalogue records, resolves current
  supersession, rejects duplicate current decisions and mismatches, and lowers
  only accepted references into Factory work.
- `tests/test_phase5_governed_factory_rights.py:68-208` is the new 208-line
  rights integration suite; the related existing integration and runtime
  tests were reviewed without edits.

This agrees with Data source governance: content-bearing acquisition needs a
versioned, artefact-bound decision for the exact transmitted representation,
with separate retention, provider-transmission and redistribution axes
(`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133`). It also agrees that
SQLite is operational state rather than the sole public/evidence authority
(`INTEGRATED_PRODUCT_AND_DATA_MODEL.md:315-331,968-983`; Builder
`AGENTS.md` and `ARCHITECTURE.md:8.1,8.4`).

## Independent findings

### Proven bounded behaviour

- Caller-supplied `rights_role`, `rights_policy_id` and provider policy values
  did not grant permission by themselves: role, rights-policy and provider-
  policy mismatch cases were blocked.
- Exact representation hash/artifact binding, source record/origin/role,
  acquisition lineage, source/representation lineage, missing/duplicate
  current decisions, explicit blocked/revoked decisions and supersession were
  exercised. Contradictory current decisions fail closed rather than being
  arbitrarily selected.
- Optional expiry is implemented as specified: absent is valid, equality at
  `expires_on` is allowed, and a later planned processing date is blocked.
- Local retention is a separate `BoundedLocalRetentionDecision`; provider
  permission is not copied into retention permission, and retention permission
  does not authorize provider transmission.
- Preflight reads the persisted SQLite decision row and its `material_json`
  through catalogue methods. The positive fixture records the decision before
  preflight; it is not a synthetic in-memory permission object.

### Material gaps

1. **Unscoped provenance is not rejected.** At
   `phase5_governed_factory_integration.py:289-291`, a source record is
   rejected only when a non-empty `about_subject_ids` set excludes the planned
   subject. A source record with no subject binding was independently created
   in a temporary catalogue, bound to a valid exact decision, and accepted by
   preflight (`accepted=1`, no diagnostic). This does not prove subject-scoped
   provenance and must be closed before provider use.

2. **Rights-policy version is presence-checked, not identity/version-checked.**
   `catalog.py:3000-3004` requires nonblank versions and
   `source_rights.py:296-299` requires a nonblank durable version, but the
   preflight has no `rights_policy_version` on `GovernedReference` and no
   comparison to the governed policy registry/version. A temporary catalogue
   decision with `rights_policy_version="999.0.0"`, superseding the original,
   was accepted (`accepted=1`). Provider policy ID/version is compared when
   supplied by the governed reference; this does not cure the rights-policy
   version gap.

3. **Schema authority is incomplete.** The rights DDL is
   `ARTIFACT_RIGHTS_TABLE_SQL` at `catalog.py:77-124` and is invoked by
   `_ensure_artifact_rights_tables()` at `catalog.py:493-496`, including from
   `migrate()` at `450-475`, but no rights migration exists in
   `runtime/migrations.py`. The temporary database reopened successfully and
   retained the tables, while `schema_migrations` remained at migration 28
   (`append_only_historical_s0_terminals`) with no rights migration. Reopen
   survival is demonstrated; upgrade ordering, checksums, versioned evolution
   and recovery/rebuild authority are not.

4. **Governance-record authority is incomplete.** The decision's canonical
   material is only SQLite `material_json`; no content-addressed durable
   decision artefact, export/import/rebuild contract, or external governance
   record is required. This conflicts with the repository boundary that
   rebuildable SQLite is not the only evidence authority. It is a product
   contract limitation, not a test failure.

5. **Concurrency/revalidation remains unproven.** Decision insertion is
   serialized by the catalogue's immediate transaction and duplicate current
   decisions fail closed when visible to preflight, but there is no database
   uniqueness constraint for one current decision per exact representation.
   Also, `ReferenceFactory` consumes an already-built plan; no rights
   revalidation between preflight and a later provider transport boundary was
   demonstrated. This is acceptable for the fake-only tranche, not for
   provider-enabled operation.

## Fresh verification

Focused command (exact command used):

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3-independent-acceptance-20261026 tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py
```

Result: **66 passed in 17.55s**. The new rights suite was rerun separately
with the same controls and a fresh basetemp: **12 passed in 7.99s**.
`git diff --check HEAD` exited 0; only pre-existing LF/CRLF warnings were
reported for unrelated dirty files.

Separate temporary file-backed SQLite probe (runtime only, no checkout file)
confirmed:

```text
positive: accepted=1, completed=1
tasks=1, physical_attempts=1, provider_receipts=1,
budget_reservations=1, cost_entries=2,
artifact_rights_decisions=1, decision_events=1, diagnostics=0
restart: completed=0, all counts unchanged
blocked missing/role/policy cases: accepted=0, completed=0,
all work/cost counts unchanged
```

The probe used the real persisted decision and fake provider only. No network,
external provider, source acquisition, model call or real transmission was
performed. Temporary probe roots were under `C:\CharityGraph-runtime`.

## Exact final path hashes

These were rechecked after testing and before writing this report:

```text
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py
9c69e04a50f56ec7a9a6b1364aa7c36f4e7d9d3ad087e886bc3636ea3286fb89  src/charitygraph/phase5_governed_factory_integration.py
8bc8f51d68eed498db2d631764976c8d1d5ae7d16d7126c33b2faed16175600c  src/charitygraph/source_rights.py
fa85b7fdf949e58a0e0819634e97d1265e27e97a90ac4ca867874ab6ab5683b7  tests/runtime/test_task_state.py
933177298b63d03a7bd51a2defa37f2a94780d9a5581cc72979b1debbd22274c  tests/test_source_rights.py
9c71f762bcae0363cff34552f68e0fe9a18c5fdd2c472f2edadf1c0eede0c01d  tests/test_phase5_governed_factory_integration.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py
```

Only this required report is new from this task. No source/test path was
edited; no private evidence, runtime database, cache, provider material,
credentials or logs were added to the repository. Gate 4 remains open.
