# G4 T3 five-subject binder independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Status: **PARTIAL — investigation in progress**

## Scope and exact lineage

Read-only acceptance of branch `gate3-cg406-remediation`, HEAD
`5bf3b530eac83c9f30ea1e3a5052e4cb8c793c9a`, parent
`4eaa7eccb38a722a88797483ecae7bfd26492b4b`, bridge fence `v97`, fence SHA-256
`c30256e691dff8393f16bf302f3d7ed57d7630d5f08ab7bb505878402fd43e5e`.
The exact direct-child commit adds only the three requested paths:

- `src/charitygraph/phase5_t3_exact_representation_rights_binding.py`
- `tests/test_phase5_t3_exact_representation_rights_binding.py`
- the prior worker report at `reports/G4_T3_FIVE_SUBJECT_EXACT_REPRESENTATION_RIGHTS_BINDING_20261101.md`

The worktree had unrelated dirty tracked and untracked paths before review; they
were preserved. No source/provider bytes, credentials, runtime state or private
material were added to this report.

## Early findings

The checked-in selection manifest has ten rows and five distinct stable subject
IDs, with one `acnc_register` and one `acnc_ais_bundle` row per subject. Its
selected-manifest identity is `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`;
the file SHA-256 is `06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`.
It declares `source_bytes_included: false`. Every declared representation ID/SHA
is the corresponding source artifact ID/SHA, so these are not accepted as
independent exact representations.

The new binder is provider-free and delegates positive lowering to the existing
`GovernedReference` / `preflight_governed_references` path. Against the real
manifest with no supplied existing representation, receipt, scope or rights
metadata it returns 10 `NOT_OBSERVED`, 0 `BOUND`, and 0 eligible rows. A
synthetic positive fixture is treated only as synthetic.

Focused binder tests: **13 passed** cache-free. Independent synthetic probes:
**11/11 passed**. T4D clean parent/HEAD reproduction and the final actual-row
rights audit will be appended below.

