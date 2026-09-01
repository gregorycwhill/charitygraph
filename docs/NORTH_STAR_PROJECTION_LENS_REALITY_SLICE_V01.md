# North-Star projection lens reality slice v0.1

This downstream experiment consumes only the 44 persisted candidate Observations
from Compact v0.2. No source payloads were retransmitted and no knowledge
generation occurred. The lens saw packet-local observation keys and semantic
fields only; Builder retained the durable-ID mapping locally.

| Subject | Observations | Assignments | Zero sections | One section | Multiple sections | Cost (USD) |
|---|---:|---:|---:|---:|---:|---:|
| Life Without Barriers | 12 | 12 | 0 | 12 | 0 | 0.000608 |
| Australian Conservation Foundation | 11 | 11 | 0 | 11 | 0 | 0.000560 |
| Australian Red Cross Society | 21 | 21 | 0 | 21 | 0 | 0.001029 |

All 44 observations received exactly one valid assignment. Populated sections
were LWB: 1, 2, 3, 4, 5, 6, 10, 13; ACF: 1, 2, 3, 4, 5, 7, 11; and Red
Cross: 1, 2, 3, 4, 5, 6, 7, 8, 10. Empty sections mean only that no sampled
observation mapped there; they are not completeness or absence claims.

Projection files preserve each packet assignment and its durable Observation ID;
the same Observation may appear in multiple section views without duplication.
Evidence and lineage remain reachable through the durable observation records.
Total lens cost was USD 0.002197 across three Luna calls with no retries.

A first schema preflight was rejected before generation because optional fields
were not strict-required; the harness corrected this mechanically before the
three successful requests. No semantic changes were made and no additional
provider call was used for that failed preflight.
