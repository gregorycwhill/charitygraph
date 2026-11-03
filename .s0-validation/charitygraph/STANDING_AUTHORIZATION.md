# Standing Luna authorization (private runtime)

The Builder supports a revocable standing authorization for routine semantic
inference. The authorization is stored only in the private runtime authority
database, never in Git.

The initial policy shape is bounded to OpenAI `gpt-5.6-luna`, governed lawful
public-source CharityGraph evidence, and approved semantic inference tasks.
It permits at most one physical transmission per deterministic task and never
authorizes automatic publication, Terra, Sol, embeddings, credentials,
non-public personal information, or ungoverned material.

Standing policy authorization and an individual exactly-once call slot are
separate. Every task still has deterministic identity, preflight reservation,
budget reconciliation and a single durable execution slot. Policies are
inspectable and revocable; expiry may be set at a project or milestone
boundary. Historical task-specific authorizations remain unchanged.

The actual product-owner standing authorization record must be established in
private runtime state through the governed operational procedure. This
document defines the contract only and is not consent itself.

## ExecutionMandate control plane

External-action authorization may be either one-off or standing.

Standing authorization is a bounded, mechanically enforced delegation
envelope. Human review is required when the envelope changes, not merely
because another conforming campaign has been prepared.

An `ExecutionMandate` is distinct from a campaign, request item, delivery
attempt, physical attempt, reservation, receipt, or provider response. Every
physical transmission must prove its provider, model, reasoning, delivery,
contract/prompt/schema identities, request ceiling, and remaining aggregate
authority against an active mandate immediately before send. Batch, Flex,
fallbacks, retries, ambiguous resends, governed promotion, CanonicalObservations,
adjudication, publication, source acquisition, and release remain outside the
Phase-5 Standard Luna mandate.

LLM autonomy can run right up to the irreversible external-action gate; a
standing mandate may authorize a bounded class of crossings of that gate.

Mandate amendments are append-only. New contract or provider-boundary
identities, delivery/retry changes, cost-cap increases, and authorization or
reservation semantic changes require fresh authorization or an explicit
amendment. Historical one-off authorizations are never relabelled as mandate
authorizations.

Monotone safety and accounting corrections are not authority expansions when
provider, model, delivery, contracts, and ceilings remain unchanged. Active-
reservation send gates, isolated rehearsal ledgers, append-only evidenced-spend
corrections, and stricter fail-closed validation may therefore be applied
without a new campaign approval. Authority-expanding changes still require
fresh review.
