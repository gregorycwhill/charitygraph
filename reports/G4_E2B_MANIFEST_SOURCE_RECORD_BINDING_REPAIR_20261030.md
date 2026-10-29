# Gate 4 E2B manifest/source-record binding repair — 2026-10-30

## Result

Completed the two bounded MEDIUM acceptance repairs in the existing five-charity
source-native `AnswerProjection`. The change is provider-free, deterministic,
read-only, and limited to this report plus the projection module and its focused
test file. No gate closure or public release is claimed.

## Repairs

1. Manifest integrity now reuses the existing `canonical_sha256()` contract. It
   recomputes the T3 `manifest_identity_sha256` over the manifest core with
   `manifest_identity_sha256` excluded, and fails closed on missing or mismatched
   identity. The immutable selected-cohort identity remains separately checked
   against the governed T3 value.
2. Each ordinal is now checked against the accepted T3 binding tuple: subject,
   scope, source family, source record ID, representation SHA-256, and rights
   record ID. A merely prefix-shaped `srcrec:` value cannot pass. No name,
   domain, lexical similarity, or semantic heuristic is used.

## Identity and provenance invariants

- Branch: `gate3-cg406-remediation`.
- Local HEAD: `c3fc30c4e81e0a862d6b75bb78344b1ce7efa86c`.
- Task fence supplied by the supervisor: `v62`, SHA-256
  `d1d4f4adc51afd58ce12bbe7ee025dc55024920f62e85a7ce85a3e98fe8e5670`.
- T3 selected-cohort identity: `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`.
- The selected-manifest file-byte SHA-256 is a different identity:
  `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`.
- The manifest's canonical self-identity is also distinct:
  `5c352f6a929508d9ecfe959cb4f8191cf776ef826b03be33f78d8c24bddbd14a`,
  reproduced with the existing canonical algorithm over the manifest core.

The projection still reads exactly ten governed representations, verifies each
representation's file-byte SHA-256, preserves the exact source family, source
record, subject, scope, date/period and field basis, emits 15 answer records,
and retains explicit currentness missingness. All prior zero-side-effect
invariants remain unchanged.

## Verification

Focused command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4b_source_answer_projection.py -q
12 passed in 0.84s
```

The focused tests cover deterministic replay, all 15 records and ten hashes,
representation-byte tampering, selected/self manifest identity tampering,
subject/scope drift, exact source-record tampering, exact rights-binding
tampering, dates/periods, explicit missingness, and no-file side effects.

The allowed-path diff has no whitespace errors. A repository-wide `git diff
--check` also encountered one unrelated pre-existing trailing-whitespace line
in `reports/G4_T4A4_SOURCE_OWNED_PROVIDER_CONTRACT_REGISTRY_20261029.md`; that
path was not edited.

No source acquisition, provider/model/network/credential call, budget
reservation or spend, SQLite/WAL/SHM access, publication, release, GitHub
mutation, watcher control, or bridge-managed commit occurred. No raw/private
source bodies, prompts, model responses, runtime state, caches, credentials or
logs were added. Pre-existing dirty and untracked material was left untouched.
