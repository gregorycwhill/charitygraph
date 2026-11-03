# G4 T4A4b independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free, report-only  
Branch: `gate3-cg406-remediation`  
HEAD: `5edcb38c6b101284782f2e5edcb146f32f972314`  
Fence: `v54`

## Disposition

**Technical acceptance: ACCEPT** for the committed provider-free expected
contract/schema binding patch. **Product acceptance: ACCEPT** for this narrow
diagnostic boundary, with real-send readiness still **NOT READY**. Gate 4 is
not closed.

## Commit and dirty-boundary verification

HEAD is a single-parent, non-merge direct child of
`d0551d348f02dbaed24cf1f37430e8b092a66578`. The exact committed paths are:

- `src/charitygraph/phase5_t4a_provider_contract_registry.py` — worktree
  SHA-256 `bdee1ce76a60a4c1cc05134ec0c9a55466433a49dbe2cbf74fd4333a2bd3ad18`
- `tests/test_phase5_t4a_provider_contract_registry.py` — worktree SHA-256
  `a0db8f51c7399f749949057dc3bdf9d44a5c0ee5ce353e0b8176a7e8087d327a`
- `reports/G4_T4A4B_EXPECTED_CONTRACT_SCHEMA_BINDING_20261029.md` — worktree
  SHA-256 `db0b629cc4755c01ff2f39ea51d42c2d6119163ddaf5e7742768670f57db742e`

The commit changes exactly those three paths; its parent tree is
`f28c5a1916430a304151230cc64403d2c8421da9` and its tree is
`36e9b3fb462d49da43b006493e4213cae2deec1c`. The pre-existing dirty source-
owned report remained unchanged at SHA-256
`2d37cc25b980d1242465b10a86066987b1d45fbd5b2a982c17d3b74e6d4f19b8`.
The four pre-existing untracked T4A2/T4A2A source/test files were preserved;
no existing dirty file was absorbed into this report.

## Independent technical assessment

- Caller `expected_contract_id` and `expected_contract_version` are recorded
  and compared exactly. Missing or mismatched values return `NOT_VERIFIED`
  with typed fail-closed reasons.
- `PROVIDER_CONTRACT_REGISTRY_SCHEMA` is the exact named schema literal for
  both entry and diagnostic. Wrong and unknown schema versions return
  `authority_registry_schema_invalid`.
- Canonical JSON bytes replay deterministically. The independently supplied
  trusted SHA-256 pin is checked against observed canonical bytes; the entry's
  self-attested `authority_content_sha256` is not trusted as that pin.
- Provider-policy ID/version and exact provider, project, service, endpoint,
  model, retention, no-training and no-sharing drift are rejected. Source
  rights are supplied and checked as a separate authority; they are not
  promoted into provider-contract authority.
- The diagnostic has no request ticket and fixes
  `send_authorization: not_authorized_for_send`. The only positive result is
  `IDENTITY_EVIDENCE_VERIFIED_NON_SEND`.

One evidence limitation remains: the focused tests directly exercise route,
policy, retention and no-sharing drift, while no-training drift is verified by
the resolver comparison and field inspection rather than a dedicated test
case. This does not change acceptance of the bounded patch.

## Focused verification

Exactly one permitted invocation was run:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4b-independent-acceptance-20261029 -ra`

Result: **22 passed, 0 failed** in 0.98s. The side-effect test observed no
socket or file-open calls. No provider/model/network/credential access,
source acquisition, spend, reservation, request, publication or external
mutation occurred. No code or existing report was changed.

## Readiness boundary

This patch does not establish a live source-owned contract or policy authority,
current route/project attestation, credential control, price/FX snapshot,
renewal evidence, or reconciled project-wide cumulative AUD10 ledger and
outstanding reservations. Source rights remain independently governed. The
result is therefore a technical/product acceptance of the provider-free
diagnostic only, not real-send authorization or Gate 4 closure.

If a next task is approved, keep it provider-free and narrow: reconcile the
project-wide cumulative AUD10 budget ledger or the current price/FX/route
authority from its governing evidence. No such task is created here.
