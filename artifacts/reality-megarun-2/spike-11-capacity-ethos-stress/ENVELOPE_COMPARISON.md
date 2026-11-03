# Envelope comparison

## Baseline envelope tested

`subject · proposition · value · attribution/source locator · authority · claim status · scope · valid/observed time · section route · confidence/review state`

This is enough for an attributed, non-comparative statement. It is deliberately not an assertion that a listed service is available now, that a reported number is capacity, or that a stated value was implemented or achieved.

|Measure|§7 capacity|§15 ethos|Combined|
|---|---:|---:|---:|
|Candidate propositions|10|8|18|
|Fit unchanged envelope|5|6|11|
|Need minimum extension|3|2|5|
|Abstain / hold|2|0|2|
|Section routing correct (accepted candidates)|8/8|8/8|16/16|
|Projection loss, unchanged envelope|3/8 (38%)|2/8 (25%)|5/16 (31%)|
|Temporal/currentness flags|4|1|5|
|Human review units|8|8|16|

The two §7 holds are deliberately not presented as propositions: one treats an advertised service description as live availability; one would infer throughput from workforce/reach material. An additional comparison hold (current availability) is counted in the ledger as a review block, not as a safe candidate. §15 has no blank-evidence hold, but a policy/commitment is never projected as implementation or outcome.

## Minimum disposable extension

Attach an optional, versioned `domain_semantics` object to a proposition; do not alter the universal envelope or public card contract.

```json
{
  "kind": "capacity|ethos",
  "capacity": {"measurement_kind": "service_description|availability|capacity|throughput", "quantity": null, "unit": null, "denominator": null, "period": null, "operational_scope": null},
  "ethos": {"assertion_stage": "value_or_commitment|policy|implementation|outcome", "commitment_type": null}
}
```

Only 5/16 accepted candidates need it (31%). It has two discriminated branches and no generic fields for relationship, financial, outcomes, classification, or every future domain. It is therefore disposable: delete it and preserve the 11 attributed statements, while explicitly losing measurement/stage precision for the five marked records. Promoting its fields into the base envelope would make a mega-schema before evidence justifies it.

## Overclaim controls demonstrated

* Service description does not mean it is open, geographically reachable, eligible, staffed, funded, or currently available.
* Workforce, branches, volunteers, deployment and reach statements do not supply a numerator, unit, time window and denominator required for capacity or throughput.
* A report period is an observation period, not a currentness warranty; silence is `not established`, never `unavailable`.
* Values, faith statements, codes and policies are attributed self-description/commitment. Implementation requires implementation evidence; outcome requires outcome evidence. Neither is inferred.

## Review burden

There are 16 reviewable accepted candidates plus 3 overclaim blocks requiring a short adjudication note: 19 units. At the prior Spike 7 planning range of 30–90 seconds each, this is 9.5–28.5 minutes (19 minutes midpoint), excluding escalation. The extension removes 5 semantic ambiguity escalations but does not lower authority review: it makes the review question explicit.
