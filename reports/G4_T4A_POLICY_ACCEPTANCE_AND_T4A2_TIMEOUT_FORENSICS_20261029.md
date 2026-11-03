# G4 T4A policy assessment and dual-timeout forensics

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Observed HEAD: `3c5cd6280e9011400399dce0153fd1dbe8180d57`  
Result: **no real send is allowed; Gate 4 remains active.** This is not Gate 4 acceptance or closure.

## Scope and authority

I read the local `AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the local North-Star projection-lens reality slice, the current T4A report, the T3/T2 rights and factory reports, the exact local code/tests, Git state, and bridge/runtime telemetry. The local North-Star file is a v0.1 projection-lens record; the repository points to the sibling Data repository's v0.3 authority, but this task prohibited external access, so I do not claim an independent remote-v0.3 read.

No source acquisition, provider/model call, spend, watcher/bridge/process management, publication, GitHub mutation, staging, deletion, replay, or resume was performed. This report is the only file written by this worker.

## 1. Independent T4A policy assessment

### Code, test, commit and diff identity

HEAD is exactly the instructed `3c5cd6280e9011400399dce0153fd1dbe8180d57`, commit `bridge: commit gate4:engineering:20261029-g4-t4a-provider-processing-policy-authority-v1`. Its commit diff added 3 files / 881 lines: the policy module, its focused tests, and the prior T4A report. The policy module and focused test have no current worktree diff. The current worktree nevertheless has substantial pre-existing dirty/untracked state; `src/charitygraph/source_rights.py` is modified, and the four timeout files below are untracked and out of bounds.

Relevant current-file identities (SHA-256; bytes; AST result) are:

| Path | Bytes | SHA-256 | AST |
|---|---:|---|---|
| `src/charitygraph/phase5_provider_processing_policy.py` | 25256 | `0c6ae732486f1d597f69d219cabd35312f46aba537905b73ce4df673e3be5b92` | OK |
| `tests/test_phase5_provider_processing_policy.py` | 9901 | `107324f7ff80d6e10ef763e48fb79143abbc09a297ce7176c4f9467c31f2fa75` | OK |
| `src/charitygraph/source_rights.py` | 18514 | `72f0cc0b3fb1f1ad0f3bb92700e6fe26bc85a9a97510a261e4ae285e66da79bc` | OK |
| `src/charitygraph/runtime/rights_governance_record.py` | 39520 | `73e0a51c721ce9281e319cc422e2dfc4fe1f8128f4ff63a6811518fd373d2819` | OK |

The AST result came from a read-only `python -B` parse loop. No pytest run was attempted by this worker: even focused pytest can create cache/temp state, and the instruction permits only this report as a repository write.

### What the policy does establish

`phase5_provider_processing_policy.py:40-49` aliases the source-owned OpenAI identity `OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1`, assigns local policy version `1.0.0`, limits routine source admission to the seven Source Universe v1 families, and narrows the T4A pilot to `acnc_register` and `acnc_ais_bundle`. `:56-87` requires non-secret provider metadata, `openai`, ordinary retention, the no-training default, and disabled data-sharing opt-in. `:102-163` requires Product Owner dated approval, policy provenance, exact source-family lists, an allowlisted operation set, `public_redistribution_allowed=False`, and a revalidation rule.

The provider configuration shape records provider, project, service, endpoint, model, delivery mode, reasoning effort and retention posture. The focused test fixture (`tests/...:32-46`) uses provider `openai`, project `proj_vnAuU8uxocL0Rosg3SulgmRI`, service `responses_api`, endpoint `https://api.openai.com/v1/responses`, model `gpt-5.6-luna`, standard delivery, low reasoning, ordinary retention, no-training true and data-sharing false. These are test/caller metadata, not proof of a currently configured live contract; the policy module deliberately supplies no guessed project, service or model default.

`ProviderProcessingDecision` (`:180-244`) binds the decision to the v29 rights-record hash, subject, scope, source family, source artifact/record, exact representation artifact/hash, rights policy identity/version, provider policy identity/version and provider-binding hash. `revalidate_provider_processing` (`:365-418`) fails closed on policy, provider, rights, subject/scope, source, representation, operation, policy-content, provider-binding or retained-byte drift. The existing T1B/v29 rights authority remains separate: `runtime/rights_governance_record.py:117-147` models independent local-retention, provider-transmission and public-redistribution axes; `:334-353` explicitly fails closed when the source-owned provider-policy version registry is absent or mismatched. Public redistribution cannot substitute for private provider-processing authority (`phase5_provider_processing_policy.py:352-355`).

### Acceptance limits and unresolved contract identity

The source-owned `source_rights.py:27` exposes the OpenAI policy identifier, and its worktree diff adds versioned rights-record fields, but there is still no `PROVIDER_POLICY_REGISTRY` containing an exact source-owned provider-policy version. The local T4A module's `1.0.0` is therefore a versioned local authority record based on the dated Product Owner approval, not independently demonstrated source-owned OpenAI contract identity. The exact live project, service, model, endpoint binding, credential/project authority and provider-contract version remain unresolved. The prior T4A report itself records this gap as `provider_contract_identity_and_version` and was authored at an earlier HEAD (`15d28d56...`), so it is evidence, not acceptance.

The policy is consequently acceptable only as a bounded, content-addressed, provider-free preflight contract: it can describe and reject a hypothetical operation. It does not authorize transmission. A real send would require an explicit, independently authoritative provider contract/configuration identity and version, exact policy/version revalidation, current v29 rights, exact subject/scope/source/representation bindings, and the immediate pre-send checks. No real send was permitted or attempted here.

Worker-reported results in `reports/G4_T4A_PROVIDER_PROCESSING_POLICY_AUTHORITY_20261029.md` were 13/17/40 passing and zero spend/calls. I did not independently verify those counts. The 9 focused policy test functions parse successfully, but no new pytest result is claimed.

## 2. T4A2 900-second timeout forensics

The immutable local instruction is `gate4:engineering:20261029-g4-t4a-real-pilot-route-budget-preflight-v1` (inbox SHA-256 `beb1776813396c4e51b9a785311d0aaca504fd7b61552763b54f3f711ff85ec3`). Its result JSON SHA-256 is `f6129bdce5551c96a351cb9608f733d4fb51c4ba399e4dcfb8fd296783640173`; captured output JSONL SHA-256 is `6ad70254736937ad97345c00eef7c62a97ea06f3957b50f36e12572ffb7900b5`.

- Declared timeout: 900 seconds; exact telemetry interval `2026-10-29T03:27:53.664406+00:00` to `2026-10-29T03:42:54.268310+00:00`; terminal state `CODEX_EXECUTION_TIMEOUT`, return code 1.
- Telemetry saw 141 events, 62 command starts and 60 completed commands, with 6 completed file-change events. The last completed focused command failed; captured output includes repeated reproducibility/source-integrity failures and a later `2 failed, 50 passed` run. There was no final worker message.
- Result attestation records no report, no commit, unchanged target HEAD, `provider_calls=0`, `source_acquisition=false`, `publication=false`, and `semantic_product_work=NOT_PERFORMED`.
- The execution directory contains only `codex-output.jsonl`; the result JSON contains no heartbeat token or separate heartbeat artifact. Before/after workspace attestation keeps branch `gate3-cg406-remediation` and HEAD `3c5cd628...` unchanged.

The two instructed files remain byte-for-byte preserved and untracked:

| Path | Bytes | SHA-256 | AST |
|---|---:|---|---|
| `src/charitygraph/phase5_t4a_real_pilot_preflight.py` | 28737 | `ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4` | OK |
| `tests/test_phase5_t4a_real_pilot_preflight.py` | 7635 | `b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2` | OK |

Direct root-cause evidence is limited to the hard deadline, repeated failed/repeated focused commands, and absence of a final message. It supports “the bounded run did not converge before its deadline.” It does not prove a deadlock, provider wait, bridge fault, or one particular model behaviour. Those are conjectures.

## 3. T4A2A separate 600-second timeout

The separate instruction is `gate4:engineering:20261029-g4-t4a2a-real-pilot-packet-timeout-recovery-v1` (inbox SHA-256 `7b536f4432b1f6a7b535ca5d92769205ad045862cd10c06e4d1bd6cab18863a9`). Its result JSON SHA-256 is `e8491af24b0e4695e772403b74c3a0ea2275bcba16382fbe39ce53ebeeb8b9e5`, and captured output JSONL SHA-256 is `7a9686460339911c33951c271a6cd42b0203c7c448b40f828a2a9181722eabee`.

- Declared timeout: 600 seconds; exact telemetry interval `2026-10-29T06:06:50.373921+00:00` to `2026-10-29T06:16:50.785294+00:00`; terminal state `CODEX_EXECUTION_TIMEOUT`, return code 1.
- Telemetry saw 155 events, 60 command starts and 59 completed commands, with 12 completed file-change events. The last event was a started, not completed, pytest command. The captured final focused run reports all six packet tests failed at `phase5_t4a_pilot_packet.py:317` while resolving a semantic contract: `ValueError: schema-version binding mismatch` from `phase5_semantic_contracts.py:459`.
- Result attestation records no report, no commit, unchanged target HEAD, `provider_calls=0`, `source_acquisition=false`, `publication=false`, and `semantic_product_work=NOT_PERFORMED`.
- The execution directory contains only `codex-output.jsonl`; the result JSON contains no heartbeat token or separate heartbeat artifact. Before/after workspace attestation keeps branch `gate3-cg406-remediation` and HEAD `3c5cd628...` unchanged.

The additional two files remain byte-for-byte preserved and untracked:

| Path | Bytes | SHA-256 | AST |
|---|---:|---|---|
| `src/charitygraph/phase5_t4a_pilot_packet.py` | 23898 | `ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46` | OK |
| `tests/test_phase5_t4a_pilot_packet.py` | 5294 | `e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08` | OK |

The direct evidence is stronger than for T4A2 about the final failing test seam and iterative edit/test activity, but it still does not establish why the process consumed the full wall-clock budget. The supported classification is a distinct timed-out implementation attempt with an unresolved test failure, not a successful recovery and not a reason to adopt its files.

## 4. One un-dispatched successor proposal

If Product Owner authority later requests one successor, make it a fresh provider-free contract-identity diagnostic, not a replay or repair of either packet/preflight. Maximum wall time: 600 seconds.

Allowed paths only:

- `src/charitygraph/phase5_t4a_provider_contract_identity_probe.py`
- `tests/test_phase5_t4a_provider_contract_identity_probe.py`
- `reports/G4_T4A_PROVIDER_CONTRACT_IDENTITY_PROBE_20261029.md`

The small deliverable would accept only explicit, non-secret provider metadata plus the existing source-owned policy identifier/version inputs, emit a typed fail-closed diagnostic when the exact source-owned contract/version is absent or mismatched, and never import a transport, read source bodies, construct a packet, reserve budget, or call a provider. Acceptance tests: deterministic hash/replay; missing contract; mismatched provider/project/service/model/endpoint; policy-version mismatch; and zero provider/cost/filesystem side effects. Stop immediately after the focused tests and report, or at the first missing authoritative contract seam. Do not dispatch this proposal from this report.

Private reports, runtime state, prompts, model responses and caches were not copied into Git. No Gate 4 acceptance or closure is claimed.
