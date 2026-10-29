# Gate 4 E3 private five-charity answer brief

Date: 2026-10-30 (Australia/Sydney)
Disposition: **DELIVERED — private derivative; not Gate 4 closure**

## What was delivered

`phase5_t4c_private_answer_brief.py` composes the accepted E2B
`AnswerProjection` without reopening SQLite, reading source bodies, acquiring
anything, or copying the E2B T3 authority constants. It produces five subject
briefs, all 15 E2B answer slots, ten source-record/hash bindings, a comparison
view, and a 20-section coverage map. Display labels are optional metadata;
`subject_id` and `scope_id` remain the identity fields.

The fenced inputs were branch `gate3-cg406-remediation`, HEAD
`6442e9abdc39d40d55b1653a1b98b24dfa78821b`, fence `v63`, SHA-256
`a5d598ab2d3509c2a95506a4d225d2a4f3d0f661d7ae4e91dca5d64290f99095`, the
accepted T3 selected manifest SHA-256
`41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`, and
the ten local representations consumed by E2B.

## Human-readable evidence sample

All supported values below are E2B source-native facts or mechanical counts;
they retain `subject_id`, `scope_id`, source family, source record, exact
representation SHA, field basis, reporting date/period, and the E2B label
`fact` in the adapter output. The display names are only for readability.

### Guide Dogs NSW/ACT

- Subject: `subject:02649cdcb42049bb8dedd30f2333e150`; scope:
  `scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248`.
- Activity fact: 10 named programs; operating in New South Wales and the
  Australian Capital Territory; country Australia; 13 named beneficiary
  categories. Source: `acnc_register`,
  `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d`,
  representation SHA
  `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2`,
  source date `2025-12-18T23:31:00.0000000Z`; field basis
  `$.Programs[].Name`, `$.OperatingInStates[].Name`, `$.Countries[].Name`,
  `$.Beneficiaries[].Name`.
- Reporting-period fact: 1 July 2024–30 June 2025; receipts `$51,977,920`,
  expenses `$52,253,502`, net surplus/deficit `-$275,582`; employees
  `208/94/40` (full-time/part-time/casual), unpaid volunteers `849`.
  Source: `acnc_ais_bundle`,
  `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a`,
  representation SHA
  `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b`,
  AIS period `2024-07-01T00:00:00.0000000Z` to
  `2025-06-30T00:00:00.0000000Z`; field basis
  `$.FinReportFrom`, `$.FinReportTo`, `$.FinReportingType`,
  `$.IncomeTotalReceipts`, `$.ExpenseTotal`, `$.NetSurplusDeficit`,
  `$.HrFullTimeEmployees`, `$.HrPartTimeEmployees`,
  `$.HrCasualEmployees`, `$.HrUnpainVolunteers`.
- Current giving terms, current capacity, outcomes/effectiveness, governance,
  and conduct/adverse history are **unanswered**. This is source silence in
  the retained E2B evidence, not a negative or clean finding.

### OzHarvest

- Subject: `subject:1823309bdd06417c9928033603cb6e39`; scope:
  `scope:95767a26704b78a0c75411dbb3322b5076ed5874fc56e335e5a9e20ea4ac0d4a`.
- Activity fact: 6 named programs; 8 Australian states/territories; country
  Australia; 25 named beneficiary categories. Source: `acnc_register`,
  `srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4`,
  representation SHA
  `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78177ceef45170e6`,
  source date `2025-12-14T23:11:19.0000000Z`; field basis
  `$.Programs[].Name`, `$.OperatingInStates[].Name`, `$.Countries[].Name`,
  `$.Beneficiaries[].Name`.
- Reporting-period fact: 1 July 2024–30 June 2025; receipts `$31,880,971`,
  expenses `$33,375,185`, net surplus/deficit `-$1,494,214`; employees
  `118/137/115` (full-time/part-time/casual), unpaid volunteers `2,085`.
  Source: `acnc_ais_bundle`,
  `srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52`,
  representation SHA
  `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb`,
  AIS period `2024-07-01T00:00:00.0000000Z` to
  `2025-06-30T00:00:00.0000000Z`; field basis is the same ten AIS paths
  listed in the Guide Dogs sample.
- The same five currentness dimensions remain **unanswered**, with source
  silence explicitly preserved.

## Five-subject comparison

These are source-reported measures, not a ranking. Reporting periods and
accounting bases differ: Human Appeal and Islamic Relief report calendar 2025;
Guide Dogs, Peter & Lyndy White, and OzHarvest report July 2024–June 2025.
Peter & Lyndy White uses special-purpose financial statements. No efficiency,
effectiveness, suitability, current availability, or giving-term conclusion is
drawn.

| Display label | Subject ID | Programs | Named states | AIS period | Receipts | Expenses | Net surplus/deficit | Employees FT/PT/casual | Unpaid volunteers |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| Guide Dogs NSW/ACT | `subject:02649…e150` | 10 | 2 | Jul 2024–Jun 2025 | $51,977,920 | $52,253,502 | -$275,582 | 208/94/40 | 849 |
| Human Appeal International Australia | `subject:0889…5c03` | 4 | 0 | Jan–Dec 2025 | $40,400,264 | $39,506,382 | $893,882 | 48/0/0 | 150 |
| Peter & Lyndy White Foundation | `subject:16fba…8b8d` | 2 | 1 | Jul 2024–Jun 2025 | $78,917,379 | $27,721,425 | $51,195,954 | 0/1/0 | 2 |
| OzHarvest | `subject:1823…e39` | 6 | 8 | Jul 2024–Jun 2025 | $31,880,971 | $33,375,185 | -$1,494,214 | 118/137/115 | 2,085 |
| Islamic Relief Australia | `subject:1a9e…e31b` | 10 | 1 | Jan–Dec 2025 | $25,561,829 | $26,230,877 | -$669,048 | 13/6/2 | 250 |

The comparison values are all citation-bearing `CitedValue` objects in the
adapter, not free-floating table numbers. The two rows with nested source
layout retain `$.data.<field>` basis where that is what E2B supplied.

## Ten source hash bindings

| Subject ID | Scope ID | Register source record / representation SHA | AIS source record / representation SHA |
|---|---|---|---|
| `subject:02649…e150` | `scope:0a100…d63248` | `srcrec:4978c7…bcd28d` / `f7b052…f0ada2` | `srcrec:554fa9…326f08a` / `70734f…e878f1b` |
| `subject:0889…5c03` | `scope:be9c7f…640913` | `srcrec:f05f13…c251d2` / `8382a8…4234773` | `srcrec:045161…95237f8` / `ea9b75…438ab33` |
| `subject:16fba…8b8d` | `scope:dd27dd…dc6e81` | `srcrec:188a39…b91dd8a` / `ead4a7…24f925c` | `srcrec:5cc396…6fda25` / `964948…e9678` |
| `subject:1823…e39` | `scope:95767a…ac0d4a` | `srcrec:5e1c9a…01adf4` / `1ba64e…5170e6` | `srcrec:e94d13…5c0c52` / `692829…e07eb` |
| `subject:1a9e…e31b` | `scope:e71cd1…d46aa1` | `srcrec:e6529d…737544c` / `a0f9c0…eac74c` | `srcrec:39443d…f4aea9` / `b02a40…63f0b7f` |

The abbreviated table is only a reading aid; the full exact strings remain in
the E2B records and the adapter's `source_hash_bindings` field.

## North Star v0.3 coverage and missingness map

Codes: `S` = supported by the bounded E2B projection; `P` = partial or
scope-limited source-native support; `M` = unassessed in this derivative. `M`
does not mean the charity lacks the field. The same code applies to all five
subjects because they share the same E2B slot contract; per-subject codes are
also emitted as `status_by_subject`.

| Section | Code | What is retained | Explicit missingness / boundary |
|---:|:---:|---|---|
| 1 Identity / regulatory | P | durable subject/scope IDs and source bindings | identity attributes and regulatory detail are outside E2B |
| 2 Purpose / cause | M | — | no purpose narrative selected |
| 3 Programs / services | P | named source-native programs | currentness, delivery party, access route |
| 4 Activities / SDGs | P | program classifications and activity fields | no SDG or independent activity assessment |
| 5 Geography / beneficiaries | P | named states, countries, beneficiaries | named is not the same as served or reached |
| 6 Participation | M | — | no participation proposition |
| 7 Direct service / capacity | M | — | current capacity, eligibility, throughput, waitlist |
| 8 Fundraising | M | — | current giving terms / offer |
| 9 Governance / leadership | M | — | governance and appointments |
| 10 People / workforce | S | AIS employee and unpaid-volunteer counts | roles, location, capability |
| 11 Scale / capability | P | selected programs, footprint and AIS measures | independent capability and constraints |
| 12 Relationships | M | — | no governed relationship edge |
| 13 Finances | S | AIS period, accounting basis, receipts, expenses, result | no independent reconciliation |
| 14 Funding / dependencies | M | — | dependency, concentration, conditionality |
| 15 Ethos / values | M | — | no values assessment |
| 16 Conduct / adverse | M | — | not assessed; no clean-record claim |
| 17 Notable history | M | — | no broader history review |
| 18 Evaluation / outcomes | M | — | no evaluation, outcome or effectiveness evidence |
| 19 Classification / search / AI discovery | P | source-native program classifications | no CharityGraph discovery decision |
| 20 Evidence / coverage / freshness / corrections | S | exact citations, hashes and missingness | reviewed universe is only these ten representations |

## Answerability and boundary result

The five subjects have 10 supported source-native slots (activity and scale)
and 5 explicitly unanswered currentness slots. The adapter preserves all
three E2B labels: supported records remain `fact`; the currentness records
remain `not_applicable` with `source_silence_is_not_absence: true`; no source
statement or unrestricted-prose inference is introduced. Program counts and
the comparison measures are mechanical selection/counting only.

Focused verification: `19 passed` across the new E3 test and the E2B focused
test. The E3 tests exercise five subjects, 15 slots, ten hash bindings,
deterministic replay, provenance and periods, explicit missingness, tampered
hash rejection, unknown-label rejection, and non-zero-side-effect rejection.

The derivative is private and read-only. It performed no provider/model or
network calls, source acquisition, budget reservation/spend, SQLite/WAL/SHM
access, publication, canonical promotion, public release, GitHub action,
watcher control, or follow-on dispatch. Pre-existing dirty and untracked paths
were preserved; only the new module, its focused test, and this report are
allowlisted outputs.
