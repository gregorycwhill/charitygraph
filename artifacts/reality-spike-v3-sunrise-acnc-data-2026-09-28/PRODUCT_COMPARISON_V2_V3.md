# Product comparison: Reality Spike v2 → v3 — Sunrise Foundation Limited

Both are non-production product experiments. ACNC `f1413902-d240-eb11-bf72-000d3ad1ce4e` remains the canonical external charity-source identity. ABN `37646526132` is used only to join official datasets.

## What changed for a donor or researcher

V2 proved the ACNC record and three AIS landing pages existed, but those pages were shells: it could not tell a researcher what Sunrise reported. V3 has a current official ACNC Register row plus substantive official 2023 AIS data, a 2022 comparison row, and the separate 2023 program-row result. The fields are preserved verbatim in `acnc_baseline.json`, so the card can report the charity's recorded status, size, location/website if disclosed, activities, beneficiaries, workforce/volunteers, and year-bound financial and balance-sheet fields whenever present in the rows.

## Substantive v3-only evidence

- Current-register source row and every source-native register column/value retained.
- 2023 AIS source row and every non-empty source-native field/value retained — including reporting, activity, workforce, financial and balance-sheet fields where Sunrise supplied them.
- 2022 AIS row retained for temporal comparison rather than treating 2023 as timeless.
- Separate 2023 ACNC programs dataset was actually queried; its Sunrise rows (or explicit absence) are retained.
- The public-report outcome is bounded: the AIS `financial report date received` value is retained, but no direct public report URL/document metadata was acquired. This is not misrepresented as proof of no lodged/required report.

## Answers to the product questions

**Did bulk data solve the page-shell problem?** Yes. It delivered substantive, row-level AIS/register data locally rather than only ACNC landing-page titles.

**What remains unavailable after the free bundle?** The actual lodged-report document and its narrative/detail, responsible-person names/count if withheld or not in the row, and any missing source-native fields. No claim is filled by inference.

**Did a lodged report exist and what did it add?** No public report document was acquired. `lodged_report.json` records the exact bounded outcome and the AIS financial-report-date field; it does not infer a no-report conclusion.

**What now requires web enrichment?** First-party mission narrative, current program detail beyond AIS classifications, and report/document content if later exposed by ACNC or Sunrise.

**Is this useful without manual research?** Yes for a regulator-led baseline and year-bound scale/activity research. It is not yet a full narrative diligence profile because a public lodged report and first-party web enrichment were not acquired.

## Remaining bottleneck

The next product seam is ACNC document metadata/direct-document acquisition (and then carefully bounded first-party enrichment), not another model step. The model has one structured baseline to summarise; it cannot recover unavailable report content.

## Scope confirmation

Only `artifacts\reality-spike-v3-sunrise-acnc-data-2026-09-28` was created for this v3 spike. S0 and Attempt20, A3/reservations/accounting, production acquisition, publication, and all v1/v2 artifacts were untouched.
