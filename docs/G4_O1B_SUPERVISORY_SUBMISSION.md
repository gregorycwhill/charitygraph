# G4-O1B supervisory submission contract

**Status:** `PENDING_EXTERNAL_VERIFICATION`  
**Boundary A:** local adapter and submission contract prepared; host-side connected-file mirror remains unavailable  
**Boundary B:** not executed

## Connected ingress candidate

Dedicated native Google Doc created through the connected Drive surface:

- Document ID: `1CfAdNTSHoa0f1KqI1BliuXCbAErD-OH-GSb0Rtu0M6A`
- URL: <https://docs.google.com/document/d/1CfAdNTSHoa0f1KqI1BliuXCbAErD-OH-GSb0Rtu0M6A/edit?usp=drivesdk>
- Title: `CharityGraph G4-O1B Autonomous Ingress Test`
- Current state at verification: empty; the connector rejected the content write because destination ownership/trust for repository/workspace metadata egress was not established.

No instruction was submitted to the document as a result of that rejection.

## Exact harmless probe

The supervising ChatGPT session may submit the following one-line canonical
JSON object only after the destination trust/egress boundary is explicitly
authorised:

```json
{"authority":{"approved":true,"authority_envelope":"gate4-local","source":"chatgpt"},"content":"Record a harmless transport probe only; do not start a watcher, call a provider, acquire sources, publish, merge, or modify product state.","content_sha256":"1e107d80657d02763fc6a85a5e3b38af1065d6f790ae75b25f0ba45da11081e7","created_at":"2026-10-20T12:30:00+00:00","instruction_id":"gate4:supervisory-roundtrip:20261020","operation":"bridge_probe","schema_version":"charitygraph.autonomous-instruction/v1","target":{"branch":"gate3-cg406-remediation","head":"91c00bc5530beee12facb155013078f1c28d27bf","model":"luna-high","repository":"charitygraph","workspace_path":"C:\\CharityGraph-clean\\charitygraph"}}
```

The `content_sha256` is the SHA-256 of the exact `content` string, not of the
whole document. The host mirror must export the document as UTF-8 without BOM,
preserve the object as exactly one canonical JSON line followed by LF, and
write it to the adapter's private materialization inbox. The adapter validates
the bytes before accepting the logical instruction.

## Host-side conversion contract

The host-side mirror must be a one-purpose exporter/importer, not a scheduler:

1. Read only the dedicated ingress document using an existing authorised
   connector or host credential.
2. Export plain UTF-8 text and verify the exact one-line canonical JSON form.
3. Call `LocalAutonomousBridge.import_materialized_instruction(path)`.
4. Publish the adapter's machine-readable result artifact and concise status
   to an approved private result location.
5. Never interpret `content` as shell, Python, or process authority.

The adapter's local result surface is the private, Git-ignored runtime path:

`runtime/gate4-autonomous-loop-20261020-commit2/bridge/results/`

The host mirror is not implemented as a Windows service or scheduled task and
the dormant historical watcher has not been started.

## Minimum external bootstrap

The exact unresolved action is to establish connector/host trust for this
specific private ingress document and one private result location, with no
broader Drive permission and no token committed to Git. The host side needs
read access to the ingress document and write access only to the result
artifact location. If the current platform cannot expose such a host-side
credentialed export path, Boundary B remains pending and the local adapter
must not be presented as a live ChatGPT-to-Windows bridge.
