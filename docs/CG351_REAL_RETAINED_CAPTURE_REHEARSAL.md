# CG351 real retained-capture rehearsal

**Status:** completed private readiness rehearsal; no acquisition, provider call,
canonical admission, projection persistence, release, or Data-repository change.

The new `reality_spike_retained` adapter mechanically reads the retained
`archive/processed/reality-spike/2026-08-10/source-inventory.json` and only
the immutable blobs and representations it names.  It verifies each source
blob against the inventory SHA-256, hashes its retained JSON representation,
and creates the shared `RetainedCaptureUniverse` consumed by both CG347
packet builders.  It does not discover, retrieve, or write source material.

## Result

`python scripts/rehearse_retained_capture.py <archive-root>` succeeded against
the local retained archive on 2026-10-09.  It built three real-organisation
universes: two contain an annual report plus a website snapshot, while the
third has an annual report only.  All five source-blob hashes matched the
central inventory.  The provider-free adapter returned a schema-valid
abstention for each domain; §15 and §17 each reached `REVIEW_REQUIRED` with
zero candidates and zero provider calls.  Their packet IDs/hashes are emitted
by the command, rather than committed, because they are private operational
evidence.

The semantic task receives only a `RetainedCaptureUniverse`.  The contract
tests replace `urllib.request.urlopen` with a failure and demonstrate that a
provider attempting acquisition fails.  The rehearsal provider is an offline
object with no transport implementation.  Thus network access from a semantic
task is a test failure, not a fallback source path.

## Next-run handoff

For the fresh 15-organisation pilot, central acquisition must first deliver
an inventory-equivalent resolved binding, immutable source blob/hash, and
retained representation for every chosen subject/source family.  Run semantic
workers in a network-disabled environment and supply only those universe
objects.  A real paid provider call remains separately authorised work; its
candidate output must remain on the existing schema-validation and
`REVIEW_REQUIRED` route.  The current retained sample proves the input seam,
not 15-case source coverage or empirical extraction quality.
