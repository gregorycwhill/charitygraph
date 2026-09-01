# Full-corpus Compact Knowledge reality slice v0.1

The first full-corpus execution attempt was correctly blocked before provider
transmission because the available shard runner was coupled to the superseded
v0.1 whole-card executor. No provider transmission occurred. The correction is
architectural simplification: deterministic shard planning remains delegated to
the established planner, while provider execution is delegated to the validated
Compact v0.2 path. It reuses every substantive governed
Baseline Corpus representation for Australian Red Cross Society, Life Without
Barriers and Australian Conservation Foundation; only robots/sitemap artefacts
are excluded.

The deterministic source-coherent partition produces 8 shards: Red Cross 5,
Life Without Barriers 2 and ACF 1. Estimated shard input tokens are 44,843,
49,163, 46,026, 44,346, 9,057, 39,977, 43,431 and 53,627. With the required
Compact v0.2 configuration (`reasoning=none`, 7,000 maximum output tokens,
one request per shard), projected exposure is USD 0.133294, above the USD 0.08
maximum. No evidence-bearing provider calls were made and no coverage was
silently reduced.

This branch records the dedicated runner and dry-run plan; it does not alter the
Compact contract, shard strategy or downstream North-Star lens.
