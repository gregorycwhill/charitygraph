# G4 provider authority registry resolver

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C local/provider-free engineering task  
Target: `gate3-cg406-remediation@9f4c9516f182e07a07d903d12d2bf303a0f99b2d`  
Fence: `v75`

## Result

Implemented one isolated, read-only source-owned provider policy/contract
registry resolver in `src/charitygraph/g4_provider_policy_registry.py`.
The resolver has no provider, filesystem, credential, catalogue, budget or
network capability. It accepts the actual supplied canonical record bytes (or
an explicitly supplied structured record), reloads and hashes those bytes,
requires an independent trusted SHA-256 pin, and returns a deterministic
content-addressed diagnostic.

The record contract requires exact contract and provider-policy IDs/versions,
authority locator and content hash, current/effective status, effective date,
renewal/check date, provider/project/service/endpoint/model route, and explicit
no-training/no-sharing posture. Missing, duplicate, non-canonical, unpinned,
hash-mismatched, identity-mismatched, stale, revoked, expired, future-effective,
route-drifted, no-sharing or rights-blocked inputs fail closed. The record's
own authority-content hash, URL, policy name, non-secret defaults, or coherent
caller assertions is never promoted to independent authority.

The resolver always emits `real_send_ready: false` and
`send_authorization: not_authorized_for_send`, including for a structurally
verified authority record. It does not implement or imply ledger, pricing/FX,
reservation, transport, publication or release authority.

## Clean preflight seam

`preflight_governed_rights` now has one optional
`provider_policy_authority` argument. When absent, the existing provider-free
rights planning and Factory lowering path is unchanged. When supplied, the
preflight performs the resolver check read-only, binds the existing
`RightsGovernanceRecord` into that check, and blocks before task construction
unless current local-retention and provider-transmission rights match the
source-owned policy identity/version. Public redistribution remains a separate
v29 axis and is not inferred from provider authority. A successful authority
check still does not make a real send ready.

`rights_governance_record.py` was not weakened or given a guessed provider
registry. Its existing exact source-rights provider-policy mapping requirement
continues to fail closed when no source-owned mapping is present.

## Verification

Focused resolver command (cache-free, no bytecode):

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest tests/test_g4_provider_policy_registry.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-provider-policy-registry-20261031 -ra
```

Result: **13 passed, 0 failed**.

Relevant clean regression command (cache-free, no bytecode):

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest tests/test_g4_provider_policy_registry.py tests/test_phase5_t4a_provider_contract_registry.py tests/test_phase5_t4a_provider_contract_identity_probe.py tests/test_phase5_provider_processing_policy.py tests/test_phase5_governed_rights_preflight.py tests/test_phase5_governed_factory_integration.py tests/test_source_rights.py tests/runtime/test_rights_governance_record.py tests/runtime/test_rights_governance_projection.py -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-provider-authority-final-20261031 -ra
```

Result: **120 passed, 1 skipped, 0 failed**. The skip is the existing
`test_phase5_governed_rights_preflight.py:228` clean-seam guard for the
pre-existing dirty rights prototype; no test was weakened.

Tests cover valid deterministic replay, canonical/hash and contract/policy
identity mismatch, missing authority and pin, invalid self-asserted authority,
duplicate entries, stale/revoked/expired and renewal-date failure, route drift,
no-sharing failure, blocked provider rights, real-send false state, and
side-effect-free blocked resolution.

`git diff --check` was run. It reports a pre-existing trailing-whitespace
finding in `reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md`;
that file was not edited by this task. Existing dirty and untracked repository
paths were preserved and not staged or changed. No private source material,
provider payload, prompt, model response, credential, cache, runtime database,
publication, release, GitHub mutation, watcher or bridge state was added or
accessed.

This is an engineering implementation report only. It does not claim a real
provider authority has been supplied, authorize provider transmission, reserve
budget, spend money, publish, or close Gate 4.
