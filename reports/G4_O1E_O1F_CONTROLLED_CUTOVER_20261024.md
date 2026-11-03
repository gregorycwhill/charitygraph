# G4-O1E/O1F controlled cutover and recovery — 2026-10-24

## Result

The committed fail-closed repair at `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2` is now loaded by exactly one supported managed launcher/watcher pair. Bounded code-changing execution remains inactive.

Final live identities:

- launcher PID: `31584`
- watcher PID: `16700`
- watcher instance: `g4-o1b-16700-e6b8488e5a07`
- branch: `gate3-cg406-remediation`
- HEAD: `0e57164bd0eb4a8197e21294bcfb603ff6b67ea2`
- runtime fingerprint: `06ff5e1169ccd7f997263e28c875e5f352c689afd1a2891d579754769b88d7b8`
- watcher state: `READY`
- error: none
- code-changing route: `False`
- last status publication sequence: `1`

## Fence chain

Fence v11 was preserved unchanged. Its recorded SHA-256 remains `f1e7ff71ee693b947f26c0f6105a50a6e52e1a9f67a078201c681f89e7807b94` and it remains the historical predecessor.

Fence v12 is the immutable active successor:

- local: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1d-dormant-state-fence-20261020-v12.json`
- Drive Desktop: `C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\cg-g4-o1b-dormant-state-fence-20261020-v12.json`
- Drive URL: `https://drive.google.com/file/d/1VB9KHbvtlHu4njAgfCtHH9oxtL7zwavq/view?usp=drivesdk`
- bytes: `2,767`
- SHA-256: `d6a4afe2ace0b532d65700a616c9af315bc50b23c066dd2e925d61dac4052b0d`

The v12 fence binds the exact branch/HEAD, preserves v11’s historical hashes and non-destructive protections, keeps technical specification `007` and campaign `403` ineligible, isolates the legacy queue and supervisor inbox, and preserves the one-managed-worker policy.

## Claim and replay reconciliation

The SQLite ledger contains six instructions. Every instruction is `complete` with `attempts=1`, no lease, and the original four events (`submitted`, `claimed`, `started`, `completed`). There are zero nonterminal instructions and zero supervisor claims. No historical instruction was replayed and no new instruction was created.

The initial unprivileged launcher attempt was rejected by argument splitting at the `My Drive` path. A correctly quoted unprivileged pair (`5528/30492`) hung while creating the atomic status temporary file because Drive Desktop grants the sandbox identity read/execute access to `artifacts`. That exact pair was stopped safely with the ledger untouched. The final supported launcher ran with the Windows user’s Drive Desktop access and reached READY.

## Evidence locations

- local status: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020\status.json`
- private Drive status: [cg-g4-o1c-cutover-status.json](https://drive.google.com/file/d/1MUOtflDgZZDEgnZbO2Gvn78sB40pIsm_/view?usp=drivesdk)
- local bridge ledger: `C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020\bridge\bridge.sqlite3`
- unchanged repair report: [G4_O1E_O1F_FAIL_CLOSED_REPAIR_20261024.md](https://drive.google.com/file/d/1bUhQAuNvx19hO8aBNsWBGQsuaT0XY8yc/view?usp=drivesdk)

The private repair report upload is inert Markdown in Drive `test/`, not an allowlisted instruction filename. Its Drive readback matches the local report content and size; the local source SHA-256 is `3c105fa5b97c5067c0a08a8f0f5ab5fa9a5deb4f616dd6cd59af565cd5689b00`.

## Boundary

The bridge is ready for independent ChatGPT supervisory recertification only. This cutover did not activate bounded code changes, dispatch O1G/O1H, call providers, mutate GitHub, alter product state, or close a gate.

**READY_FOR_CHATGPT_RECERTIFICATION**
