# G4 T4E host readback context independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free and read-only except for this report

## Verdict

| Surface | Verdict | Boundary |
|---|---|---|
| Dormant structural verifier | **ACCEPT** | Structural consistency only; never cryptographic or independent provenance authentication |
| Live bridge / watcher / launcher | **NOT AUTHORISED** | No import, integration, activation, adoption, Git mutation, provider/Drive call, publication, release or gate action |

The reviewed commit is `9f4c9516f182e07a07d903d12d2bf303a0f99b2d`, branch
`gate3-cg406-remediation`, direct child of
`9a0a7d60e920242e843f1d9f7be282a870022624`, fence contexts `v74`, `v75` and
`v120`. Its exact three changed paths are:

- `bridge/g4_t4e_host_readback.py`
- `tests/test_g4_t4e_host_readback.py`
- `reports/G4_T4E_HOST_READBACK_CONTEXT_REPAIR_20261031.md`

The current files match that commit. SHA-256 values:

| Path | SHA-256 |
|---|---|
| `bridge/g4_t4e_host_readback.py` | `915ea8b68cfd60e15914e10f1cfc946a343a1e275bbf2c643f595aa8a7bf616e` |
| `tests/test_g4_t4e_host_readback.py` | `c5e86a50ad59d218ded8a204804a66ea0b5e36c5fadd09a453d1d4ad22ce5b71` |
| `reports/G4_T4E_HOST_READBACK_CONTEXT_REPAIR_20261031.md` | `bb168ca33b14666a5a4959de92e2c6be419924d76dfadaa1150937518f69bde5` |

The exact two candidate pins remain unchanged:

- `src/charitygraph/phase5_t4d_e3_factory_handoff.py` —
  `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8`
- `tests/test_phase5_t4d_e3_factory_handoff.py` —
  `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7`

## Re-acceptance evidence

The prior PARTIAL finding was the stale fixed `HEAD`/`v73` gate. The repair
removes those fixed values, accepts syntactically valid dynamic host context,
and requires fence, status and ledger records to agree with the observed
branch, HEAD, workspace and fence version. It retains the exact candidate
allowlist and fail-closed artifact checks.

The focused cache-free disposable suite ran with `python -B`,
`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` and an external disposable
basetemp: **21 passed, 0 failed, exit 0**.

Independent adversarial probes: **9 passed, 0 failed, exit 0**. They covered:

- dynamic `v74`, `v75` and `v120` contexts without a fixed HEAD/fence stale gate;
- a syntactically self-consistent forged caller/source/reconciliation/test bundle;
- absent and caller-supplied trust roots;
- forged caller pins and candidate identities;
- timeout status upgrade rejection;
- exact two-candidate hashes and identities;
- malformed JSON, missing/extra artifacts, root escape and symlink rejection;
- redacted output, the exact positive reason, `action=NONE` and
  `adoption_grant=false`.

A forged self-consistent bundle can produce
`STRUCTURE_ONLY_UNAUTHENTICATED`, but it cannot become actionable: the result
always has `action=NONE`, `adoption_grant=false`, `recovery_authority=false`,
`host_authentication_required=true`, and unauthenticated trust scope. Caller
pins, source results, reconciliation evidence, test attestations, report
content and a caller-supplied trust root are explicitly not authenticated.
The positive reason is `structure_only_unauthenticated`; the old deceptive
`validation_failed` fallback is absent. Source timeout upgrades and all tested
tampering/layout violations remain blocked.

## Boundary and baseline

The dormant module has no bridge, subprocess, Git, provider, Drive or network
integration and performs no filesystem writes. Repository search found no code
import or call outside the dormant module/test/report surface. Synthetic test
fixtures were confined to disposable runtime space; no raw source, private
artifact bytes, credentials, cache or debug output was added to the repository.

Before and after both disposable runs, the dirty baseline was unchanged:
**140 status entries**, exact status sequence equal, and HEAD unchanged at
`9f4c9516f182e07a07d903d12d2bf303a0f99b2d`. The only repository write for this
task is this report.

## Smallest next safe step

Keep the verifier dormant. A separately authorised host-only tranche must
provide bridge-owned immutable provenance and host authentication for the
instruction, timeout result, active context, reconciliation/test evidence and
candidate package, then perform a new acceptance. Structural positivity alone
must not grant recovery, adoption or execution authority.
