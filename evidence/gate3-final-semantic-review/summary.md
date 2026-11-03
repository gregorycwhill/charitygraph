# Gate 3 final semantic review — decision dossier

**Recommendation: CLOSE_WITH_LIMITATIONS.** The Product Owner retains the closure decision. This recommendation closes the completed, bounded evaluation activity only; it does **not** establish full Source Universe adequacy, population-scale quality, or production readiness.

## Identity and integrity

The immutable execution result and plan match the accepted identities:

- Run: `run:g3fresh36-question-first-v2-v151-20261020`
- Execution-result SHA-256: `be632cdcc89e214a733d465d69001b3a9a43544c675e7ba2ccda27e0c94c7f7e`
- Execution-plan SHA-256: `31834cc1e133d6c4c80c80ae787e3cab00a5819d15c84c26353618c801095efc`
- Oracle-v2 manifest SHA-256: `7e7d2f105534864a56285fbd9ea333fdd7faac5d7023a0f1be8f02426e259816`

Question IDs, governed subject IDs, exact frozen question text, and parameter slot/value pairs match 36/36. Oracle intake case identities are unique and mapped by question ID, not row position. The oracle's declared artifact inventory and the execution-response inventory both verify. No comparison row was manufactured.

**Oracle aggregate-count caveat:** the v2 manifest and certification report each list `SUPPORTED=16`, `PARTIAL=13`, `NOT_ESTABLISHED=22` (sum 51), while the 36 case assessment rows and their 36 atomic-proposition rows yield `1/13/22` (sum 36). The package does not explain this discrepancy. The row-level files and all 19 declared successor bodies hash-verify, and the exact per-case join is intact; this review therefore scores those 36 case records and flags the aggregate as unreconciled rather than silently treating it as a 36-case distribution.

## Case-level semantic assessment

| Outcome | Cases |
|---|---:|
| Correct (including correctly bounded partial answers) | 21/36 |
| Partially correct | 14/36 |
| Incorrect | 0/36 |
| Unsupported | 1/36 |
| Unscorable | 0/36 |

`case-assessments.json` contains the 36-row question/subject/oracle-case crosswalk, output disposition, structural status, and a concise case-specific rationale.

The one unsupported output is QFT-D02A: the cited ACNC-derived purpose/program and beneficiary facts are present, but the response uses `SUPPORTED` where certified oracle v2 only supports a bounded `PARTIAL` conclusion because a scope-matched 2025 first-party purpose statement was not established. This is an outcome-strength overreach, not a fabricated fact. No material factual hallucination was identified in the reviewed outputs.

Structural validation passed for 35/36 outputs. QFT-D01B's substantive ACNC registration answer is correct, but one extra `review_date` record has empty `answer_text`, so the strict v1.5.1 validator rejected it. All raw output was preserved. No out-of-packet evidence ID was found, including in that invalid output.

## Evidence recovery, missed information, and missingness

Builder received only 36 ACNC Register and 36 ACNC AIS representations. Across 30 cases it returned 139 evidence-attributed answer records using 52 distinct packet evidence IDs. That is a traceability/volume measure, not a claim that every record is a distinct oracle proposition. Every cited ID resolves within its exact per-question packet. No response set `negative_conclusion=true`.

At the oracle case level, v2 assessed 1 case `SUPPORTED`, 13 `PARTIAL`, and 22 `NOT_ESTABLISHED` (no unscorable cases). Builder's dispositions were:

- The one oracle-supported case received a supported answer, but it is the structurally invalid output above.
- Of the 13 oracle-partial cases, eight received a bounded `PARTIAL`, one an activity-specific supported state with explicit limits, one an overstrong `SUPPORTED` state, and three `MISSING` responses.
- Of the 22 oracle-not-established cases, 12 were explicitly `MISSING`; ten returned limited ACNC facts (for example, FY capacity, responsible-person or program fields) while retaining the qualification that the demanded calendar-year, access, event, or causal proposition was not established. None converted absence into a negative conclusion.

The three oracle-partial cases without a Builder answer record are D06B (direct giving routes), D15B (safeguarding policy/accountable officers), and D17A (an FY2025 change disclosure). The first two depend on first-party giving/policy material outside the transmitted ACNC Register/AIS corpus. D17A's independent evidence is fiscal-year material, not a dated calendar-year change record; it still cannot answer the frozen calendar-year demand. These are evidence coverage/temporal limitations, not model fabrication.

Additional oracle-supported details outside the Builder packet include a nationwide service/access description (D03B), annual-report activity counts (D04A), first-party purpose language (D05A), current giving-route detail (D08A), and a staff-foundation capability statement (D11B). Where Builder returned nearby ACNC records, those remain partial rather than substitutes for the omitted source evidence. No confirmed material proposition available in the exact Builder packet was found to have been falsely negated.

## Per-template-domain performance

The sample contains two questions in each QFT-D01 through QFT-D18 family. “C” means correct, including correct bounded partials; “P” means partially correct; “U” means unsupported. These are descriptive two-case slices, not stable domain performance estimates.

| QFT family / question focus | C | P | U |
|---|---:|---:|---:|
| D01 — identity and reporting scope | 2 | 0 | 0 |
| D02 — purpose, cause, beneficiaries | 1 | 0 | 1 |
| D03 — service delivery and access | 2 | 0 | 0 |
| D04 — activity, output and attribution | 0 | 2 | 0 |
| D05 — purpose and conditional service | 1 | 1 | 0 |
| D06 — volunteer measure and giving routes | 0 | 2 | 0 |
| D07 — operational capacity and access | 0 | 2 | 0 |
| D08 — donation routes and a named offer | 1 | 1 | 0 |
| D09 — leadership and safeguarding | 0 | 2 | 0 |
| D10 — member participation and executive role | 2 | 0 | 0 |
| D11 — workforce and organisational capability | 0 | 2 | 0 |
| D12 — funding relationships | 1 | 1 | 0 |
| D13 — financial comparability and aggregation | 0 | 2 | 0 |
| D14 — partners and authority findings | 1 | 1 | 0 |
| D15 — accessibility and safeguarding | 1 | 1 | 0 |
| D16 — authority findings and correction records | 2 | 0 | 0 |
| D17 — organisational changes and revenue change | 0 | 2 | 0 |
| D18 — evaluation evidence | 2 | 0 | 0 |

## Defects and demonstrated capabilities

The isolated quality defect is conclusion strength in D02A. The isolated mechanical defect is an empty required answer value in D01B. The only repeated limitation is source visibility: two families cannot substantiate many first-party operational, giving, policy, report, and evaluation questions.

Within this sample, the remediated interface demonstrated useful bounded answers, source-cited values, partial states, and non-negated missingness. It generally kept distinct legal identity, program metadata, beneficiary categories, service eligibility, calendar-year versus financial-year measures, member participation versus volunteer counts, activity versus outcome, and reported relationships versus operational partners. This supports the semantic safety and partial-support goals, not broad coverage claims.

## Experiment limitations and closure recommendation

1. Builder saw only ACNC Register and AIS records; it did not see the broader admitted Source Universe v1 families. Oracle v2 drew on a broader research universe. Its provenance ledger lists 47 source records across varied source types; its certificate reports 45 independently verified citations and 19 successor bodies retained (no original bodies retained).
2. The executable v1.5.1 interface was implemented after the frozen question selection. The question–subject sample and wording were preserved, but the interface itself was not preregistered before selection.
3. The 36 questions cover 18 domains with two cases each. This is a small, heterogeneous evaluation, not population-scale performance.
4. The oracle is certified and all 36 cases are reported auditable/research-adequate, but oracle answers remain independent judgments and are not an exhaustive substitute for observing every source admitted to Builder.

**Recommendation: CLOSE_WITH_LIMITATIONS.** The frozen evaluation is complete and decision-useful: no case was unscorable, no incorrect factual conclusion or material hallucination was identified, 21 cases aligned with the reference disposition and material scope, and the remaining cases are explained by bounded partiality, one conclusion-strength overreach, source coverage, or one mechanical formatting failure. Retain D02A and D01B as explicit defects. The Product Owner should treat this as evidence for a bounded semantic capability, not as proof of full Source Universe adequacy or production readiness. No Gate 3 state was changed by this review.
