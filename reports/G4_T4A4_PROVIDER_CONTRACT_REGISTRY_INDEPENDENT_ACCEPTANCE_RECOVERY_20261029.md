# G4 T4A4 provider-contract registry — independent acceptance recovery

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free, report-only  
Disposition: **PARTIAL for the provider-free registry diagnostic only**. This
does not accept a live provider contract, real-send readiness, or Gate 4 closure.

## Boundary and exact identity

The local branch is `gate3-cg406-remediation`, exactly at
`d0551d348f02dbaed24cf1f37430e8b092a66578`, fence `v53`. The HEAD is the
single-parent direct child of `1d23ff731f768414c3936494727c92a450167907`, with
tree `f28c5a1916430a304151230cc64403d2c8421da9`. Its three committed paths are
exactly the resolver, its focused test, and the source-owned implementation
report.

The local Builder authority files, North Star v0.3, and the sibling Data
authority/current-state/roadmap/implementation/test and source/evidence,
taxonomy and LLM-economics governance documents were read. Their relevant
boundary is preserved here: source authority, provider handling, rights, cost,
retention and publication are separate controls; a locator or local fixture is
not live authority. The T4A3 readiness inventory remains controlling evidence
that provider contract/version, exact route attestation, current pricing/FX and
the cumulative ledger are missing.

Exact target hashes (SHA-256; the source and test are byte-identical to HEAD):

| Path | SHA-256 | HEAD blob |
|---|---|---|
| `src/charitygraph/phase5_t4a_provider_contract_registry.py` | `e6b9b5feb6d0e643353b29409fe8899918c8ff9f88c98a2aec6a535f5b0760cb` | `af4c21e7cee5a05152358cedc62bd86804c14f91` |
| `tests/test_phase5_t4a_provider_contract_registry.py` | `0594733a085cdeda5cf9a02c655df3432f80455e436433c46cb937c3f1fc5338` | `d0ec3b63798b2795272230a2e9a76e61655f8e68` |
| pre-existing dirty `reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md` | `2d37cc25b980d1242465b10a86066987b1d45fbd5b2a982c17d3b74e6d4f19b8` | `506b67bdfab96665cba8694c80890269f17be008` |

## Independent product/technical finding

**Technical acceptance: ACCEPT for the bounded provider-free diagnostic.** The
resolver parses canonical JSON, requires a separately supplied trusted SHA-256
pin, and never treats the entry's self-attested
`authority_content_sha256` as that pin. Missing, unpinned, invalid,
non-canonical, changed, stale and revoked authority fail closed with typed
`UNBOUND` or `NOT_VERIFIED` results. Provider-policy ID/version drift and exact
provider, project, service, endpoint, model, retention, no-training and
no-sharing drift are rejected. Supplied rights authority is consulted
read-only and cannot be promoted by this resolver.

The only positive state is exactly
`IDENTITY_EVIDENCE_VERIFIED_NON_SEND`; it has `request_ticket: None` and
`send_authorization: not_authorized_for_send`. The code creates no request,
credential, transport, reservation, cost, price, FX, publication or source
rights authority.

**Product acceptance: PARTIAL.** The entry carries `contract_id` and
`contract_version`, but the resolver has no caller-supplied expected contract
identity/version and therefore cannot diagnose caller contract identity or
version mismatch. The entry schema field is also a general string rather than
an exact registry-schema literal. The clean HEAD rights path has no
source-owned `PROVIDER_POLICY_REGISTRY` mapping; the current dirty
`source_rights.py` was not used as acceptance authority. No live source-owned
contract, project, service, endpoint, model, credential, price, FX, budget or
source-rights evidence is claimed.

## One focused verification

Exactly one permitted invocation was run, provider-free:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a4-provider-contract-registry-independent-recovery-20261029 -ra`

Result: **16 passed, 0 failed** in 2.48s. The focused side-effect test
observed no socket or file-open operation. No provider/model/network call,
source acquisition, credential access, spend, reservation or publication
occurred. The external basetemp was outside the repository; no bytecode or
pytest cache was enabled.

## Previous failure forensics and preservation

The preceding terminal gate
`gate4:engineering:20261029-g4-t4a4-contract-registry-independent-acceptance-mvtd7b83`
was quarantined because it changed the tracked implementation report instead
of creating this independent report. The direct local evidence is the current
Git diff: that report changed from its HEAD title/worker/target/fence and
implementation result into a different acceptance narrative, with **78
insertions and 68 deletions**. Its current worktree SHA-256 is the value above;
its HEAD blob remains `506b67...`. No separate local telemetry artifact with
the exact gate ID was found in the searched repository/runtime paths, so the
diff is the evidence used here. The tracked report was not restored, edited,
staged, committed or removed by this worker.

The four protected untracked T4A2/T4A2A files remained byte-for-byte unchanged:

| Path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_real_pilot_preflight.py` | `ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4` |
| `tests/test_phase5_t4a_real_pilot_preflight.py` | `b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2` |
| `src/charitygraph/phase5_t4a_pilot_packet.py` | `ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46` |
| `tests/test_phase5_t4a_pilot_packet.py` | `e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08` |

All other pre-existing dirty paths were preserved. The sole intended workspace
addition from this worker is this new report. No private evidence, runtime
state, cache, provider output or credential material was added.

## Real-send gap and next bounded task

Real-send authority remains absent: an independent source-owned registry
artifact and pin, exact contract identity/version comparison, source-owned
policy-version mapping, current route/credential-control attestation, current
price/FX authority and reconciled cumulative AUD10 ledger are still required.
The positive diagnostic cannot supply or imply any of them.

The next approved provider-free bounded product task is to add explicit
expected contract ID/version inputs and exact schema-literal validation to this
resolver, with focused fail-closed tests for both mismatches and replay. That
task must remain diagnostic-only and must not add provider defaults, credentials,
transport, budget reservation or send authorization. Gate 4 remains open.
