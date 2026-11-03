# G4 T4E clean-target commit independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Verdict: **PARTIAL**

## Scope and identity

Reviewed branch `gate3-cg406-remediation`, exact HEAD
`ce624f6fd81a26572744fdbce538f563c417804f`, fence
`v70 e92b8f6ec2060e4744d449dc746408c8925b23f685837bfad551f6db3db2b211`.
Compared the exact three-path commit with parent
`d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`; the paths are the dormant helper,
its focused test, and the transaction report. Read the requested repository
authority/protocol documents and the implementation/report.

## Independent execution

Copied the exact helper and focused test into a fresh disposable directory
outside the live checkout. Ran with `PYTHONDONTWRITEBYTECODE=1` and
`-p no:cacheprovider`:

```text
........                                                                 [100%]
8 passed in 10.07s
EXIT_CODE=0
```

No bytecode or pytest-cache artifacts were produced. No helper call was made
against the live checkout, and no live Git state was changed.

## Findings

The core isolation design is sound for the covered path:

- `_verify_manifest`, `_verify_anchor`, and `_verify_candidate_bytes`
  (lines 145-194) require canonical self-consistent bytes, lowercase SHA-256
  values, exact candidate paths, and equality to the separately supplied
  anchor content.
- `_validate_allowlist` (138-143), `_assert_pinned_ref` (207-214), and
  `_assert_clean_target` (197-205) enforce a unique path allowlist, exact
  branch/HEAD, and a clean isolated target.
- The default is dry-run (`dry_run=True`, line 233). The temporary clone and
  separate `GIT_INDEX_FILE` (262-274) avoid reading candidate bytes from the
  live worktree or index. The proposed commit is checked as one direct
  non-merge child and its `--no-renames` changed-path set must equal the
  allowlist (275-286).
- The real-CAS focused test independently confirmed that pre-existing dirty
  main bytes and staged index entries remain unchanged. `_compare_and_swap_ref`
  uses the expected old HEAD (217-220, 291-293), so a concurrent branch move
  is rejected rather than absorbed.

The non-dry-run transaction is not fully rollback-safe. Before the CAS, line
291 runs `git fetch ... proposed` into the host repository. A forced-CAS
conflict reproduced independently outside the checkout left the branch HEAD
unchanged but increased loose-object count from 3 to 6 and created
`.git/FETCH_HEAD` containing the proposed commit. The helper reports only
`branch ref CAS failed` (293); it does not record, remove, or expose those
partial repository side effects. Concurrent callers can also overwrite this
untracked `FETCH_HEAD` state. Therefore “ref/worktree/index unchanged” is true
for the tested failure, but “transaction rollback” is not true for the host
repository object/ref metadata.

The manifest and anchor checks establish integrity and correspondence, not
authenticity: the helper has no signature or supervisor-attestation check and
must receive the independently trusted manifest/anchor from its future host
integration. That is an integration boundary, not a reason to alter the
dormant helper in this acceptance.

## Acceptance and next safe step

**PARTIAL** — suitable for provider-free dry-run examination and for further
review of clean-target/direct-child construction, but not yet safe to wire as
a non-dry-run adoption transaction. The exact limitation is unrecorded,
unrolled-back object-store and `FETCH_HEAD` mutation between object import and
the branch CAS conflict.

Do not integrate or invoke the non-dry-run path yet. The smallest separate
bounded repair should quarantine or otherwise account for the exact objects
installed before CAS, avoid writing `FETCH_HEAD`, and add a forced-CAS test
asserting repository object/ref metadata is unchanged (plus a concurrent-CAS
race test). Re-run independent acceptance after that repair. No source/test
change was made here, as required.
