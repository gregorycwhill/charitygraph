# Product comparison: Reality Spike v1 → v2 ACNC-first

Both runs are non-production inspection material. V1 used ABR plus sparse web discovery; v2 deliberately resolves the ACNC charity-record UUID first and makes the regulator bundle the first acquisition step.

## Cross-cutting result

- **Identity clarity:** v2 separates CharityGraph's provisional subject sequence, ACNC record UUID/URL, and ABN as a supplementary ABR join attribute. V1 folder labels and card headings made ABN too prominent.
- **Baseline authority:** v2 retains the ACNC profile, people, documents, latest known AIS links, prior AIS history where found, and report/document attempts before web enrichment. This is a material provenance improvement even when the ACNC surface fails retrieval.
- **Product usefulness:** MSF remains enriched by its official site. Sunrise and Noongar now have canonical ACNC record identities and known AIS history rather than only ABR status, but the retrieved ACNC pages did not expose substantive AIS fields or a lodged-report URL; their cards remain appropriately sparse.
- **Bottleneck:** current bottleneck is ACNC document-index/field extraction, not model reasoning. Website discovery is secondary once the canonical material is acquired.

## Per-charity comparison

### Medecins Sans Frontieres Australia Limited

V1 had ABR plus two useful official pages and no ACNC/AIS/report baseline. V2 resolves ACNC `33ed3439-38af-e811-a962-000d3ad24a0d`, retains current register/profile/people/document material and a 2024 AIS landing record, while preserving the official-site enrichment. The card is more trustworthy in its identity spine; actual AIS financial detail and a lodged financial-report URL were not exposed in the retained content.

### SUNRISE FOUNDATION LIMITED

V1 was an ABR-status triage card. V2 resolves ACNC `f1413902-d240-eb11-bf72-000d3ad1ce4e` and retains known AIS landing records for 2023, 2022 and 2021 plus profile/people/documents material. That decisively improves auditability and tells a researcher exactly where the omitted baseline should be, but does not manufacture a mission, program, beneficiary or finance profile when the retrieved content supplies none.

### Noongar Boodja Trust

V1 was likewise ABR-status triage. V2 resolves ACNC `cf5f4d7d-6ab4-eb11-8236-000d3a6abd1c`, retains profile/people/documents material and a 2023 AIS landing record. It adds a canonical source spine and explicit evidence trail but cannot establish operating facts without substantive regulator fields or report content.

## Decision readout

ACNC-first is the correct product order: it prevents ABN from becoming the subject identity and converts sparse cards into inspectable regulator-led research starting points. The remaining product gap is not another semantic layer: make ACNC profile/AIS/document acquisition resilient (or use an authorised ACNC dataset/export) and extract the resulting reports. Until then, Sunrise and Noongar require significant manual follow-up; MSF is useful for discovery but still incomplete for financial and governance research.
