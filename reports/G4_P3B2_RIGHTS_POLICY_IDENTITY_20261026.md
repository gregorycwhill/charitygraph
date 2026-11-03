# Gate 4 P3b2 — governed rights-policy identity/version

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, local, bounded engineering task  
Disposition: **P3b1 PASS recommendation; P3b2 implementation and tests PASS locally.**

## Baseline and authority

The required pre-edit fence facts matched: branch `gate3-cg406-remediation`,
HEAD `1a11cef17c8577ccc5b49f86d0d4866ce57d9785`, HEAD tree
`f1a61cfbe7d200eb6b432773de22e5000444cf54`. The supplied P3b1 report hash was
`bf87d8287069b1025fe876600cc97cd21b5fd97b28d98078c4a5654554d8fef8`.

The prior 68-test governed rights/Factory suite passed before modification.
This independently supports the P3b1 PASS recommendation: empty and
cross-subject source bindings failed before work, explicit multi-subject
bindings passed, the accepted peer used the fake provider with reconciled
cost, and restart/re-entry was idempotent.

Governance anchors used were `ARCHITECTURE.md:192-202` (versioned decision
authority), the local public-source policy at
`docs/PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_POLICY.md:3-13`, and the
local acceptance evidence recording the sibling Data source-governance
separation of retention, provider transmission and redistribution at
`reports/G4_P3_SOL_INDEPENDENT_ACCEPTANCE_20261026.md:67-93` (the cited Data
authority is `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:113-133`). The
existing governed policy authority is the exact registry in
`src/charitygraph/source_rights.py:25-47`; no policy ID or version was
invented.

## P3b2 change

The tested exact identity is:

`PUBLIC_FACTS_ONLY_V1` / `1.0.0` / `public_facts_only`

`source_rights.py:55-63` now resolves an ID, version and basis against that
governed registry. `require_provider_rights` rejects an unknown or mismatched
identity before lowering. `phase5_governed_factory_integration.py:341-509`
resolves the durable current decision, rejects absent/mismatched,
duplicate/contradictory, revoked and superseded records, and records the
existing durable diagnostic. `GovernedReference` carries an optional policy
version for compatibility; when omitted, the exact durable current version is
derived and propagated into lowered task material at `:509-610`.

Optional expiry is unchanged: omission is valid, equality at `expires_on` is
valid, and a passed deadline blocks. Existing artifact, representation,
source, acquisition-lineage, provider-policy, subject/scope and rights-basis
checks remain in force. Existing `SQLiteCatalog` persistence and diagnostics
(`runtime/catalog.py:2993-3123`) were reused; no migration or schema change
was made.

## Tests and cost evidence

Focused command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3b2-rights-policy-identity-20261026-focused-final tests/test_phase5_rights_policy_identity_p3b2.py
```

Result: **7 passed**.

Regression command (P3b1 suite plus P3b2):

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3b2-rights-policy-identity-20261026-final tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py tests/test_phase5_source_subject_provenance_p3b1.py tests/test_phase5_rights_policy_identity_p3b2.py
```

Result: **75 passed** (68 prior plus 7 new).

The new file-backed SQLite tests cover arbitrary `999.0.0`, reference-version
mismatch, absent durable record, duplicate current record, revoked and
superseded current records, authorised `1.0.0`, no expiry, passed expiry,
multi-subject matching/mismatch, peer isolation, durable diagnostics and
restart idempotence. Each blocked-only case produced zero tasks, physical
attempts, provider receipts, budget reservations, cost entries and provider
request attempts. The positive fake-provider path produced 1 task, 1 physical
attempt, 1 receipt, 1 reservation, 2 reconciled cost entries,
`AUD 0.002000`, and 0 provider request-attempt rows. No real provider request
or spend occurred.

## Preservation, limits and remaining work

Pre-edit hashes matched the supplied values:

```text
8bc8f51d68eed498db2d631764976c8d1d5ae7d16d7126c33b2faed16175600c  src/charitygraph/source_rights.py
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py
7140efddfbea3077ab74b715bf1cbee8454b928d1e3d984da8bca4811eb9ba8d  src/charitygraph/phase5_governed_factory_integration.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py
```

Final hashes for changed/new paths are:

```text
72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc  src/charitygraph/source_rights.py
3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1  src/charitygraph/runtime/catalog.py (unchanged)
503d357761ab4884c4099b58e8ff15becb7214611984b46af7d68b236a8b0224  src/charitygraph/phase5_governed_factory_integration.py
df6e7049ab6c3bb36e517ae6d4cc73240c826d13dbc17e1417e145b1b99d44c9  tests/test_phase5_rights_policy_identity_p3b2.py
dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281  tests/test_phase5_governed_factory_rights.py (unchanged)
```

All pre-existing dirty/untracked paths were preserved. Only the three
allowlisted source paths were touched among existing tracked files; the only
new paths are this report and the new test. No schema migration,
content-addressed export/import authority, true provider-boundary
revalidation, concurrent rights-transaction certification, provider/API
call, acquisition, publication, release, Git operation, watcher/process
action or Gate 4 closure was performed. P3c/P4 and operational fence/gate
certification remain open work outside this tranche. No private evidence,
runtime database, cache, credential, provider payload or log was added.
