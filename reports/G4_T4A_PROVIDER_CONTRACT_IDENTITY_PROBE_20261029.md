# G4 T4A provider-contract identity probe

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
HEAD: `3c5cd6280e9011400399dce0153fd1dbe8180d57`  
Result: **implemented and fail-closed; Gate 4 remains active.**

## Scope

Added only the fresh successor paths named by the approved forensic proposal:

- `src/charitygraph/phase5_t4a_provider_contract_identity_probe.py`
- `tests/test_phase5_t4a_provider_contract_identity_probe.py`

The probe accepts explicit non-secret `ProviderConfiguration` metadata and
explicit source-owned/local policy identity inputs. It emits a typed,
canonical, SHA-256-addressed diagnostic. Product Owner approval, the local
policy version, test-fixture metadata, and an authority-shaped provider
contract are separate fields. Exact provider, project, service, endpoint and
model comparisons are mechanical and exact.

The existing source-rights/runtime seam remains authoritative: the repository
has the source-owned provider policy identifier but no exact source-owned
provider-policy version registry. Missing, stale, invalid, inconsistent or
mismatched contract identity/version therefore remains blocked. Even a
consistent supplied identity is labelled `identity_consistent_not_authorization`
and cannot authorize a request. No registry, default, credential state,
policy proof, transport, packet, budget, source body, prompt or response was
added or inferred.

## Verification

Focused command (provider-free, no pytest cache):

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_identity_probe.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a-contract-identity-probe-20261029`

Result: **8 passed**.

Static AST parse: **2 files parsed**. No provider, network, filesystem,
watcher, Drive, GitHub, source acquisition or cost operation occurred. The
focused tests cover deterministic replay/hash, missing contract and version,
stale authority, provider/project/service/model/endpoint mismatches,
policy/version mismatches, fixture-versus-authority distinction, and
monkeypatched zero-side-effect execution.

New file hashes:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_provider_contract_identity_probe.py` | `a1d7c49a362cc97529a79573d0c49b6e143032fab1ac31953ead1291889b7a05` |
| `tests/test_phase5_t4a_provider_contract_identity_probe.py` | `1fca63b44d8f3d96f3890d8bd680dafb48210fe36ae9ff02f5a438f42067af5d` |

The four prohibited timeout-attempt files were not edited; their hashes remain
`ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4`,
`b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2`,
`ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46`, and
`e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08` in the
order listed by the task.

No files were staged or committed. No Gate 4 acceptance or closure is claimed.
