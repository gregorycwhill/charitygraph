# Gate 4 P3C/P4 artifact revision and promotion capability

Date: 2026-10-26  
Result: **BLOCKED for the named pre-existing untracked artifacts**

## Scope and read-only verification

Read: `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`,
`bridge/SUPERVISOR_PROTOCOL.md`, `bridge/README.md`,
`bridge/bridge.py`, `bridge/managed_launcher.py`,
`src/charitygraph/autonomous_loop.py`,
`src/charitygraph/bounded_authority.py`, and the bridge/harness tests.
No provider, external source, Drive, watcher, or latest external fence was
accessed. No product file or Git state was changed.

The local identity matches the supplied supervisor facts:

```text
branch gate3-cg406-remediation
HEAD   4b3fbcaeaace5170994da57a4fe502e6f450ba29
tree   627fafae46e097d4d4f8d67b57a385c374b0ab84
```

The six named product/test/report files are present, byte-hash exact, and all
six are `??` pre-existing untracked paths. The supplied active-fence hash was
not re-read because the task forbids external fence access. The required report
path was absent before this task.

| path | SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

The named historical dirty tracked files remain dirty and were not touched:
`src/charitygraph/source_rights.py`, `src/charitygraph/runtime/catalog.py`,
and `src/charitygraph/phase5_governed_factory_integration.py`. P3b2 remains
quarantined and unaccepted.

## A. Fresh bounded revision instruction

No, not with the current bridge. The bounded route is active
(`bridge/bridge.py:322-328`; `src/charitygraph/bounded_authority.py:17-20`),
and envelope/target ingress is real: required target fields and full HEAD are
checked in `src/charitygraph/autonomous_loop.py:146-165`, then configured
workspace, branch, and HEAD are checked in `src/charitygraph/autonomous_loop.py:219-236`.
`bridge/bridge.py:584-681` validates the bounded execution fields,
`authority_version`, scope, `local_commit_only`, relative non-empty
`allowed_paths`, model, report path, and fresh report existence.

However, `allowed_paths` is only a path-name allowlist. It does not establish
provenance or exempt a path from baseline protection. The execution baseline
is captured in `bridge/bridge.py:733-744`; it deliberately includes tracked,
staged, deleted, renamed, and untracked paths. `capture_workspace()` records
all status paths (`src/charitygraph/bounded_authority.py:108-131`) and, for an
allowlisted dirty path, refuses `??`, deleted, symlink, or non-regular entries
because there is no stable Git ancestor (`bounded_authority.py:132-143`).

The current bridge first performs a permissive preview validation
(`bridge/bridge.py:971-975`), but the authoritative pre-launch capture then
calls `capture_workspace(..., preserve_dirty_paths=allowed_paths)` and fails
before Codex launch. The actual read-only call against the current checkout
returned:

```text
DirtyBaselineViolation: allowlisted dirty path cannot be reconciled safely: src/charitygraph/runtime/rights_governance_record.py
```

Therefore a fresh instruction cannot revise these files while preserving their
original bytes. The fresh report path itself is supported: it must be a
relative `.md`, `.json`, or `.txt` path under `reports/`, and must not already
exist (`bridge/bridge.py:647-661`). The bridge also adds the report path to the
runtime allowlist (`bridge/bridge.py:733-735`), although the protocol requires
it to be explicitly listed (`SUPERVISOR_PROTOCOL.md:42-48`).

## B. Fresh byte-exact local commit

No. The supported commit path is narrow but applies to new paths, not these
pre-existing untracked paths. `verify_local_commit()` requires a new
non-merge direct child, exactly one commit, and all committed paths in the
allowlist (`src/charitygraph/bounded_authority.py:306-321`). It then rejects
any committed path already present in the pre-execution baseline with:

```text
pre-existing dirty paths were committed: <path>
```

The one-commit flow is proven for newly created paths by
`tests/test_double_loop_harness.py:test_bounded_diff_guard_accepts_one_allowlisted_local_commit`
(lines 342-352) and
`test_bounded_execution_attests_one_allowlisted_local_commit` (lines 441-488),
where the worker explicitly stages and commits new files. The dirty tracked
case is separate: `test_bounded_diff_guard_reconciles_allowlisted_dirty_hunks_and_limits_paths`
(lines 305-330) proves private pre-edit bytes plus clean exact three-way
reconciliation, while `SUPERVISOR_PROTOCOL.md:60` states that a dirty file can
never be absorbed into a local commit. No test or implementation path provides
the missing untracked adoption/promotion operation.

## C. Existing promotion or admission support

No supported independent supervisor promotion action, bridge-signed
evidence-admission route, or narrow in-repository promotion CLI was found.
The bridge status advertises only `bridge_probe` and `codex_engineering`
(`bridge/bridge.py:304-333`), and its CLI exposes only `watch` and `poll`
(`bridge/bridge.py:1077-1094`). Report mirroring is explicitly diagnostic and
sets `product_accepted: false` even for failed or quarantined runs
(`bridge/bridge.py:947-953`; `SUPERVISOR_PROTOCOL.md:58`).

Fence handling is validation, not promotion: `_read_fence()` only reads and
checks an existing active fence against workspace, branch, and HEAD
(`bridge/bridge.py:463-475`). `matching_fence_identity()` likewise explicitly
never manufactures a fence (`bridge/managed_launcher.py:42-48`). The protocol
does describe a supervisor-only post-commit fence reconciliation
(`SUPERVISOR_PROTOCOL.md:50-56`), but that is not a local artifact-admission
operation and is outside this task.

## D. Minimal Work-session repair specification

The next Work session should receive a separately approved, provenance-bound
promotion/revision capability for exactly these pre-hashed paths, plus the new
report path:

```text
src/charitygraph/runtime/rights_governance_record.py
tests/runtime/test_rights_governance_record.py
reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md
src/charitygraph/phase5_run_diagnostics.py
tests/test_phase5_run_diagnostics.py
reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md
reports/G4_P3C_P4_ACCEPTED_ARTIFACT_REVISION_PROMOTION_CAPABILITY_20261026.md
```

That capability must, before any edit, privately snapshot and verify the six
supplied hashes; preserve before/after byte snapshots and provenance for every
adopted untracked file; reject any hash mismatch; and reject every unrelated
dirty/untracked path. A successful revision must use the same files, never a
duplicate successor module, stage only the exact allowlist, and create at most
one non-merge direct-child local-only commit. The attestation must prove that
no unrelated user dirt was absorbed and that the three dirty tracked historical
files and P3b2 were preserved and not accepted.

Only after that attestation may the supervisor perform the protocol’s new
immutable fence update for the exact child HEAD. No replay, publication, merge,
release, gate closure, watcher action, provider/source work, or follow-on
dispatch is authorised by this report.

## E. Remaining safe tranche

No named P3C/P4 product revision or promotion tranche is safely achievable
through the current bridge. Safe work is limited to non-mutating inspection or
a separately scoped bounded task that does not touch, stage, commit, or duplicate
these pre-existing untracked modules. Such work would not advance this tranche
or change the source of truth.

Recommended non-mutating handoff: retain this report as the capability
diagnosis, preserve all listed bytes and current dirt, and obtain a separately
approved Work-session promotion/revision route before attempting any artifact
revision or commit.
