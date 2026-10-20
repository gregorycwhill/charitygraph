# G4-O1C supervisory engineering submission contract

Status: `READY_FOR_SUPERVISORY_ENGINEERING_TEST`

The host-side implementation and managed watcher integration are prepared.
The final live instruction must be authored and uploaded by the supervising
ChatGPT conversation. No local instruction is being submitted on ChatGPT's
behalf here.

## Ingress

Use the existing private raw Drive folder:

- Folder: `CharityGraph Agent Bridge/artifacts`
- Folder ID: `1vph8qe-ywqHDILnsErHMyujGeQHbQhVp`
- Windows path: `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\`
- Filename: `cg-g4-o1b-instruction-<unique-id>.json`

The bytes must be exactly one canonical JSON object line followed by one LF:
UTF-8, no BOM, no CRLF, no pretty printing, no extra bytes. The watcher
records the SHA-256 of those complete materialized bytes as `source_sha256`.
The `content_sha256` field is the SHA-256 of the exact UTF-8 bytes of the
JSON `content` string only.

## Supported envelope

Required top-level keys are:

```json
{"authority":{"approved":true,"authority_envelope":"gate4-engineering","source":"chatgpt"},"content":"<bounded local repository engineering task>","content_sha256":"<sha256 of content UTF-8 bytes>","created_at":"<timezone-aware ISO-8601 timestamp>","execution":{"change_policy":"report_only","mode":"codex_exec","model":"luna-high","report_path":"reports/<fresh-report-name>.md","timeout_seconds":300},"instruction_id":"gate4:engineering:<unique-id>","operation":"codex_engineering","schema_version":"charitygraph.autonomous-instruction/v1","target":{"branch":"gate3-cg406-remediation","head":"068561551a43bbeaa0e8347e4ddff1a5caa8044d","model":"luna-high","repository":"charitygraph","workspace_path":"C:\\CharityGraph-clean\\charitygraph"}}
```

The engineering authority is exact: `source=chatgpt`, `approved=true`, and
`authority_envelope=gate4-engineering`, with no extra authority keys. The
target workspace, repository, branch and full 40-character HEAD are checked
against the host before claiming. The only supported model alias is
`luna-high`, invoked through the installed Codex CLI as `gpt-5.6-luna` with
high reasoning effort.

`report_path` must be a fresh relative `.md`, `.json` or `.txt` path under
`reports/`. `timeout_seconds` must be an integer from 30 through 900. The
worker wraps the content in a safety boundary and runs:

```text
codex exec --model gpt-5.6-luna -c model_reasoning_effort="high" --sandbox workspace-write --cd C:\CharityGraph-clean\charitygraph --json --color never --output-last-message <audit-path> <bounded-content>
```

The content must be limited to one local repository task. It must not request
provider or source acquisition, external network use, Drive sync changes,
watcher/process management, GitHub mutation, publication, merge, release,
gate closure, deletion/reset/checkout of historical work, or follow-on task
dispatch. `report_only` is the required policy for this supervisory test.

## Single-use and recovery semantics

- The SQLite ledger under the runtime bridge directory is the sole claim
  authority. Repeated upload of identical bytes is a duplicate/no-op.
- Reusing an `instruction_id` with changed content is rejected.
- A target mismatch, malformed JSON, BOM, CRLF/multiline input, bad hash,
  authority expansion, unsupported operation or unsupported model is rejected
  before claim.
- A completed or failed execution is terminal and is never relaunched by a
  repeated poll.
- If the watcher disappears after claiming/starting a child and before the
  durable completion record, the next watcher marks the lease
  `reconciliation_required` rather than guessing whether work ran. No
  automatic replay occurs.
- The legacy Gate 2 queue, technical specification `007`, campaign `403`,
  supervisor inbox and historical evidence remain fenced and untouched.

## Status and result surfaces

Canonical status filename:

`CharityGraph Agent Bridge/artifacts/cg-g4-o1c-cutover-status.json`

The status schema is `charitygraph.g4-o1c-cutover-status/v1` and includes
timestamps, launcher/child PIDs, watcher instance, branch, HEAD, fence path,
runtime fingerprint, supported operations, last event, last result and error.
The older `cg-g4-o1b-cutover-status.json` remains preserved as stale
historical evidence and is not the live locator.

For instruction ID `gate4:engineering:<id>`, the durable result is:

`CharityGraph Agent Bridge/artifacts/cg-g4-o1c-result-gate4_engineering_<id>.json`

The result schema is `charitygraph.g4-o1c-result/v1`. It includes
`execution_state`, `instruction_id`, both content/source hashes, authority and
target identities, `codex_process.launched`, child PID, return code, requested
alias, invoked CLI model, reasoning effort, Codex thread ID, event types,
timestamps, output-log path/hash, last-message path, engineering report path
and hash, and unexpected workspace changes. It also records zero Builder
provider calls, no source acquisition, no publication and
`semantic_product_work: NOT_PERFORMED`.

## Minimal harmless supervisory test specification

The supervising ChatGPT message should author one fresh envelope with
`change_policy=report_only` asking Codex to read `README.md` and the current
git identity, then write exactly one short Markdown report at a fresh
`reports/` path containing the full HEAD, branch and a statement that the
inspection was provider-free. It must explicitly forbid all external/network,
provider, source, GitHub, publication, merge, release, deletion, reset and
watcher actions.

This contract is the handoff boundary. Local fake-process tests and the
host-side launch failure/retry evidence do not constitute supervisory
acceptance; ChatGPT must originate the live instruction and independently
retrieve the resulting private Drive status and result.
