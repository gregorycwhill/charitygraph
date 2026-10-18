# Frozen v1.3 case diagnosis

The locators below are retained source-native record locators, not new
acquisition targets. “Semantic adjudication” means Python does not infer the
English meaning of a passage.

| Case | v1.3 failure classification | Frozen source-native basis | Repair/result |
| --- | --- | --- | --- |
| Good Friday Appeal / SDC-0037 | 4 incorrect requirement citation; 8 genuine unresolved temporal demand | ACNC register `srcrec:b64…5e38`, `https://www.acnc.gov.au/api/dynamics/entity/0ff5e226-38af-e811-a95e-000d3ad24c60`, supplies ABN 69084797965. The governed ABN binding is provenance-bound to that record. ABR `srcrec:b356…c3ad`, `https://abr.business.gov.au/ABN/View?abn=69084797965`, supplies the same ABN, entity name and “Active from 01 Nov 1999”. | The response marked the exact non-inference requirement supported with no citation, so correctly failed. The packet now distinguishes an uncited guard acknowledgement from factual evidence. Both frozen identity propositions have cited authority material; the governing binding itself still has null valid_from/valid_to, so any additional binding-period claim remains explicitly qualified rather than silently filled. |
| Cancer Council Victoria / SDC-0003 | 5 correct bounded support rejected mechanically | Official source `srcrec:12ec…b800`, `https://www.cancervic.org.au`, is a complete retained source-native representation. It explicitly describes Cancer Support, a support line for “all Victorians affected by cancer”, qualified-professional support, and local support service guidance. It is distinct from ACNC address/program/beneficiary metadata. The retained FY2025 report is `srcrec:8274…df0a` with its ACNC public document URL. | The old response cited the official source and annual report for bounded service, cohort and Victorian geography but the validator rejected two propositions solely from its `beneficiary_category`/`operational_geography` labels. Contract 1.4 retains the cited assertion with provenance and leaves source-text entailment for adjudication; it does not convert ACNC metadata into service scope. |
| University of Western Australia / SDC-0007 | 7 self-contradictory proposition state; 8 genuine unresolved demand | Selected annual-report record `srcrec:5b35…fca3`, public ACNC workbook URL, reports organisation-wide financial information. Official site `srcrec:7701…5a4d`, `https://www.uwa.edu.au/home`, was provider-visible and represented but not selected. | The response correctly stated no award, commitment or payment-specific evidence, but simultaneously labelled organisation-level revenue `supported` with unresolved scope. That remains invalid: strong proposition support requires resolved scope/time. The candidate packet preserves the official source for reassessment but does not claim that it supplies the missing flow joins. |
| Australian Wildlife Conservancy / SDC-0005 | 7 self-contradictory proposition state; 8 genuine unresolved temporal/service link | Official retained source `srcrec:ced5…48aa`, `https://www.australianwildlife.org/`, explicitly contains a volunteer route in the captured representation. | The source was acquired, represented, transmitted and selected. The response described a captured advertised route but labelled it `supported` while temporal status was unresolved and its service linkage was unresolved. Contract 1.4 keeps this as citeable partial knowledge only; it cannot become an enduring placement or a strong conclusion. |
| Leukaemia Foundation / SDC-0052 | 4 incorrect requirement citation; 8 genuine unresolved study demand | FY25 annual report `srcrec:863b…9c47`, public ACNC document URL, is the selected source-native representation. It supports the reported service metric (39,800 instances / 6,881 people); it does not itself supply a study design, intervention-to-study join, study population, or missingness measure. | The metric is retainable bounded partial knowledge. The response’s non-inference requirement was instead marked `supported` with no evidence and correctly failed. Contract 1.4 uses the typed guarded state for that non-evidentiary constraint; it cannot promote the metric into a study result. |
| Plan International Australia / SDC-0028 | 6 unsupported inference rejected at conclusion level; 8 genuine unresolved rule demand | Official source `srcrec:66f9…6876`, `https://www.plan.org.au`, and FY25 annual report `srcrec:af51…4ab5`, public ACNC document URL, were selected with regulator/ABR material. They are organisation/program evidence, not a supplied universal mandate-screen rule. | The old broad scope-label check incidentally invalidated three individual assertions, but could not establish their semantic truth or falsity. Contract 1.4 does not pretend otherwise. The response’s `insufficient_evidence` conclusion remains the only mechanically admissible disposition because exact rule, screening, coverage and temporal requirements are unresolved. No generic rule has been weakened. |

## Source-selection progression

| Case | Status in frozen v1.3 | Conclusion |
| --- | --- | --- |
| Amnesty / SDC-0051 | Official website and annual report were admitted, represented, transmitted and selected; PFRA and Wikimedia were rejected. | The source progression is not the blocker. The selected material was interpreted as advocacy/program metadata rather than a service cohort; result was mechanically valid insufficient evidence. |
| AWC / SDC-0005 | The official website was admitted, represented, transmitted and selected. | It was selected but misrepresented as a strong proposition despite unresolved time/service linkage; no missing-source classification. |
| UWA / SDC-0007 | Official website was admitted, represented and transmitted but not selected; the annual workbook was selected. | The annual workbook provides organisational financial facts but not the demanded award/commitment/payment/revenue joins. The official page is preserved in the next packet, but no claim is made that it fills those joins. |

## Negative controls

- Benevolent Relief Fund: historical expenditure remains unable to support a
  prospective marginal-allocation conclusion without an explicit allocation
  decision.
- Plan: organisation purpose/reporting/classification remains unable to
  support an unspecified universal mandate screen.

These are protected by exact requirement coverage plus the positive-conclusion
check; the new provenance envelope does not promote any prior result.
