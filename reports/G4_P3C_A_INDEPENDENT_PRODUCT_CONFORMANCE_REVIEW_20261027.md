# G4 P3c-A independent product conformance review

Date: 2026-10-27 (Australia/Sydney)  
Review mode: read-only, local, provider-free  
Commit reviewed: `92c280e8ac969c77c7e5831181d472d6760d8ef0`  
Parent: `9e2577e09bb9825842bdeb6f52b9466fd6c60afa`  
Verdict: **PARTIAL**

## Scope and authority

I read the repository instructions and architecture/machinery documents, plus
the local CharityGraph Data authority, integrated-model, source-evidence and
publication, taxonomy, implementation, test-plan, coverage/economics and
semantic-approval documents. The governing requirement is an exact,
artefact/representation-bound rights decision with independently recorded local
retention, provider transmission and public redistribution; unknown, stale,
unbound or mismatched records fail closed.

The commit changes exactly three paths, confirmed by `git diff-tree`:

```text
reports/G4_P3C_CLEAN_HEAD_RIGHTS_AUTHORITY_CONFORMANCE_20261027.md
src/charitygraph/runtime/rights_governance_record.py
tests/runtime/test_rights_governance_record.py
```

The working tree was dirty before review, including `source_rights.py`; it was
not used as authority and was not edited. The target commit's
`source_rights.py` blob is `bab1f855c5c4721e093f6d169b2f5ce022c12691`, while
the dirty working-tree blob is `95e7aaaebfd5f3de63c88bb2f4d01e765dda1632`.

## Independent verification

I loaded the runtime and `source_rights.py` bytes directly from `git show` in
memory. The committed source was 14,349 bytes, with raw SHA-256
`5a30a25d35de1ef9584592328306fe209e37337eaa350ca023e77f4050e28190`; the
probe passed `CLEAN_HEAD_IN_MEMORY_IMPORT_AND_BASE_POLICY_OK`. The clean source
has no `governed_rights_policy` helper, and the target runtime contains no
reference to it. The canonical record export/import hash and UTF-8 checks
passed. Eleven pure functions from the committed runtime test file passed
manually with `python -B`; no pytest cache, provider, model, network, source
acquisition or spend was used.

Commands included `git show`, `git rev-parse`,
`git diff-tree --no-commit-id --name-only -r --no-renames`, `git diff --check`,
and an in-memory `python -B -c` clean-byte loader/probe. The complete 17-test
pytest invocation was not rerun against the dirty worktree; the 11 applicable
non-filesystem test functions were independently invoked against the committed
runtime/source bytes.

The worker report is a separate bounded attestation, not this review. Its
reported raw source hash (`13824bbe...`) does not match the raw hash of the
target Git bytes above, and `git diff --check` independently reports three
trailing-whitespace lines in that committed worker report. The direct Git-byte
probe is therefore the evidence relied on here.

## Conformance that passed

- The runtime imports the committed `RightsBasis`, representation vocabulary,
  policy registry, `ArtifactRightsDecision`, and
  `BoundedLocalRetentionDecision`; it does not duplicate the dirty helper or a
  second substantive rights registry.
- Top-level rights policy ID, version and basis are checked against the
  committed registry. Provider and local-retention substantive predicates are
  delegated to the committed source-rights models.
- Local, provider and public axes are represented separately, with exact
  representation SHA, source artifact/record, subject, source role, scope and
  non-empty unique acquisition lineage. Canonical record identity is the hash
  of the versioned record bytes; storage rechecks content hashes and rejects
  unsafe links/collisions.
- `validate_history` rejects duplicate identities, missing/self targets,
  ambiguous successors, cross-binding changes and cycles. Event storage
  requires an existing deterministic record target. Supersession and
  revocation are append-only links. Optional `expires_on` behaves as required:
  equality remains eligible and a later date is denied.

## Blocking conformance gaps

1. **Provider policy version is not exact or fail-closed.** At
   `runtime/rights_governance_record.py:260-266`, an authorized provider axis
   accepts any non-empty version for the fixed provider policy ID. The
   committed source-rights authority has no provider-version registry to which
   this field is delegated. The clean-byte probe accepted provider version
   `9.9.9`.

2. **Public redistribution can be authorized under a policy that forbids it.**
   The same axis check accepts any registry policy ID/version on the public
   axis, without checking its `public_redistribution` capability. The clean
   probe authorized the public axis with
   `CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1`, whose committed
   registry entry says `public_redistribution: False`; the record was accepted
   and reported `public_redistribution_allowed == True`. This violates the
   separate publication fail-closed boundary.

3. **Overall status does not constrain other authorized axes.** The clean
   probe accepted `status="blocked"` with authorized local retention and
   accepted `status="revoked"` with authorized public redistribution. The
   current-view resolver omits such records, but the records and axis
   properties themselves remain contradictory and can be consumed outside that
   view.

4. **Local-retention review expiry is not enforced by eligibility.** A record
   with `retention_review_due_on` in the past, lifecycle
   `active_until_review`, and `review_status="current"` was accepted and
   remained promotable. The source policy requires review-date/lifecycle
   auditing and non-automatic renewal; `can_promote()` currently checks only
   `expires_on`.

5. **Lifecycle target enforcement is deferred to history validation.**
   `RightsGovernanceStore.put_record()` writes a record whose supersession or
   revocation target is absent; `validate_history()` later rejects the supplied
   set. Before versioned SQLite projection/rebuild, the persistence boundary
   should either validate the complete history before storing such a link or
   explicitly guarantee that no consumer can observe an unvalidated record.

## Required remediation before P3c-B

Use the existing committed authority, without introducing a second policy
source, to add negative tests and fail-closed validation for: the exact
provider policy version; public-axis permission; status/axis consistency;
past retention review dates; and persistence of lifecycle links with missing
targets. Re-run the clean-byte import and the complete provider-free focused
suite after remediation, with no pytest cache, and reconcile the worker-report
hash/check discrepancies.

This is an independent product/code acceptance recommendation. It does not
replace the worker's bounded attestation and does not close the Product Owner's
Gate 4 decision.
