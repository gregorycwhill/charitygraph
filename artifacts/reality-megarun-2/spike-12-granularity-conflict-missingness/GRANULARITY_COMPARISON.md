# Granularity comparison

## Result

G2, an **atomic asserted proposition with inseparable qualifiers**, is the useful ledger unit. It says one thing about one subject, within one declared scope and validity interval, while preserving source attribution. It may retain a structured value when the value cannot be split without changing meaning. It is not a sentence, a section bundle, a database cell, nor an unqualified fact.

| Test | G1 narrative claim | G2 atomic proposition candidate | G3 predicate/value record |
|---|---|---|---|
| Units from the same 12 retained evidence items | 12 | 23 | 68 |
| Cross-section reuse | 7/12, but bundles leak adjacent meanings | 20/23 reusable without restatement | 31/68 reusable; joins needed for intelligible use |
| Exact/near duplicate handling | 3 bundles require manual reading | 5 duplicate/near-duplicate candidates grouped by assertion key | 19 records collide but differ only in field fragments |
| Real period/scope near-collisions correctly not called conflict | 1/3 | 3/3 | 3/3, but only after rejoining fields |
| Source-role difference visible | mixed into prose | explicit and reviewable | explicit but spread across records |
| Abstention / missingness readable | easy, but conflated with no claim | explicit and separate | mechanically possible, poor card readability |
| Projected section quality (0–5) | 2.5 | 4.5 | 2.0 |
| Estimated reviewer decisions | 12 broad decisions | 27 (23 propositions + 4 relation decisions) | 73 (68 records + 5 joins/relation decisions) |

The counts are a small hand-audited fixture, not a forecast. G1 understates burden by hiding distinct assertions inside one review decision; G3 overstates it by requiring a reviewer to reconstruct ordinary language from fragments.

## Tests exercised

| Requirement | Finding |
|---|---|
| Cross-section reuse | G2 permits Red Cross service/footprint evidence to appear in capacity and participation views with distinct projection labels, without copying the claim. |
| Duplicates | Same `subject + predicate + normalised value + scope + validity` is a candidate duplicate. Different locator/source remains supporting evidence, not a new proposition. |
| Conflicting first-party statements | No retained substantive contradiction exists. The detector must first compare asserted predicate/value, then scope and validity. It flags the fixture as `needs_relation_review`, never as a factual conflict. |
| Scope differences | Organisation, program/service, site/branch, and population are qualifier values, not predicates and not routing buckets. A branch/service statement cannot project as organisation-wide availability. |
| Time and supersession | Report period bounds the assertion. A later source may `supersede` only after review and only for the same assertion key and scope; newer retrieval alone is insufficient. |
| Source roles | First-party report, regulator structured record, and extraction status affect evidence/review treatment, not the truth identity of a proposition. |
| Abstention | A reviewer may retain `abstain` for an examined candidate; no positive proposition is emitted. |
| Missing and not processed | These are coverage observations keyed to an entity and requested projection domain. They never mean the proposition is false or absent in the world. |
| Correction | Corrections and supersessions are typed relations between proposition revisions, preserving the original assertion and evidence. |
| Ledger/card readability | A ledger displays one short attributed assertion plus scope/time/status. Cards display only promoted propositions and a separate coverage panel. |

## Routing decision

Routing belongs primarily in a deterministic **projection view/router**, taking proposition predicate, subject type, scope, status and optional domain semantics as inputs. A proposition may carry optional `projection_hints` generated at extraction for review convenience, but those hints are not durable truth and must not be authoritative. Encoding routes on propositions would duplicate policy and make cross-section reuse brittle.

## Missingness decision

Coverage stays separate from positive propositions. A proposition asserts something; coverage records that a domain was not processed, had no compatible retained evidence, was unavailable in the examined packet, or was deliberately withheld. Combining them would turn workflow knowledge into an assertion about the organisation and would falsely make sparse controls look negatively evidenced.

## Failure modes retained by G2

* A vague predicate vocabulary can silently recreate G1; tightly controlled predicates and review examples are needed.
* Complex measures and ethos-stage distinctions still need the small optional `domain_semantics` qualifier found in Spike 11.
* Conflict resolution needs a genuinely contradictory retained corpus before any automated resolution rule is trusted.
* Entity identity and scope matching are prerequisites; without them, atomicity produces precise-looking errors.
* G2 does not solve source authority, promotion, provenance, or migration design; none is hardened here.
