# Projection compatibility certification — 262 Terra
Superseded by `PROJECTION_COMPATIBILITY_CERTIFICATION_263_TERRA.md`.
## Continuity and recovery

Canonical Builder main, certified worktree HEAD, and merge-base were each `eedf561a204d14bf235fdc5e322054f036b7fcb0`.  Certified path: `C:\CharityGraph-runtime\projection-compatibility-257`, branch `cg-projection-compatibility-257`.  The existing 257–261 diff contained only the 11 paths committed with this report.

261 baseline: `C:\CharityGraph-runtime\projection-compatibility-261-baseline`; detached HEAD, clean status, HEAD/base at the canonical SHA, safely reused.  No pytest process existed. Four unrelated pre-existing Python processes could not be attributed because process command lines are restricted; none was touched. Fresh isolated run-262 basetemps were used.

## Design and enforcement

`projection_compatibility.py` is policy `projection-compatibility.v1`: exactly six dimensions—answer intent, claim family, authority/source role, currentness, scope, coverage—and exactly ALLOW, ALLOW_WITH_QUALIFICATION, ABSTAIN. Closed INTENTS/FAMILIES provide machine-readable semantics. Existing typed bindings govern authority, claimant/host, scope, correction/currentness, assurance/evaluation, missingness, composition and CTA/link; they are predicates, not a seventh dimension. ABSTAIN wins composition; qualifiers union monotonically.

Immutable `CompatibilityAudit` carries policy version, grain, disposition, reasons, full governed inputs/refs and qualifiers; it is an ephemeral projection audit, not canonical storage. `project_subject` enforces the current section-card boundary. `stage_rc4_release` requires authoritative context after adaptation and before writes, rejecting absent context and ABSTAIN. `validate_v05_card` freshly recomputes policy and rejects absent, inconsistent or forged evidence. No context is reconstructed from public/card data or serialized into v0.5; no schema changed. There is no genuine whole-answer production seam, and none is claimed.

## Tests

Focused command:

```text
python -m pytest --basetemp=C:\CharityGraph-runtime\pytest-projection-262-focused tests/contracts/test_projection_compatibility_gate.py tests/contracts/test_projection_compatibility_archived_replays.py tests/test_v05_fixture_adapter.py tests/test_v05_release.py
```

Result: **22 passed in 1.83s**. It covers gate composition/audit, omitted context, forged audit, valid governed context, staging-before-write, archived P6, cold-start and Sequence-17.

P6 source: `C:\CharityGraph-runtime\cg-projection-factory-saturation-253-terra-p6-projection-gate-synthesis-a1\CHECKPOINT.md`, SHA-256 `AE2D65EC2446953C39BC46AF7F608A2771A597719A389DB99E62316171E7FF3C`. All 30 were provider-free at genuine `project_subject` SECTION_CARD grain. Every row used claimant role, stale currentness, checkpoint and campaign-case governed refs, preserving `CURRENTNESS_LIMIT`.

| cases | intent/family and preserved binding | expected=actual |
|---|---|---|
| G01–G02 | historical / tax_guidance, appeal | ALLOW_WITH_QUALIFICATION |
| G03–G05 | service_information/historical / capacity, process; bindings capacity, process, intake | ALLOW_WITH_QUALIFICATION |
| G06–G07 | evaluation_summary / evaluation; bindings population-comparator-horizon, arm-outcome-estimand | ALLOW_WITH_QUALIFICATION |
| G08–G09 | regulatory_history / regulatory; G09 composition progress_remaining_work | ALLOW_WITH_QUALIFICATION |
| G10–G12 | assurance/resource_flow/cash_assistance; bindings subject-period-limitation, restricted-pool, arrangement | ALLOW_WITH_QUALIFICATION |
| G13–G14 | programme_context/programme; hosted_submission_notice/hosted_submission | ALLOW_WITH_QUALIFICATION |
| A01,A02,A04,A08,A13,A14,A15 | personal_decision/recommendation/cta conflicts | ABSTAIN: CTA_OR_LINK_CONFLICT (plus missing typed binding where family requires it) |
| A03 | current_availability / service_capacity, no binding | ABSTAIN: MISSING_TYPED_BINDING, CTA_OR_LINK_CONFLICT |
| A05,A07 | evaluation/assurance, no binding | ABSTAIN: MISSING_TYPED_BINDING |
| A06 | factual_summary / regulatory, uplift scope | ABSTAIN: SCOPE_UPLIFT |
| A09 | hosted_submission, claimant/host mismatch | ABSTAIN: HOST_IS_NOT_CLAIMANT |
| A10 | service_capacity, unknown coverage/no binding | ABSTAIN: COVERAGE_UNKNOWN, MISSING_TYPED_BINDING |
| A11 | assurance, section_conflict/no binding | ABSTAIN: SECTION_COMPOSITION_CONFLICT, MISSING_TYPED_BINDING |
| A12 | regulatory, section_conflict | ABSTAIN: SECTION_COMPOSITION_CONFLICT |
| A16 | factual_summary / unknown | ABSTAIN: UNKNOWN_FAMILY |

The source fixture retains individual inputs, original reason predicates and case lineage for G01–G14/A01–A16. Cold-start hashes passed: Social Outfit `d4fe4cee29655691688f1c16ce81317350d5371fba55ddd5ded82a22ffd1204b`; Ability Options `84e9fc1212d3def3d62e008f017dff8fbaa772f42097430825db708629680066`; Australian Himalayan Foundation `01729b722366385f6fff4570feb451145e90148c17475e8150c58a6bddf1e329`. Sequence-17 archive `C:\CharityGraph-runtime\reality-sequence-17-terra-saturation-campaign\checkpoints` passed c29, c30, c31, c33-equivalent (033), c34 and c35.

Broad command/environment: `python -m pytest`, Python 3.13, same environment, distinct basetemps. Clean local base `C:\CharityGraph-runtime\projection-compatibility-261-baseline`: **1068 passed, 1 skipped, 7 failed, 3 warnings** in 94.54s. Patched: **1083 passed, 1 skipped, 7 failed, 3 warnings** in 110.00s. The +15 are compatibility tests. Failure identities exactly match: seven `tests/test_s0_identity_lineage.py` cases (mandates, policy bytes, duplicate bytes, successor/version, authorised successor, material/policy hashes, durable checkpoint); both end in identical pathlib FileNotFoundError. No unexplained regression delta. Logs: `C:\CharityGraph-runtime\projection-262-baseline.log`, `.err`, `projection-262-patched.log`, `.err`.

`git diff --check` passed. Criteria 1–17 are reconciled above. Hard-zero counts: provider/scientific calls 0; external acquisition 0; S0 0; Top-100/holdout 0; public release 0; authenticated GitHub mutation 0; Codex-side GitHub network/authentication 0; reset-credit redemption 0.
