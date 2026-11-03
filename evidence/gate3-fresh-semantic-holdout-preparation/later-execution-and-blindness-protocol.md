# Later execution and blindness protocol

This packet authorizes none of these steps. They are the required order for a later, separately authorized experiment:

1. Verify and freeze this selection manifest and its inventory.
2. Independently establish and seal the reference oracle outside Builder.
3. Acquire and represent evidence only through Source Universe v1, preserving acquisition/representation/rights states.
4. Freeze Builder evidence packets and their source/representation/rights identities.
5. Freeze prepared provider-request identities, costs and exactly-once execution controls.
6. Obtain fresh trusted direct execution authority; CG406 authority is not transferable.
7. Execute each exact request once, with no semantic retries or post-hoc sample replacement.
8. Freeze each first terminal response, its receipt and cost accounting.
9. Run mechanical schema, packet-ID, lineage and contract validation.
10. Reveal the sealed oracle only to the independent adjudicator; score against the preregistered rubric and report per-domain plus aggregate results.

Every boundary requires a content-addressed manifest. Any identity or rights drift fails closed and requires a fresh decision; it does not permit a resend or silent substitution.
