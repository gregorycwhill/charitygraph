# Projection compatibility semantic-oracle certification — 263 Terra

## Lineage and boundaries

Canonical Builder main is `eedf561a204d14bf235fdc5e322054f036b7fcb0`.  This
worktree is `C:\CharityGraph-runtime\projection-compatibility-257` on
`cg-projection-compatibility-257`; before amendment its sole local commit was
`02019a6c9539676b3606f641d0aa356e90cfcdd1` and `git rev-list --count
eedf561..HEAD` was `1`.  No GitHub network/authentication/mutation, provider
or scientific call, external acquisition, S0, Top-100/holdout, public release,
or reset-credit redemption occurred (all counts: **0**).

Campaign P6 source is `C:\CharityGraph-runtime\cg-projection-factory-saturation-253-terra-p6-projection-gate-synthesis-a1\CHECKPOINT.md`, SHA-256 `AE2D65EC2446953C39BC46AF7F608A2771A597719A389DB99E62316171E7FF3C`.
Cold-start checkpoint SHA-256 values are Social Outfit
`d4fe4cee29655691688f1c16ce81317350d5371fba55ddd5ded82a22ffd1204b`, Ability
Options `84e9fc1212d3def3d62e008f017dff8fbaa772f42097430825db708629680066`, and
Australian Himalayan Foundation
`01729b722366385f6fff4570feb451145e90148c17475e8150c58a6bddf1e329`.
Sequence-17 uses immutable local checkpoints `029`, `030`, `031`, `033`, `034`,
and `035` under `C:\CharityGraph-runtime\reality-sequence-17-terra-saturation-campaign\checkpoints`.

## Semantic repair

The policy remains exactly six dimensions: answer intent, claim family,
authority/source role, currentness, scope and coverage; and exactly three
dispositions: ALLOW, ALLOW_WITH_QUALIFICATION, ABSTAIN.  No public v0.5 schema
or parallel store changed. `PolicyInput` now has ephemeral structured
`TypedBinding` values: governed reference plus explicit components. Required
families/components are service capacity (`capacity_context` or
`access_context`), service process (`process_context`), evaluation
(`population/comparator/horizon` or `arm/outcome/unit/estimand`), assurance
(`subject/period/limitation`), resource flow (`pool/programme`), and cash
assistance (`arrangement`). A non-empty opaque reference cannot pass.

P6 fixture rows contain a source-backed explicit six-field vector, source
reference, grain, binding and exact expected audit result. G01–G14 retain
their distinct archived intent/family/role/binding semantics, all historical
only where their own archive supports it; each is AWQ with exactly
`CURRENTNESS_LIMIT`. A01–A16 are exact ABSTAIN rows. In particular A04, A08,
A13, A14 and A15 are exactly `CTA_OR_LINK_CONFLICT`; A10 is exactly
`COVERAGE_UNKNOWN`; A11 is exactly `SECTION_COMPOSITION_CONFLICT`. They no
longer receive a spurious `MISSING_TYPED_BINDING`: binding completeness is
assessed only after decisive CTA/coverage/composition refusals. A05 and A07
remain exactly `MISSING_TYPED_BINDING`.

The replay adapter rejects absent/unrecognised/incomplete case records rather
than applying generic values. ABSTAIN execution captures the actual audit and
compares disposition, ordered reasons, grain and qualifiers; it does not only
assert an exception. Cold-start f2/f3/f4 and Sequence-17 c29/c30/c31/c33/c34/c35
are six-dimensional distinct replays based on their recorded service,
missingness, relationship, evaluation, correction, tax-safety and
resource-flow limits. They are private experimental evidence, not production
claims; their supported grain is bounded card/section projection only.

## Commands and results

Focused command:

`python -m pytest --basetemp=C:\CharityGraph-runtime\pytest-projection-263-focused tests/contracts/test_projection_compatibility_gate.py tests/contracts/test_projection_compatibility_archived_replays.py tests/test_v05_fixture_adapter.py tests/test_v05_release.py`

Result: **26 passed, 0 failed**. It includes exact P6/cold-start/S17 matrices,
unknown-default rejection, partial/complete binding negatives/positive,
mechanical ABSTAIN non-override, qualifier composition, and v0.5 staging and
independent validator fail-closed checks.

Patched broad command (isolated basetemp): `python -m pytest --basetemp=C:\CharityGraph-runtime\pytest-projection-263-patched-bg`.
Result: **1087 passed, 1 skipped, 7 failed, 3 warnings** in 109.24s. The seven
failures are exactly the pre-existing `tests/test_s0_identity_lineage.py`
mandate/policy/duplicate/successor/authorised-successor/material-hash/durable-
checkpoint failures. Clean canonical-base command, run in
`C:\CharityGraph-runtime\projection-compatibility-261-baseline`, was
`python -m pytest --basetemp=C:\CharityGraph-runtime\pytest-projection-263-clean-bg`:
**1068 passed, 1 skipped, 7 failed, 3 warnings** in 81.77s, with the identical
seven failure identities. Delta is +19 passing tests (the original +15 gate
tests plus four exact semantic-oracle tests), zero new failures and zero new
warnings.

Standalone `git diff --check` and `git diff --cached --check` both exit 0;
they are rerun independently after staging and the range check is rerun after
amendment. Immutable audit objects retain policy version, inputs, refs,
reasons, grain and monotonic qualifiers; production staging/validation remains
the independent fail-closed enforcement seam.

## Reconciliation

Criteria 1–14 are satisfied by the lineage, local source hashes, exact matrix
tests, structural binding validation, unchanged six-dimension architecture and
broad delta above. Criteria 15–17 are satisfied: standalone pre-stage
`git diff --check`, standalone pre-amend `git diff --cached --check`, and
standalone post-amend `git diff --check eedf561a204d14bf235fdc5e322054f036b7fcb0..HEAD`
each exited 0. Commit `02019a6c9539676b3606f641d0aa356e90cfcdd1` was amended,
not supplemented; the final commit is recorded in the delivery status with one
commit since base and a clean worktree. Production limitation: the archive
supports bounded, source-attributed replay inputs, not whole-answer production
claims or an inference from public-card dictionaries.
