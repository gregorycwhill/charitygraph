# G4-O1C P3C independent rights-record acceptance and SQLite migration seam review

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, local, report-only

## Verdict

**PARTIAL — ACCEPTED OFFLINE ONLY as a content-addressed record/storage
substrate; not accepted as provider-ready rights authority or as a completed
SQLite migration seam.** Passing tests demonstrate useful mechanics, not
authority. The record bytes are deterministic, exact-representation-bound and
rebuildable from the private file store, but current validation duplicates only
part of source-rights policy and admits policy-invalid metadata. Events can
also target records that do not exist. These are authority defects, not merely
missing operational polish.

## Controls, inputs and preservation

| Check | Result |
|---|---|
| Workspace / branch / HEAD / tree | `C:\CharityGraph-clean\charitygraph`; `gate3-cg406-remediation`; `4b3fbcaeaace5170994da57a4fe502e6f450ba29`; `627fafae46e097d4d4f8d67b57a385c374b0ab84` |
| Required report before review | Absent; this is the only repository path written |
| Pre-edit dirty baseline | 10 tracked status paths, 278 untracked status paths, 288 hashed files; manifest SHA-256 `8e6423e314a9f060119d3856eb27427925e63f28d6982a310a5c5e41634f8c9e` |
| Prior P3C source | `src/charitygraph/runtime/rights_governance_record.py` `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| Prior P3C test | `tests/runtime/test_rights_governance_record.py` `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| Prior P3C report | `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838c` |

The relevant pre-edit paths were preserved: clean
`runtime/migrations.py` (`2c145bb6e13038bd3f92bffcb7dc0671b6e8a8b02fd1d41b8af2fea07ebd8dc7`),
dirty `runtime/catalog.py` (`3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1`),
dirty `phase5_governed_factory_integration.py`
(`503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224`), and
the prior P3C files above. No stage, commit, reset, checkout, deletion,
watcher/process, bridge, Drive, GitHub, release or external mutation occurred.

The requested sibling Data authority was available locally and read
read-only. It confirms the exact artifact/representation rights decision,
separate retention/provider/redistribution axes, seven-base vocabulary,
append-only reconstructible provenance, and SQLite as operational state. No
provider, source acquisition, real private record, network call or spend was
used.

## Reproducible verification

The requested `-p unique` control was attempted but is unavailable in this
environment: `ModuleNotFoundError: No module named 'unique'`. No test ran in
that attempt. The same commands were then run with the available controls:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-independent-focused-20261026-02 tests/runtime/test_rights_governance_record.py
13 passed in 0.74s

$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-independent-regression-20261026-01 tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py
66 passed in 18.35s
```

A temporary catalog probe passed SQLite integrity and restart, but reported
schema version 28 with rights tables created by `_ensure_artifact_rights_tables()`;
no numbered rights migration exists. All temporary roots were under
`C:\CharityGraph-runtime`; `PYTHONDONTWRITEBYTECODE=1` was set.

## Review matrix

| Area | Independent result | Evidence / limitation |
|---|---|---|
| Canonical codec and content identity | **Verified offline** | Canonical UTF-8 JSON, sorted keys, SHA-256 identity, strict noncanonical/unsupported import rejection. |
| Exact representation and lineage binding | **Verified partial** | Source/record/role/hash fields exist and lifecycle links reject cross-representation and cross-scope targets. The record has no durable subject ID and `scope` is free text. |
| Three rights axes and optional expiry | **Verified offline** | Axes are separate; absent expiry is valid and equality is valid. Stale, blocked, revoked and superseded records are omitted. |
| Current decision output | **Verified offline** | `resolve_current()` returns typed records, deterministic by content hash, and fails closed on duplicate eligible current records. It is a pure supplied-record view, not a provider-bound revalidation. |
| Corruption, hardlink, symlink and path checks | **Verified partial** | Focused tests cover corruption, collision, symlink root and hardlink target. Crash durability, directory fsync, concurrent writers and symlink/reparse TOCTOU are not proven. |
| Event chain | **Failed authority check** | `RightsGovernanceEvent` validates its own bytes but not target existence, event ordering, replay, status compatibility or restoration of events. A revoked event targeting `a…a` with no record loaded successfully. |
| Policy identity/version | **Failed authority check** | Main rights policy version is checked, but a registered non-local axis accepts `CC_BY_3_0_AU_V1` version `999.0.0`; provider policy version `999.0.0` also accepts when copied into the axis. |
| Policy semantic exactness | **Failed authority check** | The record accepts open-license, public-facts and statutory-exception provider authorization without the existing source-rights predicates for licence evidence, factual representation or Fair Dealing conditions. It cannot represent the existing `public_source_private_processing` basis. |
| Role/scope and nominal IDs | **Partial / unsafe for authority** | Only `unknown`/`ambiguous` role or scope is rejected. Arbitrary role, scope, decision ID and actor ID strings—including sensitive-looking nominal IDs—are accepted and canonicalized. |
| Signature/trust | **Not present** | Hashes detect byte alteration; there is no signature, key identity or authenticated authority. `actor_kind=code` is accepted. |
| SQLite migration/rebuild | **Failed / deferred** | Rights DDL is outside `MIGRATIONS` v1–v28. Reopen works, but versioned upgrade ordering, checksums, authoritative import, deterministic rebuild and recovery are absent. |
| Provider boundary | **Not accepted** | Existing preflight resolves SQLite rows before Factory planning; no immediate authoritative-record revalidation at the actual crossing exists. |

## Exact reproducible issues

1. `rights_governance_record.py:205-211` treats registry membership as enough
   for non-local axis policies, and `_AUXILIARY_POLICY_VERSIONS` deliberately
   has no provider version. The probe accepted unsupported axis/provider
   versions. Main `rights_policy_id`/version matching did reject `999.0.0`.
2. `rights_governance_record.py:125-151,199-245` does not carry or enforce
   representation class/factual-only/licence/legal predicate fields from
   `source_rights.py:113-183`. Three synthetic records with missing required
   source-rights predicates were accepted. This is semantic-policy duplication;
   it must not become a second rights authority.
3. `RightsGovernanceEvent` has only a hash-shaped `record_id`; store write/load
   never requires that record to exist, and there is no event restore/replay
   contract. Missing event targets therefore pass.
4. `validate_history()` checks link identity, scope and cycles, but not temporal
   ordering or a causal event chain. File replacement uses fsync on the file and
   `os.replace`, but no directory fsync or concurrency protocol is present.
   These are deferred storage/recovery semantics, distinct from the proven
   byte-integrity checks.
5. SQLite `artifact_rights_*` and diagnostics tables are created from
   `catalog.py:77-124,493-496`, not from `runtime/migrations.py:1192-1223`.
   There is no database uniqueness constraint for one current decision per
   exact representation; the Factory adapter detects conflicts in application
   memory only.

## Safe next tranche: one smallest meaningful implementation

Recommend one provider-free **P3C authority-conformance plus deterministic
SQLite projection contract** tranche, gated by explicit supervisor promotion:

```text
src/charitygraph/runtime/rights_governance_record.py       existing untracked; pre-edit e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9
tests/runtime/test_rights_governance_record.py              existing untracked; pre-edit 3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310
src/charitygraph/runtime/migrations.py                     clean tracked; pre-edit 2c145bb6e13038bd3f92bffcb7dc0671b6e8a8b02fd1d41b8af2fea07ebd8dc7
tests/runtime/test_rights_governance_migration.py           ABSENT; new exact allowlist path
```

The tranche should make the authoritative record conform to the single
source-rights policy registry, bind a governed subject/scope representation,
reject unsupported axis/provider versions, require existing event targets and
define deterministic record import-to-index rows. It must add a numbered
transactional migration and rebuild test, but must not touch the current dirty
`runtime/catalog.py` or dirty `phase5_governed_factory_integration.py` until a
supervisor supplies clean promoted versions and explicit hashes. No provider
transport, source acquisition, SQLite production database or public contract
change belongs in this tranche.

Safe promotion remains separate: stage only the three unchanged P3C paths
above after rechecking their hashes; stage the P4 diagnostic trio separately
only under its own allowlist (`phase5_run_diagnostics.py`
`9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372`, its
test `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325`, and
its report `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803`).
Do not bypass a fail-closed bridge allowlist or use broad staging.

## Operational authority limits and remaining gates

The new seam may be used as a private offline content-addressed evidence
substrate after the above conformance work; it is not by itself a human
decision, legal conclusion, provider permission, or authenticated authority.
SQLite remains a rebuildable projection, never the sole evidence authority.

No real provider pilot, provider receipt/exactly-once evidence, spend or cost
acceptance, multiworker/restart SLO, alerting/operator monitoring, approved
real subject/source cohort, immediate pre-provider revalidation, P4 diagnostic
contract acceptance, or Data/Product Owner closure was performed. P3b2 remains
quarantined and unaccepted. Gate 4 therefore remains open: this review found
offline progress, not production authority, provider readiness, migration
completion or a basis to close the gate.

