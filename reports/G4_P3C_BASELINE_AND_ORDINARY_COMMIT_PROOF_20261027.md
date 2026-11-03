# Gate 4 P3c baseline reconciliation and ordinary-commit proof

Date: 2026-10-27 (Australia/Sydney)  
Mode: provider-free, local, bounded reconciliation

## Disposition

Baseline reconciliation is complete. The fenced repository identity was
verified before this report: branch `gate3-cg406-remediation`, HEAD
`7671932137312ad0ee0e22c351eccaeb5bdcf0ef`, tree
`09bc6c3af0c57bf9eeede4795d85072e0476c0ce`. The requested report path was
absent and the Git index was empty. Existing dirty and untracked paths were
not edited, staged or absorbed.

The ordinary-commit proof was attempted as a narrow live Git route, but the
index-lock permission failure below means it was not established. Even a
successful ordinary commit would prove only one new direct-child commit
containing this report; it would not prove the dirty implementation, P3c
conformance, provider readiness, or Gate 4 acceptance.

## Exact-hunk reconciliation

Raw SHA-256 values below are the current bytes; the HEAD values are Git blob
IDs. The current raw values match the earlier bounded reports where stated.

| Path and exact dirty hunk anchors | Verified role and provenance | Risk / disposition |
|---|---|---|
| `src/charitygraph/source_rights.py` — `+55-69`; policy checks in `+315-327`; broader P3 core additions at `+104-133` and `+260-314`. HEAD blob `bab1f855c5c4721e093f6d169b2f5ce022c12691`; current raw `72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc`. | **Verified:** P3 added exact-representation decision fields, status, authority and optional expiry enforcement; P3b2 started from P3 raw `8bc8f51d68eed498db2d631764976c8d1d5ae7d16d7126c33b2faed16175600c` and added `governed_rights_policy()` plus exact policy ID/version/basis rejection. The registry itself already exists in HEAD. Evidence: P3 and P3b2 reports, and the current raw hash. | **P3b2-dependent.** It is the clean-HEAD dependency imported by the adopted rights record. The resolver is useful and mechanically bounded, but registry membership is not legal authority. Do not promote by staging this dirty path in this task. |
| `src/charitygraph/runtime/catalog.py` — rights DDL `+77-124`, lifecycle hook `+475`, helper `+492-496`, rights persistence/query/diagnostic methods `+2993-3123`. HEAD blob `5954ce82334bb4a00d0d20c697f66babca427e18`; current raw `3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1`. | **Verified:** this is the earlier P3 durable-artifact-rights Factory plumbing: exact source/representation hashes, lineage, policy versions, events and diagnostics. The P3 report records the same final raw hash and says the tables were intentionally side-installed because migrations were out of scope. | **P3 authority gap remains.** The SQLite tables are rebuildable operational state, not independent rights authority; no numbered migration, deterministic rebuild, or transactional current-frontier constraint is shown. Promote only in a separately scoped P3c-B migration/projection task. |
| `src/charitygraph/runtime/catalog.py` — P2c hunk group `+4062-4114` (physical-attempt identity/re-entry) and `+4358-4412` (pre-send replacement identity/re-entry), with exact diff headers beginning `@@ -3872,0 +4062,21` and `@@ -4124 +4358,9`. | **Verified:** these changes concern physical bundles, run/subject/scope identity, reservations and zero-crossing replacement. They are unrelated to rights authority. The current P2c reconciliation report documents the same catalog dirty context and separate P2c test evidence. | **Unrelated/P2c-dependent.** Do not absorb or partially promote this file while promoting rights. A file-level copy would mix P3 rights and P2c bytes. |
| `src/charitygraph/phase5_governed_factory_integration.py` — rights imports/fields and task material `+13`, `+25`, `+31-41`, `+65-104`, `+169-202`; rights preflight `+341-521`; orchestration `+529-610`. Subject provenance guard is the separate `+298-301` hunk. HEAD blob `b2a381ede6e3958ac9400292e16f85b0862359bc`; current raw `503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224`. | **Verified:** P3b1 produced the subject-binding guard and raw `7140efddfbea3077ab74b715bf1cbee8454b928d1e3d984da8bca4811eb9ba8d`; P3b2 began from that exact value and added rights resolution, current/superseded checks, policy-version propagation, expiry/denial diagnostics and typed-task material. P3b2 final raw hash is the current value. | **P3b2-dependent and overlapping.** It consumes both dirty `source_rights.py` and dirty catalog rights methods. It must not be promoted with either P2c catalog bytes or this report. Immediate provider-boundary revalidation is still absent. |
| `tests/test_source_rights.py` — fixture hunk `+19`, decision fixture `+29-31`; current raw `933177298b63d03a7bd51a2defa37f2a94780d9a5581cc72979b1debbd22274c`. `tests/test_phase5_governed_factory_integration.py` — fixture/rights setup `+25`, `+51-160`, assertions/isolation `+206-376`; current raw `9c71f762bcae0363cff34552f68e0fe9a18c5fdd2c472f2edadf1c0eede0c01`. | **Verified:** both raw hashes are the P3 report’s final values. The separate pre-existing `tests/test_phase5_governed_factory_rights.py` remains untracked (`??`), raw `dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281`; it is P3/P3b2 evidence, not part of this commit. | Tests exercise provider-free synthetic fixtures. They do not make the dirty implementation clean-baseline material and must remain uncommitted here. |

## Clean-HEAD dependency assessment

The adopted `src/charitygraph/runtime/rights_governance_record.py` is clean at
HEAD (raw `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9`),
but it imports `governed_rights_policy` at lines 27–33 and calls it during
record validation at lines 199–204. The HEAD `source_rights.py` blob has the
registry but no such function. This is a verified clean-HEAD import/conformance
blocker, not an inference and not P3b2 acceptance.

A separately scoped promotion of the exact `source_rights.py` dependency is
technically possible, but not from this dirty baseline under this task: the
worker must not stage the existing dirty file, and a normal bounded commit must
not absorb unrelated catalog, Factory, test or quarantined P3b2 bytes. The
minimal safe route is a supervisor-supplied clean baseline containing only the
reviewed source-rights bytes (with its tests/authority hashes recorded), followed
by P3c-A on clean paths. The dirty catalog, Factory integration, P2c changes,
and untracked P3b2 test remain excluded.

## Precise next P3c-A scope

After that clean baseline, use only:

```text
src/charitygraph/source_rights.py
src/charitygraph/runtime/rights_governance_record.py
tests/test_source_rights.py
tests/runtime/test_rights_governance_record.py
reports/G4_P3C_AUTHORITY_CONFORMANCE_20261027.md
```

Keep it provider-free and additive. Make the content-addressed record delegate
substantive predicates to the single source-rights authority; resolve every
authorized policy axis by exact ID and version; retain source/record/role,
acquisition lineage, representation artifact/hash and subject/scope binding;
require event targets before storage; and preserve independent retention,
provider and redistribution axes, append-only supersession/revocation and
optional expiry. Do not change Factory, catalog schema, source universe,
provider routes, public contract or projections.

Acceptance tests: clean-HEAD import; every supported policy ID/version and
unsupported/missing predicate; changed representation, lineage, role,
subject/scope and source-record mismatch; missing event target; duplicate
successor and lifecycle cycle; revoke/supersede; canonical export/import and
rebuild; and inclusive expiry (`planned date == expires_on`) versus expired
(`planned date > expires_on`). No provider call or source acquisition.

Optional expiry is not required for every decision. When supplied, equality is
valid and a later processing date must fail closed; omission remains an explicit
non-expiring state subject to the governing policy.

## Checks and ordinary-commit route

- `git diff --check`: passed; only pre-existing LF/CRLF warnings appeared.
- Provider-free focused tests: **61 passed**, with no cache provider, no
  bytecode, and basetemp outside the checkout under
  `C:\CharityGraph-runtime\g4-p3c-baseline-ordinary-commit-proof-20261027`.
- No provider, model, network, source acquisition, spending, production
  database, publication, release, watcher, bridge, GitHub or external action
  occurred. The focused tests used only disposable provider-free SQLite
  fixtures and basetemps under `C:\CharityGraph-runtime`.
- The report path was absent before write and the index was empty. The one
  permitted normal staging attempt was exactly:

  ```text
  git add -- reports/G4_P3C_BASELINE_AND_ORDINARY_COMMIT_PROOF_20261027.md
  ```

  It failed with exit code `128`:

  ```text
  fatal: Unable to create 'C:/CharityGraph-clean/charitygraph/.git/index.lock': Permission denied
  ```

  No alternate staging helper, permission change, bridge repair, dirty-file
  staging, retry, commit or post-commit verification was attempted. The index
  remained empty, so the required ordinary direct-child commit proof is **not
  established** and this task fails closed. The parent that would have been
  required was `7671932137312ad0ee0e22c351eccaeb5bdcf0ef`.

This report contains no private evidence, runtime state, cache, credential,
provider payload or generated public projection.
