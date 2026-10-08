# CG351 retained-capture input seam

`charitygraph.retained_capture` is the executable boundary between central
acquisition/representation and semantic workers.  `RetainedCapture` requires
the existing `SourceRecord`, its content-addressed `srcblob:` identity and
hash, one derived representation with that blob declared as input, and an
existing bounded `EvidenceFragment` whose `content_ref` names that
representation.  Its deterministic lineage ID covers all of those identities
and hashes.

`RetainedCaptureUniverse` binds already captured views to one governed subject
and permitted scopes.  `build_ethos_notability_packet` turns that universe into
the existing CG347 `FrozenEthosNotabilityPacket`; its hash includes the packet
evidence and text.  It has no locator, HTTP/client, discovery, archive-write or
provider parameter.  Central evidence preparation owns source selection and
coverage gaps.  A semantic worker receives only the supplied bounded universe.
