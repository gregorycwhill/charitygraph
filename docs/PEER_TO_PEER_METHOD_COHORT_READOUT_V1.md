# Peer-to-peer method cohort readout v1

**Status:** local, review-only fixture regression. This record is not source
acquisition, a prevalence denominator, an external precision/recall result, or
authority to promote a public surface.

## Family boundary

The cohort covers the specific **peer-to-peer fundraising** family: a
supporter is evidenced as raising or collecting support from their own network
for the organisation or named campaign. It is distinct from a generic donation
page, an event, a community program, and a payment/platform provider.

No assertion of currentness, campaign identity, delivery party, payment
instrument, compensation, reach, amount raised, or channel effectiveness is
made unless separately evidenced.

## Fixture result

`tests/fixtures/peer_to_peer_method_cohort.json` contains six retained,
source-free test descriptors, each carrying its native wording. The focused
test evaluates the governed claim compiler and reports one outcome per
descriptor:

| Outcome | Cases | Denominator |
| --- | ---: | ---: |
| Reviewed, bound P2P practice candidate | 2 | 6 |
| Generic donation/event/platform wording retained as unresolved/no-match | 3 | 6 |
| P2P wording with ambiguous subject binding blocked | 1 | 6 |

The three no-match rows remain visible as source-native, unprocessed claims;
they do not become a negative claim that a charity lacks peer-to-peer
fundraising. The ambiguous-binding row also remains a refusal, rather than a
candidate or a negative.

## Guardrails exercised

- A positive mapping requires an explicit supplied claim and a `practice`
  evidence facet; this test adds no text-matching inference.
- Generic online donation copy cannot establish peer-to-peer practice.
- A community event cannot establish peer-to-peer mechanics.
- Naming a platform cannot establish a provider relationship or peer-to-peer
  practice.
- An ambiguous organisational binding cannot be promoted.

The 2/6 candidate count is only local fixture coverage. It does not alter the
closed source-backed scale gate or the 290 external-cohort requirement.
