# Classification rules applied to each row

Every one of the 30 row identities in `row-classification.json` is a `CATALOG_MECHANICAL_GAP`: its governed artifact, frozen source-record ID and acquisition-receipt ID already existed, but the copied development catalog did not reconstruct the ordinary source-record/receipt linkage.

| Family | Rows | Provider payload actually assessed | Classification and governing rule |
| --- | ---: | --- | --- |
| `ato_abr_dgr` | 12 | Source-native HTML table facts, rendered as structured JSON | `REPRESENTATION_MUST_BE_NARROWED`; `PUBLIC_FACTS_ONLY_V1` allows only `structured_factual` and `factual_representation_only`, not the full HTML body. |
| `annual_report` PDF | 10 | First `min(5, floor(page_count/5))` retained PDF pages’ native text | `REPRESENTATION_MUST_BE_NARROWED`; `AU_FAIR_DEALING_ANALYTICAL_PROCESSING_V1` permits a bounded excerpt, never a complete work, and the V1 bound is at most five pages and 20%. |
| `annual_report` XLSX | 1 | No payload constructed | `TRUE_POLICY_GAP`; existing policy has no deterministic workbook sheet/range boundary. The source remains catalogued but provider-ineligible. |
| `wikipedia_wikimedia` | 4 | Bound source-native search-result record, without article body/snippet copying | `REPRESENTATION_MUST_BE_NARROWED`; `PUBLIC_FACTS_ONLY_V1` applies to the factual structured record, not the raw multi-result API body. |
| `pfra` | 3 | Exact source-native membership card bound through the governed ACNC website locator | `REPRESENTATION_MUST_BE_NARROWED`; `PUBLIC_FACTS_ONLY_V1` permits the factual card rather than the full membership-page body. |

For every allowed narrowed representation, the decision is keyed to `(original source artifact ID, SHA-256 of exact transmitted representation)`, carries the original source record, role, origin and receipt, uses no local retention authorization, and prohibits public redistribution. That preserves the exact artifact/representation distinction and fail-closed behaviour.
