# Sealed independent-oracle construction instructions

## Isolation boundary

Create the oracle in a physically or access-controlled workspace separate from Builder execution and semantic-development materials. The reviewer receives only the frozen holdout manifest, frozen demand-definition vocabulary, this rubric, and the oracle handoff template. The reviewer must not receive Builder semantic responses, Builder outcome labels, validation outcomes, CG406 answers/patterns, or development diagnostics.

The implementation agent must not create, inspect, copy, or summarize the completed oracle. Return only a sealed oracle package hash, manifest hash, row count, and a statement that the contents remained inaccessible to Builder.

## Oracle workflow

1. Verify the incoming selection and vocabulary hashes against `artifact-inventory.json`.
2. For each frozen instance ID, independently research and adjudicate the exact demand definition using authoritative sources appropriate to the proposition. The reviewer may use public sources beyond Source Universe v1.
3. For each conclusion, record the reference vocabulary state, subject/scope/time, material proposition decomposition, source-to-claim locators, and limitations.
4. Classify every material limitation separately: `SOURCE_UNIVERSE_COVERAGE_GAP`, `ACQUISITION_GAP`, `REPRESENTATION_GAP`, `SELECTION_GAP`, `INTERPRETATION_FAILURE`, `VALIDATION_FAILURE`, or `UNRESOLVED`.
5. Freeze all reference rows, compute a row ledger SHA-256 and an oracle manifest SHA-256, and seal the content outside Builder.
6. Supply Builder only the oracle package identities after Builder's first terminal response freeze and mechanical validation. Do not disclose answer content earlier.

## Required sealed handoff fields

`oracle_workspace_identity`, `selection_manifest_sha256`, `demand_vocabulary_sha256`, `rubric_sha256`, `reference_row_count`, `independent_reference_ledger_sha256`, `oracle_manifest_sha256`, `sealed_at`, `reviewer_attestation`, `builder_content_disclosure_before_terminal_freeze=false`.
