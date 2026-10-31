# G4 T4E clean-target commit transaction

Date: 2026-10-31 (Australia/Sydney)  
Task: dormant host-side helper; no bridge ingress or live-target invocation.

Implemented only:

- `src/charitygraph/g4_clean_target_commit.py`
- `tests/test_g4_clean_target_commit.py`
- this report

The helper requires canonical exact-byte candidate-manifest bytes, a separate
canonical source/test content anchor, and candidate bytes supplied independently.
It validates hashes, paths, pinned branch/HEAD, and a clean isolated target. It
builds the tree and one non-merge direct child in a disposable clone outside
the repository, verifies the exact allowlist and resulting bytes, and defaults
to dry-run. Explicit non-dry-run operation performs only a compare-and-swap
branch-ref update; a failed CAS leaves the ref, worktree, and index unchanged.

The future bridge seam is a host-owned call that supplies a separately verified
manifest/anchor and a supervisor-created clean target checkout, then reviews
the returned direct-child attestation before any separately authorised ingress
activation. This helper does not promote timed-out output, acquire sources,
write bridge metadata, stage a live checkout, or update a fence. Unreachable
objects created in a disposable build are temporary and are not installed in
the target repository during dry-run; production integration should retain the
same fail-closed CAS and independent verification boundary.

Focused tests cover dry-run success, stale HEAD, altered bytes/hash, wrong
paths, dirty isolated target, real-CAS preservation of dirty main worktree and
index, CAS rollback, and no unexpected validation mutations. Tests create only
temporary Git repositories outside this worktree. The pre-existing dirty and
untracked checkout state was not used as candidate evidence and was preserved.
