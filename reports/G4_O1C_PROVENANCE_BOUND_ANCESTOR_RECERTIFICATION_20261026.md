# G4-O1C provenance-bound ancestor recertification

Date: 2026-10-26 (Australia/Sydney)  
Disposition: **PASS — read-only recertification**

## Boundary and repository identity

Only this report was written. No product, harness, configuration, process,
provider, external source, Drive, GitHub, publication, release, gate, or Git
commit action was performed. Tests were not run because this task was limited
to read-only verification.

```text
workspace  C:\CharityGraph-clean\charitygraph
branch     gate3-cg406-remediation
target     4054349481b2f6ed99e92b0f669bd304703df68e
source     4b3fbcaeaace5170994da57a4fe502e6f450ba29
ancestry   PASS (git merge-base --is-ancestor exit 0)
```

## Adoption-path verification

The two completed source result records were read from the local bridge
runtime evidence. Both are `CODEX_ENGINEERING_COMPLETED`, verified, and
non-quarantined. In each pair, the result’s `source_sha256` equals the local
source-instruction file hash; instruction ID, content hash, execution object,
and target identity match; and the source report hash matches its current
report bytes.

| source | instruction SHA-256 | result SHA-256 |
|---|---|---|
| P3C content-addressed rights | `162a7f89824fc411337193ac0846cd9a25b819f827820361b15d1f8e5992fb47` | `309ae4eed2eaf8bb5a813906fdc0227803b2c4c29ab125103ba4117d9da85a14` |
| P4 run diagnostics | `6f2c970379d04eac3dfb261146587287f4fef95d657ba83af3211e08afcd2c6c` | `04b0c6209e0ea2b20c6695d6f82793163dc0b63116046a20664122597f5a36c9` |

All six paths remain Git-untracked (`??`), were absent from each applicable
source `before.entries`, and match the applicable source `after.entries` hash:

| path | SHA-256 |
|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |

## Implementation and harness confirmation

`bridge/SUPERVISOR_PROTOCOL.md:50-56` requires exact source-result and
source-instruction hashes, completed verified non-quarantined attestations,
new untracked artifact bytes, and ancestor history. `bridge/bridge.py:706-810`
implements those checks, including identity matching, before/after untracked
status, exact hashes, and `git merge-base --is-ancestor`. The harness covers
successful ancestor adoption and rejects failed/mismatched or diverged source
history in `tests/test_double_loop_harness.py:600-710`.

The six artifacts therefore remain byte-identical to their completed source
attestations, and the ancestor-provenance adoption repair remains recertified
at target HEAD.
