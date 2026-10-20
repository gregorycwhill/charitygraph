# Controlled G4-O1B bridge cutover

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

The only enabled cutover operation is `bridge_probe`. It records a harmless
transport result and performs no product, provider, source, publication, or
GitHub action. The adapter owns the only claim ledger; the launcher owns only
process supervision.
