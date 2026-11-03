# G4 provider-policy registry reacceptance forensic

Date: 2026-10-31 (Australia/Sydney)
Target: `gate3-cg406-remediation@3eb28abf4647136132e7fe558900d091c21d814b`
Parent: `85f6ff5753124dee6716aeae3fc9c2dccbc657d4`
Fence: `v77`

## Verdict

**PARTIAL.** The dormant fail-closed structural control is **ACCEPTED**. It
remains `STRUCTURE_ONLY_UNAUTHENTICATED`; source-owned legal/provider authority
is **MISSING** and is not inferred or accepted.

## Independent scope and integrity

The parent-to-HEAD diff contains exactly four paths:

- `src/charitygraph/g4_provider_policy_registry.py`
- `src/charitygraph/phase5_governed_rights_preflight.py`
- `tests/test_g4_provider_policy_registry.py`
- `reports/G4_PROVIDER_AUTHORITY_REGISTRY_REPAIR_20261031.md`

HEAD blobs were checked from Git and matched after extraction: `edbff640`,
`a7bd5836`, `a86c9097`, and `bb3e869f` respectively. The exact archives were
created with `git archive` outside the checkout; no dirty Factory, rights,
evidence or runtime files were copied into them. The exact four-path
`git diff --check` is clean.

The pre-existing dirty report under review was not touched. Stable
before/after fingerprint: Git blob `612874bff4bd3f3288ca2c8aa2e3c929e6c451e1`,
length 6191 bytes. Its current SHA-256 is
`2e6c6f8cdfe620f3869ef03562de2a1ca1579386a3595f658186b58be35529ff`.

## Clean archive validation

All runs used `python -B`, `PYTHONDONTWRITEBYTECODE=1`, pytest cache disabled,
and basetemps outside the repository. Parent versus repaired HEAD:

| Selection | Parent | HEAD |
|---|---:|---:|
| Focused registry/adversarial file | 13 passed | 19 passed |
| Rights preflight + Factory + governed Factory integration | 15 passed | 15 passed |
| Broader nine-file relevant selection | 119 passed, 1 failed | 125 passed, 1 failed |

The identical broad failure is
`tests/runtime/test_rights_governance_record.py::test_compatibility_matches_existing_artifact_rights_decision_and_sqlite_projection`.
The legacy `ArtifactRightsDecision` fixture rejects four extra fields. It is
outside the four repair paths and fails identically on parent and HEAD; no
repair-path test failed. A first long-basetemp attempt failed only through
Windows path-length directory creation; the short external-basetemp rerun above
is the valid result.

## Adversarial and boundary findings

- Caller-generated coherent record plus matching caller pin remains
  `STRUCTURE_ONLY_UNAUTHENTICATED`, with `authority_verified=False`,
  `action=NONE`, and `real_send_ready=False`.
- Missing, non-canonical, self-referential, mismatched or incorrectly hashed
  separately supplied `authority_document_bytes` blocks resolution.
- No caller pin, locator, policy name, default, or forged registry entry creates
  source-owned authority; duplicate, stale, expired, route-mismatched and
  no-sharing cases fail closed.
- `require_authenticated_provider_authority_for_real_send` fails closed for
  missing or unauthenticated provider authority and independently preserves
  rights, v29 projection, route, local-retention and provider-transmission
  checks.
- The compatibility-only `provider_policy_authority` argument remains outside
  the provider-free no-send gate. Clean Factory lowering remains provider-free
  and uses the existing fake-provider path. No rights or projection bypass was
  identified by the focused, regression or static caller checks.

No source/provider/network/budget/model/Drive/GitHub/bridge/watcher action,
publication, release, gate closure, Git metadata change, or runtime-state
change was performed. Only this new report was written; private evidence and
runtime material remain excluded.
