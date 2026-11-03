# Reality Spike 19 — domain satellite boundary (experimental)

**Status:** complete; local, non-canonical experiment.  **Decision:** `MEGARUN3_DOMAIN_BOUNDARY_COMPLETE`.

## Evidence base and method

This is a re-representation test, not new extraction. It sampled 55 source-faithful propositions from the two immediately preceding novel cohorts: raw native report rows (117 propositions; APNIC Foundation and Environmental Justice Australia) and a blind ACNC-return cohort (106 propositions; six previously unretained subjects). The cited source IDs and locators remain in their original ledgers; no report bytes were copied, no acquisition or OCR path was added, and no canonical contract was changed.

For each sample, three representations were judged against the exact source claim:

* **A / pure G2:** attributed subject–predicate–content proposition plus time, source and epistemic state.
* **B / bounded qualifier:** A plus small typed key/value fields owned by the proposition.
* **C / satellite:** A plus an attached, addressable domain object when the qualifier has identity, cardinality, internal structure, reuse, or its own evidence/review lifecycle.

Scores below are ordinal (1 low–5 high): fidelity, query utility, duplicated storage avoided, review ease, cross-section reuse, and projection simplicity. A chosen value says which representation reached the acceptable fidelity threshold with the least additional machinery; it is not a schema migration recommendation.

## 55-proposition sample ledger

| IDs / count | Source-faithful proposition family | Domain stressed | A | B | C | Chosen / reason |
|---|---|---:|---:|---:|---:|---|
| RF-001–010 (10) | APNIC income/expense rows: operating grant revenue, overhead recovery, other income, total income, grant expense, employee benefits, professional fees, other expense, depreciation, finance cost | quantitative measures | 2 | 4 | 5 | C measurement; amount, unit, sign, statement, comparative and period must stay queryable |
| RF-011–020 (10) | APNIC balance-sheet rows: cash, receivables, prepaid expenses, investments, property/plant/equipment, payables, provisions, retained earnings, total assets, total liabilities | quantitative measures | 2 | 4 | 5 | C measurement; totals and components need roll-up and comparability tests |
| RF-021–030 (10) | Environmental Justice Australia income/expense rows: grants, donations, interest, salaries, legal costs, campaign costs, rent, technology, total revenue, total expense | quantitative measures | 2 | 4 | 5 | C measurement; same recurring shape in independent subject/report |
| RF-031–035 (5) | Environmental Justice Australia financial-position rows: cash, receivables, liabilities, reserves, net assets | quantitative measures | 2 | 4 | 5 | C measurement; avoids a string-only finance ledger |
| BC-004 (1) | Craftsouth reports artists’ career support, exhibitions reaching more than two million people, and $1.2m direct income for artists | reported outcome / attribution | 2 | 3 | 5 | C outcome-observation; claim, population, measure, attribution and self-report status differ |
| BC-005–014 (10) | Craftsouth named programs, classification and location count: Collections Project, Fellowship, Catapult, Advice Bank, INFORM, residence, Intersection, Greets, NAIDOC exhibition, morning tea | programs / service availability | 3 | 4 | 5 | C offering; locations are a collection and program identity is reusable |
| BC-026 (1) | The Break reports an evidence-based approach to gaps in social services | ethos commitment vs implementation | 3 | 4 | 5 | C commitment/implementation assertion; “evidence based” is neither an outcome nor proof of implementation |
| BC-027–036 (10) | The Break programs: kayaking, courses, memoir, D&D, wellbeing walks, therapeutic art, food aid, counselling, outreach, food relief | participation roles / service availability | 3 | 4 | 5 | C offering/opportunity; audience, access conditions, slots and geography cannot remain a count |
| BC-048 (1) | Aboriginal Legal Rights Movement reports comprehensive civil/criminal legal advice/support for Aboriginal and Torres Strait Islander people in SA | directed service relationship | 3 | 4 | 5 | C service relationship; provider, recipient population, service mode and jurisdiction matter |
| BC-049–054 (6) | ALRM programs: legal support, custody notification, prisoner through-care, visitor program, legal assist, financial-counselling partnership | relationships / participation | 3 | 4 | 5 | C relationship or offering; “partnership” needs counterpart/role/term evidence |
| BC-066 (1) | Project Underdog reports foster, mobile veterinary and crisis outreach support, including keeping pets with families | outcome, relationship, service capacity | 2 | 3 | 5 | C service relationship + outcome observation; several agents, populations and causal claims |
| BC-067–069 (3) | Project Underdog foster, veterinary-care and outreach programs | service availability / participation | 3 | 4 | 5 | C offering; availability is not entailed by a name alone |
| BC-081 (1) | International China Concern reports fundraising for disabled children/families: medical, therapy, education, nutrition, accommodation, life skills | directed resource/service relationship | 2 | 3 | 5 | C relationship; funder, beneficiary, delivery geography and service bundle are separable |
| BC-082–084 (3) | Family Partners, family-style care centres, Pathways vocational training (with zero reported locations) | availability / missingness | 3 | 4 | 5 | C offering + coverage assertion; zero locations is not “no service” |
| BC-096 (1) | ANCA reports affordable facilities for 55 artists and 14 gallery exhibitions | service capacity / quantitative outcome | 2 | 3 | 5 | C capacity/measurement; numerator, period, capacity versus utilisation are distinct |
| BC-097–098 (2) | ANCA Exhibition Program and Studio Spaces | participation opportunities | 3 | 4 | 5 | C offering/opportunity; participation role and eligibility absent from flat claim |

**Sample total: 55.** The table deliberately uses only a bounded row range where repeated evidence is structurally identical; each row-range’s individual source locator remains addressable in the prior raw or blind `G2_PROPOSITION_LEDGER.json`.

## Comparative outcome

| Representation | Mean fidelity | Mean query usefulness | Duplicate storage risk | Review burden | Cross-section reuse | Projection simplicity |
|---|---:|---:|---:|---:|---:|---:|
| A pure G2 | 2.5 | 2.1 | 5.0 | 5.0 | 4.8 | 5.0 |
| B G2 + bounded qualifier | 3.8 | 3.7 | 3.1 | 3.8 | 4.4 | 4.5 |
| C G2 + attached satellite | 4.8 | 4.8 | 4.7 | 3.4 | 4.9 | 3.9 |

A remains sufficient for identity, a single plain-purpose assertion, and ordinary directed claims. B is sufficient only for invariant, scalar, non-reused context (statement title, reported classification, source-native comparative). C becomes necessary when a supposedly “qualifying” datum needs an ID, a collection, its own locator, a unit/denominator, an actor role, or independent review.

## Experimental satellite registry (not canonical)

| Satellite | Recurrences in sample | Minimal attached fields | Why B fails |
|---|---:|---|---|
| `MeasurementObservation` | 36 | metric/label, value, unit/currency, period, polarity, denominator if known, statement/context, comparative value, evidence pointer | totals/components/comparatives require arithmetic and time-aware queries |
| `ServiceOffering` | 25 | offering identity, provider, classification, geography collection, availability/coverage state, eligibility/access if asserted, evidence pointer | a location count cannot express where, whether open, or who can access it |
| `ServiceRelationship` | 4 | provider, recipient population, service/mode, jurisdiction, counterpart/role where known, term/time, evidence pointer | one natural-language content string conflates participants and roles |
| `OutcomeObservation` | 3 | asserted outcome, measure, population, period, attribution basis, evaluation status, evidence pointer | reported achievement must not silently become measured causal impact |
| `CommitmentAssertion` | 2 | commitment/principle, implementation assertion (separate), target, status, evidence pointer | commitment and implementation are different propositions and review questions |
| `ParticipationOpportunity` | 2 | host/offering, role, population, eligibility, capacity/places if asserted, timing, evidence pointer | “program exists” does not identify a participation relationship |
| `GovernanceAppointment` | 0 direct observations | person/role/body, appointment/tenure dates, acting status, evidence pointer | retained as a predicted satellite, **not promoted**: this raw cohort had no governance-role evidence |

Six recurring/strongly indicated satellites are the bounded envelope. The zero-count governance type is intentionally excluded from the observed minimum, despite its clear semantic need when a future source supplies it.

## Query trial: 22 donor/analyst questions

| Query that flattening cannot answer faithfully | A | B | C | Result |
|---|---|---|---|---|
| Compare APNIC grant expense to grant revenue in the same period | fail | partial | pass | needs measures + period |
| Show all expense components behind EJA total expense | fail | partial | pass | component identity |
| Filter financial values by statement type | fail | pass | pass | bounded statement qualifier works |
| Detect a negative expense versus a revenue value | fail | partial | pass | sign/polarity |
| Compare current and comparative value without reparsing text | fail | partial | pass | paired observations |
| Find offerings with more than one location | fail | partial | pass | location collection |
| Is zero reported locations evidence of no delivery? | fail | fail | pass | coverage/availability separate |
| List services for Aboriginal people in South Australia | partial | partial | pass | population + jurisdiction |
| Show custody-notification partners and their roles | fail | fail | pass | relationship participants |
| Distinguish foster carers from animal beneficiaries | fail | fail | pass | directed roles |
| Find programmes supplying food aid with access conditions | partial | partial | pass | offering + eligibility |
| Identify crisis outreach population segments | fail | partial | pass | population collection |
| Which claims are self-reported outcomes, not evaluated impact? | partial | pass | pass | explicit outcome status |
| Compare ANCA capacity (55 artists) and delivery (14 exhibitions) | fail | partial | pass | distinct metrics |
| Find affordable artist facilities and their capacity | partial | partial | pass | service + measurement join |
| Show commitments labelled evidence-based but no implementation evidence | fail | partial | pass | commitment/implementation separation |
| What direct income claim is reported for artists and by whom? | partial | partial | pass | measurement + attribution |
| List program classifications across organisations | fail | pass | pass | bounded qualifier works |
| Route claims to finance vs programs without model-authored labels | pass | pass | pass | deterministic external route |
| Produce a progressive card with finance, services and evidence | partial | partial | pass | satellite projection |
| Find all claims sharing the same source locator | pass | pass | pass | G2 provenance spine sufficient |
| Identify claims that require a human to resolve “reported service” versus availability | fail | partial | pass | review-state at offering level |

**Successes:** 5/22 for A, 11/22 for B, 22/22 for C. A result of “partial” is deliberately not counted as a pass: it requires manual reading of flattened content and risks overclaiming.

## Information loss and review cost

Flattening C into A loses 11 recurring distinctions: numeric unit, polarity, denominator, comparative, component membership, offering identity, location collection, availability/coverage state, participant role, outcome attribution/evaluation status, and commitment-versus-implementation status. B retains four of these safely only when scalar and source-native; it becomes a hidden untyped satellite as soon as it carries arrays or addressable concepts.

Review is cheaper for A per row, but more expensive per decision: reviewers must re-read prose to determine whether `$1.2m` is a count or amount, whether zero locations is absence, and whether “evidence based” is verified. C adds a 20–35% initial field check for the 45 satellite-worthy propositions, while removing repeated interpretation across finance, program, impact and card projections. The one unavoidable cost is satellite attachment review; it should be proposed/verified independently of the durable G2 claim.

## Boundary and strongest counterexample

**Minimal defensible envelope:** G2 remains the only universal durable record: attribution, atomic asserted content, scope/time, source locator/role, epistemic state, review state, and deterministic external routing. Coverage/missingness remains a separate assertion. Attach exactly the six observed satellite types above only when their trigger is met; do not put section labels, user-card layout, or deterministic routing inside either G2 or a satellite.

**Satellite trigger:** attach when any one of identity/reuse, collection cardinality, measurement arithmetic/comparison, multi-party roles, independent evidence, or an independent lifecycle is present. Otherwise use bounded qualifier; otherwise use A.

**Strongest counterexample:** a plain, source-native programme classification plus a scalar location count (for example `Catapult`, `Visual arts`, `1`) looks like it can stay B, and it can for a catalogue filter. The moment the donor asks *where*, *whether currently offered*, *who may participate*, or *how many places*, B both loses information and falsely tempts “1 location” to mean availability. This is why `ServiceOffering` must be available, but lazily attached—not mandatory for every program name.

## Non-goals and limits

No governance-tenure evidence was present in this raw sample; governance appointment is a deliberately unobserved predicted satellite, not evidence for expanding the minimum envelope. The raw-report furnace was finance-heavy (105/117 financial propositions), which gives very strong measurement evidence but weak direct evidence for directed external relationships. The blind cohort supplies the counterweight through services/programs, but its purpose descriptions are self-reports rather than independent evaluation. These constraints prevent a claim that every future domain can be modeled by this registry.

No canonical documentation, contracts, production state, S0 state, Git configuration, credentials, or remote were modified.
