# G4-O1C v29 provenance-bound adoption schema review

Date: 2026-10-26 (Australia/Sydney)  
Inspection HEAD: `1e3e4b8f36ca8b4591a786e6cda1f0ff56265ece`  
Branch: `gate3-cg406-remediation`

## Scope and result

Read-only inspection of the active parser/validator in `bridge/bridge.py:584-763`,
`src/charitygraph/bounded_authority.py:190-238,363-413`, and the adoption tests
and helper in `tests/test_double_loop_harness.py:70-113,402-450,579-650`.
No adoption, queueing, source-result access, test run, commit, or external action
was performed. The files contain no literal `v29` token; this report treats the
current HEAD implementation as the referenced active v29 path.

## Exact autonomous-instruction/v1 shape

The envelope has these top-level members: `schema_version`, `instruction_id`,
`content`, `content_sha256`, `authority`, `target`, `operation`, `created_at`,
and, for this route, `execution`. The schema value is exactly
`charitygraph.autonomous-instruction/v1`; the operation is `codex_engineering`.
The authority object must be exactly:

```json
{"source":"chatgpt","approved":true,"authority_envelope":"gate4-engineering"}
```

`content_sha256` is SHA-256 of the exact UTF-8 content string. The target must
identify `repository`, absolute `workspace_path`, `branch`, full 40-hex `head`,
and model `luna-high`; bounded validation also requires those values to match
the inspected workspace and current HEAD.

For `provenance_bound_adoption`, `execution` has exactly these ten members:

```text
mode, change_policy, model, report_path, timeout_seconds,
authority_version, scope, allowed_paths, commit_policy, adopted_artifacts
```

Required fixed values are `mode=codex_exec`,
`change_policy=provenance_bound_adoption`,
`authority_version=charitygraph.g4-o1d-local-implementation/v1`,
`scope=bounded_local_builder_code_change`, and
`commit_policy=local_commit_only`. `timeout_seconds` is an integer from 30
through 900. `report_path` is a fresh relative `reports/` path ending in
`.md`, `.json`, or `.txt`. The allowlist is relative, non-empty, traversal-free,
and the bridge requires its set to be exactly adopted paths plus that fresh
report path, with no duplicate entries.

Each `adopted_artifacts` member has exactly these five fields—no
`source_result_filename` or `source_result_path` field exists:

```json
{
  "path":"relative/path",
  "sha256":"<lowercase SHA-256 of current artifact bytes>",
  "source_instruction_id":"<completed source instruction>",
  "source_result_file":"cg-g4-o1c-result-<name>.json",
  "source_result_sha256":"<lowercase SHA-256 of raw source-result bytes>"
}
```

`path` must be an allowlisted relative path and all artifact paths must be
unique. Both hashes must be exactly 64 lowercase hexadecimal characters.
`source_result_file` must be a basename beginning `cg-g4-o1c-result-`, ending
`.json`, with no slash or backslash. The bridge resolves that basename beneath
its configured `artifacts_root` and additionally requires the resolved parent
to be exactly that root; absolute paths and subdirectories are invalid.

## Provenance and hash semantics

Before launch, every listed artifact must still be a non-symlink regular file
with Git status `??` and byte hash equal to the item `sha256`. The referenced
source-result bytes must hash exactly to `source_result_sha256`; the validator
then parses those same raw bytes as JSON and requires:

```text
schema == charitygraph.g4-o1c-result/v1
instruction_id == source_instruction_id
execution_state == CODEX_ENGINEERING_COMPLETED
workspace_attestation.verified == true
workspace_attestation.quarantined == false
```

The source attestation must have started at the current HEAD, must not list the
artifact in `before.entries`, and must show in `after.entries` the exact tuple
`["??", artifact_sha256, <diff-hash>]`, with the path in `changed_paths`.
Thus `source_result_sha256` pins the raw result file, not its internal
`source_sha256`, the instruction content hash, or the artifact hash. The
artifact `sha256` pins the artifact bytes at adoption launch.

## Can one task adopt the six P3c/P4 artifacts unchanged?

The schema and commit verifier support one task listing all six: use six
distinct `adopted_artifacts` entries and an allowlist containing those six paths
plus one fresh report path. The verifier does not require the post-worker bytes
to differ from the pre-launch bytes; unchanged adoption is therefore
technically permitted if all six are committed in the one allowlisted commit.

That is conditional, not established by their present hashes. The current six
are all `??` regular files and currently hash as follows:

| path | current SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

Each still needs its own matching completed source result whose `before.head`
is current `1e3e4b8…` and whose attestation proves that file was newly created
untracked. The earlier six-file inventory was at `4b3fbca…`; a result tied to
that historical HEAD is rejected. The current tests exercise one adopted file,
not a six-member list, and do not prove this exact six-file case.

## One-commit and post-commit fence handling

The worker may create at most one local commit. `verify_local_commit` requires
one non-merge direct child of the starting HEAD, exactly one commit in the
range, every adopted path present in the commit, no non-allowlisted path, no
pre-existing dirty path absorbed, and no committed symlink. Unrelated dirty
paths remain protected. The bridge records the resulting `commit_head` and
`commit_paths` in `workspace_attestation.local_commit`.

Because that commit changes HEAD, the supervisor—not the worker—must reconcile
the post-commit fence: create a new immutable fence from the latest fence
template, increment its version/ID, set `supersedes` to the prior fence, and
record the exact branch, new HEAD, and implementation revision from the commit
attestation. The old fence and historical evidence remain preserved. The
managed launcher remains idle until the newer exact fence and HEAD are observed.
This review did not create or upload a fence.

## Compact structural example (not queued or executable)

This shows current HEAD and the exact member names. The source-result hash is
illustrative; the referenced result must exist and satisfy the provenance checks
above before any real instruction could be accepted.

```json
{
  "schema_version":"charitygraph.autonomous-instruction/v1",
  "instruction_id":"gate4:review:adoption-schema-exact",
  "content":"Read-only schema review; do not execute adoption.",
  "content_sha256":"0091515f9fd0df3bae81b81ef0b263ca4c6df99ebb01de52723a12c763c2c27f",
  "authority":{"source":"chatgpt","approved":true,"authority_envelope":"gate4-engineering"},
  "target":{"repository":"charitygraph","workspace_path":"C:\\CharityGraph-clean\\charitygraph","branch":"gate3-cg406-remediation","head":"1e3e4b8f36ca8b4591a786e6cda1f0ff56265ece","model":"luna-high"},
  "operation":"codex_engineering",
  "created_at":"2026-10-26T00:00:00+00:00",
  "execution":{"mode":"codex_exec","change_policy":"provenance_bound_adoption","model":"luna-high","report_path":"reports/example-fresh-review-20261026.md","timeout_seconds":30,"authority_version":"charitygraph.g4-o1d-local-implementation/v1","scope":"bounded_local_builder_code_change","allowed_paths":["src/charitygraph/runtime/rights_governance_record.py","reports/example-fresh-review-20261026.md"],"commit_policy":"local_commit_only","adopted_artifacts":[{"path":"src/charitygraph/runtime/rights_governance_record.py","sha256":"e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9","source_instruction_id":"gate4:engineering:prior-adoption-source","source_result_file":"cg-g4-o1c-result-prior-adoption-source.json","source_result_sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}
}
```

