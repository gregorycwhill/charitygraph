# Reality Spike 8 — Architecture inversion / straight-line challenge

`REALITY_SPIKE_8_ARCHITECTURE_INVERSION_DISCOVERED`

Completed concrete A/B/C outputs for 5/5 required subjects, from actual local retained state. Provider calls: 0. Network acquisition: 0. S0/canonical mutation: 0.

## Result

B reproduces A’s populated North-Star sections and explicit missingness exactly for all five subjects. Its card remains useful because retained facts already have subject, evidence, authority, time, and section assignment. C demonstrates that the preferred Spike-7 orientation surface can be query-time, but only as a bounded read model with a ledger and visible coverage.

## Forced decisions and observed consequence

|Decision|Observed result|
|---|---|
|Universal envelope vs domain records|Works for this structured-baseline replay; does not certify relationships, units, conflicts or corrections.|
|Write/build vs query/render projection|B is replayable/materialized; C is compact but selection and cache/correction behaviour become view policy.|
|Promotion prerequisite vs status metadata|Metadata safely labels this experiment’s already-accepted inputs; it cannot replace review for Spike-6/7 candidates.|
|Stored vs derived section assignment|Existing assignment can be deterministically replayed; deriving a new assignment is the missing semantic work, not free simplification.|
|Explicit missingness vs computed coverage|Computed B coverage matches A here; explicit durable coverage is stronger when “not processed” has workflow meaning.|
|Cards vs ephemeral projections|Card is a useful cache/read model; ledger/propositions must remain the truth surface.|
|Historical runtime vs migration boundary|Historical compiler enables A but is clear migration residue; keep compatibility at a boundary, not in the active product path.|

## Recommendation for final synthesis

Adopt the simplest faithful shape as: **durable, source-attributed proposition envelope with status, scope/time and explicit coverage; deterministic versioned North-Star routing; progressive card plus evidence ledger as read models; query-time AI only over that ledger.** Keep domain extensions and governance records where measurement, relationships, conflict, correction, or high-risk candidate review require them.

The straight-line challenger gets dangerously wrong the idea that all proposition values are interchangeable. Without durable conflict/supersession, authority granularity, unit/relationship semantics, and risk gates, it can turn first-party or model-extracted text into apparently settled product claims. Its success is evidence against duplicated phase translations and card materialization as canonical state—not against evidence governance.

See [actual path](PATH_A_ACTUAL.md), [straight-line path](PATH_B_STRAIGHT_LINE.md), [query-time path](PATH_C_QUERY_TIME.md), [parity/losses](PARITY_AND_LOSSES.md), [budget](COMPLEXITY_BUDGET.md), [delete test](DELETE_TEST.md), and `summary.json`.
