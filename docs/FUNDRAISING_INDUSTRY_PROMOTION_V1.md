# Fundraising industry promotion boundary v1

**Status:** Review-only internal candidate contract.  It implements the bounded
4 October 2026 research gate and does not authorise acquisition, canonical
promotion, public projection, or source-adapter scale.

**Integration basis:** clean successor worktree `terra/t07-govern-industry-source-promotion-paths`, based on Builder `2151733`; selected 287 implementation commits `51f8715`, `777980f`, `6b5b942`, `1ee922c`, `1d7ae85`, `fe0c0d4`, and `08ba60c` were cherry-picked in dependency order.  This boundary is refined by local commit `8b932be` to consume structured facets rather than infer them from prose.

`fundraising_industry_promotion.promote_industry_record` accepts an already
retained, source-native record and returns `IndustryPromotionCandidate` items.
It has no persistence or canonical-promotion operation.  Every output remains
`review_required`, unless it is `identity_blocked` or `unsupported`.

## Required evidence boundary

The caller supplies the bound subject identity, observation date, source record
identifier, source URL/location and wording.  The boundary creates a content
hash and an evidence reference, and preserves source family, source role,
scope, observation date, lifecycle (normally `unknown`) and review state.

Canonical facets are accepted only from the record's explicit
`source_supported_facets` field.  This is a structured source/crosswalk output;
the promotion boundary deliberately does not classify source prose.  An absent
facet remains absent.  PFRA-scoped F2F evidence may propose only the F2F facet
and does not establish setting, delivery party, compensation, regular giving or
current use.

FIA and P2P records may propose a campaign and source-native metric candidate.
Reported amounts remain source metrics: they are not AIS donations,
fundraising expenditure, an allocation, proceeds, ROI or effectiveness claim.
Money is attached only to the explicit campaign record; aggregate or portfolio
money with no supported campaign/practice scope is `unsupported`.

A provider relationship requires a separately resolved provider subject and
separate provider evidence IDs.  A provider name, award nomination, directory
entry, or ambiguous provider binding does not create one.

## Review outcome

A reviewer must make any later governed-decision/promotion under the ordinary
identity, source-rights, evidence and public-projection controls.  This module
does not represent that decision and cannot turn review candidates into
canonical observations.  Research retrieval remains outside this path.
