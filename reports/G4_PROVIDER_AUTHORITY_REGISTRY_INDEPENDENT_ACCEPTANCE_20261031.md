# G4 provider authority registry — independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C independent acceptance  
Verdict: **REJECT for product authority acceptance; PARTIAL for provider-free structural engineering**

## Scope and identity

The checked target is `gate3-cg406-remediation@85f6ff5753124dee6716aeae3fc9c2dccbc657d4`,
parent `9f4c9516f182e07a07d903d12d2bf303a0f99b2d`, with acceptance fence v76.
The exact direct-child diff contains only these four paths:

- `src/charitygraph/g4_provider_policy_registry.py`
- `src/charitygraph/phase5_governed_rights_preflight.py`
- `tests/test_g4_provider_policy_registry.py`
- `reports/G4_PROVIDER_AUTHORITY_REGISTRY_20261031.md`

Binary direct-child diff SHA-256: `fac1a398ead618f1d085b337ff832c910a0a6a67d6c11533dd58bb4f80c3c725`.
The worker report labels itself fence v75 and names the parent rather than this
target commit; that is metadata drift, not a changed code path.

Target blob SHA-256 values are:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/g4_provider_policy_registry.py` | `aef81b13a4efb4d68e2a232a414524ede65aa0ef2ea3f3c809c5998553ffbf2f` |
| `src/charitygraph/phase5_governed_rights_preflight.py` | `18843d36cd5c80178f6282fb7f0e555389915b0f95c9cf78c81b99d340abc4f3` |
| `tests/test_g4_provider_policy_registry.py` | `977b3f2accc12a6db2497a9fb0001db988ac404e5f2a91bff64b8268c4a0b946` |
| `reports/G4_PROVIDER_AUTHORITY_REGISTRY_20261031.md` | `5f6fef052ac6bcc5be02af876fabd3946c2478b81d9c2827c33454bcda82f952` |

## Authority and architecture review

I reviewed Builder `ARCHITECTURE.md` and `BUILDER_MACHINERY.md`, and the local
Data authority documents `DOCUMENT_AUTHORITY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md` and `TEST_PLAN.md`.
The governing rule is that source/evidence/rights/decision/projection states stay
separate; immutable rights records are authoritative; SQLite/v29 is a verified
current-state projection; local retention, provider transmission and public
redistribution are independent axes; provider policy is a condition, not source
permission; and fake/recorded providers are required for implementation tests.

The existing T4A provider-contract registry and identity probe are provider-free
diagnostics. They also accept a caller-supplied record plus a caller-supplied
trusted SHA; neither is a durable source-owned registry or an authenticated
external authority. The new G4 module creates a parallel `ProviderPolicyRecord`
and resolver rather than binding to that existing authority seam. A source-owned
registry symbol is absent from `source_rights.py` (also asserted by the relevant
preflight test).

The v29 seam is otherwise correctly conservative: the new preflight reloads the
content-addressed rights record, requires a current projection row, compares the
row field-by-field, and passes the same record as `rights_authority`. It checks
local retention and provider transmission separately when that optional check is
used. The resolver always emits `real_send_ready=False` and
`send_authorization=not_authorized_for_send`.

## Independent execution

Both commands were run with `PYTHONDONTWRITEBYTECODE=1`, `python -B`,
`-p no:cacheprovider`, empty pytest addopts, and basetemp outside the repository:

- Focused: `tests/test_g4_provider_policy_registry.py` — **13 passed, 0 failed**.
- Relevant regression suite from the worker command — **120 passed, 1 skipped,
  0 failed** in 11.18 seconds.
- The one skip is exactly `tests/test_phase5_governed_rights_preflight.py:228`:
  `clean seam test is isolated from the pre-existing dirty rights prototype`.
  It is caused by the pre-existing dirty overlay in
  `phase5_governed_factory_integration.py`, not by a changed target path.

An exact-HEAD compatibility probe loaded that committed pre-existing integration
from the Git object database in memory. The new preflight lowered one fixture to
`accepted_count=1`, one Factory manifest task, and `_model_task.provider_id=fake`.
This proves backward-compatible provider-free lowering; it is not evidence of
provider-send readiness.

## Adversarial results

The following provider-free matrix was run independently against the resolver:

| Probe | Result | Acceptance meaning |
|---|---|---|
| Canonical positive record | `verified`, send false | Structural success only |
| Coherent forged record with caller-created matching pin | `verified` | **Blocking: caller can self-issue the supposed trusted pin** |
| `authority_content_sha256` inconsistent with actual canonical bytes | `verified` | **Blocking: record authority-content hash is not checked** |
| Noncanonical JSON bytes | `blocked` (`authority_record_not_canonical`) | Correct fail-closed behavior |
| Wrong/invalid/missing trusted pin | blocked/missing | Correct fail-closed behavior |
| Stale, revoked, expired, future-effective, renewal-expired | blocked | Correct temporal/status behavior |
| No-sharing posture or route drift | blocked | Correct posture/route behavior |
| Duplicate authority entries | invalid | Correct duplicate rejection |
| Local retention blocked; provider transmission blocked; policy identity drift | blocked | Axes and identity are not conflated |
| Missing authority | missing | Correct fail-closed behavior |
| Missing v29 current projection | blocked, with no runtime side effects | Correct projection boundary |
| No source-owned registry | absent; no provider authority invented | Product authority remains unresolved |

## Acceptance findings

1. The resolver proves canonical parsing, structural SHA comparison, identity,
   status, date, route, posture and rights consistency. It does not prove that
   the SHA pin came from an independently authenticated source-owned authority.
   Since both record and pin are ordinary caller inputs, a coherent forged record
   is accepted as `verified`. This is the decisive product-authority failure.

2. `ProviderPolicyRecord.authority_content_sha256` is stored but never compared
   with the observed canonical-byte hash. A self-consistent external pin can
   therefore validate a record whose authority-content field is false.

3. `provider_policy_authority` defaults to `None` in
   `preflight_governed_rights`; validation runs only when the caller supplies it.
   The inspected target has no live external provider boundary: Factory lowering
   hard-codes the fake provider and the resolver cannot authorize a send. However,
   any future/provider-capable consumer of the lowered plan would not receive a
   mandatory source-authority gate from this API. This is a boundary-design risk,
   not evidence that a real send occurred.

4. The worker’s direct-child `git diff --check` is not clean: it reports trailing
   whitespace in the new worker report and a new blank line at EOF in the new test.
   The worker report’s claim that only a pre-existing report finding remained is
   therefore not reconciled.

## Worktree and safety reconciliation

Before this acceptance report, the worktree had 14 tracked dirty paths and 342
untracked paths. The tracked dirty paths were pre-existing documentation,
reports, factory/integration/runtime/source-rights code and tests; none is one of
the four direct-child target paths. Pre-report path fingerprint (tracked dirty
plus untracked names excluding this report):
`47385296a177820d2d204504d62402dd2f9a2b560cd2c59ef4daadaa01a46b4c`.

No source was acquired, no external source or Drive was accessed, and no provider,
model, credential, budget reservation, spend, publication, GitHub mutation,
watcher/bridge state or gate state was touched. No code, Git metadata, runtime
state or pre-existing dirty path was edited. Only this report is being added.

## Smallest next safe work

Keep the structural resolver as a provider-free diagnostic, but block product
acceptance until Data/Builder provide a durable source-owned provider-contract
authority binding (or an independently authenticated equivalent), require the
record’s authority-content hash to equal the canonical bytes, and make the
validated authority a mandatory precondition at every real provider boundary.
Add focused regressions for caller-created self-pins and authority-content-hash
mismatch, then rerun the clean exact-target suite. No provider call or budget
reservation is required for that repair.
