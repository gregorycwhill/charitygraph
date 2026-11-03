# G4 T4A provider-contract identity probe — independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Worker: bounded G4-O1C, local/provider-free  
Reviewed HEAD: `372ca4183ee9511d99e3c06bab1a5c17bf0aa4b5`  
Disposition: **ACCEPT — diagnostic fit for purpose; Gate 4 remains active.**

## Boundary and evidence

The reviewed commit is a single-parent direct child of
`3c5cd6280e9011400399dce0153fd1dbe8180d57` and changes exactly three paths:

- `reports/G4_T4A_PROVIDER_CONTRACT_IDENTITY_PROBE_20261029.md`
- `src/charitygraph/phase5_t4a_provider_contract_identity_probe.py`
- `tests/test_phase5_t4a_provider_contract_identity_probe.py`

The committed files are byte-identical to the worktree at review time. Independent
SHA-256 hashes are:

| File | SHA-256 |
|---|---|
| diagnostic source | `a1d7c49a362cc97529a79573d0c49b6e143032fab1ac31953ead1291889b7a05` |
| focused tests | `1fca63b44d8f3d96f3890d8bd680dafb48210fe36ae9ff02f5a438f42067af5d` |
| committed predecessor report | `59daaf8a45be6c4812f7d0c385da1bec29ce94b7bedc7fcae0be3c9dc3f03c8e` |

The predecessor report’s HEAD field names the parent commit rather than the
reviewed commit; this is a report metadata defect, not a diagnostic-code defect.

The pre-existing dirty work was preserved. In particular, the four protected
files remained unchanged with these observed SHA-256 hashes:

| File | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4a_real_pilot_preflight.py` | `ccf296dcc551d55c1b94f282653222e7a1fccdfa77d2bdb8757ce0793dd7b2a4` |
| `tests/test_phase5_t4a_real_pilot_preflight.py` | `b6583eb1069b5898b139fe31c450e9d95498c3fd24dd15031a11f6e77cbaebd2` |
| `src/charitygraph/phase5_t4a_pilot_packet.py` | `ce27cbc7a31eb1fce1127e4986bd77aeb3405898c4d582fe1d6ac8bf625ffa46` |
| `tests/test_phase5_t4a_pilot_packet.py` | `e9e20a08f501f79b5fd4954322b8deffecf4733a8234c9074abc6951de9b2e08` |

## Technical acceptance

I read the repository instructions, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`,
the locally available Data authority/current-state/roadmap/plan documents and
North Star v0.3, the predecessor report, the committed source/tests, and the
provider-processing, source-rights and runtime-rights seams.

The diagnostic is a pure, typed comparison over explicit non-secret inputs. It
canonicalises and hashes the binding, authority-shaped contract and diagnostic;
compares provider, project, service, endpoint and model exactly; and fails closed
for missing or invalid configured metadata, missing contract identity/version,
stale or revoked contract status, missing authority evidence, policy identity or
version mismatch, and each route-field mismatch. Fixture metadata is explicitly
blocked as authority. A successful comparison is named
`identity_consistent_not_authorization` and cannot authorize a request.

The source-rights module exposes the provider policy identifier but no
`PROVIDER_POLICY_REGISTRY`. The runtime explicitly rejects provider
authorization without that exact source-owned version mapping. The probe respects
that boundary: it does not invent a registry or verify an authority artifact’s
bytes. Consequently, a supplied `authority_content_sha256` is evidence metadata
only; it is not independently verified against source-owned bytes. Malformed
scalar inputs that cannot form a diagnostic fail through validation exceptions,
which is fail-closed but not a normalized diagnostic result.

Static AST parsing independently succeeded for both files. The source imports no
provider, network or transport client. The tests’ socket/URL/open monkeypatch
assertions passed, with no provider request, transport, credential/secret read,
source acquisition, budget reservation, cost operation, watcher or other side
effect.

## Verification

Independently run, provider-free, with no pytest cache or bytecode writes and an
external basetemp:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_provider_contract_identity_probe.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a-contract-identity-probe-independent-20261029`

Result: **8 passed in 0.52s**. This independently confirms deterministic replay
and content hashing, missing/stale/mismatched identity and version handling,
exact route comparisons, fixture/authority separation, and the zero-side-effect
guard. Pre-existing unrelated repository `__pycache__` material was observed and
left untouched.

## What this accepts, and what remains missing

Accepted: this is a suitable provider-free safety diagnostic for detecting
internal identity inconsistency before any hypothetical send. It is not a
provider-contract authority, provider authorization, request preflight, transport
test, budget approval, real-data evidence check, or Gate 4 acceptance/closure.

Before a real send, the exact missing evidence includes a current source-owned
provider contract/version artifact with independently verifiable content and
authority; an exact source-owned provider-policy version registry recognized by
the rights/runtime authority; a current rights decision and provider-processing
decision bound to the exact retained representation and acquisition lineage; a
fresh authorized non-secret route/credential-control attestation; and an
explicitly reserved, reconciled cohort budget plus request/transport identity
and response-reconciliation controls. None is supplied or implied here.

The next genuine product decision is whether Product Owner/Data authority should
establish that source-owned contract/version authority and then separately
authorize a bounded real-send packet under the existing rights, cost and review
controls. Until then, the correct state remains provider-free diagnostic accepted,
send readiness unresolved, and Gate 4 active.

No code, source, provider/model call, acquisition, spend, GitHub mutation,
publication, release, merge, process/watch management or protected dirty file was
changed. This report contains no private source, provider payload, credential or
runtime material.
