# Review burden

Current governance would require individual human promotion for each semantic candidate group. Spike 6 bounded **16 groups across 5 charities**: World Vision 9, Red Cross 7, the other three 0. This is an intentionally narrow report-rich cohort, not a rate estimate for the sector.

Assumption: a reviewer spends **30–90 seconds per candidate** to read the locator, check extraction/section fit, and accept/reject/escalate; midpoint 60 seconds. This excludes acquisition, OCR, policy escalation, disagreement resolution, and QA sampling.

|Scope / scenario|Candidates|30 sec|60 sec midpoint|90 sec|
|---|---:|---:|---:|---:|
|Observed five-subject sample|16|8 min|16 min|24 min|
|8 charities, sparse-cohort rate (3.2/charity)|~26|13 min|26 min|39 min|
|100 charities, same mix|~320|2.7 h|5.3 h|8 h|
|10,000 charities, same mix|~32,000|267 h|533 h|800 h|
|100 charities, report-rich rate (8/charity)|~800|6.7 h|13.3 h|20 h|
|10,000 charities, report-rich rate|~80,000|667 h|1,333 h|2,000 h|

The sparse-rate extrapolation is mechanically derived from this sample; it should not be used for staffing. Report availability, proposition density, high-risk routing, and repeat-document deduplication dominate the real distribution. At 10,000, promotion-everything becomes a material operating model, not a UI detail. P1 can defer low-risk review while preserving a queue, but must not make hard-gated claim types cheaper by relabelling them.
