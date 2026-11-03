# G4 T4A9 timeout and partial SQLite export forensics

Date: 2026-10-30 (Australia/Sydney)  
Worker: fresh bounded G4-O1C, report-only, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD: `b3e01793100b9c92e992559187a3177db650662b`  
Fence: `v58` / `9ca4ce44dc90eeb11640b3456e08d997d9be469d78590ad82e6f8c415b6567c6`

## Disposition

**PARTIAL — salvageable mechanical semantics, not acceptable as a factual
project-wide accounting export.** The partial source is syntactically valid,
read-only by construction, deterministic in its in-memory outputs, and
fail-closed around several graph, currency, coverage and authority conditions.
It is not independently trusted, does not establish current project-wide
coverage, and does not authorize a provider call, reservation, send or gate
closure.

No project-wide budget attestation is made here.

## Authority grounding

Read before review: local `AGENTS.md`, `ARCHITECTURE.md` and
`BUILDER_MACHINERY.md`; Data `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`,
`NORTH_STAR_TARGET_CARD_V0_3.md`, `COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`, `SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md` and `TEST_PLAN.md`;
and the prior T4A8R independent review. Applied here: Python may check exact
schema, identifiers, joins and arithmetic, but source authority, coverage,
missingness and trust remain separate and no empty result is treated as zero.

## Immutable-run evidence

The local bridge result identifies the timed-out instruction as
`gate4:engineering:20261030-g4-t4a9-readonly-sqlite-accounting-export-sol-1306-d25e`,
with source SHA-256
`802ed182c8c2423703b3c86cac3143e92c8b479e8ccee93166599d84c3f6ca64`,
`provider_calls: 0`, `publication: false`, `source_acquisition: false`, and
`execution_state: CODEX_EXECUTION_TIMEOUT`. Its recorded execution window was
13:07:03.474924Z to 13:17:04.637337Z: the 600-second bridge deadline.

The execution directory contains only `codex-output.jsonl` (1,400,572 bytes,
SHA-256
`4e605e309645d9c9d4c6438950eef812b7ad8456745e8958ce19762a09d527bd`). The
recorded `codex-last-message.txt` path does not exist, and no prior engineering
report exists.

The parsed stream contains 57 JSON events: 1 `thread.started`, 1
`turn.started`, 25 `item.started`, and 30 `item.completed`. It records:

- repository/instruction/schema archaeology;
- creation and revision of only the two partial target files;
- historical focused pytest results of 6 passed, then 7 passed, using external
  basetemp directories with bytecode and pytest cache disabled;
- a completed hash/status check, including `all=330`, `preexisting=328`,
  `modified=11`, `untracked=317` after excluding the two partials and the
  intended report; and
- no completion event for the report write. At 13:16:30.647622Z the model
  stream logged an idle-websocket disconnect and retry. At 13:16:56.131385Z
  an `apply_patch` verification error was logged; the final event was a
  started-but-uncompleted report file-change item.

This is evidence of progress to the reporting boundary, followed by a
tool/transport failure near the hard deadline, not evidence of a stalled
accounting operation. The likely contributors to the deadline were very large
instruction/schema output, two full focused test runs, final reconciliation,
the failed patch verification, and the websocket retry. This is an
engineering forensic inference, not a bridge assertion.

## Workspace and partial-file preservation

The fresh baseline observed before this report was 330 porcelain entries: 11
modified tracked paths and 317 pre-existing untracked entries outside the two
partial targets. The only target statuses are `??` for the two partial files;
the report path was absent. HEAD and branch remain exact. The bridge
attestation recorded two changed paths, zero unexpected paths, no local or
bridge-owned commit, and `verified: true`.

The partials were read, not edited, removed, renamed, staged, reset, executed
as product, or recreated. Current identities are:

| forensic file | bytes / lines | SHA-256 |
|---|---:|---|
| `src/charitygraph/phase5_t4a_sqlite_accounting_export.py` | 39,634 / 668 | `ae44e25a1eb7aa123da2151dd32f136aca14d04287631dec1e2a7e416e35a8a8` |
| `tests/test_phase5_t4a_sqlite_accounting_export.py` | 11,000 / 198 | `db395f8d6ae7c005f3c98570cb9e1ee355ffeb964899b861c810916a4dc71a1d` |

The one fresh permitted collection check was:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest --collect-only -q -p no:cacheprovider -o addopts='' --basetemp C:\CharityGraph-runtime\g4-t4a9-forensics-20261030-01 tests/test_phase5_t4a_sqlite_accounting_export.py
```

Result: **7 tests collected in 0.85s**. No test body ran and no repository
runtime database was opened or modified by this review.

## Independent partial-source inspection

Both files parse with Python AST syntax `OK`. The source imports only standard
library modules plus existing `canonical_json_bytes`, T4A project-budget
snapshot machinery, and runtime migrations. It defines one frozen result
dataclass, `extract_sqlite_accounting_source(...)`, and deterministic helpers.
The test module defines seven tests and exercises the source API plus two
private helpers. The imported paths exist and the API shape is coherent for a
synthetic fixture; historical worker execution also recorded both focused
passes as passing. That is salvage evidence, not acceptance evidence.

The source references this table/column contract:

| group | tables and selected columns |
|---|---|
| migration | `schema_migrations(version,name,checksum,applied_at)` |
| accounting | `cohorts(cohort_id,budget_cap_amount,accounting_currency)`; `runs(run_id,cohort_id,run_kind,status,created_at,updated_at)`; `tasks(model_task_id,run_id,subject_id,scope_id,cohort_id,task_type,task_schema_id,provider_id,model_snapshot,status,attempt_count)` |
| attempts/reservations | `task_attempts(task_run_id,model_task_id,attempt_number,status,provider_request_id,provider_batch_id,pricing_snapshot_id,fx_snapshot_id,reservation_id,usage_json)`; `budget_reservations(reservation_id,cohort_id,run_id,reserved_amount,status,accounting_currency)`; `reservation_tasks(reservation_id,model_task_id)` |
| money | `cost_entries(entry_key,cohort_id,run_id,task_run_id,reservation_id,entry_type,provider_amount,provider_currency,aud_amount,adjustment_direction,pricing_snapshot_id,fx_snapshot_id,usage_json,accounting_amount,accounting_currency)` |
| physical/provider graph | `physical_attempts`; `physical_attempt_members`; `provider_request_items`; `delivery_jobs`; `provider_receipts`; `provider_request_attempts`, using the identifiers and linkage columns named in source lines 77–116 |
| optional authority | probes for `pricing_snapshots`, `pricing_records`, `fx_snapshots`, and `fx_records` |

Against the current migration source (SHA-256
`75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c`), the
required columns are present at supported version 29. The actual schema also
contains source columns that the partial does not export, including
`provider_receipts.raw_result_ref`, `provider_receipts.usage_json`,
`provider_request_items.result_ref`/`usage_json`, delivery timestamps and
payload metadata, provider-attempt usage/failure fields, and
`cost_entries.provider_invoice_ref`. The partial therefore produces a
deliberately reduced projection, not a lossless source dump.

Most importantly, the current migration set defines no pricing or FX authority
tables. It persists pricing/FX IDs on attempts, costs and jobs, but the
authority records are absent. The partial notices this and marks pricing
coverage incomplete (`pricing_fx_authority_records_unavailable`) rather than
turning missing authority into zero or a positive claim. Its source hash and
project-wide coverage are caller-supplied assertions; they are not recomputed
from a live exported catalogue.

The source does enforce or attempt to enforce useful mechanics: SQLite URI
`mode=ro`, `PRAGMA query_only=ON`, migration identity, required columns,
orphan/linkage checks, duplicate physical-attempt detection, AUD arithmetic,
unpriced actual detection, explicit coverage flags, canonical evidence and
manifest bytes, and negative `independent_trust`/send fields. These semantics
are consistent with the local architecture and Data governance rule that
source, evidence, candidate, decision, canonical observation, coverage and
derivative states remain separate and that missingness is not zero.

## Unexpected activity and authority boundary

The historical test fixtures necessarily created synthetic SQLite databases
under the two external basetemp directories and applied the catalogue schema
there. That is expected test activity, not a product/runtime export. The event
stream and bridge attestation show no provider/model/network/credential call,
source acquisition, publication, unexpected path, report completion, schema
change to the repository runtime, or real-send authority. No factual
cumulative AUD10 position is inferred.

The T4A8R independent review remains applicable: the prior caller-bound
adapter was only `PARTIAL`, had no live project-wide source view, and rejected
budget, pricing/FX, provider-route and real-send conclusions. This review does
not upgrade those dispositions.

## Smallest distinct successor (recommendation only)

Within 600 seconds, use a clean, distinct pure-contract slice with exactly
these allowed new paths:

- `src/charitygraph/phase5_t4a9_sqlite_accounting_contract.py`
- `tests/test_phase5_t4a9_sqlite_accounting_contract.py`
- `reports/G4_T4A9_SQLITE_ACCOUNTING_CONTRACT_SUCCESSOR_20261030.md`

Limit the slice to deterministic mapping validation for the
`cost_entries` → `provider_request_items` → `provider_receipts` and
`task_attempts` identity chain. Use fixture mappings only; do not open a
catalogue, add schema, acquire sources, call a model/provider, reserve budget,
or infer zero from an empty or absent table. Require caller-supplied authority
and provenance without self-pinning source authority. Preserve unknown,
unpriced and incomplete states explicitly. Test only the new module's pure
contract cases plus no-write/no-network guards. The two partial files above
remain byte-preserved forensic evidence and must not be imported, edited,
removed, staged, renamed, reset, absorbed or used as the successor's source.

This report is diagnostic only. It does not authorize adoption, commit,
promotion, publication, provider transmission, gate closure or follow-on
dispatch.
