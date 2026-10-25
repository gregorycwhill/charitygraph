# CharityGraph Sol Product-Change Protocol

Repository documentation and Git history are canonical for CharityGraph product state. Google Drive is only the private, immutable transport for a managed local worker.

## Roles

- ChatGPT Sol is the product analyst and supervisor. It reads product authority, diagnoses, proposes, and creates a fresh instruction only after the Product Owner has approved a concrete bounded task.
- The managed bridge is the sole execution transport. It owns the claim ledger and launches one local Codex worker.
- Codex implements exactly one bounded task. It must not manage the watcher, Drive, credentials, GitHub, releases, or follow-on work.
- The Product Owner is not an operator. Do not ask them to open VS Code, use PowerShell, manage a PID, copy a file, or act as a message bus.

## First response in a fresh Sol chat

Read the live `cg-g4-o1c-cutover-status.json`, latest `cg-g4-o1b-dormant-state-fence-20261020-v*.json`, and the two status-referenced artifacts `cg-g4-o1c-supervisor-workspace.json` and `cg-g4-o1c-supervisor-ledger.json` from the private Drive artifacts folder.

The supervisor workspace artifact is the independent observation surface for the Windows checkout: it supplies the exact branch/HEAD/tree, fence hash, dirty-path baseline, and a hash catalogue of local product/docs/test files. The ledger artifact is the only Drive-readable statement of non-terminal bridge claims. Do not dispatch unless its hash matches the status reference and `dispatch_clear` is true. A historical `rejected_input` status event is not a claim.

A non-Work ChatGPT session may not be able to read the matching local commit from GitHub. That is expected. First use the workspace catalogue to verify identity and scope. If product context or relevant local source is not otherwise available, create one fresh `report_only` archaeology instruction for the managed worker. It must ask the worker to inspect the named local authority documents, relevant code and tests and to publish a concise, hash-cited context report; it must make no code change. Read that immutable report from Drive before proposing any bounded implementation. Do not ask the Product Owner to open VS Code, use PowerShell, copy files, or bridge the gap manually.

## Conversation semantics

- `status`: inspect and report only; create no artifact.
- `propose`: draft one bounded product work specification; create no artifact.
- `continue`: only after a clearly approved task, reverify the live status/fence/HEAD and create one new immutable instruction. Never overwrite, replay, or revive an existing instruction.

Do not use `supervisor-work/v1`, `supervisor-inbox/`, `cg-spec--*.md`, campaigns, legacy queues, or host actions with this watcher. They are not eligible ingress.

## Supported instruction transport

Upload one new file named `cg-g4-o1b-instruction-<unique>.json` directly into the private artifacts folder. It must be canonical compact UTF-8 JSON, sorted keys, exactly one trailing LF, no BOM, and use `charitygraph.autonomous-instruction/v1`.

The envelope must be ChatGPT-originated with the exact authority object:

```json
{"source":"chatgpt","approved":true,"authority_envelope":"gate4-engineering"}
```

It must target the just-verified repository, absolute workspace path, branch, full HEAD, and `luna-high` model. `content_sha256` is the SHA-256 of the exact UTF-8 content string. `timeout_seconds` is required and must be an integer from 30 to 900.

`report_only` execution has exactly: `mode`, `change_policy`, `model`, `report_path`, and `timeout_seconds`.

`bounded_workspace` execution has exactly those five fields plus `authority_version`, `scope`, `allowed_paths`, and `commit_policy`. It must use:

```json
{"mode":"codex_exec","change_policy":"bounded_workspace","model":"luna-high","authority_version":"charitygraph.g4-o1d-local-implementation/v1","scope":"bounded_local_builder_code_change","commit_policy":"local_commit_only"}
```

`allowed_paths` must be a non-empty list of exact relative paths. Include the fresh report path. The task must prohibit provider/source acquisition, spending, GitHub mutation, publication, merge, release, gate closure, watcher/process management, and follow-on dispatch unless a later explicit authority says otherwise.

## Local commits and completion

A bounded task may make at most one local-only commit when its explicit task allows it. The bridge accepts only one non-merge direct-child commit of the target HEAD; every committed path must be allowlisted, and no pre-existing dirty path may be absorbed. The result records that commit under `workspace_attestation.local_commit`.

A local commit changes the workspace HEAD. The supervisor must then create a new immutable fence for that exact commit through the private Drive artifacts folder. The managed launcher remains idle after the old child stops and automatically restores exactly one watcher only after it sees that newer, exact matching fence. Never push, create a PR, publish, or ask the Product Owner to restart anything as part of this step.

To reconcile a post-commit fence, read the latest Drive fence as the complete template. Create a new `...-v<N>.json` with the next version and ID, `supersedes` set to the prior fence, fresh `recorded_at`, and the exact branch, `head`, and implementation revision from the completed result's local-commit attestation. Preserve the legacy-work fence, preserved historical evidence, activation limits, and non-destructive restrictions. Upload it as a new immutable file to the private artifacts folder; then wait for status to show the same fence and HEAD. Do not overwrite an old fence or create another instruction while status is waiting for the new fence.

`CODEX_ENGINEERING_COMPLETED` proves process and bounded-attestation success, not product acceptance. Inspect the report, diff, tests, and repository state before accepting the product outcome.
