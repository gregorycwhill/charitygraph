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
* A Section 16 payload needs a narrow procedural/legal status (for example
  `alleged`, `under_investigation`, `finding_made`, `appealed`, `overturned`,
  `remediated`, `open` or `closed`) as a value of the proposition, not as
  `confidence` or `outcome_state`.

No current contract requires a new primitive for this preflight.  Before
provider execution, the exact enumerated status vocabulary and its permitted
transitions require human approval; unrestricted English must not become a
Python classifier.

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

`ObservationTime` can represent a conduct/event period, reporting or allegation
date, finding/action date, effective date, reporting period and observation
time.  A single proposition should use the fields that its source supports;
separate observations are preferable when dates have different semantic roles.
The following remain an explicit design question before implementation: whether
a single matter/event DTO needs multiple named date roles (conduct, report,
investigation, finding, penalty, remediation, appeal and current-as-of) rather
than several linked observations.  Do not overload one date or `confidence`.

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

## Deterministic corpus and pressure-case preflight

The frozen `baseline-corpus-v1-final-correction2-20260830` contains ten
registered subjects.  Deterministic metadata inspection found ACNC Register and
AIS/financial material for all ten, ABR material for all ten, official-site
material for eight (two homepage transport failures), Wikipedia material for a
subset, and one exact PFRA membership record (Australian Red Cross).  The
source registry contains no regulator, court/tribunal, government-inquiry or
enforcement source role for this frozen corpus.  ACNC register/AIS records are
identity/reporting material, not evidence of an adverse finding.  Official
websites and annual-report PDFs contain policy/governance text, but the frozen
metadata does not establish a formal finding, proceeding, sanction, penalty,
undertaking or resolution chain.

Accordingly, no organisation is selected merely for fame or convenience, and
Australian Red Cross is not reused as a Section 16 case.  The existing corpus
does not contain an adequate authoritative multi-state pressure case.  A later
bounded tranche must acquire a governed case (for example a regulator/court
record plus any official response and, where applicable, appeal/remediation)
before any Section 16 provider call.  This is a source-coverage gap, not a
semantic model failure.

## Provider-boundary sketch (not implemented)

The future task should be narrower than the durable ontology and should carry:

* Builder-owned schema/profile and task identifiers;
* stable subject and scope identifiers;
* an enumerated proposition class and procedural status;
* optional narrow temporal fields or references;
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

The current Builder Luna snapshot is USD 0.20 per million input tokens and
USD 1.20 per million output tokens.  For one bounded pressure-case packet,
using the existing frozen representations, a conservative planning range is
20,000–40,000 input tokens and a 24,000-token output ceiling.  The resulting
maximum projection is `(40,000 × 0.20 + 24,000 × 1.20) / 1,000,000 =
USD 0.0368` before any separately approved transport retry policy.  One call
should be sufficient if the case is bounded; section partitioning is only
needed if the measured packet or output contract exceeds the configured request
bound.  This is an estimate, not a reservation or authorization.

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
