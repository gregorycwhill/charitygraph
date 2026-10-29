# G4 T4A4b expected contract/schema binding

Date: 2026-10-29 (Australia/Sydney)  
Target: `gate3-cg406-remediation` at `d0551d348f02dbaed24cf1f37430e8b092a66578`  
Fence: `v53`  
Disposition: **provider-free patch verified; live-send readiness unchanged**

## Bounded patch

- The resolver now accepts explicit `expected_contract_id` and
  `expected_contract_version` inputs, records them in the diagnostic, and
  fails closed with typed missing/mismatch reasons on exact comparison.
- `ProviderContractRegistryEntry.schema_id` and the diagnostic schema use the
  one named `PROVIDER_CONTRACT_REGISTRY_SCHEMA` literal. Unknown or wrong
  schema versions fail closed with `authority_registry_schema_invalid`.
- Canonical fixtures use that named constant. Existing independent SHA pin,
  canonical-byte, policy/route/retention/no-sharing drift, and `NON_SEND`
  behaviour remain unchanged. The only positive result remains
  `IDENTITY_EVIDENCE_VERIFIED_NON_SEND`, with no request ticket and
  `not_authorized_for_send`.

## Verification and scope

Command: `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4b-pytest-20261029 -ra`  
Result: **22 passed, 0 failed**. The side-effect test observed no socket or
file-open calls. No provider, model, network, credential, source, spend,
reservation, transport, publication or external action occurred.

The intended direct-child commit scope is exactly these three paths:

- `src/charitygraph/phase5_t4a_provider_contract_registry.py` — SHA-256
  `bdee1ce76a60a4c1cc05134ec0c9a55466433a49dbe2cbf74fd4333a2bd3ad18`
- `tests/test_phase5_t4a_provider_contract_registry.py` — SHA-256
  `a0db8f51c7399f749949057dc3bdf9d44a5c0ee5ce353e0b8176a7e8087d327a`
- `reports/G4_T4A4B_EXPECTED_CONTRACT_SCHEMA_BINDING_20261029.md` — this
  report

Pre-existing dirty report `reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md`
was not changed by this task. No private evidence, runtime state, cache,
bytecode, credentials or provider material was added.

The exact allowlisted `git add` attestation could not write
`.git/index.lock` because the repository index is ACL read-only in this
worker. No commit was made; the intended three-path scope above remains the
complete uncommitted task output.

## Remaining factual gaps

The patch does not create or infer a live source-owned provider contract or
policy authority. The exact source-owned contract/policy ID and version,
independent authority artifact and pin, effective status, renewal evidence,
route/project/service/endpoint/model attestation, price/FX snapshot and
reconciled cumulative AUD10 ledger/outstanding reservations remain absent.
The provider-free diagnostic therefore does not establish real-send
readiness, reservation authority, budget authority or permission to send.
