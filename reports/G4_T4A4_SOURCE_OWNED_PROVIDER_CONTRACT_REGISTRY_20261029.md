# G4 T4A4 source-owned provider-contract registry resolver — independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Scope: resolver only; no Gate 4 or real-send acceptance  
Disposition: **PARTIAL**

## Identity and authority basis

Reviewed exact local HEAD `d0551d348f02dbaed24cf1f37430e8b092a66578`,
parent `1d23ff731f768414c3936494727c92a450167907`, fence `v53`, and tree
`f28c5a1916430a304151230cc64403d2c8421da9`. The HEAD is a direct-child
three-file commit: the resolver, its focused test, and this report.

SHA-256 of the three target bytes before this report was replaced:

| Target-commit path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_provider_contract_registry.py` | `e6b9b5feb6d0e643353b29409fe8899918c8ff9f88c98a2aec6a535f5b0760cb` |
| `tests/test_phase5_t4a_provider_contract_registry.py` | `0594733a085cdeda5cf9a02c655df3432f80455e436433c46cb937c3f1fc5338` |
| prior committed report bytes | `26446f05b6b64bbd74f6326d8d204f8bc2f8d18c3f12ed08b053a0792e943313` |

The local Data authority read was at HEAD
`f5f154cf2e3f107a9a2563c94626a0e39419fd3e`; the relevant local hashes were
`DOCUMENT_AUTHORITY.md` `693af004b54cd0b23f5a02e7c2f9da1d93a01655045c073ff2e8e4e04f6fcf08`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`
`59a31bb01900d801cb762ad351bb58d00979c14532a9bfbceb25bd8e0260c627`,
`NORTH_STAR_TARGET_CARD_V0_3.md` `1c19d0a3b0b08579e0b1d7da46081f4558aa93a89cc1d0e80d530d2c7c00f090`, and
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`
`891cd0f869b7882f078669d22ac8e4ae5fdf53712721b5230fba29ca279d4463`.
They keep source authority, provider handling, rights, cost and publication
as separate governed dimensions; silence or a locator is not authority.

## Acceptance findings

- **Verified:** canonical JSON is parsed and non-canonical bytes fail closed.
  The trusted SHA-256 is a separate input; the entry’s
  `authority_content_sha256` is not used as that pin (`_load_authority`,
  lines 157–208). Missing, invalid, unpinned, changed, stale and revoked
  authority produce typed diagnostic blockers.
- **Verified:** policy ID/version, provider, project, service, endpoint,
  model, retention, no-training and no-sharing drift fail closed. Focused
  tests cover those fields (tests lines 104–176). A successful diagnostic has
  `request_ticket: None` and `send_authorization: not_authorized_for_send`
  (resolver lines 92–106); no credential, transport, price, FX, reservation,
  cost ledger or publication authority is created.
- **Verified with boundary:** rights are consulted read-only when supplied;
  they cannot be promoted by this resolver. Clean runtime rights validation
  still fails closed because clean `source_rights.py` has no exact
  `PROVIDER_POLICY_REGISTRY` mapping. The current dirty `source_rights.py`
  remained pre-existing and was not used as acceptance authority.
- **Gap:** there is no caller-supplied expected contract ID/version and no
  contract identity comparison. The resolver can pin and report the entry’s
  contract fields, but cannot diagnose a caller contract-ID/version mismatch.
- **Gap:** `ProviderContractRegistryEntry.schema_id` is typed as `str`, not the
  exact registry schema literal; a pinned entry carrying a wrong schema value
  is not rejected as a schema mismatch.
- **Evidence gap:** no real source-owned provider contract/version, independent
  authority pin, exact provider-policy version registry, current route
  attestation, price/FX authority or cumulative AUD10 ledger was found
  locally. The fixture locator is not live authority. T4A3 and the prior probe
  acceptance remain controlling evidence of those missing inputs.

## Independent test and preservation

Exactly one focused invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4-independent-acceptance-20261029-r3 -ra`

Result: **16 passed, 0 failed** in 0.86s. The resolver’s side-effect test
observed no socket or file-open calls; only pytest’s external runtime basetemp
was used. No provider/model/network/source/credential/cost operation occurred.

The pre-existing dirty baseline was not absorbed. The four protected T4A2/
T4A2A files remained byte-for-byte unchanged: `ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4`,
`b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2`,
`ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46`, and
`e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08`.
No private evidence, cache, bytecode, runtime state, provider output or other
repository path was changed; this report is the sole intended repository
change.

## Factual gaps and next decision

The next factual inputs are an independently verifiable source-owned registry
artifact with exact schema, contract/policy identity and version, route and
posture, status/renewal evidence and independent pin, plus current pricing/FX
and cumulative-ledger attestations. The genuine Product Owner/Data decision is
whether to establish that authority and separately authorize a bounded real-send
packet. This resolver does not supply either authority or send readiness.
