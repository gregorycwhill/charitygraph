# CharityGraph public card-projection specification

**Status:** Reference for public contract 0.5 compatibility  
**Internal authority:** governed observations attached to durable subjects and scopes  
**Canonical public contract:** sibling Data repository PUBLIC_CONTRACT_0_5.md

A card is a stable, versioned public projection selected for one immutable release. It is not Builder's internal knowledge store and must never be manually edited.

## Projection contents

A release card may project public-safe identity, relationships, governed observations, source-record references, compact evidence, coverage, derivatives and release metadata. JSON, Markdown, CSV and Parquet representations must agree on shared released values, while preserving their appropriate structural detail.

The literal causebase_id remains only as the immutable public 0.5 compatibility key. It does not name Builder's internal SubjectRecord identifier, which is subject_id.

## Projection rules

- source-native records, candidates, decisions and canonical observations remain distinct internally;
- sparse projections are valid when public evidence is sparse;
- source statement labels, periods, scope, signs and conflicts remain available through public contract 0.5 structures;
- participation modes and opportunities remain distinct, as do action destinations and evidence URLs;
- a projected fundraising-expenditure value identifies its method and support; null with explicit coverage is valid;
- a card may expose a governed correction or context status but never raw submissions or private evidence;
- summaries, classifications, embeddings and similarities are derivatives with lineage, not independent facts.

See BUILD_AND_PUBLICATION.md for release acceptance and the Data public-contract documentation for exact schema semantics.