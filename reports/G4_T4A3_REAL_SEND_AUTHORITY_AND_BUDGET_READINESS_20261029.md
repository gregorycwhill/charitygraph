# G4 T4A3 real-send authority and budget readiness

Date: 2026-10-29 (Australia/Sydney)  
Target: `1d23ff731f768414c3936494727c92a450167907`  
Fence: `v52`  
Disposition: **NOT READY for one real provider request.** The accepted one-subject/two-source packet is ready only as a provider-free, private offline packet.

## Authority grounding

The Builder instructions, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, Data
authority/current state/plans, North Star `north-star-v0.3`, source/publication
governance, and the T2/T3/T4A evidence were read. Data HEAD is
`f5f154cf2e3f107a9a2563c94626a0e39419fd3e`.

Relevant authority hashes: Data `DOCUMENT_AUTHORITY.md`
`693af004b54cd0b23f5a02e7c2f9da1d93a01655045c073ff2e8e4e04f6fcf08`;
Data `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`
`59a31bb01900d801cb762ad351bb58d00979c14532a9bfbceb25bd8e0260c627`;
Data `NORTH_STAR_TARGET_CARD_V0_3.md`
`1c19d0a3b0b08579e0b1d7da46081f4558aa93a89cc1d0e80d530d2c7c00f090`.
Data authority makes source/evidence governance authoritative
(`DOCUMENT_AUTHORITY.md:66-69`), and the active North Star is explicitly
`north-star-v0.3` and not a public schema (`DOCUMENT_AUTHORITY.md:87-93`,
`NORTH_STAR_TARGET_CARD_V0_3.md:1-12`).

## Readiness matrix

| Check | Result | Evidence and exact meaning |
|---|---|---|
| One-subject/two-source offline packet | **VERIFIED** | Accepted packet report SHA-256 `12a85219fcbe3de6bfac28f664b1a0a4e9510a4efb6297ef7e43bbbbc5059bfe`; packet identity `92354b66502c7643b98532db96c1f2c42d6c85b1270295e70acd27e57f34ae73`; retained ACNC register/AIS source and representation hashes are listed in `reports/G4_T4A2B_SINGLE_SUBJECT_OFFLINE_PACKET_20261029.md:10-26,50-55`. The packet records no source bodies and no semantic output. |
| Exact T3 manifest / subject, scope, source and representation binding | **VERIFIED** | Selected manifest SHA `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`, emitted identity `e5209bc535d2cc9bc8f9108fa40878ca4d79ad2a7644afbd757282d5e0047640`, and the two exact rows are retained in `reports/G4_T4A2B_SINGLE_SUBJECT_OFFLINE_PACKET_20261029.md:10-26`. |
| Local rights and v29 governance | **VERIFIED for private local processing** | Packet binds rights policy `CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1/1.0.0`, rights-record schema `1.0`, and v29 projection (`reports/G4_T4A2B_SINGLE_SUBJECT_OFFLINE_PACKET_20261029.md:28-35`). Data keeps local retention, provider transmission and public redistribution separate (`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md:115-129`). |
| Source universe / source-policy status | **NOT APPLICABLE as a blocker** | The packet uses admitted ACNC families only. User-approved ACNC use is not the missing authority; provider transmission and publication remain separate controls. |
| Source-owned provider-policy registry/version | **MISSING** | Builder has only `OPENAI_PROVIDER_POLICY_ID` and a rights `RIGHTS_POLICY_REGISTRY` (`src/charitygraph/source_rights.py:27-45`); it has no `PROVIDER_POLICY_REGISTRY`. The clean runtime explicitly fails closed when that registry is absent (`src/charitygraph/runtime/rights_governance_record.py:321-350`). This is confirmed by the accepted probe review (`reports/G4_T4A_PROVIDER_CONTRACT_IDENTITY_PROBE_INDEPENDENT_ACCEPTANCE_20261029.md:55-60`). |
| Source-owned provider contract identity/version and independently verifiable authority | **MISSING** | `SourceOwnedProviderContract` is an input assertion, not a registry or verifier (`src/charitygraph/phase5_t4a_provider_contract_identity_probe.py:51-82,137-142`). Missing contract identity/version is a deliberate blocked result (`:194-215`); even an internally consistent comparison is not authorization (`reports/G4_T4A_PROVIDER_CONTRACT_IDENTITY_PROBE_INDEPENDENT_ACCEPTANCE_20261029.md:46-53,83-97`). |
| Exact project/service/endpoint/model binding | **MISSING factual attestation** | The dirty no-send preflight has non-authoritative route defaults of model `gpt-5.6-luna`, endpoint `/v1/responses`, service `responses_api` (`src/charitygraph/phase5_t4a_real_pilot_preflight.py:42-48`). Its caller-supplied contract is optional in the no-send planner and `send_ready` is hard-coded false (`:408-425,474-544`). No current source-owned project binding or fresh non-secret route attestation is present. Do not promote these defaults. |
| Current packet committed spend / outstanding reservations | **VERIFIED: AUD 0.00 / 0** | Accepted packet records zero provider calls, transport requests, reservations, costs and publications (`reports/G4_T4A2B_OFFLINE_PACKET_INDEPENDENT_ACCEPTANCE_20261029.md:49-53`; source `src/charitygraph/phase5_t4a_single_subject_offline_packet.py:241-245`). This is packet-local, not a project-wide cumulative ledger. |
| Project-wide cumulative AUD10 position | **MISSING factual ledger attestation** | The governing plan requires the AUD10 cap to include extraction, judgement, writing, embeddings, retries and escalation, with actuals and unused reserve reconciled (`reports/G4_T2_T3_T4_SUPERVISORY_PLAN_20261028.md:207-213`). No current authoritative cumulative ledger and outstanding-reservation snapshot is bound to this packet. Historical CG406/development ledgers and synthetic T2 reservations are not transferable authority. |
| Current price snapshot, FX and maximum per-request bound | **MISSING factual authority** | The dirty preflight carries `openai-model-pages-2026-09-07`, FX `1.52`, programme cap AUD10 and preferred pilot ceiling AUD4 as inputs/defaults (`src/charitygraph/phase5_t4a_real_pilot_preflight.py:416-420,511-520`), but no current authority-bound pricing/FX snapshot or hard one-request maximum is supplied. The pricing loader requires a source-hashed governed snapshot (`src/charitygraph/s0_pricing.py:105-150`). |
| Reservation, actual-cost and release machinery | **VERIFIED as reusable machinery; MISSING as a pilot-bound record** | Clean catalogue supports reservation position, append-only actuals, pricing/FX identities and requires a canonical reservation before actual settlement (`src/charitygraph/runtime/catalog.py:1725-1778,2607-2716`). Data policy requires reserve-before-paid-task and reconciliation (`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md:71-83`). No reservation was made here. |
| Transport identity, idempotency and ambiguity reconciliation | **VERIFIED as reusable machinery; MISSING as a pilot-bound ticket** | Standard transport derives a physical-attempt client ID and persists send-start/ambiguous/response states without automatic resend (`src/charitygraph/phase5_standard_transport.py:283-289,361-453`; Data transport policy `docs/operations/openai-standard-transport-reconciliation.md:7-17`). This packet has no physical attempt, request ticket, provider receipt or response reconciliation. |
| Explicit no-publication boundary | **VERIFIED; public redistribution is NOT APPLICABLE to this private pilot** | Packet records `public_redistribution: not_assessed`, zero publications and `send_authorization: not_authorized_for_send` (`reports/G4_T4A2B_OFFLINE_PACKET_INDEPENDENT_ACCEPTANCE_20261029.md:49-53`). No publication or release action is implied. |

## Smallest truthful next implementation

Implement **one provider-free, source-owned provider contract/version registry
resolver and fail-closed authority check** in the clean rights path. It must
consume an authority-supplied entry containing only non-secret metadata:
contract ID/version, provider-policy ID/version, authority locator and content
hash, current/effective status, selected service/no-sharing posture and renewal
rule. It must verify the entry's content hash, compare the caller-supplied
project/service/endpoint/model binding exactly, and reject missing, stale,
revoked, mismatched or unverified entries before task/request construction.
It must not invent provider configuration, read credentials, create a
reservation, call a provider, or authorize publication. Focused replay tests
should prove zero side effects on every blocked path.

The implementation is bounded, but supplying the exact registry values,
effective evidence and renewal/no-sharing decision is a new Product Owner/Data
authority decision. The absent project/config attestation, current pricing/FX
capture and cumulative ledger snapshot are factual inputs to obtain under that
authority; they are not permission to guess defaults. Until both authority and
those factual attestations are present, the truthful state remains
`provider-free accepted / send readiness unresolved`.

No provider, network, credential, source acquisition, budget reservation,
model call, test run, publication, release, watcher, Drive/GitHub operation or
existing dirty-file modification occurred. Only this report was written.
