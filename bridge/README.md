# Controlled G4-O1C bridge cutover

The sole supported entrypoint for the cutover is:

```powershell
python bridge\managed_launcher.py --artifacts-root "C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts" --workspace-root "C:\CharityGraph-clean\charitygraph" --runtime-root "C:\CharityGraph-clean\charitygraph\runtime\g4-o1b-controlled-cutover-20261020" --no-sound
```

Only files named `cg-g4-o1b-instruction-*.json` directly under the private
Drive-synced `artifacts` folder are eligible. The file must be exactly one
canonical UTF-8 JSON line followed by LF and contain the
`charitygraph.autonomous-instruction/v1` envelope. The watcher never scans or
claims the legacy queue, supervisor inbox, technical-spec Markdown, campaign
state, or historical `.json` files.

The enabled operations are `bridge_probe` and the bounded
`codex_engineering` operation. `bridge_probe` records a harmless transport
result. `codex_engineering` launches exactly one `codex exec` subprocess using
the `luna-high` -> `gpt-5.6-luna` / high-reasoning mapping, workspace-write
sandbox, a report path under `reports/`, and durable process/session evidence.
It does not permit provider/source acquisition, GitHub mutation, publication,
merge, release, gate closure, host actions, or follow-on dispatch.

The adapter owns the only claim ledger; the launcher owns only process
supervision. The canonical live status is
`cg-g4-o1c-cutover-status.json`; the older
`cg-g4-o1b-cutover-status.json` is preserved as historical/stale evidence.
