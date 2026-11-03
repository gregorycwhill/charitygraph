# G4 operator-health runtime export independent acceptance and second-ingress feasibility

Date: 2026-10-31 (Australia/Sydney)
Disposition: **PASS, bounded local runtime contract; PARTIAL/NOT VERIFIED for a second independently authenticated ingress.**

## Boundary and identity

Inspection was performed at exact HEAD `50a9bd1a9e6450a8cdc26a12acd4cef21f67964f`,
whose direct parent is `c9e349f17b28eab34fc6c57aad9082130d6456d7`. The immutable
v82 fence SHA supplied with the instruction was
`b21f8fad1beb77073b116cd05b84014374b9d67c3699b5dbd442046aa974639e`.
The v82 instruction was report-only and targeted this exact HEAD. Existing dirty
paths were preserved and were not used as acceptance evidence.

Authority consulted: repository `AGENTS.md`, `ARCHITECTURE.md`,
`BUILDER_MACHINERY.md`, the active Data `NORTH_STAR_TARGET_CARD_V0_3.md`,
`DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `BUILDER_TO_65K_PLAN.md`,
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md`, and
`TEST_PLAN.md`. The review applied their typed identity/provenance,
explicit-missingness, Python-control-plane, fail-closed cost, and no-discovery
boundaries.

The exact v81 direct-child commit contains only these three paths:

| Path | Committed blob SHA-1 | File SHA-256 |
|---|---|---|
| `src/charitygraph/phase5_operator_health_runtime_contract.py` | `adb9ad37f264c4e4dd5060b72633932a36647db8` | `a0d0a80f1353ae79de1ab2880684fa54b418a2e617fdbf51ddc7a403548f109c` |
| `tests/test_phase5_operator_health_runtime_contract.py` | `d6cccfef63e82acab39ea127ef3597c567dcf7ac` | `7ad52ea4529a7b1a90ffdd3af79b56c9f9341a15ad4323d671d65b50360b5c77` |
| `reports/G4_BUILDER_OPERATOR_HEALTH_RUNTIME_EXPORT_CONTRACT_20261031.md` | `7199e77cfe6a98abc0a8d72743620f5a6fba4690` | committed report path unchanged |

## Independent verification

Cache-free commands used `python -B`, `PYTHONDONTWRITEBYTECODE=1`,
`-p no:cacheprovider`, and fresh basetemp directories under
`C:\CharityGraph-runtime`:

```text
python -B -m pytest -p no:cacheprovider --basetemp <fresh> tests/test_phase5_operator_health_runtime_contract.py tests/test_phase5_operator_health.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_delivery.py tests/test_phase5_run_diagnostics.py tests/runtime/test_phase5_run_diagnostics_catalog.py tests/test_phase5_standard_transport.py tests/runtime/test_budget_ledger.py
```

**111 passed in 12.10s.** The new runtime-contract file independently passed
**6 passed in 1.26s**. The existing read-only host-readback contract independently
passed **21 passed in 2.56s**. No provider, Drive, source, credential, watcher,
launcher or GitHub action was invoked.

## Runtime contract acceptance

| Claim | Result | Evidence and boundary |
|---|---|---|
| Real persisted catalogue export equals a direct operator-health projection | **PASS, bounded** | `phase5_operator_health_runtime_contract.py:184-218`; test `:119-143`. Uses synthetic SQLite rows and the real read-only catalogue adapter. |
| Fixture and SQLite sidecars remain read-only | **PASS** | Test `:112-143` hashes the database, WAL and SHM before/after. |
| Canonical JSON is stable and SHA is reproducible | **PASS** | Test `:146-157`; canonical sorting/serialization and SHA are at source `:84-93`, `:230-247`. |
| Run/task/request/subject/scope/source/time identity is preserved | **PASS, bounded** | Source `:138-173` and tests `:125-127`; identity is checked against persisted rows and supplied as-of/reporting-window values. |
| Stalled, retry, failure and recovery indicators | **PASS, bounded** | Test `:128-132`; observer-derived flags are compared at source `:212-217`. |
| Missing, malformed and explicit-zero usage | **PASS** | Test `:161-179`; missing and invalid JSON remain distinct from observed `0/0`. |
| Duplicate, conflicting and unidentifiable receipts | **PASS, fail-closed** | Test `:181-220`; exact duplicates are counted once with an issue, conflicting identity is ambiguous, and missing receipt identity prevents cost totals. |
| Payload/reference exclusion | **PASS** | Test `:141-143`; forbidden key parts are rejected by source `:41-53`, `:96-105`, and safe persisted rows are constructed at `:108-136`. |
| Actual/reserved/forecast project cost missingness | **PASS, non-inferential** | Test `:133-137`; the persisted safe view intentionally lacks provider receipt identity, so all three amounts remain null/ambiguous rather than being fabricated. This does **not** establish project-wide completeness. |
| Pricing/FX provenance | **PASS when supplied; otherwise missing/ambiguous** | Test `:208-215`; source cost closure is `:175-181`. No pricing, FX, ledger or zero-cost value is invented. |
| Provider effects and live runtime wiring | **NOT ESTABLISHED** | The run was provider-free and the contract code has no provider transport. Synthetic tests cannot prove live route policy, provider-side exactly-once effects, or host wiring. |

The result is therefore **PASS** for the bounded persisted-runtime export
contract and **PARTIAL** as industrialisation evidence. It does not support Gate 4
closure. The requested Builder-to-65k state remains unchanged: Gate 1 `CLOSED`,
Gate 2 `ACTIVE`, 12% earned.

## Second-ingress feasibility

The local bridge contract was inspected read-only, including
`bridge/bridge.py`, `bridge/managed_launcher.py`, `bridge/SUPERVISOR_PROTOCOL.md`,
`bridge/README.md`, the bridge tests, and `bridge/g4_t4e_host_readback.py`.

| Candidate | Result | Finding |
|---|---|---|
| A. Native Google Doc/Sheet reconstructed by a host adapter | **NOT VERIFIED / not implementable by this worker** | The repository contains no Docs/Sheets API reader or native-document host adapter. The historical supervisory record says the native Doc readback was empty, its content write was rejected, and no host mirror existed. The worker is not authorised to inspect Drive sync or host credentials, so current host read capability is **NOT VERIFIED**. |
| B. Existing bridge-native/repo transport | **PASS locally; PARTIAL as a second independent channel** | The managed bridge reads only directly materialised `cg-g4-o1b-instruction-*.json` files, requires canonical UTF-8 bytes with one trailing LF, exact authority and target identity, and checks the local fence/branch/HEAD. `bridge.py:488-496, 574-583`; launcher `managed_launcher.py:51-78, 157-170`. This is the existing raw-file channel, not a second independently authenticated source, and the bridge cannot attest Drive delivery. |
| C. Exported conversation-file reference to Drive raw JSON | **NOT VERIFIED / not currently supported** | No local contract dereferences a conversation export or a native-file reference. The current watcher scans only the direct raw-file prefix. A reference must not be assumed safe merely because it is a `.gdoc` pointer or a Drive filename. |

The exact capability currently proven by code is local read access to an already
materialised raw-file folder. `bridge.py` explicitly describes Drive delivery as
atomic local writes only and asks the supervisor to compare Drive modified time
with local status. The dormant T4E readback is even narrower: it returns
`STRUCTURE_ONLY_UNAUTHENTICATED`, `action=NONE`, and no recovery/adoption grant;
its source docstring and `verify_host_readback` contract state that it performs
no writes, process starts, provider calls, bridge calls or watcher calls. Thus a
private native Doc/Sheet path and any host-owned conversation exporter remain
unverified from this worker's allowed boundary.

## Smallest safe recommended follow-up (not implemented here)

If Product Owner authority confirms that a second *logical* ingress over the
already authenticated raw-file folder is sufficient, the smallest bounded task
is a same-folder reference envelope: a canonical conversation-export reference
containing the sibling raw instruction filename, exact raw-byte SHA-256, exact
instruction/content identity, target branch/HEAD, and fence SHA. The bridge
would resolve only a regular sibling file, verify the complete byte hash and
canonical UTF-8/no-BOM/one-trailing-LF form, then pass the referenced bytes
through the existing single claim ledger. This creates no Docs/Sheets API,
credential, service, watcher or new transport. It is not cryptographic source
authentication; if independent authentication means a new trust root or signed
identity, this route is blocked pending that product decision.

Exact future allowlist:

- `bridge/bridge.py`
- `tests/test_bridge_cutover.py`
- one fresh `reports/G4_SECOND_INGRESS_REFERENCE_ACCEPTANCE_<date>.md`

Required acceptance tests include canonical UTF-8/no BOM/one trailing LF,
pretty/multiline/CRLF/malformed/duplicate-key rejection, reference tamper and
path-traversal rejection, exact content/byte/identity hash checks, exact
supervisor authority and branch/HEAD/fence checks, identical duplicate no-op,
conflicting duplicate rejection, one-claim semantics, and preservation of
staged/untracked dirty paths. A separate unattended host acceptance must then
author the reference through the existing authenticated host/Drive path,
observe materialisation, run the managed launcher without manual intervention,
and reconcile one immutable result. That host acceptance is not established by
this local report.

No code, bridge, Drive, provider, source, credential, watcher, runtime or Git
metadata was changed by this task other than this new report. No private raw
material, prompts, model responses, credentials, runtime state or cache was
added to Git.
