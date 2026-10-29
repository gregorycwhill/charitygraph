# G4 T4A4 source-owned provider-contract registry resolver

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
Branch: `gate3-cg406-remediation`  
Reviewed HEAD: `1d23ff731f768414c3936494727c92a450167907`  
Fence: `v52`

## Result

Implemented only the requested provider-free resolver, focused tests and this
report. The resolver consumes either exact canonical registry bytes or a
separately supplied typed entry, and requires an independently supplied
SHA-256 pin. The entry's own authority content hash is not accepted as that
pin. It compares contract and provider-policy identity/version, provider,
project, service, endpoint, model, retention and no-sharing posture exactly.
Missing, invalid, non-canonical, unpinned, changed, stale, revoked and
mismatched authority fails closed with typed diagnostics.

A successful result is exactly
`IDENTITY_EVIDENCE_VERIFIED_NON_SEND`; it contains no request ticket and
always reports `not_authorized_for_send`. No provider contract value, project
default, policy version, credential, source body, transport, reservation,
cost or publication authority was invented. Existing route/provider and
source/runtime-rights models are reused read-only; rights remain a separate
authority and cannot be promoted by this resolver.

## Verification

The first focused command, with no bytecode or pytest cache and an external
basetemp, exposed five fixture/comparison failures (`11 passed, 5 failed`):

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4-provider-contract-registry-20261029 -ra`

The bounded repair made canonical fixtures include the explicit schema field
and allowed non-authoritative caller metadata to reach exact drift comparison;
it did not add a source or provider default.

The second and final focused command was:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4-provider-contract-registry-20261029-r2 -ra`

Result: **16 passed, 0 failed.** Read-only AST parsing also passed for the new
source and test files. The tests cover canonical replay/hash, independent pin
versus forged self-hash, missing/stale/revoked/invalid authority, policy
identity/version drift, every route attribute, retention/no-sharing drift and
zero network/provider/cost/filesystem side effects.

## Exact new-file hashes

Final source and test SHA-256 values:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_provider_contract_registry.py` | `e6b9b5feb6d0e643353b29409fe8899918c8ff9f88c98a2aec6a535f5b0760cb` |
| `tests/test_phase5_t4a_provider_contract_registry.py` | `0594733a085cdeda5cf9a02c655df3432f80455e436433c46cb937c3f1fc5338` |

The four protected T4A2/T4A2A files remained byte-for-byte unchanged:

`ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4`,
`b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2`,
`ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46`, and
`e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08` in the
task's listed order.

## Remaining authority gap and next decision

The current T4A3 inventory remains controlling: no exact source-owned provider
contract/version artifact, source-owned provider-policy version registry,
fresh route attestation, current price/FX authority or cumulative AUD10 ledger
has been supplied. This implementation does not close any of those gaps and
does not claim real-send readiness. The next Product Owner/Data authority
decision is whether to establish the exact source-owned contract/policy
authority and separately authorize a bounded real-send packet under existing
rights, cost and review controls.

No provider/model call, source acquisition, spending, external network,
credential access, Drive/GitHub action, publication, release, merge, watcher,
gate closure or follow-on task occurred. No private material was added.
