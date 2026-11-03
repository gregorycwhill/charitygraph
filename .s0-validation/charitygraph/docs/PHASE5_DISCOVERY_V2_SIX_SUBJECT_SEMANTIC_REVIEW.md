# Phase-5 Discovery V2 six-subject semantic review

Status: private experimental analysis only. This report is not governed knowledge, is not a promotion decision, and does not create CanonicalObservations.

## Decision

`DISCOVERY_V2_READY_FOR_WIDER_PHASE5_EXECUTION`

The six-subject Batch experiment is ready to support a wider candidate-discovery tranche, subject to the normal card-blind review and governance gates. No contract, prompt, schema, evidence-packet, or model correction is indicated by this experiment. The observed weaknesses are candidate-layer review matters rather than execution-readiness blockers.

## Experiment and transport result

- Delivery job: `deliveryjob:phase5-discovery-v2-six-slice-utf8-correction-v1`
- Provider Batch: `batch_6aa0149cf16881909088c855380ca617`
- Six of six items completed and parsed as `DiscoveryV2_valid`.
- Aggregate usage: 72,313 input tokens, 5,436 output tokens, 777 reasoning tokens.
- Usage-derived cost: USD 0.010494 / AUD 0.015954.
- All six responses had successful HTTP/body completion, null `incomplete_details`, and no truncation indication.
- No result was promoted and no CanonicalObservation was created.

| ABN | Subject | Rank/stratum | Estimated input | Actual input | Ratio | New proposals | Prior output hash |
|---|---|---:|---:|---:|---:|---:|---|
| 22627812672 | The Benevolent Relief Fund | 26 / lower | 6,095 | 7,525 | 1.2346 | 1 | `168913d7e40f...484237` |
| 84114483091 | The Church Of Jesus Christ Of Latter-day Saints Australia | 21 / lower | 8,225 | 10,173 | 1.2368 | 7 | `3e26dc60d1e...e8ac0` |
| 56749449191 | RSPCA Victoria | 52 / middle | 8,433 | 10,930 | 1.2961 | 2 | `fb67bb98b508...e868a` |
| 57001594074 | World Wide Fund For Nature Australia | 54 / middle | 10,324 | 13,076 | 1.2666 | 4 | `88de52321665...1572a3` |
| 74851544037 | RSPCA Queensland | 34 / higher | 11,175 | 13,462 | 1.2047 | 8 | `9de6a7b1b9d8...5401f3` |
| 33107782196 | Oz Harvest Limited | 57 / higher | 14,260 | 17,147 | 1.2025 | 9 | `5048b9d10dfd...7f84f4` |

## Proposal-level descriptive review

All 31 proposals below had exactly one valid evidence reference. The descriptions are evidence-derived summaries of the retained packet material, not adjudicated semantic truth.

### The Benevolent Relief Fund — 1

- `BRF Donations Request` — program, current, high confidence; the retained record explicitly lists the request under Programs with family services and Australian community beneficiaries. This is a warning case because the same label was previously insufficient/unknown, so the new current/program disposition requires downstream review.

### LDS Australia — 7

- `Religion` — program, current, high; umbrella/organising concept.
- `Missionary program housing and vehicle provision` — service, current, medium; missionary support detail.
- `Faith-building activities for adults and youth` — service, current, medium; faith-building activity detail.
- `Religious and self-reliance education courses` — service, current, high.
- `Religious literature and related resources` — service, current, high.
- `Hardship assistance and counselling referrals` — service, current, high.
- `Congregational gathering and worship resources` — service, current, medium.

The output reproduces the seven-item semantic set but does not preserve the prior explicit parent fields for the component items in the returned proposal shape.

### RSPCA Victoria — 2

- `Animal Adoptions` — service, current, high; clear named service match.
- `Animal rescue, sheltering, veterinary care, rehabilitation and rehoming services` — service, current, medium; a broad bundle of the narrative animal-welfare activity rather than a set of separately named services.

### WWF Australia — 4

- `REGENERATIVE SKY (CLIMATE)` — program, current, high.
- `REGENERATIVE COUNTRY` — program, current, high.
- `REGENERATIVE SALTWATER` — program, current, high.
- `INCLUSIVE CONSERVATION` — program, current, high.

The AIS program names and dedicated webpages support the program interpretation, while the notes retain the competing possibility that these are strategic themes or portfolios. Case and label normalisation is not material instability.

### RSPCA Queensland — 8

- `Aware` — program, current, high; named source entry corresponding to RSPCA Aware.
- `Animal Rescue` — program, current, high.
- `Animal Adoptions` — program, current, high.
- `Animal Hospital` — service, current, high.
- `Pets in Crisis` — program, current, high.
- `Wildlife Hospital` — service, current, high.
- `Animal Research` — program, current, high.
- `RSPCA Lottery` — campaign, current, high; fundraising-campaign/service interpretation remains a review point.

The richer explicit Programs list yields more distinct named candidates than Victoria. It does not reproduce prior-only `Wildlife Rehabilitation Centre`, `Operation Wanted`, or `RSPCA QLD Inspectorate`.

### OzHarvest — 9

- `Food Rescue` — program, current, high.
- `Nourish` — program, current, high.
- `NEST` — program, current, high.
- `FEAST` — program, current, high.
- `Fight Food Waste` — program, current, high.
- `Food Relief` — program, current, high.
- `Use It Up` — campaign, current, high.
- `OzHarvest free supermarkets` — service, current, medium; generic free-supermarket description with Sydney and Adelaide locations.
- `Refettorio OzHarvest Sydney` — service, current, medium; free restaurant/lunch service.

The output surfaces children of the prior `education programs` and `direct-to-community initiatives` umbrellas without returning those parent portfolios.

## Aggregate quality and stability

- 31 proposals: 17 programs, 12 services, and 2 campaigns.
- Confidence: 25 high and 6 medium; no low-confidence output.
- 31/31 evidence references were valid; there were no obvious within-output duplicates.
- No response was truncated, and all outputs were far below the 8,000-token cap (246–1,419 output tokens).
- Most new proposals are clear semantic continuations of the retained outputs. Approximate descriptive correspondence is 30/31 clear or probable; the RSPCA Victoria broad service is better treated as a plausible re-granularised expansion than an exact identity match. This is not a formal benchmark score.
- Strict string overlap is lower than semantic correspondence because of case, label, parent-field, and granularity changes.

The main recurring pattern is granularity movement: umbrella/portfolio candidates may be flattened into named children, or several related services may be bundled. That is expected to require review in a candidate layer and does not indicate a transport, schema, or parser defect.

## RSPCA paired comparison

Victoria returned two candidates because its retained material exposes an umbrella RSPCA Victoria context plus Animal Adoptions, while broader activity is compressed into one bundled service. Queensland returned eight distinct named candidates because its packet contains a richer explicit Programs list and more individual classifications. This is an observable source-detail and naming-structure difference, not evidence that one charity or route is semantically better, and it does not establish model causality.

## Sparse-case review

The Benevolent Relief Fund packet yielded only the explicit `BRF Donations Request`. There is no clear sign in this packet of multiple missed named services. The material is sparse, and the prior grant-making-operations candidate was organisational practice and previously insufficient evidence. The appropriate response is later governed evidence acquisition/review, not a prompt or model escalation based on this sample.

## Model, cap, and input calibration

Luna with low reasoning was sufficient for this discovery family across all six subjects. There is no evidence here requiring Terra or higher reasoning. The actual-to-estimated input ratios ranged from 1.2047 to 1.2961; retaining a conservative 1.30x planning factor covers the observed maximum with approximately 0.0039 headroom. The local estimate was 56,563 input tokens for the Red Cross control versus 69,725 actual input tokens; that empirical calibration remains a planning datum and is not redesigned in this review.

## Comparison against retained prior outputs

| Subject | Comparison | Interpretation |
|---|---|---|
| Benevolent Relief Fund | New output retains the prior label but changes insufficient/unknown to current/program; prior grant-making-operations item is absent. | Material disposition change; review warning, not a contract failure. |
| LDS Australia | Seven semantic items reproduced; missionary, faith-building, and worship labels/granularity shifted; prior parent relationships are not explicit. | Strong semantic stability with hierarchy flattening. |
| RSPCA Victoria | Animal Adoptions matches; prior portfolio umbrella is absent; a broad multi-service candidate appears. | Plausible re-granularisation, not strict identity. |
| WWF Australia | Four program names reproduced with case/label normalisation. | Strong stability; strategic-theme interpretation remains reviewable. |
| RSPCA Queensland | Eight clear/probable matches; three prior-only items absent; some program/service dispositions differ. | Strong correspondence with source-list and granularity effects. |
| OzHarvest | Nine members correspond to prior candidates; two prior umbrella parents are flattened into children. | Strong correspondence with split/flattening. |

## Recommended next bounded tranche

Do not execute from this report. For the next calibration slice, use 12 new subjects: four lower-, four middle-, and four higher-input subjects, including a related pair if the planning matrix provides one. Use the existing build-phase `Standard` policy, the same Discovery V2 contract/schema, Luna with low reasoning, one task per subject, no Batch, no Flex, and no promotion. Preserve the 1.30x input authorization factor. Select subjects to add source-detail and granularity diversity rather than to optimise apparent proposal counts.

## Guardrails and conclusion

The candidate layer remains card-blind and evidence-grounded, but one evidence locator per proposal limits evidence diversity. The results must therefore remain proposals for review, not automatic governed facts. The six-subject experiment crosses the current execution-readiness uncertainties: provider-shaped output was parsed, usage was reconciled, evidence references validated, and semantic correspondence was generally strong. Proceeding to a wider Standard-mode candidate tranche is justified; automatic promotion, adjudication, or full-workload execution is not implied.
