# Targeted v1.4 diagnostics for Sol

These are descriptions of the frozen model outputs and mechanical contract
validation, not semantic adjudications. The full per-proposition/per-requirement
states, selected and rejected IDs, evidence lineage and locators are in
`sol-handoff.json`.

- Good Friday Appeal (SDC-0037): `insufficient_evidence`, mechanically invalid.
  The response identifies the entity/ABN and notes the ABR active date of
  1 November 1999, but marks the temporal proposition supported while its
  scope is bounded and time unresolved. It incorrectly treats the governed
  binding's missing bounds as overriding the authority record's own date.
- Cancer Council Victoria (SDC-0003): the only raw `supported` result;
  mechanically valid. The response cites service-specific descriptions,
  beneficiaries, Victoria operating geography and a 2025 period, while keeping
  headquarters != delivery geography as a separate guarded non-inference.
  Sol must judge whether those citations entail the bounded service/cohort
  demand; no automatic semantic pass is asserted here.
- Australian Wildlife Conservancy (SDC-0005): `insufficient_evidence`,
  mechanically invalid. The official website lists volunteer and other
  participation routes. The output does not establish an advertised,
  time-bounded opportunity, eligibility, or an ongoing placement; one
  proposition is nevertheless declared supported with unresolved time.
- Amnesty International Australia (SDC-0051): `insufficient_evidence`,
  mechanically invalid. The response cites service/geography/population
  material but does not establish the required completed filtering operation,
  exclusions, or bounded cohort. Two requirements are incorrectly marked
  `guarded` although they are not frozen non-inference requirements.
- University of Western Australia (SDC-0007): `insufficient_evidence`,
  mechanically valid. Organization-level program/financial information and
  2025 revenue do not establish the requested award, commitment, payment, or
  financial-line joins. The output preserves those dimensions separately.
- Leukaemia Foundation (SDC-0052): `insufficient_evidence`, mechanically
  invalid. FY25 program/service metrics do not establish intervention-to-study
  design or study-to-population links. Two requirements misuse `guarded`.
- Caritas Australia (SDC-0038): `insufficient_evidence`, mechanically
  invalid. Dated governance records are identified, but do not bind the opaque
  target subject to the named person/role and all requested relations. Six
  requirements are incorrectly marked `guarded`.
- Plan International Australia (SDC-0028): `insufficient_evidence`,
  mechanically valid. Organization-level propositions are supported, but
  source-specific screening criteria and a rule-defined temporal obligation
  are not supplied; no qualified selection decision is asserted.
- Benevolent Relief Fund (SDC-0014): `insufficient_evidence`, mechanically
  valid. Historical expenditure of AUD 37,094,958 for the year ended
  30 June 2024 is preserved as historical. No future allocation decision or
  proposed marginal destination is evidenced.
- SDC-0019 (Church of Jesus Christ of Latter-day Saints Australia):
  `insufficient_evidence`, mechanically invalid. The response distinguishes
  contingent-liability context from an allegation or finding and does not
  claim a correction/finding chain. Three requirements misuse `guarded`.
  Classification remains `CANDIDATE_SOURCE_GAP`; Source Universe v1 is not
  expanded.

Across v1.3 to v1.4, raw outcomes did not change (11 insufficient, 1
supported); mechanical validity stayed 6/12 but six rows flipped. Three former
mechanical failures now validate (Cancer Council, UWA, Plan); three former
valid outputs now fail typed `guarded` validation (Amnesty, Caritas, SDC-0019).
The other v1.4 invalid patterns are two strong proposition assertions with
unresolved scope/time (Good Friday, AWC). These distinctions are retained for
independent Sol review; no Gate-3 closure recommendation is made.
