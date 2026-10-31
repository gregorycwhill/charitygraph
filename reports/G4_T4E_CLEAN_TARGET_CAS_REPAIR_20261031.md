# G4 T4E clean-target CAS/object-side-effect repair

Date: 2026-10-31 (Australia/Sydney)  
Task: bounded repair of the dormant host-side clean-target transaction.

Implemented only in the approved source and focused test:

- `src/charitygraph/g4_clean_target_commit.py`
- `tests/test_g4_clean_target_commit.py`

The non-dry-run import now uses supported `git fetch --no-write-fetch-head`.
Before import it inventories every object reachable from the proposed commit
and records which were already present. Success and post-import failure
attestations expose the reachable IDs, the exact conservative set that may
have been installed, the subset observed present afterward, and before/after
`FETCH_HEAD` hashes. Dry-run results explicitly attest that no host import was
attempted. Fetch failures also carry the same failure attestation.

CAS failure does not attempt to unlink objects. The attestation records
`unlink_performed: false` and requires a host-owned reachability audit across
refs, reflogs, worktrees, and concurrent operations before ordinary garbage
collection/pruning. The helper therefore does not claim atomic rollback of
unreachable Git objects; it accounts for them and leaves any cleanup to safe,
repository-level maintenance.

Focused verification, run with bytecode and pytest cache disabled and an
external temporary basetemp:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --basetemp <external-temp> tests/test_g4_clean_target_commit.py
.........                                                                [100%]
9 passed
```

The disposable-repository tests cover exact candidate/tree validation,
dry-run, real success, forced CAS failure with unchanged `FETCH_HEAD`,
explicit object-side-effect attestation, concurrent branch movement, dirty
main worktree/index preservation, and validation failure isolation. No live
CharityGraph repository helper invocation, provider access, bridge/process
management, publication, or GitHub mutation was performed.
