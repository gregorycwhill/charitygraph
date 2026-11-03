# G4 P3c/P4 provenance-bound adoption — 2026-10-26

Status: **FAIL CLOSED — no adoption or commit**

## Boundary and contradiction

The six requested files were found as regular, pre-existing Git-untracked
(`??`) files. Their current bytes match the hashes recorded by the local
recertification evidence. The current repository is branch
`gate3-cg406-remediation`, HEAD
`4054349481b2f6ed99e92b0f669bd304703df68e`, tree
`a36ca417f7fb15764f02be6fc7517ad1f9d16b0e`, and the recorded source HEAD
`4b3fbcaeaace5170994da57a4fe502e6f450ba29` is an ancestor.

Adoption requires independently reading each raw source-result file from the
configured artifact root and verifying its source instruction identity, raw
SHA-256, completed/non-quarantined attestation, and original created-untracked
attestation. The permitted local artifact root
`C:\CharityGraph-runtime\artifacts` contains no `cg-g4-o1c-result-*.json`
files. The bridge documentation identifies the source-result transport as a
private Drive-synced artifact folder; this task forbids Drive/provider access.
The prior local recertification reports record source/result SHA pairs, but are
not a substitute for raw artifact-root verification. Therefore the adoption
precondition is unverified and the task stops without staging or committing.

## Six unchanged artifacts

| path | current SHA-256 | status |
|---|---|---|
| `src/charitygraph/runtime/rights_governance_record.py` | `e5e5d55fcef5dcb3c465b5859e834067f9d1ac908adb817d9dca3e697753c3b9` | `??` |
| `tests/runtime/test_rights_governance_record.py` | `3441be1fe98baab3927ab1429a3d8ade6db56f1d441ef486706ab6c06f9ca310` | `??` |
| `reports/G4_P3C_CONTENT_ADDRESSED_RIGHTS_RECORD_AUTHORITY_20261026.md` | `cf990b61a80956d1b85ecec927d075a9b349ee029d2e62d71f3dea79d7ab838` | `??` |
| `src/charitygraph/phase5_run_diagnostics.py` | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` | `??` |
| `tests/test_phase5_run_diagnostics.py` | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` | `??` |
| `reports/G4_P3C_P4_RUN_DIAGNOSTICS_20261026.md` | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` | `??` |

Pre/post hashes for all six are identical. Exact adoption diff: none. No
unrelated dirty or untracked path was staged, changed, or absorbed. No local
commit was created; the branch and HEAD remain unchanged. This report is the
only new path written by this task and is intentionally uncommitted because
the requested seven-path commit cannot be made safely.

## Source provenance record available locally

The local ancestor recertification reports list these prior source/result SHA
pairs, without exposing the raw result files or enough identity to replace
them:

| source label | instruction SHA-256 | result SHA-256 | raw verification here |
|---|---|---|---|
| P3C content-addressed rights | `162a7f89824fc411337193ac0846cd9a25b819f827820361b15d1f8e5992fb47` | `309ae4eed2eaf8bb5a813906fdc0227803b2c4c29ab125103ba4117d9da85a14` | **not performed** |
| P4 run diagnostics | `6f2c970379d04eac3dfb261146587287f4fef95d657ba83af3211e08afcd2c6c` | `04b0c6209ea2b20c6695d6f82793163dc0b63116046a20664122597f5a36c9` | **not performed** |

## Tests

- Focused: `python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-g4p3c-p4-adoption-focused-20261026-01 tests/runtime/test_rights_governance_record.py tests/test_phase5_run_diagnostics.py` — **20 passed**.
- Focused regressions: the six provider-free Phase 5/runtime suites — **101 passed**.

No provider, network, source acquisition, spending, watcher/process,
publication, GitHub, merge, release, fence, or follow-on action occurred.

## Retained product limitations

This report does not claim semantic or product acceptance. P3c rights-policy
validation, subject/scope/SQLite/revalidation gaps, and P4 synthetic-only
diagnostics, ledger-validity, and ambiguous-crossing gaps remain open. P3b2
remains quarantined and was not adopted. Gate 4 remains open.
