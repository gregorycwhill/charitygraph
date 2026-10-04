# F2F currentness policy

**Status:** Working implementation policy.  It is a Builder-only governed-decision input, not a public claim schema.

Face-to-face (F2F) is represented as a scoped, evidence-bound fundraising-practice observation. It is never a timeless `uses_face_to_face` flag and does not allocate income, expenditure, ROI, or causal effectiveness.

| Source role | May establish deterministically | Cannot establish without its own explicit evidence |
| --- | --- | --- |
| PFRA membership | Membership status in the PFRA universe | Charity F2F use, its currentness, setting, agency, regular-giving arrangement, or organisation-wide coverage |
| Agency-client evidence | Source-stated F2F practice and source-stated scope/time | Unstated setting, agency role, regular giving, geography, or continuous use |
| First-party F2F page | Source-stated F2F practice and source-stated scope/time | Details not stated by the page |
| Annual report | Practice for the report’s stated period | Current practice after that period |
| Historical story | Historical practice in its stated period | Current practice |
| Explicit cessation | Discontinued practice from the stated cessation | Any later restart or organisation-wide absence |
| Scoped source inventory | `not_found_in_scoped_source`, with the precise coverage universe | Absence outside that source universe |

`current`, `recent`, `historical`, `discontinued`, `unknown`, and `not_found_in_scoped_source` are distinct values. The policy contains no universal age threshold: `recent` is retained only when source semantics/adjudication expressly supplies it. A missing, ambiguous, or unresolved subject binding produces `unknown` before any practice claim can be promoted.

A declared `valid_to` is a hard temporal boundary: a source-adapter assertion cannot be labelled `current` beyond it. Likewise, `discontinued` requires an explicit cessation boundary; an undated assertion does not manufacture one. `not_found_in_scoped_source` records only the declared search universe and is never rendered or stored as practice absence.

Every input retains source wording, evidence id, observation date, optional valid interval, source role, binding status, and scope. Source adapters/semantic adjudication determine source-native meaning; `decide_f2f_currentness` is only the deterministic governance step.
