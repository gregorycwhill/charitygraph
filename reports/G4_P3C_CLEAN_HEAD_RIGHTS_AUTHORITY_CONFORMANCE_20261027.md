# G4 P3c-A clean-HEAD rights-authority conformance

Date: 2026-10-27 (Australia/Sydney)  
Mode: provider-free, local, bounded worker task  
Result: **IMPLEMENTED_AND_VERIFIED_BOUNDED_WORKER_RESULT**  
Product/Gate 4 acceptance: **not claimed**

## Boundary and classification

The fenced repository was verified at branch `gate3-cg406-remediation`, HEAD
`9e2577e09bb9825842bdeb6f52b9466fd6c60afa`. Existing dirty and untracked work
was preserved. The adopted runtime record was classified as a clean,
content-addressed provenance/storage substrate whose policy validation depended
on the dirty-only `governed_rights_policy` helper. The committed
`source_rights.py` registry and decision models remain the single substantive
rights authority; no dirty source-rights bytes were edited or promoted.

## Bounded implementation

Only these implementation/test paths were changed, plus this report:

- `src/charitygraph/runtime/rights_governance_record.py`
- `tests/runtime/test_rights_governance_record.py`
- `reports/G4_P3C_CLEAN_HEAD_RIGHTS_AUTHORITY_CONFORMANCE_20261027.md`

The runtime now delegates vocabulary, policy identity/version/basis and
substantive provider/local-retention predicates to the committed
`source_rights.py` registry, `ArtifactRightsDecision`, and
`BoundedLocalRetentionDecision`. It does not import the dirty helper or create
a second substantive policy registry. The record retains independent local,
provider, and public axes; source/record/subject/role, scope and acquisition
lineage; exact representation artifact/hash; append-only supersession and
revocation; deterministic content identity; and inclusive optional expiry.
Authorized lifecycle links and stored audit events require existing targets;
subject, source record, role, lineage, representation, and scope changes are
rejected as cross-binding successors.

## Clean-HEAD proof

A disposable import environment under `C:\CharityGraph-runtime` used the
actual committed HEAD bytes of `src/charitygraph/source_rights.py`. The copied
file had Git blob `bab1f855c5c4721e093f6d169b2f5ce022c12691`, matching
`git hash-object` of the disposable copy; its raw SHA-256 was
`13824bbe1bea1bb87d77636eca38a2794c294ad5b05d00d0b5ce0ea2ae5ccc98`.

Against that disposable clean-head source, the final runtime import and policy
probe passed:

```text
CLEAN_HEAD_FINAL_IMPORT_AND_POLICY_VALIDATION_OK
```

## Verification

- Focused provider-free suite, no checkout cache: `17 passed`.
- Provider-free regression suites (`test_source_rights.py`, governed Factory
  rights/integration, Factory, and runtime task-state): passed.
- `git diff --check`: passed; only pre-existing line-ending warnings appeared.
- Adversarial coverage includes unknown policy ID/version, unsupported axis
  versions, missing source-rights predicates, changed representation/source
  role/lineage/subject/scope, duplicate current decisions, invalid lifecycle
  targets/cycles, revocation/supersession, missing event targets, and expiry
  equality versus later-date expiry.

No provider/model call, network or source acquisition, spend, production
database, publication, release, watcher, GitHub action, staging, commit, or
follow-on dispatch occurred. No private evidence, source body, credential,
cache, runtime state, or generated public projection was added to Git.

This report is worker evidence only. It does not close a gate, establish
provider readiness, or constitute Product Owner acceptance.
