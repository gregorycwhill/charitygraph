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
