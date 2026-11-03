# G4 Phase 5 provider-history evidence adapter — independent acceptance

Date: 2026-11-01 (Australia/Sydney)  
Disposition: **FAIL for code semantics; PARTIAL for real-world provider evidence**.

This was a report-only, provider-free acceptance. No provider, model, Drive,
watcher, GitHub, publication, release, or spend action was performed.

## Exact scope and diff

Verified HEAD is `c571ac9aa1030e4a0aa5b4240c975ff6408b6ea7` on
`gate3-cg406-remediation`, with parent
`2af1d063595d68adbbd4826937023230bc6ef8a2`. The supplied fence was v93,
SHA-256 `4cde7f9c17f4eb7de4c95ab874ac2419c0022c80c73ad8d592067baf94fed838`.

`git diff-tree` independently shows exactly these three files in the direct
child commit:

```text
A reports/G4_PHASE5_PROVIDER_HISTORY_EVIDENCE_ADAPTER_20261101.md
A src/charitygraph/phase5_provider_history_evidence_adapter.py
A tests/test_phase5_provider_history_evidence_adapter.py
```

The implementation and focused-test SHA-256 values match the worker report:

```text
751d48a5747ae3408a704043fca1cc4554b75005258f963b5e620fa5b6344898  src/charitygraph/phase5_provider_history_evidence_adapter.py
c147bb767fbaa9c59cef0b448fc0d325e6601361e8d925f514c463ffc2f396c7  tests/test_phase5_provider_history_evidence_adapter.py
```

The commit has one pre-existing trailing-whitespace warning in its separate
worker report; no product-source diff expansion was found. The checkout had
many unrelated dirty tracked and untracked paths at launch. They were not
edited, staged, or absorbed. This acceptance report is the only new worktree
path from this task.

## Verification

All commands were cache-free with `PYTHONDONTWRITEBYTECODE=1` and a
`C:\CharityGraph-runtime\...` `--basetemp` outside the checkout.

```text
python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-acceptance-20261101-a tests/test_phase5_provider_history_evidence_adapter.py
20 passed

python -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-phase5-provider-history-acceptance-20261101-b tests/test_phase5_run_inventory_audit.py tests/test_phase5_project_cost_reconciliation.py
51 passed
```

The worker's reported 83 combined and 46 diagnostics tests were not rerun
because this acceptance was limited to the focused adapter plus the needed
run-inventory and project-cost regressions. No test failure occurred in the
independently run 71 tests.

## Code-semantics result

The following passed in focused tests and independent probes:

- exact raw export SHA-256 binding and acquisition SHA mismatch failure;
- schema/version, scope, identity, time-window and missingness handling;
- deterministic ordering of normalised records and permutation-stable
  reconciliation-source canonicalisation;
- duplicate/conflicting run records and conflicting physical-attempt mappings;
- receipt foreign-key, missing amount/currency/pricing/FX and source-silence
  diagnostics;
- forged `authenticated`, `verified`, `complete`, `source_owned` and signed-
  looking caller fields never create authority;
- run-inventory delegation returns `NOT_AUTHORITATIVE`; cost reconciliation is
  reference-only and does not aggregate or replace the existing contract; and
- every probed untrusted condition retained
  `project_wide_authoritative=false`, `authoritative_total=null`, and
  `remaining_spend=null`.

Two findings prevent code-semantics acceptance:

1. **Private-material projection leakage.** The accepted raw envelope's
   `source_identity` mapping is copied wholesale into `export.source_identity`
   (`phase5_provider_history_evidence_adapter.py:425-433`). An adversarial
   synthetic export containing `credential` and private billing/source-content
   fields caused both sentinels to appear in canonical output. Top-level raw
   payload and unrecognised record fields were omitted, but this identity path
   is not allowlisted/redacted. This violates the no-credential/private-source
   leakage boundary.
2. A run-index row with a `run_id` but no `physical_attempt_id` remains an
   observed row without a dedicated missing-attempt diagnostic. The authority
   invariant stays fail-closed, but the requested missing-attempt failure is
   not explicit. Receipt-side missing physical attempts are explicit.

For semantic-equivalence clarity, normalised record order is stable when raw
records are permuted, while the full projection hash intentionally changes
because the raw export byte SHA is part of the immutable source binding.

## Real-world provider evidence

**PARTIAL / unavailable.** No authenticated provider-native cumulative run
inventory, billing/receipt population, trusted host attestation, or source-owned
completeness boundary was available locally, and no live acquisition was
authorised for this acceptance. Structural tests therefore do not establish
provider completeness, cumulative inventory, invoice truth, pricing/FX truth,
or budget authority.

## Private-material and authority inspection

The commit path and this report contain no raw provider export, credential,
receipt/billing payload, runtime database, cache, model response, prompt, or
public projection. Synthetic sentinel probes were process-local only. The
implementation's detected identity-field leakage is a code-path defect, not an
actual provider secret found in the repository.

## Next bounded Gate 4 product tranche

Remain blocked from acceptance/promotion until a bounded remediation redacts
or strictly allowlists identity fields, adds explicit missing run-attempt
diagnostics, and adds regression probes for both. Then independently verify a
host-authenticated read-only ingress that binds cumulative run-index and
receipt bytes to source identity, scope/window, timestamps, schema/version,
completeness boundary and exact SHA-256 before any authority decision is
considered. The existing run-inventory and project-cost contracts remain the
only accounting authorities; this adapter must not promote source-owned
completeness or close Gate 4.

