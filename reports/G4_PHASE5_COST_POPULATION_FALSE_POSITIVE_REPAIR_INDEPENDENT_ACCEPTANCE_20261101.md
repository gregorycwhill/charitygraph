# G4 Phase-5 cost-population false-positive repair — independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Target HEAD: `5fe83f43aea7c8f88c6ad0519bf4dc3bcd2adff2`  
Parent: `33cf117c69fbe8785e6803cda108fc08d4651838`  
Branch: `gate3-cg406-remediation`  
Fence supplied: v88, SHA-256 `22b9d57358e7cf6a190150165e11e658c730fe6fe5c3b4c60c2a0960d68d18a2`

## Disposition

- **Bounded code semantics: PARTIAL.** The two reported false positives are
  repaired for the covered inputs, but a material trust-boundary bypass remains.
- **Actual project-wide factual authority: FAIL.** No independently verified
  complete real-project run inventory or spend/price/FX evidence was established.
- **Gate 4 closure readiness: FAIL.** No closure, release, scorecard change or
  project-wide AUD 10 remainder claim is supported.

## Scope and provenance

`git diff-tree --no-commit-id --name-status -r 5fe83f43^ 5fe83f43` resolves to
exactly the three stated paths: the reconciliation module, its focused tests,
and the prior implementation report. The live checkout had numerous unrelated
dirty and untracked paths; they were not read into the archive overlay and were
left untouched. The target report did not exist before this review.

Exact archive SHA-256 values (LF-normalised archive bytes) were:

- implementation: `796481deee4f1a3d7a0f658af28e7eb7c97c44e74a863ac69cb03167f32832f4`
- focused tests: `902fd285be9cd81d2bb999c6d21f228c35c7716d28ceaee3e9785b1bc590ca14`
- prior implementation report: `32e14ed513ef08a5bcc5990c9a5454b5abe09ba3b5892d6b710a875c1ced5f15`

The prior implementation report is stale as acceptance metadata: its lines 4–5
name parent HEAD `33cf117c...` and v87, not this target HEAD/v88. Its claimed
27/135 counts were therefore independently rerun.

## Independent execution

An exact-HEAD `git archive` was expanded outside the live checkout at
`C:\CharityGraph-runtime\g4-phase5-fp-repair-f4f40b0ae87a4e5f9b4c67bbb300d0e4`.
All runs used `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and basetemp
outside that overlay.

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-pytest-basetemp-fa8332d7da4c46bfa92bd29f5f7efd55 tests/test_phase5_project_cost_reconciliation.py
27 passed in 3.14s

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-related-basetemp-7c28e11f8d4048379a6645a1fe2fac24 [the eight exact-HEAD operator-health/accounting test files]
108 passed in 2.52s
```

The combined independent result is **135 passed**. No provider/model call,
source acquisition, Drive, watcher, GitHub, publication, release, gate closure
or follow-on dispatch occurred.

## Passing bounded evidence

- Default `project_wide=True` no longer derives expected history from the local
  `runs` table (`phase5_project_cost_reconciliation.py:330-510, 1253-1272`);
  the complete internally consistent two-run fixture instead reports
  `MISSING_TRUSTED_RUN_INVENTORY` and no authoritative total (focused tests
  `:445-456`).
- A bounded manifest remains non-authoritative even when its population
  diagnostics are complete (`tests/test_phase5_project_cost_reconciliation.py:367-382`).
- Missing runs, stale schema, missing attempts/receipts/cost, unknown amounts,
  missing pricing/FX, retry ambiguity, duplicate/conflicting receipts,
  reservation/release uncertainty and contradictory physical/request/receipt
  identities veto authority in the focused suite (`:84-119`, `:193-346`,
  `:385-443`).
- `send_ambiguous` without a cost row now vetoes authority while preserving the
  observed subtotal of `3.3`; mixed-run unknown cost preserves the known
  subtotal of `1.1` and remains non-authoritative (`:489-524`). No fabricated
  zero or project-wide remaining spend was observed; `remaining_spend` remains
  null/unknown.
- The adapter opens path inputs with SQLite `mode=ro&immutable=1`, applies
  `query_only`, selects an allowlisted schema, and the projection uses Decimal,
  sorted canonical JSON and safe projected identities (`phase5_operator_health_catalogue.py:228-270, 281-382`; reconciliation `:1213-1229`).
  The source file remained byte-stable in the canonical-hash test and raw usage,
  provider response and payload fields were absent (`tests/:166-178`).

## Material remaining failure

`_trusted_population_inventory` (`phase5_project_cost_reconciliation.py:284-327`)
checks only caller-provided mapping fields: `state=source_owned`, a non-empty
source, unique values after `str()`, scope/provenance/completeness strings and
complete evidence text. It does not verify that the manifest is source-owned,
independently authenticated, cryptographically bound, or issued by a trusted
registry. A caller-supplied copy of the test fixture with `kind=project_wide`
and matching local run IDs therefore bypasses the missing boundary at
`:592-597` and returns:

```text
status=AUTHORITATIVE
authoritative_total=3.3
reason_codes=[]
remaining_spend=None
```

The same provider-free probe showed duplicate IDs rejected as
`MISSING_TRUSTED_RUN_INVENTORY`, and a JSON-shaped malformed ID failed closed
with `MISSING_RUN_RECORD`/`SOURCE_RUN_SCOPE_MISMATCH`. Those negative cases do
not cure the full-shape forged-manifest bypass. The existing “untrusted caller”
test (`:459-471`) only omits required fields; it does not challenge a forged
complete manifest.

This is a code-level acceptance failure, independent of the absence of real
project evidence. The synthetic fixture can demonstrate Decimal arithmetic and
linkage, but cannot establish historical population, provider exactly-once
effects, invoice truth, pricing/FX authority, unpersisted charges or cumulative
AUD 10 spend authority.

## Next authorised substantive successor

Require a trusted source-owned cumulative inventory acquisition/attestation (or
a durable second-ingress independent review) whose authenticity, scope,
completeness, unique run IDs and lineage are verified outside caller-controlled
fields, then add a regression for a forged full-shape manifest. Until that
evidence and repair exist, retain the project-wide authority veto.
