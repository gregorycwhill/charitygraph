# G4 T3 exact-representation and rights-binding seam

Date: 2026-11-01 (Australia/Sydney)  
Result: **PARTIAL — reusable provider-free binder added; real cohort remains blocked**

## Bounded input and current facts

This task consumes the existing, read-only selection manifest at
`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json`. It does not
rewrite or acquire it. The manifest records five distinct subjects and ten
rows: one `acnc_register` and one `acnc_ais_bundle` row per subject. Its direct
selected-manifest hash is
`41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`. The
manifest file SHA-256 observed locally is
`06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`. It declares
`source_bytes_included: false`, ten `bound_not_task_eligible` rows, zero
eligible private-retention rows, zero preflight tasks, zero provider requests
and AUD 0.00 spend.

Direct supporting input hashes: recovery summary
`828478f3dc2f78a008c91c0ce0a3135968fe07973551305c8fb5ac75ed1088df` and
source-lineage recovery
`7f3664ac1bfa5d1312aff5e8b8eee62ffdf048d18f00d4f6dc61ec69439743b2`.
Execution was local on branch `gate3-cg406-remediation` at the supplied exact
HEAD `4eaa7eccb38a722a88797483ecae7bfd26492b4b`.

The ten manifest rows contain source object IDs/SHA-256 values and provisional
representation IDs/SHA-256 values, but no independently observed representation
metadata or bytes. The binder therefore treats the manifest representation
fields as selection claims only; equality with a source SHA never proves a
representation. No source object, exact representation, validated receipt or
current v29 rights decision was imported or created by this task.

## Implementation seam

Added `src/charitygraph/phase5_t3_exact_representation_rights_binding.py`.
It is a versioned, deterministic, provider-free binder that:

* validates the immutable ten-row selection identity and preserves every row
  and subject, including supplied `source_silent` coverage records;
* accepts only caller-supplied existing representation/receipt/rights metadata
  and verifies exact source-to-representation lineage, subject and scope;
* keeps local retention, private-provider processing and public redistribution
  decisions separate and fail-closed;
* emits typed `BLOCKED`/`NOT_OBSERVED` rows without zero-value substitution;
* binds an affirmative local decision to the exact representation SHA, policy
  identity/version, lawful-access, no-circumvention, explicit-prohibition,
  assessed-authority and review-deadline predicates; and
* lowers only genuinely complete positive rows to the existing
  `GovernedReference`/`preflight_governed_references` contract. It does not
  create a second rights ledger, representation engine, provider route or
  public projection.

The real-manifest case remains not observed because the checked-in selection
input contains no exact representation evidence. The local result was ten
`NOT_OBSERVED`, zero `BOUND`, zero eligible rows, with per-row missing source
record, receipt, governed scope and exact representation observations. A synthetic
positive fixture in the focused tests exercises the existing governed
preflight/Factory handoff without claiming that any real cohort row is
eligible.

## Verification

Added `tests/test_phase5_t3_exact_representation_rights_binding.py` with
permutation-stable canonical hashing and negative cases for source-vs-
representation SHA substitution, cross-subject/scope binding, stale/revoked
or mismatched policy versions, invalid review dates, missing provider
conditions, public-redistribution overreach, unauthorized source families,
explicit prohibitions, duplicate/conflicting receipts, and fake provider/rights
metadata. The tests contain only synthetic metadata and bytes in temporary
runtime fixtures; no private bytes or credentials are committed.

The new focused suite passed 13/13 cache-free. The small existing governed
rights/Factory/reconciliation set ran cache-free with an external basetemp:
89 passed, 1 skipped, and 3 existing T4D handoff failures (provider-rights
references absent in a synthetic internal-policy fixture, plus two mixed-scope
boundary assertions). Those failures were outside the three new paths and no
existing files were changed by this task. No provider/model call, spending,
publication, source acquisition, release, gate closure or follow-on dispatch
is performed here.

## Next Gate 4 product tranche

Provide a governed, independently observed exact representation registry plus
validated acquisition receipts and current v29 per-artifact rights decisions
for the ten selected rows. Re-run this binder against those existing inputs,
then let the current governed preflight/Factory path decide task eligibility;
do not promote the synthetic fixture or infer provider/public rights from the
approved internal-use authority.
