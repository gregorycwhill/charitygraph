# G4 T4A2B single-subject offline packet — 2026-10-29

## Result

Implemented one provider-free, internal-only packet constructor and focused
tests. The retained fixture is available and the final direct smoke produced a
ready packet for one governed ACNC subject with exactly two retained records.
The packet is not a provider request, does not authorize sending, and was not
published. Gate 4 remains open.

## Exact retained inputs

- Subject: `subject:02649cdcb42049bb8dedd30f2333e150`
- Scope: `scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248`
- T3 selected manifest SHA-256: `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`
- Emitted T3 manifest identity for fence `v51`: `e5209bc535d2cc9bc8f9108fa40878ca4d79ad2a7644afbd757282d5e0047640`
- Source provenance: epoch `v45`, producer revision `61dd0cd1a89ed22118fc81bab89611eb1ddb2428`

| Role | Source record | Acquisition receipt | Source / representation SHA-256 | Rights record |
|---|---|---|---|---|
| `acnc_register` / `register_identity` | `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d` | `acq:0b099288968c5ac89fc4bff0811f021787281fb38737565221c506123098b63e` | `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` | `af9088b4615a92bd76686529159ea6d0187f43ec88891cf5327410fc3cc83a41` |
| `acnc_ais_bundle` / `annual_information_statement` | `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a` | `acq:e094f723f29b2d0394805ee00d0c1f5cdce483d96c2dee14ca7ea4c1da69eac4` | `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` | `7a15a57c3e58ba0c908db6d4ee1c577540aa8440d199eb6d0fdd058eff3c4ad8` |

Representation artifact IDs remained distinct (`artifact:<hash>` from
`srcblob:<hash>`), with matching content hashes and preserved acquisition
lineage. No source body was included in the packet or report.

## Contract bindings

- T3 manifest: `charitygraph.gate4.t3.selected-binding-manifest/v2`.
- Factory plan: `charitygraph.gate4.t3.real-evidence-factory-plan/v1`.
- Representation: `urn:charitygraph:builder:schema:acnc-source-native-representation:1.0`, version `1.0`.
- Rights record: `urn:charitygraph:builder:schema:rights-governance-record`, version `1.0`; rebuildable rights projection migration `v29`.
- Rights policy: `CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` / `1.0.0`.
- Current semantic contract resolved from the registry: contract `1.2`, task profile version `2`, schema `urn:charitygraph:builder:schema:direct-service-wire-output:1.2` / `1.2-section-discriminated`, planner schema `urn:charitygraph:phase5:planned:direct_service_semantics:v2`, prompt policy `direct-service-access-v1:prompt-policy:v3-representation`.

The prior schema-version issue was resolved by binding `resolve_contract` to the
registry's current direct-service entry and its declared planner schema/prompt
policy values, rather than carrying a stale literal. Wrong-version resolution
remains a typed `schema_version_mismatch` diagnostic.

Provider processing records policy
`OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1` / `1.0.0`, but
the source-owned provider contract is unbound. The packet therefore records
`send_authorization: not_authorized_for_send`, zero provider calls, zero
transport requests, zero reservations/cost entries, and zero publications.
Public redistribution remains `not_assessed`; semantic output is
`not_attempted`.

## Verification and hashes

- Static AST parse: passed; production `250` lines, focused test `91` lines.
- Final direct offline smoke: passed; packet SHA-256
  `92354b66502c7643b98532db96c1f2c42d6c85b1270295e70acd27e57f34ae73`, two
  records, factory state `provider_contract_blocked`.
- Focused pytest was capped at two invocations as instructed. The first
  invocation exposed an unsupported new ID prefix (5 failed). After that fix,
  the second invocation recorded 4 passed and 1 failure because the expected
  provider-only blocked status was not yet classified as offline-ready. The
  final narrow correction was verified by the direct smoke; no third pytest
  invocation was run.

Exact new-file SHA-256:

- `src/charitygraph/phase5_t4a_single_subject_offline_packet.py` — `2bfe994fb7f04916eed4a97863761916e8bf32ffa2b2f4eb2e3af2893d3b53b3`.
- `tests/test_phase5_t4a_single_subject_offline_packet.py` — `d25c28fff11e307df13c565fbdcb79271990ce02e31832aa70dd1c15d34feae2`.

All pre-existing dirty and untracked paths were preserved. No provider/model,
network, credential, Drive, GitHub, source acquisition, staging, commit,
publication, release, merge, watcher or gate operation was performed.
