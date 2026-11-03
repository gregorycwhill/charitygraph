# G4 T4E host readback independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Target: `gate3-cg406-remediation@9a0a7d60e920242e843f1d9f7be282a870022624`  
Parent: `354619c30b5fe85c2a4d513b111315c432524fc6`  
Requested fence: `v74`

## Verdict

| Surface | Verdict | Boundary |
|---|---|---|
| Dormant `bridge/g4_t4e_host_readback.py` | **PARTIAL** | Structurally useful and fail-closed; not independently authenticated and not accepted for the requested v74/child context |
| Live bridge / watcher / launcher | **NOT AUTHORISED** | No integration, activation, Git transaction, adoption, provider, Drive, publication or release action |

The module must remain dormant and its positive result must remain
`action=NONE`. A positive readback is not provenance authentication or
recovery authority.

The review was grounded in the repository instructions, `BUILDER_MACHINERY.md`,
`ARCHITECTURE.md`, the sibling Data repository's `DOCUMENT_AUTHORITY.md`,
`CURRENT_STATE.md`, `IMPLEMENTATION_PLAN.md`, `TEST_PLAN.md` and the prior T4E
host-recovery design/recovery-authority acceptance reports.

## Exact evidence

The reviewed commit is exactly three paths and is the direct child of the
stated parent:

| Path | SHA-256 |
|---|---|
| `bridge/g4_t4e_host_readback.py` | `f5e6c8ddc3810553c554048e31a920f516139d15ec958d6556e19c5d9cf29da7` |
| `tests/test_g4_t4e_host_readback.py` | `3abdfcdea0f986ca6d8dc5002c4110e46b4874218055322730e758f65b8125a9` |
| pre-existing dormant report | `dc9bbe316fd3bb49b5b49c99478ba8f2fed8d1e0f4fd16768c60f24c4e8e997f` |

The exact candidate allowlist bytes are unchanged and match the module pins:

- `src/charitygraph/phase5_t4d_e3_factory_handoff.py` —
  `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8`
- `tests/test_phase5_t4d_e3_factory_handoff.py` —
  `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7`

The module constants are `EXPECTED_HEAD=354619c...` and
`EXPECTED_FENCE_VERSION=v73`, not the requested active child HEAD and fence
`v74`. Supplying the requested child HEAD and `v74` was blocked with
`head_pin_invalid` and `fence_version_invalid`. This is safe fail-closed
behaviour, but it is not acceptance of the requested context.

## Independent execution and probes

With `python -B`, `PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled and an
external disposable basetemp, the focused suite completed **12 passed, 0
failed, exit 0**. The verifier itself performed no writes. Tests wrote only
synthetic fixtures in disposable runtime temp space.

The suite and read-only static review covered:

- byte-hash tampering, missing/extra files, duplicate source identity and
  source/test allowlist mismatch — blocked;
- path traversal, root escape and symlink artifacts — blocked;
- noncanonical JSON and duplicate-identity conditions — blocked;
- stale target context, active/ambiguous ledger state and timeout upgrade —
  blocked;
- immutable/redacted output, preservation of fixture bytes and
  `action=NONE` — passed.

Additional synthetic probes found:

- a caller-chosen `pin_set_id`, self-generated timeout result, self-generated
  `independent=true` reconciliation result, fake test attestations and
  caller-supplied artifact hashes can form a positive structural result;
- an active ambiguous ledger claim is blocked with
  `ledger_claim_or_dispatch_blocker`;
- a non-empty reconciliation report containing a synthetic private-raw-data
  marker is accepted as an artifact, although the returned attestation does
  not expose that marker. The module does not validate report privacy content;
- the positive result currently carries the fallback reason
  `validation_failed` when no failure reason exists. This is misleading but
  does not make the result actionable.

The decisive trust-boundary finding is that `HostReadbackConfig`,
`ExpectedArtifact` identities/hashes, `pin_set_id`, the source timeout record,
the reconciliation result and test attestations are all caller-supplied.
There is no signature, bridge-owned immutable provenance record, or other
independent origin check. The existing positive fixture therefore proves
structural consistency only; it does not authenticate the claimed source or
independent reviewer.

## Bridge and workspace boundary

Repository search found no import or call from the live bridge, watcher or
launcher; references are confined to the dormant module, its focused tests and
reports. `git diff-tree` confirms the exact three added paths above. No Git,
Drive, provider, network, process, acquisition, publication or activation
operation occurred.

Before and after the disposable test run, the pre-existing worktree baseline
was unchanged: **139 status entries** (**14** tracked modifications, **125**
untracked entries, **0** staged). HEAD remained `9a0a7d60...`; no pre-existing
dirty or index state was changed. The only repository output of this task is
this report; no private raw source, credential, cache, runtime artifact or
debug file was added.

## Minimum next safe step

Keep this module dormant. A future separately authorised host-only tranche
must obtain bridge-owned immutable bytes for the instruction, timeout result,
fence/status/ledger, independent reconciliation and exact candidate package;
construct the config from those authenticated reads; verify the requested
v74/child context; and repeat independent acceptance. Until then, do not
claim authenticated provenance, integrate the live bridge, adopt files, move
refs or close any gate.
