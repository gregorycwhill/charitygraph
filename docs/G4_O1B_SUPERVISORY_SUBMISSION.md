# G4-O1B controlled cutover supervisory submission contract

Status: `READY_FOR_SUPERVISORY_TEST`

Boundary A is prepared: the private Drive raw-file ingress is synced and
byte-verified, historical Gate-2 work is fenced, and exactly one managed
cutover watcher is live. Boundary B is intentionally pending the supervising
ChatGPT-originated submission. Local tests are not end-to-end acceptance.

## Direct raw Drive ingress

Use the existing private `artifacts/` folder, not Google Docs:

- Drive folder ID: `1vph8qe-ywqHDILnsErHMyujGeQHbQhVp`
- Folder locator: `CharityGraph Agent Bridge/artifacts`
- Filename: `cg-g4-o1b-instruction-supervisory-probe-20261020.json`
- Windows sync path: `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\`

The file must be exactly one UTF-8 JSON object line followed by LF, with no
BOM, no pretty printing and no extra bytes. Upload or create the raw file
directly in the private folder. Do not place it in `queue/`, `supervisor-inbox/`
or `test/`.

The watcher accepts only the filename prefix `cg-g4-o1b-instruction-` and the
operation `bridge_probe`; it ignores all historical queue/spec/campaign files.

## Exact harmless one-use probe

Use this exact one-line object:

```json
{"authority":{"approved":true,"authority_envelope":"gate4-local","source":"chatgpt"},"content":"Record a harmless transport probe only; do not start a watcher, call a provider, acquire sources, publish, merge, or modify product state.","content_sha256":"1e107d80657d02763fc6a85a5e3b38af1065d6f790ae75b25f0ba45da11081e7","created_at":"2026-10-20T12:30:00+00:00","instruction_id":"gate4:supervisory-roundtrip:20261020","operation":"bridge_probe","schema_version":"charitygraph.autonomous-instruction/v1","target":{"branch":"gate3-cg406-remediation","head":"8292561f3469f4a861b8dca80c91a8fda0feb9f5","model":"luna-high","repository":"charitygraph","workspace_path":"C:\\CharityGraph-clean\\charitygraph"}}
```

The `content_sha256` is the SHA-256 of the exact `content` value, not of the
whole JSON file. The whole file's SHA is the materialized-byte identity that
the watcher records independently.

## Expected result

After Drive Desktop materializes the file, the watcher will claim it once and
write a private result named:

`CharityGraph Agent Bridge/artifacts/cg-g4-o1b-result-gate4_supervisory-roundtrip_20261020.json`

It will also refresh:

`CharityGraph Agent Bridge/artifacts/cg-g4-o1b-cutover-status.json`

The result schema is `charitygraph.g4-o1b-result/v1`. Expected fields include
`instruction_id`, `content_sha256`, `source_sha256`, `authority`, `target`,
`execution_state: TRANSPORT_PROBE_COMPLETED`, `provider_calls: 0`,
`source_acquisition: false`, `publication: false`, and
`semantic_product_work: NOT_PERFORMED`.

Re-reading the input or submitting the same bytes again must produce a
duplicate/no-op and must not create a second physical result.

## Current host identity

- Workspace: `C:\CharityGraph-clean\charitygraph`
- Branch: `gate3-cg406-remediation`
- HEAD: `8292561f3469f4a861b8dca80c91a8fda0feb9f5`
- Fence: `artifacts/cg-g4-o1b-dormant-state-fence-20261020-v3.json`
- Result/status surface: private Drive-synced `artifacts/`

Do not start another watcher. Do not submit any old Gate-2 technical spec or
campaign item. Do not treat this harmless probe as product, Gate-4 or
end-to-end semantic acceptance.
