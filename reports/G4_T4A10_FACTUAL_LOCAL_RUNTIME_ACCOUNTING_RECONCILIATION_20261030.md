# G4 T4A10 factual local runtime accounting reconciliation

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, read-only  
Branch: `gate3-cg406-remediation`  
HEAD: `a850f8104cf3e3f9150df27c4671ab084ba0453e`  
Fence: `v60` / `849f55679e1609e06d9e7e49b9226d72ecbd0b218f803a5a0358d9f7f7f73715`

## Result

**No COMPLETE current project-wide accounting snapshot exists in the inspected
local material.** The source-bearing runtime catalogue is **PARTIAL**: it is
stale, schema 27 rather than migration 29, lacks a project-wide coverage
manifest and independently authoritative pricing/FX/route records, and still
contains planned, ready, active and in-progress work. Migration-29 databases
found in the permitted local runtime are test fixtures or bounded offline
rehearsals, not independent current project facts.

No provider/model/network/credential call, source acquisition, budget
reservation, spend, publication, release, GitHub/Drive mutation, watcher or
process management occurred. No send ticket or send authorization was
produced.

## Authority and reproducibility

The required local and sibling authority documents were read before inspection:
`AGENTS.md`, `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, Data
`DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`, `NORTH_STAR_TARGET_CARD_V0_3.md`,
`COVERAGE_LLM_ECONOMICS_AND_OPEN_CURATION_POLICY.md`,
`INTEGRATED_PRODUCT_AND_DATA_MODEL.md`,
`SOURCE_EVIDENCE_AND_PUBLICATION_GOVERNANCE.md`,
`TAXONOMY_AND_SCHEME_GOVERNANCE.md`, `IMPLEMENTATION_PLAN.md` and
`TEST_PLAN.md`.

Relevant source hashes observed:

| Material | SHA-256 |
|---|---|
| `src/charitygraph/runtime/migrations.py` | `75b257c5756dd49155a4b11f0acd7dc32b45f86d5a27981e339a154f2661380c` |
| `src/charitygraph/runtime/catalog.py` | `3e1a4cea7994f141778d74b767f026ce80dcabe21592de597f7b01a8260383b1` |
| `phase5_t4a9_sqlite_accounting_contract.py` | `0774def89df1e1fdba73dd317ad347fa7eaed5ed71b2863a95914f42f1150d9b` |
| `phase5_t4a_durable_accounting_export.py` | `6fc68a6a1ccbca9f8188c38d36286505f34af100882f8ca34264b32590395fe0` |
| `phase5_t4a_project_budget_snapshot.py` | `ac202755d4a42ed812a03b80688f239abb1763f110fa2bc684132b499a37e24f` |
| `phase5_t4a_budget_attestation.py` | `14324f22ba94aa374adae6c82402c4cb0d40610213a9522de523bb05b3e436fc` |

`migrations.py` declares `SUPPORTED_VERSION = 29`; migration 29 is only the
rebuildable private rights projection. It does not create pricing or FX
authority tables. The catalogue default path is
`<runtime_root>\state\charitygraph.sqlite3`; SQLite is operational state, not
the evidence authority.

## Database inventory

All opened databases used SQLite URI `mode=ro` and `PRAGMA query_only=ON`.
Counts below are observed rows, not attestations. Paths are abbreviated to
local roots where they are runtime-sensitive.

| Local database | File SHA-256 | Schema | Authority classification |
|---|---|---:|---|
| `C:\CharityGraph-runtime\state\charitygraph.sqlite3` | `54516e8f211f584bbb6b84ff445179ed2df714c0b79d0cd454b960c563de4eaf` | 27 | Source-bearing operational catalogue; stale/partial, not a current project snapshot. Last DB write: 2026-09-26. |
| `runtime/gate4-autonomous-loop-20261020/builder.sqlite3` | `92506cc798c8b12bb5fe96358c90270dee7eb98d16c65124dc6bb04be305cd07` | 28 | Fake-provider rehearsal; not independent source-owned fact. |
| `runtime/gate4-autonomous-loop-20261020-commit2/builder.sqlite3` | `f5f06b92535e1d39be2befbbd3a9ca1af3a7f9cfccdd84692409a2c9a950c95f` | 28 | Duplicate/second fake-provider rehearsal; not independent source-owned fact. |
| `C:\CharityGraph-runtime\g4-t4a9-focused-02\...\accounting.sqlite3` | `40d33aca7e9dabe42b5609f4ed0065da33fad4ba9568d5ebe9080c8314418d40` | 29 | One-row synthetic T4A9 fixture (`provider:offline`); caller fixture, not authority. |
| `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\catalog.sqlite3` | `b0f31dc8da88cb11bac0e86b70e5cd545e36b5fc8b6af425b1d4f2657eea3962` | 29 | Ten-row ACNC source/rights probe with zero accounting rows; not a project ledger. |

The live bridge database at
`runtime/g4-o1b-controlled-cutover-20261020/bridge/bridge.sqlite3` was not
opened or hashed because it was process-locked and is bridge-owned, not a
Builder accounting authority. It was excluded from the evidence base.

## Source-bearing catalogue facts

The schema-27 source-bearing catalogue contains 11 cohorts, 21 runs, 202
logical tasks, 79 task attempts, 239 reservations, 216 cost entries, 192
physical attempts, 186 request items, 192 provider attempts, 163 receipts,
98 delivery jobs, 1,097 acquisition receipts, 1,043 source records, 906
evidence locators and 405 artefact-index rows. Source provenance is present as
catalogue records: 27 source definitions, 1,081 available acquisitions, 7
failed, 1 partial and 8 unavailable. The source-record families include
admitted families such as ACNC, ATO/ABR, annual reports, official websites,
PFRA and Wikipedia/Wikimedia, alongside historical/non-admitted records. This
does not make the accounting population complete or re-authorize acquisition.

Observed run status: 15 failed and 6 planned. Observed task status: 47
`failed_terminal`, 123 `ready`, and 32 `succeeded`. Reservations: 93 active,
8 consumed and 138 released. These are evidence of unresolved/currently
unsettled runtime state, not zeroes.

Observed accounting totals within this one stale catalogue are:

| Record class | Rows | Observed AUD amount |
|---|---:|---:|
| `actual` cost entries | 74 | 3.046828 |
| `reservation_release` entries | 142 | 7.431865 |
| active reservations | 93 | 1.721402 |
| consumed reservations | 8 | 0.555644 |
| released reservations | 138 | 9.724654 |

These are not a cumulative project-wide AUD10 attestation. They cannot be
combined with other runtime databases, and an empty/missing authority record
must not be interpreted as zero AUD.

## Attempt/receipt/linkage reconciliation

Within the existing schema-27 rows, mechanical joins are internally
consistent for the rows present: all 186 request items have a delivery job
with matching run, provider and route; all 192 provider attempts have their
request-item/job links; and all 192 physical attempts have exactly one member
and exactly one provider attempt. The 192 physical statuses are 157
`validated`, 6 `receipt_persisted` and 29 `failed`; the 29 failed physical
attempts have no receipt, while the 163 receipts have distinct physical and
provider-request identities. This is a terminal-status observation, not proof
that omitted or future populations do not exist.

The provider route observed in persisted rows is provider `openai`, model route
`gpt-5.6-luna`, with standard and batch delivery. This is caller/runtime row
metadata, not trusted route authority. The catalogue has zero
`standard_transport_traces`, zero S0 attestation windows and zero source
runtime-authority rows. `delivery_jobs` has no project, endpoint or service
authority field. No selected provider project or endpoint is independently
established.

Pricing/FX IDs are present on the 74 actual cost rows and 32 successful task
attempts, but the database contains no pricing or FX authority tables. The
IDs are references without independently trusted price, rate, version or
source authority. Three failed task attempts lack pricing/FX IDs and five
lack provider request IDs; 123 tasks remain ready. Unknown/held status values
were not observed in this database, but coverage is still **UNVERIFIABLE**
because there is no project-wide population declaration and the runtime has
planned/ready/active/in-progress records.

## Complete-snapshot assessment

| Required element | Status | Evidence |
|---|---|---|
| Current project-wide snapshot with trusted source pin | **ABSENT** | No project ID/coverage manifest; source DB is schema 27 and last-written 2026-09-26. File hash is reproducibility metadata, not independent authority. |
| Provider attempt/receipt links | **PARTIAL** | Existing rows join mechanically; 192 attempts versus 163 receipts, with 29 failed attempts intentionally receipt-less; no population-completeness proof. |
| Cumulative actuals | **PARTIAL** | AUD 3.046828 observed in one stale catalogue only. |
| Reservations and ambiguous attempts | **PARTIAL** | Active/consumed/released rows exist; no complete project-wide reconciliation and no explicit unknown/ambiguous coverage assertion. |
| Selected provider/project/model/endpoint | **PARTIAL** | Provider/model/delivery route observed; project, service, endpoint and authority version absent. |
| Pricing and FX authority | **ABSENT** | IDs only; no authority tables or source-owned pricing/FX records. |
| Real-send authority | **ABSENT** | No send ticket, independent route authority or current rights/provider revalidation. |

The migration-29 fixtures do not change these statuses: their positive rows
are synthetic/caller-supplied, and the single-subject source probe has zero
accounting rows. No evidence of zero AUD is asserted for any excluded or
unopened population.

## Read-only safety note

The inspected WAL-mode databases had no WAL/SHM sidecars before the first
metadata check. Python read-only opening materialized zero-byte `-wal` and
32 KiB `-shm` sidecars for the five opened databases; no schema/data writes,
checkpoint or vacuum were issued. A cleanup attempt was rejected by the
execution policy, so those sidecars remain runtime artefacts and are not part
of this report or Git. The bridge database was not opened. Future inspection
should prefer a static copy/snapshot supplied by the runtime owner or a
read-only method proven not to materialize WAL sidecars.

## One bounded factual remediation

Produce one independently pinned, source-owned, provider-free snapshot from the
actual current runtime owner. It must declare project/run/cohort scope and
coverage, export every cohort/run/task/attempt/reservation/cost/physical/member/
request-item/delivery-job/provider-attempt/receipt row, and separately bind
pricing, FX and provider route authority. Mechanical acceptance is:

1. exact owner/path, file hash, schema/migration identity and as-of time are
   independently supplied and reproducible;
2. all rows are covered by the manifest, including active, failed, pending,
   held, ambiguous, unpriced and unknown states; no empty view is called zero;
3. every join and reverse link is checked, every actual has provider amount,
   currency, pricing and FX authority, and every route has provider/project/
   service/endpoint/model identity;
4. the snapshot passes the existing pure T4A9/T4A6/T4A7 validators while
   remaining `CANDIDATE_NOT_ATTESTED` until independent pin verification; and
5. the operation makes no database/schema/WAL mutation, provider call,
   reservation, acquisition, publication or send authorization.

## North Star boundary and private-material disposition

This work advances North Star v0.3 §20 (Evidence / coverage / freshness /
corrections) only at the Builder control-plane accounting/coverage level. It
does not establish charity knowledge for §13 Finances. Sections 1–19 remain
untouched as North Star subject knowledge, including identity, purpose,
programs, activities, beneficiaries, participation, service capacity,
fundraising, governance, workforce, capability, relationships, funding,
ethos, conduct, history, evaluation and classification/search.

The report contains no personal information, credentials, raw reports, source
bytes, prompts, model responses or private payloads. Existing dirty and
untracked files were preserved. No code or tests were edited, and no Gate 4
acceptance/closure or follow-on dispatch is claimed.
