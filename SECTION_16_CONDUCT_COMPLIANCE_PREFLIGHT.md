# Section 16 conduct, adverse matters & compliance — deterministic preflight

**Status:** Phase 3 design/preflight only; no provider execution and no source
acquisition.  This note is a bounded implementation proposal for human review,
not a claim that Section 16 is complete.

**Authority basis:** the merged Data North Star, roadmap and implementation
plan, together with the Builder observation-first contracts on this branch.
The existing direct-service pressure case remains a pressure test only;
Sections 6, 11 and 13 are not product-wide completion claims.

## Product question

Section 16 must answer neutral, source-qualified questions about a complaint,
allegation, investigation, finding, enforcement action, sanction or
remediation, including who made the proposition, what it concerns, its time and
scope, and its current status.  It must not produce a CharityGraph judgement
such as `reputable`, `unethical` or `bad actor`.  A source's own adverse
description is represented as source-reported knowledge, not silently promoted
to an organisation-wide conclusion.

## Minimum semantic distinctions

The approved proposition/event vocabulary is deliberately bounded.  It
describes what procedural or conduct fact is reported, never the authority of
the source:

`complaint`, `allegation`, `investigation`, `proceeding`, `finding`,
`enforcement_action`, `sanction_or_penalty`, `undertaking_or_agreement`,
`remediation_or_corrective_action`, `subject_response`, `appeal_or_review`,
`correction_or_variation`, `overturning`, `matter_status`.

The following distinctions are necessary where the evidence supports them:

| Distinction | Proposed representation | Boundary |
| --- | --- | --- |
| complaint / allegation / report | an observation or assertion with a typed proposition class and procedural status | does not establish a breach or finding |
| referral / investigation / proceeding | observation (or event-like proposition) with the relevant procedural status | investigation is not guilt or a finding |
| regulator finding | source-qualified observation/assertion | regulator authority is provenance, not an unconditional truth rule |
| court/tribunal finding | source-qualified observation/assertion | preserve jurisdiction and decision scope when available |
| enforcement action / sanction / penalty | a distinct proposition, optionally related to the underlying matter | action is not the same proposition as conduct |
| undertaking / agreement / corrective or remedial action | distinct commitment/action proposition | completion is not independently verified unless evidenced |
| subject response | distinct source-reported proposition | response is not exoneration or admission by inference |
| appeal / review / withdrawal / correction / variation / overturning | append-only later observation/assertion and governed adjudication | prior material remains historically observable |
| resolution / closure / current status | explicit status proposition with an observation time | absence of a current update is not “no adverse conduct” |

This is a vocabulary boundary, not a new bespoke compliance database.  Generic
`Observation`, `Assertion`, `AdjudicationDecision`, `EvidenceFragment`,
`PartyRole` and `RelationshipStatement` remain the durable primitives.

## Claim status versus procedural status

The existing contracts keep these axes separate:

* `Observation.outcome_state` and `Assertion.outcome_state` express the
  epistemic state (for example `supported`, `contradicted`, `unknown` or
  `insufficient_evidence`).
* `lifecycle_status` expresses the record lifecycle (`candidate`, `accepted`,
  `superseded`, `withdrawn`, and so on).
* `AdjudicationDecision` records a governed review outcome over candidate
  records.
* A Section 16 payload needs a separate narrow procedural status, initially:
  `pending`, `ongoing`, `in_force`, `completed`, `fulfilled`,
  `no_longer_in_force`, `withdrawn`, `varied`, `overturned`, `stayed`,
  `closed`, `unknown`.  Event types such as `finding_made`, `remediated` and
  `appeal` remain proposition classes, not statuses.

The real pressure case should use only class/status combinations supported by
the source (for example undertaking `in_force`/`fulfilled`/
`no_longer_in_force`, investigation `ongoing`/`completed`/`closed`, and
appeal/review `pending`/`ongoing`/`completed`/`withdrawn`).  `fulfilled` remains
distinct from `completed`, and `no_longer_in_force` remains distinct from a
generic `closed` status.  No complex legal state machine is proposed.

No current contract requires a new primitive for this preflight.  Builder will
validate the eventual typed values mechanically; it must not infer status from
prose.

## Source authority

`SourceDefinition`/`SourceRecord` source family, role, publisher, rights and
lineage are the authority inputs.  A future task must preserve roles such as
regulator, court/tribunal, government inquiry, organisation self-report,
auditor/assurance, independent journalism, advocacy/allegation and
social/community commentary where the acquisition policy establishes them.
There is no automatic “regulator always true” or “journalism always false”
ranking.  Python must not infer authority from words in a document; authority
is deterministic source metadata and governance.

## Temporal requirements

The approved rule is one legally/procedurally distinct proposition or status =
one `Observation`/`Assertion` candidate with its own `ObservationTime`.
`effective_from`/`effective_to` carry an applicable or in-force interval;
`observed_at` follows existing source-observation semantics; `assessed_at` is
used only under existing governance; and `reporting_period` is populated only
when the source supplies one.  Separate observations preserve issue,
fulfilment, appeal and current-status dates without a multi-date matter DTO.
The LWB packet chronology is reconstructible under this rule; no new temporal
primitive is required.

## Scope and ownership

Bind each proposition to the lowest evidence-supported `subject_id` and
`scope_id`: legal entity, organisation, program, service, project, site,
predecessor or reporting/network group as applicable.  A reporting group is a
scope, not a replacement subject.  A partner's conduct is not the charity's;
network material is not each member's; a historical predecessor is not the
successor without explicit lifecycle evidence.  Shared provenance and source
co-location do not confer proposition ownership.  Existing `ScopeRecord`,
`PartyRole` and directed `RelationshipStatement` provide the required
non-propagating structure; no automatic parent/network/funder propagation is
permitted.

## Corrections and historical integrity

The append-only model supports the required histories.  For example, an
allegation can remain an historical observation while a later regulator
investigation records “no breach”; a finding can be followed by an appeal and
an overturned or varied decision.  New observations/assertions and
`AdjudicationDecision` records drive the current projection through explicit
supersession/correction and status propositions.  Earlier evidence is never
deleted, and missing or stale updates remain explicit rather than becoming a
negative assertion.

## Deterministic corpus and pressure-case packet

The selected subject is the existing Life Without Barriers holdout
(`subject:ca2a7205d6de410c85cb2a08196206dc`, ABN `15101252171`).  It was chosen
for source-state diversity, not editorial singling-out.  The bounded private
packet is frozen at:

`C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\packet.json`

Packet SHA-256: `35a44dde214ec360394e39aa15917230865fff8c99b80cdce636a8937506d994`.
The private acquisition report is
`C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\manifest-report.json`.

Ordered accepted sources are:

| Source | Source record | Role | Representation |
| --- | --- | --- | --- |
| NDIS Commission 2020 compliance notice | `srcrec:898766af7c3624fced893a04b550059c87fe1be45871be0259eef07eee3b6b21` | regulator enforcement/compliance action | native HTML |
| NDIS Commission 2023 undertaking page | `srcrec:dd8c70b78cc766a8ba66cf74575547233e004199b67e36063b661e24d27e8ec9` | regulator-published enforceable undertaking | native HTML |
| 2023 enforceable-undertaking PDF | `srcrec:4c1d129b170866bb55d7013c38417a17c5866ab499b3694b3bbeb775b22b7be1` | regulated-entity undertaking document | native PDF, 6/6 pages |
| NDIS Commission 2025 compliance notice | `srcrec:8c39eaf19d794611ce4c81a8fb1011e05ae3fa6e4c963d938cb46cd7f47fa6aa` | regulator enforcement/compliance action | native HTML |
| Current NDIS provider registration | `srcrec:61d455442ae83a77b885408397436f90e3391611c69a0edfde33de2e34c57144` | regulator registration status | native HTML |

The optional supported-accommodation inquiry was inspected and excluded: LWB
appears among several providers and in aggregate/context tables, but no
separable LWB-specific Section 16 proposition was admitted.  Its private
artefact remains outside the packet.  No direct formal notice PDFs were linked
by the two notice pages.

All five accepted records are published by the NDIS Quality and Safeguards
Commission and were retrieved on 1 September 2026.  Their private content
artefacts are, in packet order:

`srcblob:0b06b0522b95b58f6bdc7be813131518c28443e3adbb94f01bf524400040738f`,
`srcblob:77b9e59558a46f381294a62dc00dd1cd1134f9b3275d0251a8339721555e2fdf`,
`srcblob:3d147dd4af7c50a6735cf5ad1af2fed1fb04b8e3c50d32fccae6f0d1641d158f`,
`srcblob:e975f9142ae123c1eee9640b9bbfc5e43559e024149fa2360ead726d57c2cdaf`,
`srcblob:12164aae3ab54e783d39ab6ee6715bf617d499170677e10e75d7d298e493f1ca`.
The PDF representation is native, six pages, with no extraction or visual gap;
HTML representations are native and complete.  Rights are retained as private
review-only NDIS Commission material under the existing source governance.

## Provider-boundary sketch (not implemented)

The future task should be narrower than the durable ontology and should carry:

* Builder-owned schema/profile and task identifiers;
* stable subject and scope identifiers;
* an enumerated proposition class and separately enumerated procedural status;
* one `ObservationTime` per proposition/status;
* source-record/evidence-locator identifiers with exact bounded excerpts;
* explicit relationship/party-role references only when the evidence supports
  them; and
* qualifications and an epistemic result state.

The model must not receive or emit unrestricted `CanonicalValue`, invent source
authority, propagate scope, or emit a CharityGraph moral judgement.  Domain
conversion, validation, lineage and publication eligibility remain deterministic
Builder responsibilities.  No schema probe, provider DTO or migration is
introduced by this preflight.

## Economics preflight

The five accepted source representations contain approximately 927,185
characters (about 231,796 tokens at the existing four-characters-per-token
planning estimate); the private frozen packet metadata is 7,287 bytes.  This
whole packet is larger than a single bounded request, so Section 16 must use
task-specific/section-partitioned representations rather than one whole-card
transmission.  At the current Luna snapshot (USD 0.20/M input, USD 1.20/M
output), a 40,000-token bounded task with a 24,000-token output ceiling would
project USD 0.0368 before any separately approved retry exposure.  No budget
was reserved and no provider call was made.

## Empirical acceptance inventory

The private deterministic inventory records the following candidate states (not
model gold): 2020 compliance action and subsequent fulfilment; 2023 undertaking
given by LWB and accepted/published by the Commission, with later
`no_longer_in_force` status; 2025 compliance action with its bounded in-force
interval and later `no_longer_in_force` status; and current approved provider
registration through 21 July 2028.  The 2023 PDF separately identifies LWB as
the undertaking giver and the Commission as accepting delegate.  The source
wording is preserved as non-legal, source-reported material and does not get
upgraded to a broader misconduct claim.

Chronology is reconstructible with separate observations: 2020 issue/status and
fulfilment; 2023 undertaking/given and status; 2025 issue/effective interval
and status; current registration as-of state.  No new temporal or matter/group
primitive is required.

## Stronger review routing

Before publication, route allegations without a formal finding, conflicting or
scope-ambiguous sources, current-status ambiguity, reputational claims lacking
regulator/court authority, historical actions presented as current breach,
overturned/varied findings, and ownership ambiguity for stronger assurance or
human review.  Luna output is never automatically publishable adverse truth.

## Bounded acceptance questions

1. Can an allegation be represented without becoming a finding?
2. Can a formal finding be distinguished from an allegation?
3. Can an investigation be represented without implying guilt or breach?
4. Can a penalty or enforcement action be represented separately from the underlying conduct?
5. Can an undertaking, corrective action or remediation be represented without implying independent verification?
6. Can an organisation response be preserved without treating it as an adjudicated fact?
7. Can current status differ from historical status?
8. Can correction, withdrawal, variation or overturning change the current projection without deleting history?
9. Can each claim be bound to the lowest supported subject or scope?
10. Can source role and authority remain explicit and proposition-specific?
11. Can evidence and complete source lineage be reconstructed for every proposition?
12. Can conflicting sources coexist without an automatic truth ranking?
13. Can absence of evidence remain unknown rather than “no adverse conduct”?
14. Can downstream projections avoid reputational overstatement?
15. Does any required procedural state or multi-date relation need a new durable primitive?
16. Can the provider wire DTO remain narrower than the durable ontology?
17. Can reporting-group, predecessor, partner and network scope be represented without propagation?
18. Can the review path require stronger controls for high-consequence claims?

**Next boundary:** source acquisition and human approval of the enumerated
procedural/status vocabulary.  No Section 16 semantics are claimed complete by
this document.
