# G4 Phase-5 project-cost reconciliation — independent acceptance

Date: 2026-10-31 (Australia/Sydney)  
Disposition: **PARTIAL** — the committed local diagnostic is materially useful and provider-free, but project-wide incurred spend, source-owned pricing/FX authority, and cumulative-budget completeness are not established.

## Authority and exact commit

- Branch: `gate3-cg406-remediation`
- HEAD: `a9aa4ccc4b97be7cad80a69aedd59d80314a0ba9`
- Parent: `e215f3ca82307bc398433c54940ef312b5cbde3e`
- Supplied immutable v84 fence SHA-256: `cc638c3ab0c565c274c86985f62f23d70bab03ddfab634faa24bd711d3b830df`
- The supplied fence was not a local Git object and therefore was not independently recomputed here.

`git diff-tree` shows exactly these three committed additions and no other commit paths:

1. `src/charitygraph/phase5_project_cost_reconciliation.py`
2. `tests/test_phase5_project_cost_reconciliation.py`
3. `reports/G4_PHASE5_PROJECT_COST_RECONCILIATION_IMPLEMENTATION_20261031.md`

SHA-256: implementation `f4aeef0f956a601128e356a38e05ee4c607fc1e3b0f982485cf518bed0fd5900`; tests `f012b8f6906a7d193d06c0fccb6b6f26c0c4b1d46ac69b92ca36c33c963b4da0`; implementation report `31832796cd64d363c7f6ef6853bec059f73f05c2abcce559d3ee4a3ca7ae3c55`.

The commit is a direct child of the required parent and contains no unrelated dirty material. `git diff --check` reported one Markdown trailing-space line in the committed implementation report (line 3, used as a Markdown line break); no code whitespace defect was observed.

## Independent tests

All commands were cache-free, bytecode-disabled, local-only and provider-free:

```text
python -m pytest -p no:cacheprovider tests/test_phase5_project_cost_reconciliation.py
8 passed in 1.97s

python -m pytest -p no:cacheprovider tests/test_phase5_project_cost_reconciliation.py tests/test_phase5_operator_health_catalogue.py tests/test_phase5_operator_health_runtime_contract.py
22 passed in 3.59s

python -m pytest -p no:cacheprovider tests/test_phase5_t4a9_sqlite_accounting_contract.py tests/test_phase5_t4a8_durable_accounting_export.py tests/runtime/test_currency_accounting.py
26 passed in 1.95s
```

The first two commands reproduce the claimed 8 focused and 22 combined results. The additional accounting/interface regressions also passed. No provider, model, source, spend, publication, bridge mutation, watcher or host-process action occurred.

## Verified behaviour

The implementation projects the existing `Phase5OperatorHealthCatalogueAdapter` snapshot and does not write the catalogue. On supported synthetic migration-29 fixtures it verifies or preserves:

- explicit multi-run and multi-cohort selection, run-missing diagnostics, subject/scope/provider/task/attempt/request/physical-attempt/receipt and provenance identifiers;
- exact non-negative `Decimal` aggregation and stable canonical JSON/SHA-256 output under repeated reads;
- separate actual-charge, reservation and estimate totals; reservations and estimates are not silently treated as incurred spend;
- receipt-linked actuals only when AUD amount, provider amount/currency, pricing and FX identifiers, receipt identity, runtime linkage, usage and non-ambiguous crossing checks pass;
- identical receipt replay de-duplication, conflicting receipt blocking, replayed-attempt marking, and explicit ambiguous-crossing/unreconciled records;
- stale/unsupported schema, missing requested run, missing price/FX/usage, unknown cost type, absent authenticated boundary and incomplete linkage as non-success states; and
- allowlisted safe projection with no raw prompt, payload, result body, credential or transport exception leakage and unchanged fixture bytes.

These are valid local diagnostics. The `authenticated` and `complete` boundary fields are caller-supplied assertions; this module does not authenticate an external ledger, verify provider exactly-once effects, or prove that the selected runs are the whole project.

## Persisted interface and semantic limitations

Migration 29 is the current declared runtime schema (`SUPPORTED_VERSION = 29`). Its existing cost, reservation, task-attempt, physical-attempt, request-item, delivery-attempt and provider-receipt tables are structurally readable through the adapter’s safe allowlist. The real local source-bearing catalogue was independently opened read-only with `mode=ro` and `query_only=ON`:

- DB SHA-256: `54516e8f211f584bbb6b84ff445179ed2df714c0b79d0cd454b960c563de4eaf`
- schema 27; 21 runs; 216 cost entries; 74 actual entries; 239 reservations; 163 receipts;
- direct persisted actual rows sum to AUD `3.046828`.

That catalogue is stale/unsupported and has no authenticated project-wide coverage boundary. The new reconciliation correctly returned `coverage=unknown`, `STALE_OR_UNSUPPORTED_SCHEMA`, `MISSING_REQUESTED_RUN` for the suppressed stale export rows, and `MISSING_PROJECT_WIDE_LEDGER`; it did not turn the direct observed amount into a current project total. Therefore actual project-wide incurred spend is **not known**. It must not be reported as zero. The approved AUD10 cumulative cap is not a ledger, route authority, pricing/FX authority, reservation, or proof of spend.

Important gaps not exercised by the green fixture count:

- the adapter’s `delivery_by_item` and the reconciliation’s `attempt_by_request` maps collapse multiple persisted delivery attempts to one row; replay history and conflicting multi-attempt receipt relationships can therefore be under-observed;
- cost linkage selects the first request for a task and falls back from a declared request receipt to the first receipt on the physical attempt without explicitly flagging contradictory request/attempt/physical receipt IDs;
- reservation rows are reported/summed as supplied, without the actual cost receipt de-duplication/conflict discipline or net release reconciliation;
- provider currency is shape-checked only, and pricing/FX IDs are presence checks. No source-owned provider contract, rate, invoice, project identity, FX rate or external exactly-once authority is present; and
- source/provenance identifiers are copied from the catalogue snapshot. They are lineage, not independent authority.

Consequently, the implementation is accepted as a bounded read-only diagnostic seam, not as production pre-send budget authority or a project-wide accounting attestation.

## Dirty baseline and ingress boundary

Before this report, Git reported 19 modified entries and 137 untracked entries, including historical evidence/scratch, unrelated Factory/T4A/T4E work and the four unadopted CGDOC1 ingress inbox files:

- `gate4_engineering_20261031-g4-doc-export-ingress-hardening-optin-v83-sol-1018-50f8ef0a.json`
- `gate4_engineering_20261031-g4-doc-export-second-ingress-dormant-v82-sol-0957-04ff9b8f.json`
- `gate4_engineering_20261031-g4-doc-export-second-ingress-independent-accept-v83-sol-1010-4cd6c671.json`
- `gate4_engineering_20261031-g4-doc-export-timeout-independent-review-v83-sol-1036-f0ec86.json`

Those runtime artifacts and historical scratch were inspected but not staged, adopted, modified, deleted or cleaned. The exact three-file commit did not absorb them. No private material, runtime database, cache, model response, prompt, credential, raw source or public projection was added by this task.

## North Star and Gate 4 impact

Direct North Star v0.3 sections are **13 Finances**, **14 Funding / dependencies**, and **20 Evidence / coverage / freshness / corrections**. Adjacent reusable evidence is relevant to **11 Scale / capability** (operational scale telemetry) and **19 Classification / search / AI discovery** (model-task economics and provenance). This is internal Builder operational evidence, not charity expenditure knowledge or a public release projection.

The Gate 4 industrialisation exit criterion for spend/cost telemetry remains **blocked/partial**: local deterministic aggregation and safe missingness pass, while current project-wide population, source-owned provider route, pricing/FX, authenticated cumulative ledger, live pre-send authority and provider-side effect reconciliation do not. Preserve the canonical Builder-to-65k position: Gate 1 CLOSED, Gate 2 ACTIVE, 12% earned. No Gate 4 credit or closure is earned by this report.

## Highest-value bounded successor

Supply one independently authenticated, source-owned project-ledger export covering the selected and historical runs, with provider contract/project identity, pricing and FX snapshots, reservation/release rules, receipt identity, exact coverage manifest and content hashes. Add a read-only adapter acceptance that rejects stale/mismatched scope and exercises multiple attempts and contradictory receipt identities. Separately, any CGDOC1 recovery should occur only on a clean target with the existing four ingress paths isolated and a dormant/default-off end-to-end acceptance; it is not evidence for this cost gate.

