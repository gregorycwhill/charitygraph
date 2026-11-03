# CG360 immutable Builder stage-manifest contract

Every bounded Builder stage writes one immutable manifest using
`schemas/builder-stage-manifest-v1.schema.json` (with a minimal valid example
at `schemas/examples/builder-stage-manifest-v1.cohort.example.json`).  The manifest has a content
hash, hashes the exact output artifact, carries the exact cohort hash, and
links only to the immediately preceding manifest.  A successor must retain all
predecessor bindings byte-for-byte and add its own output binding:

`cohort -> authorised corpus -> evidence registry/packet -> extraction request-set -> structured output -> Semantic Demand evaluation`.

The runtime must call `verify_manifest` with the on-disk predecessor before it
constructs a request or reaches a provider. Missing artifacts, stale bytes,
missing cohort identity, non-adjacent predecessors, changed inherited hashes,
and altered manifest bytes are hard failures. Manifests are append-only run
evidence; historical CG359 artifacts are not rewritten.

CG359's contradictory accounts are reconciled as an identity failure, not a
semantic result: T04 reported no correctly bound cohort/corpus; later T05/T06
could independently packetise from paths and the Luna runner independently
rebuilt requests from its corpus/representation arguments. Neither handoff
required the T04 predecessor hash. Thus the recorded 15 attempts/30 packets
describe a later packetisation state but cannot prove it was the failed T04
state. The new chain makes that substitution fail before provider execution.
