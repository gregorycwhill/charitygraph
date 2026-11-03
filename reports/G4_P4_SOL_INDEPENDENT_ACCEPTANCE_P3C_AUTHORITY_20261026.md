# G4-O1C P4 independent acceptance and P3C authority mapping — 26 October 2026

Mode: provider-free, local, `REPORT_ONLY`. This is an independent review of
the already-untracked P4 module/test/report. No code or test files were
changed, and this report does not accept P3b2, close Gate 4, authorize a
provider, or establish production readiness.

## Verdict

**PARTIAL — ACCEPTED OFFLINE ONLY for the narrow pure projection behavior;
REJECTED as a reusable operations interface against current run/ledger
contracts.**

The projection is genuinely read-only, deterministic, content-hashed, and
privacy-allowlisted for well-formed caller-supplied mappings. The focused
tests and requested regression set pass. However, the evidence is fixture
driven: it does not prove direct consumption of the actual durable run/ledger
contracts, and the implementation rejects or misrepresents several current
economics/transport cases. It remains mock-only/demonstration product
progress, not live operations evidence.

## Controls and preservation

| Control | Independent result |
|---|---|
| Workspace/branch/HEAD | `C:\CharityGraph-clean\charitygraph`; `gate3-cg406-remediation`; `4b3fbcaeaace5170994da57a4fe502e6f450ba29` |
| HEAD tree | `627fafae46e097d4d4f8d67b57a385c374b0ab84` |
| Required report before review | absent; written once at this path |
| P4 module SHA-256 | `9bdf60728321cddf4c66eb7b2eb79b51920c7d6f6d5c158a6bb5ad91aa5db372` |
| P4 test SHA-256 | `869217891583433b0f719a1f1d75873f133a45be522e3e0416a8215747d35325` |
| Prior P4 report SHA-256 | `e9760a3cc60053f0e7f4a5e1f9c3fc0a20249178b2a7eb6fdc92663c4cd9f803` |
| Pre-report dirty/untracked inventory | 284 records; aggregate SHA-256 `80d2f6cf1f7082624e3d98b8012c9904608e74e0602158221dcce93b222b61b6` |

All pre-existing dirty/untracked paths, including the three P4 paths, were
preserved byte-for-byte. No stage, commit, reset, checkout, deletion,
watcher/process action, bridge/fence access, provider/network access, source
acquisition, spending, publication, or external mutation occurred.

The sibling Data authority files named by the repository instructions are not
present in this checkout. I did not access an external or sibling checkout.
The P3C mapping below therefore separates local Builder authority/current
code from the earlier in-repository archaeology; it does not claim a fresh
Data-authority read.

## Independent P4 inspection

`phase5_run_diagnostics.py` is a pure 470-line projection seam. It opens no
database, schedules no work, calls no provider, and persists no state. It
recursively rejects sensitive-looking input keys and binary floats, requires
run/provenance/item identity, canonicalises sorted JSON with compact separators,
and hashes the exact returned UTF-8 bytes (`:68-81`, `:318-320`, `:322-440`).
Duplicate item IDs, duplicate reservations/cost-entry keys, unknown
reservations, currency conflicts, malformed decimals, contradictory summaries,
and over-cap observed concurrency fail closed. Output excludes prompts, source
text, credentials, and response bodies by allowlisting fields.

The acceptance matrix is:

| Area | Result | Evidence/shortcoming |
|---|---|---|
| Read-only boundary | **Pass offline** | Pure mapping/list construction; no I/O or mutation in module. |
| Canonical SHA-256 | **Pass offline** | Seven focused tests verify reordered equivalent input yields identical bytes/hash. |
| Decimal/no-float handling | **Partial** | Exact finite decimals work, but the implementation is not complete against the real ledger algebra below. |
| Subject/scope grouping | **Partial** | Groups supplied strings, but validates neither typed durable IDs nor ledger joins. The Standard test fabricates `subject-*` from request IDs and assigns one synthetic scope (`tests/test_phase5_run_diagnostics.py:126-131`). |
| Run/transport contract | **Partial** | Standard results are manually enriched; actual `ambiguous_crossings` from the coordinator is not consumed. A prior crossing is therefore reported as zero by the manual probe. Status values are any nonblank text, so `made_up_status` is accepted. |
| Stop/ambiguous/restart markers | **Partial** | Basic item/systemic/ambiguous/replayed cases pass, but no consistency check joins item flags, run stop, prior crossings, receipts, or resend evidence. |
| Ledger identity/no double count | **Partial** | Duplicate cost keys are caught, but duplicate task/attempt/receipt rows and orphan rows are accepted and merely counted. A probe with unrelated durable rows returned counts successfully. |
| Real accounting compatibility | **Fail for current contract** | `CostLedgerEntry` permits `adjustment` plus `adjustment_direction` (`contracts/economics.py:321-360`); P4 rejects it as unsupported. The current authority also permits actual overrun and separately exposes credits/adjustments (`economics.py:463-539`); P4 rejects actual+release above reservation (`phase5_run_diagnostics.py:261-268`) and does not include `other` in reconciliation. |
| Privacy | **Partial** | Output is allowlisted, but opaque-ID/reference format is not enforced; arbitrary sensitive text placed inside an accepted ID/reference would be emitted. |
| Rights/publication authority | **Not observed** | Explicitly outside this projection; the limitations field correctly says so. |

The seven tests therefore demonstrate a useful synthetic seam, not truthful
population metrics. The SQLite test creates a private five-table schema with
minimal columns (`tests/test_phase5_run_diagnostics.py:177-197`), not a
`SQLiteCatalog` snapshot or a validated `CostLedger`. The passing 108-test
regression set is valuable regression evidence, but does not remove these
contract gaps.

## Commands and outcomes

All commands used `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`,
`-o addopts= -p no:cacheprovider`, and basetemps outside the checkout:

```text
`$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-independent-focused-20261026-01 tests/test_phase5_run_diagnostics.py`
7 passed in 0.72s

`$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-independent-regression-20261026-01 tests/test_phase5_run_diagnostics.py tests/test_phase5_standard_transport.py tests/test_phase5_factory.py tests/test_phase5_governed_factory_integration.py tests/test_source_rights.py tests/test_phase5_governed_factory_rights.py tests/runtime/test_task_state.py`
108 passed in 13.29s

`$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\CharityGraph-runtime\g4-p4-independent-economics-20261026-01 tests/runtime/test_budget_ledger.py tests/runtime/test_currency_accounting.py`
8 passed in 1.84s
```

Read-only probes additionally showed: arbitrary status accepted;
unrelated task/attempt/receipt rows accepted; actual-contract adjustment
rejected as `unsupported accounting entry type`; a legitimate actual overrun
rejected as `accounting actuals and releases exceed reservation`; and a run
with `ambiguous_crossings=1` reported zero crossings.

## P3C authority mapping and smallest safe next tranche

Local Builder authority says governed decisions/observations are durable
knowledge authority while SQLite is mutable, rebuildable operational state
(`ARCHITECTURE.md:64-80, 318-327, 355-369`). Current rights tables are created
by `ARTIFACT_RIGHTS_TABLE_SQL` and `_ensure_artifact_rights_tables()` in
`runtime/catalog.py:77-124, 450-496`, outside numbered `MIGRATIONS`, which end
at v28 in `runtime/migrations.py:1192-1223`. Rights material is persisted in
SQLite `material_json` with hashes/events; there is no independent
content-addressed governance-record import/export authority in the current
path. There is no database-enforced unique current decision for each exact
representation; application preflight detects competing current decisions.
The preflight check occurs before Factory planning, not at the future provider
boundary. These findings agree with the earlier P3 archaeology and are not
retroactive acceptance of quarantined P3b2.

No code tranche is safe until Product Owner/Data authority resolves the
durable rights-record contract. The precise decision must name: (1) canonical
record ID/schema and content-addressed bytes; (2) binding to source artifact,
source record, source role, exact representation hash and policy versions;
(3) status, supersession, current-uniqueness and expiry/revalidation rules;
and (4) migration, rebuild and provider-boundary read semantics.

Concrete options are:

1. **Recommended:** external/versioned content-addressed governance records
   remain authority; SQLite becomes a rebuildable indexed projection with a
   numbered migration, uniqueness constraint, and immediate pre-provider
   revalidation. This preserves existing source-evidence/publication
   boundaries and is the clearest recovery path.
2. Make the numbered SQLite schema the canonical rights authority. This is
   smaller operationally, but conflicts with the existing “SQLite is not sole
   evidence authority” boundary and needs explicit Data/Product Owner approval.
3. Keep append-only SQLite `material_json` as the only durable decision
   record and add constraints/revalidation. This is least disruptive but
   leaves rebuild/evidence authority and cross-product portability unresolved;
   it is not recommended.

After option 1 is approved, the smallest engineering tranche should be
explicitly allowlisted and begin with these currently absent paths only:

```text
src/charitygraph/runtime/rights_governance_record.py
tests/runtime/test_rights_governance_record.py
reports/G4_P3C_RIGHTS_GOVERNANCE_MIGRATION_20261026.md
```

That tranche should define/verify canonical bytes, record import/export,
hash/idempotency, supersession and exact-representation binding without
provider calls. A subsequent separately authorised migration tranche must
touch only clean, supervisor-promoted versions of `runtime/migrations.py`,
`runtime/catalog.py`, `phase5_governed_factory_integration.py`, and their
dedicated tests; it must add transactional current-decision uniqueness and a
rights revalidation immediately before the actual provider crossing. If the
authority decision is not made, the safe next action is a decision record,
not implementation. A harness failure is not a substitute for that policy
decision.

## Promotion and remaining Gate 4 evidence

The P4 module/test/prior report are untracked preserved worktree files. Safe
promotion is a supervisor action: first record the unchanged dirty inventory,
then explicitly re-allowlist exactly those three paths, independently verify
their bytes and tests, and stage only those paths in a dedicated commit. Do
not use broad add commands. If bridge guards reject re-allowlisting paths that
were untracked after the prior task, retain them uncommitted and create a new
bounded promotion window/allowlist; do not bypass the guard or include other
dirty paths. This review made no staging or commit attempt.

Gate 4 still lacks an industrialisation pilot over an approved real-provider
cohort, provider receipts and provider-side exactly-once/ambiguity evidence,
production multiworker scheduling, restart/resume SLOs, alerts and operator
diagnostics, approved subject/source cohort and cost/economics acceptance,
rights revalidation at the provider boundary, and Product Owner/Data closure.
The P4 artifact can become a useful offline diagnostic adapter after the
contract fixes and real-run/ledger integration tests; it is not presently a
reusable production operations interface or Gate 4 closure evidence.

The report’s own post-write SHA-256 is supplied in the worker handoff rather
than embedded here, avoiding a self-referential hash.
