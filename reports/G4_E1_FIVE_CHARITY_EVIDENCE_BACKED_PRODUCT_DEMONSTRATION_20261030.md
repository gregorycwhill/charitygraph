# G4-E1 five-charity evidence-backed product demonstration

Date: 2026-10-30 (Australia/Sydney)  
Worker: bounded G4-O1C, report-only, provider-free  
Branch: `gate3-cg406-remediation`  
HEAD: `ebd8fdb270863aab05642c76b10eff40b2a6872d`  
Immutable fence: `v61`, SHA-256 `c96b1a435d3b4c5b806c97e597dc868cf146a561b4611db7a5549daf79b069a6`

## Disposition

**REAL_EVIDENCE_DEMONSTRATED — bounded private preview.**

This report is a real-data product demonstration over the retained,
content-addressed ACNC register and AIS representations for all five subjects
in the approved five-charity subset. It demonstrates that Builder can answer a
small set of useful charity questions from source-native representations while
keeping source identity, subject/scope, dates, source facts, first-party claims,
inferences and missingness separate.

This is not a canonical-observation promotion, model run, public projection,
publication or complete North Star assessment. The preview is limited to the
ten retained ACNC representations inspected below. The T3 rights records
authorize local private processing; provider transmission is blocked and
public redistribution remains not assessed.

## What was inspected

The exact T3 manifest is
`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json` (local
file SHA-256
`06d406393d5ee738e7bad2c8113a06302836e72d53bd06dd77a945bd4f7276d4`;
declared selected-manifest SHA-256
`41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`).
Its ten rows bind five subjects, one `acnc_register` representation and one
`acnc_ais_bundle` representation per subject. The manifest is identity and
lineage metadata; it is not treated as a source body.

I directly opened only the ten immutable JSON files under:

`C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\`

Each filename is its SHA-256, and a fresh local hash check matched every file.
No SQLite database, WAL, SHM or journal was opened; no existing file was
modified; no source was acquired; and no provider, model, credential, network,
Drive, GitHub, watcher or process operation occurred. The retained source
bytes were not available as a separate safe source archive in this task, but
the retained source-native representation files themselves were present and
readable, so the requested stop condition did not arise.

The local rights records in the same probe state, for all ten rows,
`rights_basis=public_source_private_processing`,
`local_retention.status=authorized`, `provider_transmission.status=blocked`,
and `public_redistribution.status=not_assessed`, under
`CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1` version `1.0.0`. These are private
processing permissions, not third-party licences.

## Evidence key

The following keys are used in every portrait and question answer. They are
exact local content-addressed locators, not URL-only references.

| Key | Source family / role | Subject and source record | Exact representation file and SHA-256 |
|---|---|---|---|
| Guide Dogs R | `acnc_register` / `register_identity` | ABN `52000399744`; `subject:02649cdcb42049bb8dedd30f2333e150`; `srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\f7\f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2`; SHA `f7b0522efbf6253cfa13713750a96100c601fd801fd209524f948dc134f0ada2` |
| Guide Dogs A | `acnc_ais_bundle` / `annual_information_statement` | Same subject; `srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\70\70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b`; SHA `70734f7c268aba097a37ab30c75640aca151583c2d616004cc90dffc0e878f1b` |
| Human Appeal R | `acnc_register` / `register_identity` | ABN `26164251245`; `subject:0889b4decb854e71ab4784479ca95c03`; `srcrec:f05f137023221378d486eef96e0c4efe377bb4811ac63fbbbb9aa8f103c251d2` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\83\8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773`; SHA `8382a8ca22b00b71244664d85d6db3d0bdc1bafa40192ffb437e6227c4234773` |
| Human Appeal A | `acnc_ais_bundle` / `annual_information_statement` | Same subject; `srcrec:045161751edf9950655698373906590d67abf2c35ba33dd804b61b3ac95237f8` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\ea\ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33`; SHA `ea9b75510efe03a1ef829bb5e044988de371d133c3bedbedb060914be438ab33` |
| Peter & Lyndy R | `acnc_register` / `register_identity` | ABN `52404606134`; `subject:16fba76fde2242d5870835b18b4e8b8d`; `srcrec:188a391cee048ab2fa7720aeb2c58f5b1e025039ef674ef8a6fd6ea0ab91dd8a` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\ea\ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c`; SHA `ead4a76bbbd9ad9aa29d79e82219b707d28f34d5232b00311544b8e6424f925c` |
| Peter & Lyndy A | `acnc_ais_bundle` / `annual_information_statement` | Same subject; `srcrec:5cc396995aea23edbab90c78b47101651f3a085f34ab088417dc3e1caa6fda25` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\96\9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678`; SHA `9649487585e0267792c3b9c7ffa36261f0a5e93e69e87cac3e7f8154622e9678` |
| OzHarvest R | `acnc_register` / `register_identity` | ABN `33107782196`; `subject:1823309bdd06417c9928033603cb6e39`; `srcrec:5e1c9ac1b0378a22557a9bf804697719133663123e7f603d76eb41fd2601adf4` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\1b\1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6`; SHA `1ba64e644b28ff4528f6b075d42babb34ad5ee66fa9ce78110077ceef45170e6` |
| OzHarvest A | `acnc_ais_bundle` / `annual_information_statement` | Same subject; `srcrec:e94d13fec302f9cefc42569b4d191dae5b360565c8c3d8b4e1cded8ece5c0c52` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\69\692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb`; SHA `692829d7188a787f2df3b91df982a2de34e6c86787b19d31d202737a072e07eb` |
| Islamic Relief R | `acnc_register` / `register_identity` | ABN `82147006639`; `subject:1a9ec5de3fc043ff9226fb95a6cae31b`; `srcrec:e6529d39e4cf32248a4792142cdc5e5bfb5cb45c5055180f35662344c737544c` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\a0\a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c`; SHA `a0f9c00f981fe7724262474f10212e08d3a775884055001181b06664c7eac74c` |
| Islamic Relief A | `acnc_ais_bundle` / `annual_information_statement` | Same subject; `srcrec:39443daa20d28eadd1164573c635a5c0aa2d89d3b7a8753b14f8321b90f4aea9` | `C:\CharityGraph-runtime\g4-t4a-single-subject-report-probe\representations\objects\sha256\b0\b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f`; SHA `b02a4079bd2ac8316123ad9ad7ff8cf9dfe3bf8832ac22bef6b2133d963f0b7f` |

`R` answers use only register fields. `A` answers use only AIS fields. Where
the AIS contains narrative, it is reported as a first-party source statement,
not independently verified fact. The register and AIS are both ACNC-source
representations and therefore agreement is source-family agreement, not
independent corroboration.

## Five private evidence-backed portraits

### 1. Guide Dogs NSW/ACT — ABN 52000399744

The register identifies a registered large charity established in 1961, based
in St Leonards NSW, with operating states NSW and ACT and a governed website
field. Its retained program set includes orientation and mobility, independent
living, connection, disability-inclusion training, access and technology,
information access, funding support, guide-dog training, canine court support
and therapy dogs, all classified in the register primarily as disability
services or animal therapy. (`Guide Dogs R`.) The AIS for statement year 2025
covers 1 July 2024–30 June 2025 and reports general-purpose simplified
disclosure statements: receipts `$51,977,920`, expenses `$52,253,502`, and
net surplus/deficit `-$275,582`. It reports 208 full-time, 94 part-time and
40 casual employees, plus 849 unpaid volunteers, and fundraising as `Yes`
with online fundraising `True`. (`Guide Dogs A`.)

Questions demonstrated:

1. **What does it do, and what kind of services are represented?** It states
   that it provides guide dogs and orientation and mobility services enabling
   people with low vision or blindness to move safely and independently; the
   register's program classifications add disability services and animal
   therapy. This is a source statement plus source-native program structure,
   not a CharityGraph effectiveness assessment. (`Guide Dogs A`; `Guide Dogs R`.)
2. **Where is the represented operating footprint?** The register supports
   NSW and ACT and the address is St Leonards NSW 2065. It does not establish
   service availability at every site or current intake. (`Guide Dogs R`.)
3. **What is the latest retained reporting-period scale?** For the 2025 AIS
   period, the source reports the receipts, expenses, result, employee counts
   and volunteer count above. It does not establish current capacity, waitlist
   or unit cost. (`Guide Dogs A`.)

### 2. Human Appeal International Australia — ABN 26164251245

The register identifies a registered large charity established in 2013, based
in Lakemba NSW, with beneficiary entries for children, youth, adults and
families, and countries including Afghanistan, Bangladesh, India, Indonesia,
Jordan, Lebanon, Nepal, Niger, Pakistan, Somalia, Sri Lanka, Yemen, Bosnia and
Herzegovina and Kyrgyzstan. Its four represented programs are Emergency Care,
Water Solutions, Health and Education Programs, and Orphan Sponsorship and
Community Development, with source classifications including emergency medical
services, clean water supply, health promotion and orphanages. (`Human Appeal R`.)
The 2025 AIS describes humanitarian aid for people affected by conflict and
global disasters, covers 1 January–31 December 2025, and reports special-purpose
statements: receipts `$40,400,264`, expenses `$39,506,382`, net surplus/deficit
`$893,882`, 48 full-time employees and 150 unpaid volunteers. Fundraising is
`Yes` and online fundraising `True`. (`Human Appeal A`.)

Questions demonstrated:

1. **What does it represent as its activity?** Humanitarian aid around the
   globe for people affected by conflict and disasters, supported by the four
   named program records. The wording is a first-party AIS statement; no
   outcome or delivery-quality inference is made. (`Human Appeal A`; `Human Appeal R`.)
2. **Which populations and geographies are actually named in the retained
   register?** Children, youth, adults and families are listed, together with
   the fourteen named countries above. The list does not prove that every
   program currently operates in every named country. (`Human Appeal R`.)
3. **What is the latest retained reporting-period scale?** The 2025 AIS
   supports the receipts, expenses, result, 48 full-time employees and 150
   volunteers above. Current program availability and humanitarian reach are
   unanswered by these two bodies. (`Human Appeal A`.)

### 3. The Peter & Lyndy White Foundation — ABN 52404606134

The register identifies a registered large charity established in 2019, based
in South Yarra VIC. It represents Social Housing Projects across Benalla,
Wangaratta, Shepparton, Euroa, Tatura, Numurkah and Wodonga, plus Crisis relief
in the City of Casey; the source classifications are social housing and
homeless services. Its register narrative says it works with not-for-profit
housing providers to build social housing for people at risk of homelessness
and provides some emergency crisis relief. (`Peter & Lyndy R`.) The 2025 AIS
covers 1 July 2024–30 June 2025, uses special-purpose statements, and reports
receipts `$78,917,379`, expenses `$27,721,425`, net surplus/deficit
`$51,195,954`, Australian grant/donation expense `$27,594,763`, one part-time
employee and two unpaid volunteers; fundraising is `No` and online fundraising
`False`. (`Peter & Lyndy A`.)

Questions demonstrated:

1. **What activities and program scopes are represented?** Social Housing
   Projects and Crisis relief, with the named Victorian locations and the
   register narrative above. The narrative is source-attributed and does not
   establish current construction or crisis-service availability. (`Peter & Lyndy R`.)
2. **What financial basis is retained?** The AIS gives a 2025 reporting period,
   special-purpose accounting basis, receipts, expenses, Australian grant/
   donation expense and result as stated above. These are source-native figures,
   not an independently reconciled funding or expenditure analysis. (`Peter & Lyndy A`.)
3. **Does the evidence establish a current donor-facing offer or service
   capacity?** **Unanswered.** The ACNC bodies show programs, a fundraising
   flag and financial measures, but no current giving terms, intake route,
   capacity, waitlist or delivery schedule. (`Peter & Lyndy R`; `Peter & Lyndy A`.)

There is a material representation tension: the AIS narrative describes social
housing and crisis-relief activity, while several structured activity flags are
false, including housing and social services. This is retained as a source
conflict/semantic limitation; the preview does not force a resolution.

### 4. Oz Harvest Limited — ABN 33107782196

The register identifies a registered large charity established in 2003, based
in Alexandria NSW, operating across all Australian states and territories. It
represents six programs: Food Rescue, Nourish, NEST, FEAST, Fight Food Waste
and Food Relief, with source classifications including food banks, food aid,
adult/basic education, STEM education and climate change. (`OzHarvest R`.)
The 2025 AIS covers 1 July 2024–30 June 2025 and states that OzHarvest collects
excess food, delivers it to more than 1,550 charities, operates 70 refrigerated
vans, rescues over 300 tonnes weekly from more than 2,600 food donors, and runs
free supermarkets, a free restaurant and three education programs. These are
first-party reported metrics. The same AIS reports general-purpose statements:
receipts `$31,880,971`, expenses `$33,375,185`, net surplus/deficit
`-$1,494,214`, 118 full-time, 137 part-time and 115 casual employees, and
2,085 unpaid volunteers; fundraising is `Yes` and online fundraising `True`.
(`OzHarvest A`.)

Questions demonstrated:

1. **What does it do?** The retained first-party AIS describes national food
   rescue, food relief, free community initiatives and food-waste education;
   the register supplies the six program records and classifications. (`OzHarvest A`; `OzHarvest R`.)
2. **What is the represented footprint?** The register supports Australia-wide
   operation and the program locations include the Australian states and
   territories, with specific education locations in the program records. This
   is not proof of current availability at each location. (`OzHarvest R`.)
3. **What scale is actually reported?** The 2025 AIS supports the first-party
   operational metrics and the financial/workforce figures above. It does not
   provide an independent impact evaluation or causal claim. (`OzHarvest A`.)

### 5. Islamic Relief Australia — ABN 82147006639

The register identifies a registered large charity established in 1983, based
in Auburn NSW, operating in NSW and naming 26 countries. Its ten represented
programs include Qurban, Orphan Sponsorship, Al Firdaus College Youth Project,
Winterisation, health-care projects, housing for poor and orphan families,
water and sanitation, and primary/secondary education. (`Islamic Relief R`.)
The 2025 AIS covers 1 January–31 December 2025 and states that funds were
raised through events, online donations and collections at shopping centres
and other public spaces, then contributed to emergency response, development,
and seasonal/welfare programs. It also states that the organisation partnered
with UNICEF on early-childhood projects and supported projects in the named
countries. These are first-party statements, not independently adjudicated
relationships or outcomes. The AIS reports receipts `$25,561,829`, expenses
`$26,230,877`, net surplus/deficit `-$669,048`, 13 full-time, 6 part-time and
2 casual employees, 250 unpaid volunteers, and fundraising `Yes` with online
fundraising `True`. (`Islamic Relief A`.)

Questions demonstrated:

1. **How does it say it raises funds and uses them?** Events, online donations
   and public-space collections are stated, with the stated destination being
   emergency, development and seasonal/welfare programs. This is not proof of
   a current Giving Offer or legal restriction. (`Islamic Relief A`.)
2. **What programs and geographies are represented?** The register supports
   the ten named program records, NSW as the operating state, and the 26 named
   countries. Program-level currentness and delivery status remain unanswered.
   (`Islamic Relief R`.)
3. **What is the latest retained reporting-period scale?** The 2025 AIS
   supports the receipts, expenses, result, 21 employees in total and 250
   volunteers above. It does not establish outcomes, effectiveness or current
   service capacity. (`Islamic Relief A`.)

## North Star v0.3 coverage and missingness

Codes: `S` = at least one bounded source-supported proposition; `P` = partial,
source-attributed or scope-limited support; `M` = no substantive proposition
was supported by the two inspected ACNC bodies. `M` is not a claim that the
charity lacks the field: this review did not inspect the wider admitted source
universe, and source silence is not absence.

| v0.3 section | Guide Dogs | Human Appeal | Peter & Lyndy White | OzHarvest | Islamic Relief | Evidence boundary / missingness |
|---|---:|---:|---:|---:|---:|---|
| 1 Identity / regulatory | S | S | S | S | S | ACNC name, ABN, registered status, address, website, establishment and version fields. |
| 2 Purpose / cause | P | P | P | P | P | AIS activity narrative and register summary; legal-purpose detail and independent cause assessment not established. |
| 3 Programs / services | P | P | P | P | P | Named source-native programs and classifications; currentness, delivery party and access route usually missing. |
| 4 Activities / SDGs | P | P | P | P | P | AIS activity fields and narratives; no SDG proposition or independent activity assessment. |
| 5 Geography / beneficiaries | P | P | P | P | P | Register beneficiary/country/state/program-location fields; named is not the same as served or reached. |
| 6 Participation | M | M | M | M | M | No bounded participation, membership, co-design or volunteering-opportunity proposition used. |
| 7 Direct service / capacity | P | P | P | P | P | Service/program descriptions exist; current availability, eligibility, throughput, waitlist and capacity are unanswered. |
| 8 Fundraising | P | P | P | P | P | AIS fundraising flags; Islamic Relief has a source narrative of mechanisms. No current Giving Offer/terms projection. |
| 9 Governance / leadership | M | M | M | M | M | No leadership/appointment proposition was inspected or claimed; silence is not a clean governance record. |
| 10 People / workforce | S | S | S | S | S | AIS employee and unpaid-volunteer counts for statement year 2025; role, location and capability detail missing. |
| 11 Scale / capability | P | P | P | P | P | Charity size, program footprint and selected source metrics; no independent capability or constraint assessment. |
| 12 Relationships | M | M | M | P | P | OzHarvest charity-delivery and Islamic Relief–UNICEF statements are first-party source claims only; no governed relationship edge. |
| 13 Finances | S | S | S | S | S | AIS reporting period, accounting basis and source-native receipts/expenses/result; no independent reconciliation. |
| 14 Funding / dependencies | P | P | P | P | P | Income/grant fields and narratives; no funder concentration, dependency or conditionality assessment. |
| 15 Ethos / values | P | P | P | P | P | First-party mission/activity language; no independent implementation or values assessment. |
| 16 Conduct / adverse | M | M | M | M | M | Not assessed. No adverse silence is converted into a clean record. |
| 17 Notable history | P | P | P | P | P | Establishment dates; OzHarvest also has a first-party founding narrative. No broader history review. |
| 18 Evaluation / outcomes | M | M | M | M | M | No evaluation design, comparator, outcome or causal evidence in the inspected representations. |
| 19 Classification / search / AI discovery | P | P | P | P | P | ACNC program classifications and aliases; no CharityGraph-assessed classification or discovery decision. |
| 20 Evidence / coverage / freshness / corrections | S | S | S | S | S | Exact source record, family, scope, local hash and rights state are retained; reviewed universe is only these ten bodies. |

The most important missing fields across all five are current availability and
capacity, referral/intake, current giving terms, governance, participation,
adverse history, evaluation/outcomes, funding dependency, and independently
verified relationships. The preview deliberately does not fill these with
universal priors, peer fill, forced estimates or lexical inference.

## Cross-charity comparison

The following comparison uses only the source-native 2025 AIS fields. Periods
and accounting bases differ: Guide Dogs and OzHarvest report 1 July 2024–30
June 2025, while Human Appeal, Peter & Lyndy White and Islamic Relief report
calendar 2025; Peter & Lyndy White uses special-purpose statements. The figures
must not be read as a performance ranking.

| Charity | Represented program breadth | AIS period | Receipts | Expenses | Net surplus/deficit | Employees (FT/PT/casual) | Unpaid volunteers | Fundraising |
|---|---:|---|---:|---:|---:|---:|---:|---|
| Guide Dogs NSW/ACT | 10 | Jul 2024–Jun 2025 | $51,977,920 | $52,253,502 | -$275,582 | 342 (208/94/40) | 849 | Yes; online true |
| Human Appeal International Australia | 4 | Jan–Dec 2025 | $40,400,264 | $39,506,382 | $893,882 | 48 (48/0/0) | 150 | Yes; online true |
| Peter & Lyndy White Foundation | 2 | Jul 2024–Jun 2025 | $78,917,379 | $27,721,425 | $51,195,954 | 1 (0/1/0) | 2 | No; online false |
| OzHarvest | 6 | Jul 2024–Jun 2025 | $31,880,971 | $33,375,185 | -$1,494,214 | 370 (118/137/115) | 2,085 | Yes; online true |
| Islamic Relief Australia | 10 | Jan–Dec 2025 | $25,561,829 | $26,230,877 | -$669,048 | 21 (13/6/2) | 250 | Yes; online true |

The comparison demonstrates a useful product pattern: a user can compare
program breadth, represented geography, source-reported fundraising practice,
workforce and reporting-period financial measures while retaining the exact
source basis and refusing to imply comparable effectiveness, current capacity
or donor suitability.

## Counts and current user proposition

- **10** source-native representation bodies physically inspected: five
  `acnc_register` and five `acnc_ais_bundle` JSON files.
- **5** exact subject/scope pairs inspected, each with two distinct source
  records and a current local-private rights record.
- **50** bounded supported claim groups used in the preview: ten per subject
  covering identity, source date/period, programs, geography/beneficiaries,
  purpose/activity, financial basis, financial measures, workforce,
  fundraising/operating status, and evidence/rights lineage. This is a
  conservative report count of claim groups, not a claim that the catalogue
  contains only fifty propositions.
- **15** question slots demonstrated: three per subject, with explicit
  unanswered states where the retained evidence cannot support an answer.

The demonstrated user proposition is:

> **For a named Australian charity, CharityGraph can provide a private,
> evidence-backed “what does this organisation do, where/for whom, and what
> recent source-reported operating/financial context exists?” preview with
> exact subject, source-family, source-record, scope, date and hash lineage,
> while refusing to turn source silence into a negative claim.**

## Priority successor: integrate a bounded answer projection

The smallest useful successor is a provider-free, read-only answer projection
over these retained representations, not a new acquisition or scraper.

**Exact code seam:** extend the existing
`build_single_subject_offline_packet()` seam in
`src/charitygraph/phase5_t4a_single_subject_offline_packet.py:142-248`, using
the exact-row selection at `:187-194` and the source identity envelope at
`:_source_identity()`/the `source_records` projection at `:231-232`. Keep the
preview derivative separate from the packet's current identity-only contract.
The existing packet intentionally emits no source body (`:3-5`, `:244-245`),
which is the correct boundary. Do not use the stale execution constants at
`:38-40` as current authority: they still name fence `v51` and an older HEAD.

The successor should emit a typed `AnswerProjection` derivative containing
`subject_id`, `scope_id`, `question_id`, `answer_state`, a bounded answer or
explicit unanswered state, `source_family`, `source_record_id`,
`representation_sha256`, exact local representation locator, source date/
reporting period, and a `fact_vs_source_statement_vs_inference` label. The
North Star 20-section matrix should remain coverage metadata, not canonical
knowledge. Any unrestricted semantic synthesis must remain a typed model task
under the existing semantic-contract machinery; Python should only select
fields, verify hashes, join exact IDs, validate schema and compile the preview.

Acceptance criteria for one realistic 900-second worker:

1. Read the ten direct representation files and reject any hash mismatch;
   opening SQLite/WAL remains prohibited.
2. Produce 15 deterministic question records, three per subject, with every
   positive answer carrying the exact source-family, source-record and
   content-addressed hash from the evidence key above.
3. Preserve explicit states for unsupported current capacity, giving terms,
   evaluation, governance and adverse-history questions; no source silence is
   rendered as “none” or “clean”.
4. Add focused tests for subject/scope drift, representation tampering,
   missingness-state preservation, date/period retention and zero provider,
   budget, acquisition and publication side effects. Reuse the existing
   `tests/test_phase5_t4a_single_subject_offline_packet.py` expectations at
   `:41-90` as the boundary tests.
5. Keep the output private and derivative-only. No canonical promotion,
   public projection, release, provider call or code-path discovery is part of
   that worker.

This successor is deliberately small enough for a single 900-second bounded
worker: exact-file verification and schema first, deterministic projection
second, focused tests third. A later approved semantic task can improve the
question wording, but it must consume this evidence envelope and preserve the
same citation and missingness contract.

## Blockers and boundary disposition

There was no blocker to this report: the ten retained representation bodies
were present and readable without opening SQLite/WAL, and all five subjects
received a substantive preview. The concrete integration blocker is that the
existing offline packet implementation and tests are still pinned to the older
`v51`/`372ca418...` execution context, while the current worker is fenced at
`v61`/`ebd8fdb...`; T4A11 independently classifies the surrounding catalogue
state as partial and not authoritative. This report does not repair that
stale seam.

The smallest genuine successor is therefore the bounded answer-projection
worker above, beginning with exact current-fence reconciliation and direct
representation hashing, then adding the 15 cited answer records. No provider,
model, source acquisition, budget reservation, SQLite/WAL access, publication,
release, Gate 4 acceptance/closure or follow-on dispatch is implied.

Pre-existing dirty and untracked T4A2/T4A8/T4A9 material was left untouched.
Only this report was added. The report contains no credentials, prompts, model
responses, raw source archive bytes, runtime databases, WAL/SHM files or
public projection material.
