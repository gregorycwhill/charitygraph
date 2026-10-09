# CG353 t05 bounded workshop tuning and freeze

Status: private final candidate freeze; blind outputs were neither opened nor
used.  This record is evidence for the successor validation task, not a
promotion decision.

## Lineage and evidence

The Builder chain begins at `afdbf64096fcaa9a528b4a9e08832931c971a137` and
the Data chain begins at `5be5947be3475598b3259564d517460510083803`.
The fixed CG352 split remains ten challenge cases and five blind controls;
the rich corpus is
`120e20160adbfd27a53b526b200e85841850ded612a839dd4381110295300644`.

Workshop t03's dedicated-arm ledger is not a semantic comparator: it records
seven stale-representation packet failures and three pre-existing coverage
abstentions, with zero provider calls.  That is a packet/provenance defect,
not a Luna or semantic failure.  Workshop t04 did execute all 30 challenge
calls through `openai.responses` with `gpt-5.6-luna`: A validated 8/10,
B 10/10, and C 10/10.  A's two invalid responses were output-limit malformed
responses.  The C schema/provider path is therefore structurally viable.

The recorded t04 totals were A: 10 calls, 49,335 input / 5,792 output tokens,
US$0.016818; B: 10, 120,850 / 626, US$0.024922; and C: 10, 169,130 / 2,797,
US$0.037181.  C replaces A+B's twenty calls with ten and is US$0.004559
lower than A+B, but its general output was materially thinner on rich cases.
There are no independent challenge review labels sufficient to establish
semantic non-inferiority; validation alone must not be treated as quality.

## The only revision

One generalisable prompt-only revision was made: C now carries the existing
complete-evidence, exact-evidence-id, scope/time/qualification, abstention,
and §16/§17 separation instructions explicitly into its nested
`ethos_notability` output.  It adds neither organisation-specific content nor
lexical/Python inference.  The schema and retained packet selection are
unchanged.

The minimum discriminating rerun was C/EEN-10, selected because it was the
only t04 C result containing an Ethos candidate.  It used the hash-verified
retained fallback after the rich-root locator check stopped before any call.
The v2 result is valid (one general atom, zero Ethos and one history
candidate), versus the v1 result (one general atom, one Ethos and one history
candidate).  This is a safety-direction change, but one case without
independent review cannot establish improvement.  It consumed 20,106 input
and 359 output tokens, US$0.004452.  The report SHA-256 is
`f0ba5da232ec3f122efd6d1e3a6d370bac636e94b9cc8fcb4cfbbce8e0956378`.
The shared cumulative ledger is now 33 calls and US$0.088276, leaving
US$1.911724 beneath the US$2.00 cap.

## Frozen identities and blind decision gates

The final C candidate is frozen as prompt
`cg353-unified-prompt-v2` SHA-256
`6cd2b5fc88e4f6dc1d952af4166b5e85e0a02bb3e51f456342ff06e7c60bba44`,
unified schema SHA-256
`542d23c8ca4aa6e86edc40a5a3189ec1f6c227c28e50ebb87f4871668e137281`,
and existing packet selection `central-packet-selection-v1` bound to the
frozen corpus above.  No further prompt, schema, packet, or decision-rule
tuning is authorised before blind validation.

The blind comparison may promote C only if pre-labelled review shows: no new
dangerous-category error against B; no material regression in general or
Ethos/Notability supported outputs; provenance and schema validation at least
as good as B; and a meaningful efficiency benefit (fewer calls or materially
lower USD).  Otherwise the immutable decision is dedicated-vs-unified
negative, with no automatic knowledge promotion.  Because workshop labels do
not prove the non-inferiority gates, the frozen current decision is
**not ready for promotion**; t06 must validate dedicated versus this frozen C
candidate on the five blind controls without tuning.
