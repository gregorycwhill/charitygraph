# CG353 architecture decision: insufficient evidence

Status: private decision; no public contract, candidate, governed observation,
release projection, GitHub mutation or provider call is authorised by this
record.

## Decision

**INSUFFICIENT_EVIDENCE.**  Retain `ethos-notability-extraction-v1` as the
dedicated default-capable private specialist path.  Do not wire the C unified
output into the general semantic extraction path.  The dedicated path remains
available for escalation, recovery and research; neither lane promotes a
candidate without the existing review/governance boundary.

This is not a preference for extra calls.  The durable rule remains: shared
retained evidence should be read in as few model calls as quality safely
permits.  The quality and evidence gates were not met, so call reduction is
not sufficient to change architecture.

## Frozen evidence and gates

The unchanged CG352 cohort is 10 workshop challenges plus 5 deterministic
blind controls, cohort SHA-256
`8f2de067b29c1834b5d9307ed580fd2cfb42045fa633104dfab1a6512b2222e4`.
The central retained corpus is
`120e20160adbfd27a53b526b200e85841850ded612a839dd4381110295300644`; packet
selection is `central-packet-selection-v1`.  The frozen unified candidate is
prompt `cg353-unified-prompt-v2`
`6cd2b5fc88e4f6dc1d952af4166b5e85e0a02bb3e51f456342ff06e7c60bba44` and
schema `542d23c8ca4aa6e86edc40a5a3189ec1f6c227c28e50ebb87f4871668e137281`.

Workshop t04 used the production-like `openai.responses` provider with
`gpt-5.6-luna`: A validated 8/10, B 10/10 and C 10/10.  A used 10 calls,
49,335 input/5,792 output tokens and US$0.016818; B used 10 calls,
120,850/626 and US$0.024922; C used 10 calls, 169,130/2,797 and US$0.037181.
C was US$0.004559 below A+B and halved calls, but its rich-case general output
was materially thinner.  The one frozen t05 C re-run was valid and cost
US$0.004452 (20,106/359 tokens), but was not independently review-labelled.

Final t06 released all five controls without tuning.  Every case failed before
a provider request because its immutable representation was absent or did not
match the frozen hash; B and C therefore each recorded five packet failures,
zero valid outputs, zero tokens and zero USD.  The report SHA-256 is
`f533de7504fb12f3be53ddad16a75738dedd7be18b6796f51faf6b12d754da97`.
The independent reference contains only `NOT_EVALUABLE` labels, so it cannot
prove the required non-inferiority or dangerous-category gates.  Thus neither
the review-quality gate nor the blind-comparison gate passed.

## Boundary and recovery rule

Acquisition remains central and source-oriented: semantic workers consume
retained immutable captures only and never discover, browse or fetch sources.
The t06 missing representations are coverage/provenance faults, not a reason
to substitute a locator or reacquire inside a semantic worker.  Python owns
transport, fixed slicing, hashes, schemas, provenance validation, cost caps
and routing.  It must not be extended with prose heuristics for Ethos or
Notability; model output remains candidate/review material and §16/§17 stay
separate.

The exact next substantive tranche is to repair and re-freeze representation
continuity centrally for the same five blind captures, then rerun frozen B/C
with independent evaluable review labels and no prompt/schema/packet tuning.
Only that evidence can reopen the unified-default decision.
