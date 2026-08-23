# CharityGraph Builder — Agent Instructions

**Status:** Canonical repository instructions  
**Architecture authority:** [ARCHITECTURE.md](ARCHITECTURE.md)

Read the sibling Data repository's DOCUMENT_AUTHORITY.md, current state and plans before changing cross-product behaviour. Builder's internal authority is governed typed observations attached to durable subjects and scopes. Cards are public release projections, not canonical stored knowledge.

## Boundaries

- Do not add raw sources, private evidence, reports, website snapshots, prompts, model responses, runtime state, caches, credentials, logs or debug files to Git.
- Do not manually edit generated public projections.
- Do not change public contract 0.5, immutable release bytes, schemas, Viewer selection or compatibility identifiers without a separately approved migration.
- Do not create a database, index the archive, acquire sources or call a model unless the task specifically authorises it.

## Evidence and identity

Names and domains never create or resolve a subject by themselves. Preserve source records, bindings, evidence, candidates, governed decisions, canonical observations, coverage and derivatives as separate states. A local SQLite catalogue is rebuildable operational state, never the only evidence authority.

Treat funding source, fundraising practice, campaign and expenditure as different domains. Expenditure may be unavailable; universal priors, peer fill, forced midpoint and forced point estimates are prohibited.

## Compatibility

Literal compatibility identifiers such as causebase_id, causebase_builder, the causebase CLI alias and CAUSEBASE environment aliases remain isolated where code, tests or immutable public 0.5 bytes require them. Do not introduce those terms into new architecture or product prose.

## Completion

Run relevant tests, inspect generated diagnostics where applicable, verify publication allowlists and representation consistency, and report private-material exclusion. Do not use broad add-all Git commands.