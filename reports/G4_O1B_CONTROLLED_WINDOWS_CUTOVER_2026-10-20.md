# G4-O1B controlled Windows cutover — 20 October 2026

Disposition: `READY_FOR_SUPERVISORY_TEST`

This report is Boundary A preparation only. The final ChatGPT-originated
round-trip has not been performed, and no local simulation is claimed as
end-to-end acceptance.

## Drive ingress

The staged bootstrap file exists at
`C:\Users\grego\My Drive\CharityGraph Agent Bridge\test\cg-g4-o1b-controlled-windows-cutover-bootstrap-20261020.txt` and matches Drive file ID `1YPyEg2wO2uLHkaOr7pVc2KNYORJFOjrt` exactly: 5,675 bytes, SHA-256 `8899BF2D94A39960D714DE53BCEA1B0473955E29725A03433CDAACF5960AE4A1`.

The inert raw probe also syncs exactly at
`C:\Users\grego\My Drive\CharityGraph Agent Bridge\test\cg-g4-o1b-inert-chatgpt-raw-sync-probe-20261020.txt`: 240 bytes, SHA-256 `8942ed6d50b78924bc9cdc6cc0930e1173ded182095dd2cfd547d916e5122a52`, with the expected UTF-8 BOM and CRLF bytes. It was not executable.

The live ingress is the raw private Drive `artifacts/` folder (ID
`1vph8qe-ywqHDILnsErHMyujGeQHbQhVp`). No Docs exporter was added.

## Dormant-state reconciliation

The append-only fence is mirrored at:

- `artifacts/cg-g4-o1b-dormant-state-fence-20261020-v3.json`
- `state/fences/cg-g4-o1b-dormant-state-fence-20261020-v3.json`
- `state/campaign-rejections/g4-o1b-fenced-g2-403-20261020-v3.json`

Technical spec 007 and its `.hold` copy remain byte-identical at SHA-256
`64f9fad279fe378c7ad0eae40eb5d38b44ba050c22efb0b65f60eed18cc838d1`.
There is no matching technical-spec claim or consumed marker. Campaign 403's
original record remains preserved; its pre-fence state was `RUNNING`, with
manifest SHA `c8bef9592b5314b85bb0cf24555987d6e8e32e51eea8710a60dda5b609406e86`.
No Task-2 a1 physical run evidence was found. The new watcher cannot claim
any of this historical material: it only scans the new G4-O1B instruction
filename prefix. Historical files deleted: 0. Historical files modified: 0.

## Single managed watcher

The supported entrypoint is `bridge/managed_launcher.py`. The current live
processes are launcher PID `10012` and child watcher PID `2496`; both are
Python 3.13 processes, with no duplicate cutover watcher. Current status is
idle-ready with no error, bound to branch `gate3-cg406-remediation` at HEAD
`8292561f3469f4a861b8dca80c91a8fda0feb9f5`, fence v3, runtime fingerprint
`6e8dbc45a6c209639c2198fb3c5290eabae861db71e40f4b599e802413853b58`.

The old historical bridge implementation was not present in the local
checkout or Drive mirror. The cutover therefore restores one narrow managed
launcher around the new adapter, without replaying or importing the old
queue/campaign scheduler. The adapter remains the sole instruction claim
ledger; the launcher only supervises the one child.

## Verification

Focused command:

```text
python -m pytest tests/test_autonomous_loop.py tests/test_bridge_cutover.py tests/test_phase5_factory.py tests/test_phase5_factory_chaos.py tests/test_phase5_batch_bytes_and_attempts.py tests/test_standard_delivery_job.py tests/runtime/test_task_state.py -q -p no:cacheprovider -o addopts=''
```

Result: **33 passed**.

Covered cutover behavior includes exact canonical bytes, BOM/CRLF boundary,
duplicate delivery, changed bytes under reused identity, stale ownership,
ambiguous interruption and explicit reconciliation, workspace/branch/HEAD
identity, and legacy-file exclusion. The broader suite remains subject to the
previous protected `.s0-policy-data` fixture failures; those fixtures were not
modified.

## Local commits

- `c06b253` — add controlled G4-O1B managed raw-file watcher
- `feb65e9` — fix managed cutover launcher handoff
- `8292561` — select highest versioned cutover fence

Earlier G4-O1B commits remain preserved: `2e15b2d`, `84b7921`, `c042266`,
`a23993e`, `91c00bc`, and `6d738a5`.

No provider spend, source acquisition, GitHub publication, merge, release,
Gate-3 reopening or Gate-4 closure occurred.
