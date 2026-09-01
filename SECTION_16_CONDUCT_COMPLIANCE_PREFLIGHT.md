# Section 16 conduct, adverse matters & compliance — deterministic preflight

**Status:** Phase 3 design/preflight only; no new Section 16 evidence was sent
to a provider in this correction.  A single non-sensitive schema acceptance
probe is diagnostic only, and the bounded source packet is private runtime
material.  This note is not a claim that Section 16 is complete.

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

## Provider-boundary contract (implemented; execution not authorised)

The future task should be narrower than the durable ontology and should carry:

* Builder-owned schema/profile and task identifiers;
* stable subject and scope identifiers;
* an enumerated proposition class and separately enumerated procedural status;
* one `ObservationTime` per proposition/status;
* source-record/evidence-locator identifiers with exact bounded excerpts;
* explicit relationship/party-role references only when the evidence supports
  them; and
* qualifications and an epistemic result state.

The implemented transport DTO is `ConductComplianceWireOutput`.  Its closed
proposition classes are `complaint`, `allegation`, `investigation`, `proceeding`,
`finding`, `enforcement_action`, `sanction_or_penalty`,
`undertaking_or_agreement`, `remediation_or_corrective_action`,
`subject_response`, `appeal_or_review`, `correction_or_variation`, `overturning`
and `matter_status`.  Procedural status is a separate closed value set:
`pending`, `ongoing`, `in_force`, `completed`, `fulfilled`,
`no_longer_in_force`, `withdrawn`, `varied`, `overturned`, `stayed`, `closed` or
`unknown`.

Proposition ownership is one of `source_publisher`, `target_subject`,
`other_named_party` or `unknown`; the third value requires a nonblank owner
label.  Temporal fields are simple strings/nulls (`effective_from`,
`effective_to`, `observed_at`, `reporting_period`) and convert deterministically
to existing `ObservationTime`.  Every proposition requires at least one
supporting task-visible evidence key.  Scope and evidence bindings are exact
allow-list mappings; cross-bundle or invented IDs fail closed.  Bundle 4 may
return an empty proposition collection and must not manufacture a registration
or exoneration claim.

The provider wire object contains no Builder schema identity, task ID,
`CanonicalValue`, authority ranking or arbitrary map.  Deterministic conversion
projects valid output to existing append-only `Observation` records under the
`conduct_compliance.<proposition_class>` predicate; output remains candidate /
review-required and is never automatically promoted to public adverse truth.

The boundary-control correction is now explicit across sections: ordinary
registration conditions, variations, audit requirements and approval conditions
are not automatically Section 16 propositions.  There is no
`regulatory_condition` proposition class.  A registration/status control may
return an empty collection; a non-empty result is accepted only after the same
Section 16 evidence, scope, ownership and class validation as any other bundle.
Source headers expose `source_key`, source-record ID, source role and
publisher/authority.  Provider evidence references use one ephemeral
`E######` evidence-key field; the private task binding maps each key exactly to
one canonical durable locator.  Durable locators are never placed on the wire,
and the historical response using `S001:L0002`/`S001:L0003` remains invalid and
unchanged.

The strict schema SHA-256 is
`dc59f1f031160397489d92aba157d80426a2675799d14ec5cfd7169d1d66998e` after
the evidence-key correction (the prior diagnostic schema was
`a56a0d8e1e1f5f26b83b2f54d0f5d263a3c6035bfa64efa03fd19fde97c09e03`; 4
objects, 2 arrays, 4 enums, 3 `$ref` branches, no patterns, formats or typed
maps).  The schema has exactly one evidence-key field and no locator alias.
No migration is required.

## Economics and deterministic task preflight

The five accepted source representations contain approximately 927,185
characters (about 231,796 tokens at the existing four-characters-per-token
planning estimate); the private frozen packet metadata is 7,287 bytes.  This
whole packet is larger than a single bounded request, so Section 16 uses four
task-specific bundles rather than one whole-card transmission.  Each bundle is
represented generically (HTML visible main content; all six native PDF pages)
without semantic phrase selection.

The private preflight report is
`C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\bundles-v2\section16-provider-preflight.json`.
The bundles and exact task identities are deterministic.  At the Luna snapshot
(USD 0.20/M input, USD 1.20/M output), the 24,000-token projections are:

| Bundle | Source records | Characters | Input tokens | 12k USD | 16k USD | 24k USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 compliance action | 1 | 697 | 935 | 0.014587 | 0.019387 | 0.028987 |
| 2023 enforceable undertaking | 2 | 8,738 | 10,801 | 0.016560 | 0.021360 | 0.030960 |
| 2025 compliance action | 1 | 623 | 899 | 0.014580 | 0.019380 | 0.028980 |
| Current registration section-boundary control | 1 | 1,655 | 2,519 | 0.014904 | 0.019704 | 0.029304 |

The regenerated v2 bundle identities are private and recorded in the report,
including each bundle SHA, evidence-map SHA, prompt SHA, task/run/task-run ID,
input estimate and accounting identity.  Aggregate maximum at the recommended
24,000 ceiling is USD 0.118231.  No FX snapshot was used, so no AUD conversion
is asserted.  All four tasks have `authorization_state: not_authorized`,
physical maximum attempts 1 and no active reservation.  The underlying frozen
packet SHA remains `35a44dde214ec360394e39aa15917230865fff8c99b80cdce636a8937506d994`.

For auditability, the regenerated private identity rows are:

| Bundle | Bundle SHA | Evidence-map SHA | Prompt SHA | Input tokens | USD @24k | Authorization |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2020 compliance action | `6ff2ca3b089b06c5ae4c2488e45adf75f158fab457cd7b57202d4f7e2ad9337a` | `61bfeb1d56b88e839df2654edde0178b1e15923a5797c983c4609dace64b35aa` | `d327b4f5756b8b55ee274ed92ba1f9e37116707469532cc4848e949b2ef13666` | 935 | 0.028987 | not_authorized |
| 2023 enforceable undertaking | `951570dbceaa924205f6b3632dba44ecf3f3609fa3b3ff31bbab2a7a6373413e` | `3524f83c4358b805b53f7f9cd91159b1dbdbcef6f0fb36b03aa2bcda46c1a116` | `db4ce7ce26d277fd1cdc3420ba661dd5f38c3a1c01c3d039511baafb1a843a93` | 10,801 | 0.0309602 | not_authorized |
| 2025 compliance action | `1fff5f9763618e7992ca312eb48e9e1dd063b9d6217599764784ee89d28d08b2` | `61bfeb1d56b88e839df2654edde0178b1e15923a5797c983c4609dace64b35aa` | `690660f33ef411b7e173146685c0f90b737665b72e681f7682f545ddea1e8afc` | 899 | 0.0289798 | not_authorized |
| Current registration section-boundary control | `798be9a8aef9a8412d65b0bd2751e8e7dafe31cd66654bb5263a9988e75e75c4` | `929e93d23197ff2279db6f7103d48390bfbedefbe8cbd24a81922a7d998f0dc1` | `896061a4d9af579462e6b82ac756f46941a41e03f9504c971ecb8ef8076036ba` | 2,519 | 0.0293038 | not_authorized |

The corresponding regenerated task/run/task-run and source-record identities
(also retained in the private report) are:

| Bundle | Task | Run | Task-run | Source records |
| --- | --- | --- | --- | --- |
| 2020 | `modeltask:2bc085126bfc663e93e2c8157249ac21b29f5347f70c6ee54d2ca799bb55b9bd` | `run:d9608adfa06d58a4332ff69555004e852d335d945e2107e6846f659efd973df9` | `taskrun:954cdb922ce820e80c3de1f5c4b516129bfc56214abeaf5c228179549e4aac52` | `srcrec:898766af7c3624fced893a04b550059c87fe1be45871be0259eef07eee3b6b21` |
| 2023 | `modeltask:171c03bc2c3325e3066d6a6bb426e480bc253b60dfcdb7fca3bb64cff8ffbacb` | `run:7b5b9790f45dd11116d0408f99cc4a410f759981c51ba211dda24d9b88080d4d` | `taskrun:1669aba28a20978ab360f75dcb0916f8a75636677e5f5e838c20a5ad540609b8` | `srcrec:dd8c70b78cc766a8ba66cf74575547233e004199b67e36063b661e24d27e8ec9`, `srcrec:4c1d129b170866bb55d7013c38417a17c5866ab499b3694b3bbeb775b22b7be1` |
| 2025 | `modeltask:4eab9a1735bf80b880370758784967628bcf738cb8f6c2274d9ef610104b755` | `run:adfc3fa7428fa84b9086e20d2a9a5cf9c0554c2226be7da9483efa030ce3c24b` | `taskrun:462037f77f9a98e4ac21d87922f140eb7bac32b9830a175ebd2d068265af797a` | `srcrec:8c39eaf19d794611ce4c81a8fb1011e05ae3fa6e4c963d938cb46cd7f47fa6aa` |
| Boundary control | `modeltask:b599c6d0b3ad8de0f44879abc260dc38e0c69f1ecd862110c18a0836a4e4e6c8` | `run:e88aa543c52a25219a00495fea9272ca09a8655fb47f42a14a3fb9b39f5116d1` | `taskrun:00a605795b6d33bdf3965b98c7bb2034e0ca7724c7ab86378197277a6d445b8b` | `srcrec:61d455442ae83a77b885408397436f90e3391611c69a0edfde33de2e34c57144` |

These are regenerated identities and do not reuse the earlier v1 task records.

The prior registration boundary experiment is preserved as historical runtime
evidence: one completed request (`modeltask:dcf...`, response
`resp_0ffc...`, USD 0.001857) returned two propositions, both labelled
`enforcement_action`, with invalid durable locator syntax.  No knowledge was
persisted and no later task ran.  Under the corrected boundary these are
adjacent registration-condition statements, not safely admitted Section 16
enforcement propositions: the source text is present, but the class and
target-subject ownership are unsupported by the boundary, and the supplied
locators are invalid.  This is not treated as a factual hallucination finding.

The next boundary is explicit authorization for the corrected
`current_registration_section_boundary_control` only after provider schema
acceptance.  No pressure-case evidence was sent in this correction.

## Schema acceptance probe

After local validation, one tiny non-sensitive empty-output probe was sent using
the strict schema above, with no subject, charity, source or evidence content.
It completed successfully: response ID `resp_0b5f1df3e3f4b233006a96366e0a8c87d0a036a05154cce23b`,
status `completed`, one physical transmission, 576 input tokens, 16 output
tokens, latency 2.74 seconds and cost USD 0.000134.  The private raw response
and metadata are under
`C:\CharityGraph-runtime\section16-lwb-pressure-case-20260901\schema-probe-v1\`;
the diagnostic output is not canonical knowledge.  No LWB evidence was
transmitted, and no retry or repair probe was made.

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

**Next boundary:** corrected provider-contract implementation, deterministic
event/source partitioning, exact task/cost preflight, schema acceptance, then
explicit authorization to transmit a selected frozen pressure-case bundle.
Section 16 semantics are not claimed complete by this document.
