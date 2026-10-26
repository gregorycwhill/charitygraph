# Gate 4 P3C — content-addressed rights record authority

Date: 2026-10-26 (Australia/Sydney)  
Mode: provider-free, local, offline only  
Disposition: **bounded implementation complete; Gate 4 remains open**

## Authority and boundary

The controlling Product Owner decision approved Option 1: immutable,
versioned, content-addressed rights governance records are the private
authoritative evidence; SQLite remains a rebuildable operational projection.
The record binds the exact source artifact, source record, source role,
acquisition/receipt lineage, representation SHA-256, rights basis, policy
identity/version, purpose/scope, evidence locator/hash, assessment date,
independent local-retention/provider-transmission/public-redistribution axes,
review status, optional expiry, and append-only actor/time and lifecycle
metadata. No substantive source-rights policy was changed or invented.

The local fence remained `gate3-cg406-remediation`, HEAD
`4b3fbcaeaace5170994da57a4fe502e6f450ba29`, tree
`627fafae46e097d4d4f8d67b57a385c374b0ab84`. Pre-existing tracked dirty and
untracked paths were preserved; only the three fresh allowlisted paths were
created. No provider, network, source acquisition, spend, publication, Git
staging/commit, SQLite production mutation, watcher, bridge, Drive, GitHub,
release, merge, or gate action occurred.

## New private authority seam

`src/charitygraph/runtime/rights_governance_record.py` provides:

- `RightsGovernanceRecord` and `RightsAxis`, retaining the existing
  `ArtifactRightsDecision` field terminology and the approved seven rights
  bases. Unknown/version-mismatched main policies, unknown roles/scopes,
  malformed hashes, cross-bound lifecycle links, inconsistent statuses, and
  ambiguous metadata fail closed.
- `canonical_bytes()`, `export_record()` and `import_record()`. The exact
  UTF-8 JSON envelope is format `charitygraph.rights-governance-record/1`,
  schema `urn:charitygraph:builder:schema:rights-governance-record`, version
  `1.0`; keys are canonicalized with the existing Builder canonical codec.
  `record_id` is SHA-256 of those bytes. Set-like acquisition lineage is
  sorted, so equivalent reordered input has the same identity.
- `RightsGovernanceStore(private_root)`, which requires a caller-selected
  absolute dedicated root and writes once to:

  ```text
  <private-root>/records/sha256/<first-two>/<record-sha256>.json
  <private-root>/events/sha256/<first-two>/<event-sha256>.json
  ```

  Existing identical bytes are idempotent. Corruption, content collisions,
  symlinks, hardlinks, non-canonical imports, and unsafe roots fail closed.
  The module does not read or write any default workspace/global path at
  import.
- `RightsGovernanceEvent`, `validate_history()` and `resolve_current()`. Old
  record bytes are never mutated. Supersession/revocation links must remain on
  the exact representation and scope, cycles and multiple successors fail
  closed, and unknown/expired/revoked/superseded/review-required records are
  not auto-promoted. An explicit expiry blocks only after the date; equality
  remains usable. The resolver is a pure view over supplied records.

Restore is standalone: point a new `RightsGovernanceStore` at the same private
root, call `restore_records()`, validate history, and use the resulting records
or `resolve_current()`; individual records can be reloaded with
`load_record(record_id)`. SQLite reindexing is not implemented by this tranche.

## Tests and compatibility

The new file-backed tests use fresh pytest bases below
`C:\CharityGraph-runtime`, never the checkout. They cover canonical identity
and roundtrip, restart/load/restore, exact source and representation binding,
separate rights axes, optional expiry, append-only lifecycle, duplicate
idempotence, corruption/collision, unsupported schema/basis/role, malformed
and impossible chains, scope isolation, privacy allowlisting, path/link
safety, and absence of task/attempt/reservation/cost/provider side effects.
One test compares the seam's intended compatibility fields with the existing
`ArtifactRightsDecision` and writes only a temporary `SQLiteCatalog` fixture;
the production catalog was not changed.

Commands and results:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-rights-record-final-focused-20261026-11 tests/runtime/test_rights_governance_record.py
13 passed in 0.76s

$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p3c-rights-record-final-20261026-10 tests/runtime/test_rights_governance_record.py tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/test_phase5_governed_factory_integration.py tests/test_phase5_factory.py tests/runtime/test_task_state.py
79 passed in 12.74s
```

New-file SHA-256 values before this report was written:

```text
e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9  src/charitygraph/runtime/rights_governance_record.py
3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310  tests/runtime/test_rights_governance_record.py
```

The three new files remain uncommitted and unstaged. Existing dirty tracked
paths, including `source_rights.py`, `phase5_governed_factory_integration.py`,
`runtime/catalog.py`, the P3b2 rights tests, and P4 diagnostics remain outside
this change.

## Deliberate remaining work

This is not a migration or production integration. The following remain
unimplemented and require separate authority/allowlists:

1. a numbered SQLite migration plus deterministic upgrade/rebuild projection
   from private authoritative records;
2. production catalogue indexing/reindex commands and current-decision
   projection semantics;
3. database-enforced uniqueness for one current decision per exact
   representation, rather than an application-only check;
4. immediate pre-provider-crossing rights revalidation against the private
   authoritative record, including expiry/supersession/revocation; and
5. production pilot authority, provider receipts/exactly-once ambiguity
   evidence, operational diagnostics/SLOs, and Gate 4 acceptance.

The earlier P4 run-diagnostics work remains offline partial evidence: it is
fixture-driven and does not yet consume the real run/ledger contracts; it has
known gaps around ledger joins, status validation, adjustment/credit and
legitimate-overrun algebra, duplicate durable rows, and actual crossing
markers. This P3C seam does not repair or integrate P4. Gate 4 is therefore
open, and the quarantined P3b2 result is neither reconstructed nor accepted.
