# CG351 retained-capture input seam

`charitygraph.retained_capture` is the executable boundary between central
acquisition/representation and semantic workers.  `RetainedCapture` requires
the existing `SourceRecord`, its content-addressed `srcblob:` identity and
hash, one derived representation with that blob declared as input, and an
existing bounded `EvidenceFragment` whose `content_ref` names that
representation.  Its deterministic lineage ID covers all of those identities
and hashes.

`RetainedCaptureUniverse` accepts only resolved deterministic subject bindings,
rejects conflicting source/representation identities, and binds the already
captured views to one governed subject and permitted scopes.  It can contain
multiple source families. `build_ethos_notability_packet` turns that universe
into the existing CG347 `FrozenEthosNotabilityPacket`; its hash includes the
complete retained provenance, exact fragment locator/hash, retrieval/version
metadata and packet-selection version.  This permits one retained source
version to appear in independently versioned §15 and §17 packet views without
copying it into a domain archive. It has no locator, HTTP/client, discovery,
archive-write or provider parameter. Central evidence preparation owns source
selection and coverage gaps. A semantic worker receives only the supplied
bounded universe.
